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
    "Признаки для поиска",
    "Операция разрешения атрибута",
    "Матрица решений",
    "Как оценивать результат операции",
    "Пакет передачи человеку",
    "Пороги внутри профиля",
    "function formatList",
]:
    assert expected in admin_js, expected
for expected in [
    "resolution_state",
    "Операция разрешения",
    "Пакет передачи",
    "resolutionProgressText",
]:
    assert expected in operator_js, expected
print("assets resolver-профиля проверены")

profiles_active = request("/admin/config/active/attribute_resolution_profiles")
payload = profiles_active["payload"]
login_profile = next(profile for profile in payload["profiles"] if profile["profile_id"] == "profile.password_reset.login_from_ad")
assert login_profile["candidate_source"]["source_type"] == "react_call", login_profile
assert login_profile["candidate_source"]["operation_id"] == "search_ad_users", login_profile
assert login_profile["result_policy"]["result_type"] == "list", login_profile
assert login_profile["result_policy"]["list_path"] == "users", login_profile
assert login_profile["result_policy"]["output_mapping"]["user_id"] == "user_id", login_profile
assert login_profile["decision_policy"]["multiple_results"] == "ask_disambiguation", login_profile
assert "department" in login_profile["clarification_policy"]["ask_for_attributes"], login_profile
assert login_profile["confidence_thresholds"]["auto_fill"] >= login_profile["confidence_thresholds"]["clarification"], login_profile
print("default resolver-профиль проверен")

simulation = request(
    "/admin/scenarios/password_reset/simulate",
    {
        "operator_id": "admin-stage12_7",
        "text": "Иванов Иван не может войти в доменную учетную запись",
    },
)
state = simulation["resolution_state"]["user_login"]
assert state["status"] == "question_required", simulation
assert state["attempt"] == 1 and state["max_attempts"] == 2, simulation
assert state["effective_confidence_thresholds"]["auto_accept_confidence"] >= state["effective_confidence_thresholds"]["clarification_confidence"], simulation
assert "должность" in state["pending_question"].lower(), simulation
assert state["decision"] == "ask_clarification", simulation
assert state["candidate_source"]["tool_name"] == "search_ad_users", simulation
print("dry-run состояния resolver-профиля проверен")


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


bad_mapping = copy.deepcopy(payload)
bad_mapping["profiles"][0]["candidate_source"]["parameter_mapping"]["login"] = "attribute:missing_identity_marker"
validated = validate_payload(bad_mapping, "bad-mapping")
assert validated["validation"]["status"] == "invalid", validated
assert any("missing_identity_marker" in error for error in validated["validation"]["errors"]), validated

bad_output = copy.deepcopy(payload)
bad_output["profiles"][0]["result_policy"]["output_mapping"]["undeclared_identity_marker"] = "login"
validated = validate_payload(bad_output, "bad-output")
assert validated["validation"]["status"] == "invalid", validated
assert any("undeclared_identity_marker" in error for error in validated["validation"]["errors"]), validated
print("валидация resolver-профиля проверена")

print("Smoke-проверка этапа 12.7 завершена.")
PY
