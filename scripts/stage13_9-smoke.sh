#!/usr/bin/env bash
set -euo pipefail

if [ -x ".venv/bin/python" ]; then
  PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

HOST="${ORCHESTRATOR_HOST:-127.0.0.1}"
PORT="${ORCHESTRATOR_PORT:-18117}"
BASE_URL="http://${HOST}:${PORT}"
LOG_FILE="${STAGE13_9_LOG_FILE:-/tmp/servicedesk-stage13-9-orchestrator.log}"
STATE_DB="${STAGE13_9_STATE_DB:-/tmp/servicedesk-stage13-9-orchestrator-${PORT}-$$.sqlite}"
INDEX_PATH="${STAGE13_9_INDEX_PATH:-/tmp/servicedesk-stage13-9-knowledge-${PORT}-$$.json}"

ORCHESTRATOR_STATE_DB="${STATE_DB}" \
KNOWLEDGE_INDEX_PATH="${INDEX_PATH}" \
SECURITY_AUTH_MODE="${SECURITY_AUTH_MODE:-dev_header}" \
SECURITY_DEV_ACTOR="${SECURITY_DEV_ACTOR:-admin-1}" \
SECURITY_RATE_LIMIT_PER_MINUTE="${SECURITY_RATE_LIMIT_PER_MINUTE:-600}" \
INTEGRATION_CALLBACK_TOKEN="${INTEGRATION_CALLBACK_TOKEN:-dev-callback-token}" \
  "${PYTHON_BIN}" -m uvicorn apps.orchestrator.app.main:app --host "${HOST}" --port "${PORT}" >"${LOG_FILE}" 2>&1 &
SERVER_PID="$!"

cleanup() {
  kill "${SERVER_PID}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

BASE_URL="${BASE_URL}" "${PYTHON_BIN}" - <<'PY'
import copy
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

base_url = os.environ["BASE_URL"]
admin_headers = {"X-ServiceDesk-Actor": "admin-1", "X-ServiceDesk-Session": "stage13_9:admin"}


def request(path, payload=None, expected_status=200, parse_json=True):
    data = None
    method = "GET"
    headers = dict(admin_headers)
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        method = "POST"
        headers["Content-Type"] = "application/json"
    req = Request(f"{base_url}{path}", data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=5) as response:
            status = response.status
            body = response.read().decode("utf-8")
    except HTTPError as error:
        status = error.code
        body = error.read().decode("utf-8")

    if status != expected_status:
        raise SystemExit(f"{path}: expected HTTP {expected_status}, got {status}: {body}")
    if not parse_json:
        return body
    return json.loads(body) if body else {}


last_error = None
for _ in range(60):
    try:
        if request("/healthz") == {"status": "ok"}:
            break
    except (HTTPError, URLError, TimeoutError) as error:
        last_error = error
        time.sleep(0.5)
else:
    raise SystemExit(f"healthz did not become ready: {last_error}")

admin_js = request("/admin/static/app.js", parse_json=False)
for expected in [
    "Разрешенные группы действий ReAct",
    "Чтение и диагностика",
    "Стоп-условия",
    "allowed_react_action_groups",
    "all_required_slots_filled",
]:
    assert expected in admin_js, expected
for removed in [
    "allowed_tool_classes",
    "Классы инструментов",
]:
    assert removed not in admin_js, removed
print("UI чекбоксов ReAct-планирования проверен")

active = request("/admin/config/active/orchestrator_policy")
payload = active["payload"]
for policy in payload["policies"]:
    assert "allowed_react_action_groups" in policy, policy
    assert "allowed_tool_classes" not in policy, policy
    assert policy["allowed_react_action_groups"], policy
    assert policy["stop_conditions"], policy
    assert "all_required_slots_filled" in policy["stop_conditions"], policy
    assert "consecutive_tool_errors" in policy["stop_conditions"], policy
print("active ReAct policies используют новую модель")

bad_empty_groups = copy.deepcopy(payload)
bad_empty_groups["policies"][0]["allowed_react_action_groups"] = []
draft = request(
    "/admin/config/drafts",
    {
        "domain": "orchestrator_policy",
        "payload": bad_empty_groups,
        "operator_id": "admin-stage13_9-empty-groups",
        "base_version_id": active["active_version_id"],
    },
)
validated = request(f"/admin/config/drafts/{draft['draft_id']}/validate", {"operator_id": "admin-stage13_9-empty-groups"})
assert validated["validation"]["status"] == "invalid", validated
assert any("allowed_react_action_groups" in error for error in validated["validation"]["errors"]), validated
print("валидация непустых групп ReAct проверена")

bad_error_limit = copy.deepcopy(payload)
bad_error_limit["policies"][0]["max_iterations"] = 2
bad_error_limit["policies"][0]["consecutive_tool_errors_to_escalate"] = 3
draft = request(
    "/admin/config/drafts",
    {
        "domain": "orchestrator_policy",
        "payload": bad_error_limit,
        "operator_id": "admin-stage13_9-bad-limit",
        "base_version_id": active["active_version_id"],
    },
)
validated = request(f"/admin/config/drafts/{draft['draft_id']}/validate", {"operator_id": "admin-stage13_9-bad-limit"})
assert validated["validation"]["status"] == "invalid", validated
assert any("max_iterations" in error for error in validated["validation"]["errors"]), validated
print("валидация лимита ошибок проверена")

legacy_payload = copy.deepcopy(payload)
legacy_policy = legacy_payload["policies"][0]
legacy_policy["allowed_tool_classes"] = ["read_only", "action"]
legacy_policy.pop("allowed_react_action_groups")
legacy_draft = request(
    "/admin/config/drafts",
    {
        "domain": "orchestrator_policy",
        "payload": legacy_payload,
        "operator_id": "admin-stage13_9-legacy",
        "base_version_id": active["active_version_id"],
    },
)
legacy_validated = request(f"/admin/config/drafts/{legacy_draft['draft_id']}/validate", {"operator_id": "admin-stage13_9-legacy"})
assert legacy_validated["validation"]["status"] == "invalid", legacy_validated
assert any("allowed_tool_classes" in error or "allowed_react_action_groups" in error for error in legacy_validated["validation"]["errors"]), legacy_validated
print("старое поле allowed_tool_classes отклоняется")

detail = request("/operator/scenarios/network_issue")
policy = detail["orchestrator_policy"]
assert "allowed_react_action_groups" in policy, policy
assert "allowed_tool_classes" not in policy, policy
print("Operator API возвращает новую модель ReAct-планирования")

print("Smoke-проверка этапа 13.9 завершена.")
PY
