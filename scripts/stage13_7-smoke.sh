#!/usr/bin/env bash
set -euo pipefail

if [ -x ".venv/bin/python" ]; then
  PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

HOST="${ORCHESTRATOR_HOST:-127.0.0.1}"
PORT="${ORCHESTRATOR_PORT:-18115}"
BASE_URL="http://${HOST}:${PORT}"
LOG_FILE="${STAGE13_7_LOG_FILE:-/tmp/servicedesk-stage13-7-orchestrator.log}"
STATE_DB="${STAGE13_7_STATE_DB:-/tmp/servicedesk-stage13-7-orchestrator-${PORT}-$$.sqlite}"
INDEX_PATH="${STAGE13_7_INDEX_PATH:-/tmp/servicedesk-stage13-7-knowledge-${PORT}-$$.json}"

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
admin_headers = {"X-ServiceDesk-Actor": "admin-1", "X-ServiceDesk-Session": "stage13_7:admin"}


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
assert "Профили действий канала" in admin_js, admin_js[:500]
assert "Профили канала" not in admin_js, admin_js[:500]
assert "profile_major_incident" not in admin_js, admin_js[:500]
assert "channel_profile_mapping" not in admin_js, admin_js[:500]
assert "Оповещать дежурных" not in admin_js, admin_js[:500]
print("UI блока 5 не содержит mapping профилей")

escalations_active = request("/admin/config/active/escalation_policies")
for policy in escalations_active["payload"]["policies"]:
    assert "channel_profile_mapping" not in policy, policy
    assert "notify_on_call" not in policy["major_incident"], policy

channels_active = request("/admin/config/active/interaction_channels")
debug = next(channel for channel in channels_active["payload"]["channels"] if channel["channel_id"] == "debug")
event_types = [profile["event_type"] for profile in debug["action_profiles"]]
for event_type in ["standard_handoff", "no_answer", "major_incident", "policy_blocked"]:
    assert event_types.count(event_type) == 1, debug

simulation = request(
    "/admin/scenarios/network_issue/simulate",
    {
        "operator_id": "admin-stage13_7",
        "text": "VPN недоступен, больше 20 пользователей",
    },
)
profiles = simulation["channel_action_profiles"]
assert set(["standard_handoff", "no_answer", "major_incident", "policy_blocked"]) <= set(profiles), simulation
assert profiles["major_incident"]["action"]["action_type"] == "debug_stop", simulation
print("dry-run вычисляет профили по event_type канала")

bad_channels = copy.deepcopy(channels_active["payload"])
bad_debug = next(channel for channel in bad_channels["channels"] if channel["channel_id"] == "debug")
duplicate = copy.deepcopy(next(profile for profile in bad_debug["action_profiles"] if profile["event_type"] == "major_incident"))
duplicate["profile_id"] = "major_incident_duplicate"
bad_debug["action_profiles"].append(duplicate)
draft = request(
    "/admin/config/drafts",
    {
        "domain": "interaction_channels",
        "payload": bad_channels,
        "operator_id": "admin-stage13_7-duplicate",
        "base_version_id": channels_active["active_version_id"],
    },
)
validated = request(f"/admin/config/drafts/{draft['draft_id']}/validate", {"operator_id": "admin-stage13_7-duplicate"})
assert validated["validation"]["status"] == "invalid", validated
assert any("несколько action profile" in error and "major_incident" in error for error in validated["validation"]["errors"]), validated

print("Smoke-проверка этапа 13.7 завершена.")
PY
