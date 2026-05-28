#!/usr/bin/env bash
set -euo pipefail

if [ -x ".venv/bin/python" ]; then
  PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

HOST="${ORCHESTRATOR_HOST:-127.0.0.1}"
PORT="${ORCHESTRATOR_PORT:-18108}"
BASE_URL="http://${HOST}:${PORT}"
LOG_FILE="${STAGE12_7_LOG_FILE:-/tmp/servicedesk-stage12-7-orchestrator.log}"
STATE_DB="${STAGE12_7_STATE_DB:-/tmp/servicedesk-stage12-7-orchestrator-${PORT}-$$.sqlite}"
INDEX_PATH="${STAGE12_7_INDEX_PATH:-/tmp/servicedesk-stage12-7-knowledge-${PORT}-$$.json}"

ORCHESTRATOR_STATE_DB="${STATE_DB}" \
KNOWLEDGE_INDEX_PATH="${INDEX_PATH}" \
INTEGRATION_ENDPOINT_PROFILE="${INTEGRATION_ENDPOINT_PROFILE:-mock}" \
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
admin_headers = {"X-ServiceDesk-Actor": "admin-1", "X-ServiceDesk-Session": "stage12_7:admin"}


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
operator_js = request("/operator/static/app.js", parse_json=False)
for expected in [
    "Политика неоднозначности",
    "Промежуточные атрибуты",
    "Следующий шаг при неоднозначности",
    "Пакет передачи Л1",
    "mini-workflow",
    "function formatList",
]:
    assert expected in admin_js, expected
for expected in [
    "resolution_state",
    "Текущий шаг",
    "Пакет Л1",
    "resolutionProgressText",
]:
    assert expected in operator_js, expected
print("assets mini-workflow проверены")

profiles_active = request("/admin/config/active/attribute_resolution_profiles")
payload = profiles_active["payload"]
login_profile = next(profile for profile in payload["profiles"] if profile["profile_id"] == "profile.password_reset.login_from_ad")
assert login_profile["resolution_mode"] == "branching", login_profile
assert login_profile["attempt_scope"] == "profile", login_profile
assert "ad_candidates" in login_profile["intermediate_attributes"], login_profile
assert login_profile["ambiguity_policy"]["action"] == "clarification", login_profile
assert login_profile["ambiguity_policy"]["candidate_count_attribute"] == "ad_candidates", login_profile
assert login_profile["confidence_thresholds"]["auto_fill"] >= login_profile["confidence_thresholds"]["clarification"], login_profile
assert any(step["type"] == "rag_search" for step in login_profile["steps"]), login_profile
assert any(step.get("on_ambiguous_step") == "ask_identity_hint" for step in login_profile["steps"]), login_profile
assert any(step["type"] == "operator_handoff" for step in login_profile["steps"]), login_profile
print("default mini-workflow проверен")

simulation = request(
    "/admin/scenarios/password_reset/simulate",
    {
        "operator_id": "admin-stage12_7",
        "text": "Иванов Иван не может войти в доменную учетную запись",
    },
)
state = simulation["resolution_state"]["user_login"]
assert state["status"] == "question_required", simulation
assert state["current_step_id"] == "ask_identity_hint", simulation
assert state["attempt"] == 1 and state["max_attempts"] == 2, simulation
assert "ad_candidates" in state["intermediate_attributes"], simulation
assert state["candidate_summary"]["source_attribute"] == "ad_candidates", simulation
assert "должность" in state["pending_question"].lower(), simulation
assert any(step["step_id"] == "search_history_hint" for step in state["completed_steps"]), simulation
print("dry-run состояния разрешения слота проверен")


def validate_payload(candidate, label):
    draft = request(
        "/admin/config/drafts",
        {
            "domain": "attribute_resolution_profiles",
            "payload": candidate,
            "operator_id": f"admin-stage12_7-{label}",
            "base_version_id": profiles_active["active_version_id"],
        },
    )
    return request(
        f"/admin/config/drafts/{draft['draft_id']}/validate",
        {"operator_id": f"admin-stage12_7-{label}"},
    )


bad_transition = copy.deepcopy(payload)
bad_transition["profiles"][0]["steps"][0]["on_ambiguous_step"] = "missing_step"
validated = validate_payload(bad_transition, "bad-transition")
assert validated["validation"]["status"] == "invalid", validated
assert any("on_ambiguous_step" in error for error in validated["validation"]["errors"]), validated

bad_attribute = copy.deepcopy(payload)
bad_attribute["profiles"][0]["steps"][0]["outputs"].append("undeclared_identity_marker")
validated = validate_payload(bad_attribute, "bad-attribute")
assert validated["validation"]["status"] == "invalid", validated
assert any("undeclared_identity_marker" in error for error in validated["validation"]["errors"]), validated
print("валидация mini-workflow проверена")

print("Smoke-проверка этапа 12.7 завершена.")
PY
