#!/usr/bin/env bash
set -euo pipefail

if [ -x ".venv/bin/python" ]; then
  PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

HOST="${ORCHESTRATOR_HOST:-127.0.0.1}"
PORT="${ORCHESTRATOR_PORT:-18116}"
BASE_URL="http://${HOST}:${PORT}"
LOG_FILE="${STAGE13_8_LOG_FILE:-/tmp/servicedesk-stage13-8-orchestrator.log}"
STATE_DB="${STAGE13_8_STATE_DB:-/tmp/servicedesk-stage13-8-orchestrator-${PORT}-$$.sqlite}"
INDEX_PATH="${STAGE13_8_INDEX_PATH:-/tmp/servicedesk-stage13-8-knowledge-${PORT}-$$.json}"

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
admin_headers = {"X-ServiceDesk-Actor": "admin-1", "X-ServiceDesk-Session": "stage13_8:admin"}


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
    "Условия передачи",
    "2 ошибки инструментов подряд",
    "Пакет передачи",
    "Собранные слоты",
    "handoff_conditions",
    "handoff_package",
]:
    assert expected in admin_js, expected
for removed in [
    "l2_conditions",
    "escalation_package",
]:
    assert removed not in admin_js, removed
print("UI чекбоксов блока 5 проверен")

escalations_active = request("/admin/config/active/escalation_policies")
payload = escalations_active["payload"]
for policy in payload["policies"]:
    assert "handoff_conditions" in policy, policy
    assert "handoff_package" in policy, policy
    assert "l2_conditions" not in policy, policy
    assert "escalation_package" not in policy, policy
    assert {"slots", "user_notification"} <= set(policy["handoff_package"]), policy
print("active escalation policies используют новую модель")

bad_required = copy.deepcopy(payload)
bad_required["policies"][0]["handoff_package"] = [
    item
    for item in bad_required["policies"][0]["handoff_package"]
    if item != "user_notification"
]
draft = request(
    "/admin/config/drafts",
    {
        "domain": "escalation_policies",
        "payload": bad_required,
        "operator_id": "admin-stage13_8-missing-package",
        "base_version_id": escalations_active["active_version_id"],
    },
)
validated = request(f"/admin/config/drafts/{draft['draft_id']}/validate", {"operator_id": "admin-stage13_8-missing-package"})
assert validated["validation"]["status"] == "invalid", validated
assert any("handoff package" in error and "user_notification" in error for error in validated["validation"]["errors"]), validated
print("валидация обязательного пакета передачи проверена")

legacy_payload = copy.deepcopy(payload)
legacy_policy = legacy_payload["policies"][0]
legacy_policy["l2_conditions"] = legacy_policy.pop("handoff_conditions")
legacy_policy["escalation_package"] = legacy_policy.pop("handoff_package")
legacy_draft = request(
    "/admin/config/drafts",
    {
        "domain": "escalation_policies",
        "payload": legacy_payload,
        "operator_id": "admin-stage13_8-legacy",
        "base_version_id": escalations_active["active_version_id"],
    },
)
legacy_validated = request(f"/admin/config/drafts/{legacy_draft['draft_id']}/validate", {"operator_id": "admin-stage13_8-legacy"})
assert legacy_validated["validation"]["status"] == "invalid", legacy_validated
assert any("l2_conditions" in error or "handoff_conditions" in error for error in legacy_validated["validation"]["errors"]), legacy_validated
print("старые поля l2_conditions/escalation_package отклоняются")

detail = request("/operator/scenarios/network_issue")
policy = detail["escalation_policy"]
assert "handoff_conditions" in policy and "handoff_package" in policy, policy
assert "escalation_package" not in policy, policy
print("Operator API возвращает новую модель блока 5")

print("Smoke-проверка этапа 13.8 завершена.")
PY
