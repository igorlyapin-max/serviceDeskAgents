#!/usr/bin/env bash
set -euo pipefail

if [ -x ".venv/bin/python" ]; then
  PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

HOST="${ORCHESTRATOR_HOST:-127.0.0.1}"
PORT="${ORCHESTRATOR_PORT:-18114}"
BASE_URL="http://${HOST}:${PORT}"
LOG_FILE="${STAGE13_6_LOG_FILE:-/tmp/servicedesk-stage13-6-orchestrator.log}"
STATE_DB="${STAGE13_6_STATE_DB:-/tmp/servicedesk-stage13-6-orchestrator-${PORT}-$$.sqlite}"
INDEX_PATH="${STAGE13_6_INDEX_PATH:-/tmp/servicedesk-stage13-6-knowledge-${PORT}-$$.json}"

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
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

base_url = os.environ["BASE_URL"]
admin_headers = {"X-ServiceDesk-Actor": "admin-1", "X-ServiceDesk-Session": "stage13_6:admin"}


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
assert "Профили действий канала" not in admin_js, admin_js[:500]
assert "channel-profile-add" not in admin_js, admin_js[:500]
assert "Оповещать дежурных" not in admin_js, admin_js[:500]
assert "Major Incident" not in admin_js, admin_js[:500]
assert "major_incident" not in admin_js, admin_js[:500]
assert "notify_on_call" not in admin_js, admin_js[:500]
assert "channel_profile_mapping" not in admin_js, admin_js[:500]
assert "Профиль канала" not in operator_js, operator_js[:500]
assert "channel_action_profiles" not in operator_js, operator_js[:500]
assert "Major Incident" not in operator_js, operator_js[:500]
assert "major_incident" not in operator_js, operator_js[:500]
assert "notify_on_call" not in operator_js, operator_js[:500]
print("assets каналов без action-профилей проверены")

channels_active = request("/admin/config/active/interaction_channels")
channel_by_id = {channel["channel_id"]: channel for channel in channels_active["payload"]["channels"]}
for channel in channel_by_id.values():
    assert "action_profiles" not in channel, channel
    assert "question_delivery" not in channel, channel
    assert "incomplete_discussion_action" not in channel, channel
    assert "escalation_action" not in channel, channel
print("default каналы без action-профилей проверены")

escalations_active = request("/admin/config/active/escalation_policies")
policy = next(item for item in escalations_active["payload"]["policies"] if item["policy_id"] == "escalation.network_issue")
assert "channel_profile_mapping" not in policy, policy
assert "major_incident" not in policy, policy
assert "affected_users_threshold" not in policy.get("handoff_conditions", []), policy

simulation = request(
    "/admin/scenarios/network_issue/simulate",
    {
        "operator_id": "admin-stage13_6",
        "text": "VPN недоступен для отдела, больше 20 пользователей",
    },
)
assert "channel_action_profiles" not in simulation, simulation
assert simulation["escalation_action"]["action_type"] == "debug_stop", simulation
print("dry-run fallback канала debug проверен")

messenger_simulation = request(
    "/admin/scenarios/network_issue/simulate",
    {
        "operator_id": "admin-stage13_6",
        "text": "VPN недоступен для отдела, больше 20 пользователей",
        "channel_id": "messenger_bot",
    },
)
assert messenger_simulation["interaction_channel"]["channel_id"] == "messenger_bot", messenger_simulation
assert "channel_action_profiles" not in messenger_simulation, messenger_simulation
assert messenger_simulation["escalation_action"]["action_type"] == "call_specialist", messenger_simulation
print("dry-run fallback реального канала проверен")

print("Smoke-проверка этапа 13.6 завершена.")
PY
