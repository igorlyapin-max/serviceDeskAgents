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
import copy
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
for expected in [
    "Профили действий канала",
    "notify_on_call",
]:
    assert expected in admin_js, expected
assert "Оповещать дежурных" not in admin_js, admin_js[:500]
assert "channel_profile_mapping" not in admin_js, admin_js[:500]
for expected in [
    "Профиль канала",
    "channel_action_profiles",
    "notify_on_call",
]:
    assert expected in operator_js, expected
print("assets профилей канала проверены")

channels_active = request("/admin/config/active/interaction_channels")
channel_by_id = {channel["channel_id"]: channel for channel in channels_active["payload"]["channels"]}
messenger_profiles = {profile["profile_id"]: profile for profile in channel_by_id["messenger_bot"]["action_profiles"]}
debug_profiles = {profile["profile_id"]: profile for profile in channel_by_id["debug"]["action_profiles"]}
assert messenger_profiles["major_incident"]["action"]["action_type"] == "notify_on_call", messenger_profiles["major_incident"]
assert debug_profiles["major_incident"]["action"]["action_type"] == "debug_stop", debug_profiles["major_incident"]
print("default action profiles проверены")

escalations_active = request("/admin/config/active/escalation_policies")
policy = next(item for item in escalations_active["payload"]["policies"] if item["policy_id"] == "escalation.network_issue")
assert "channel_profile_mapping" not in policy, policy
assert "notify_on_call" not in policy["major_incident"], policy

simulation = request(
    "/admin/scenarios/network_issue/simulate",
    {
        "operator_id": "admin-stage13_6",
        "text": "VPN недоступен для отдела, больше 20 пользователей",
    },
)
profiles = simulation["channel_action_profiles"]
assert profiles["major_incident"]["event_type"] == "major_incident", simulation
assert profiles["major_incident"]["action"]["action_type"] == "debug_stop", simulation
print("dry-run профилей канала проверен")

bad_channels = copy.deepcopy(channels_active["payload"])
debug = next(channel for channel in bad_channels["channels"] if channel["channel_id"] == "debug")
debug["action_profiles"] = [profile for profile in debug["action_profiles"] if profile["profile_id"] != "major_incident"]
draft = request(
    "/admin/config/drafts",
    {
        "domain": "interaction_channels",
        "payload": bad_channels,
        "operator_id": "admin-stage13_6-bad-channel",
        "base_version_id": channels_active["active_version_id"],
    },
)
validated = request(f"/admin/config/drafts/{draft['draft_id']}/validate", {"operator_id": "admin-stage13_6-bad-channel"})
assert validated["validation"]["status"] == "invalid", validated
assert any("major_incident" in error for error in validated["validation"]["errors"]), validated
print("валидация профилей канала проверена")

print("Smoke-проверка этапа 13.6 завершена.")
PY
