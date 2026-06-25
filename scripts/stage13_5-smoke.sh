#!/usr/bin/env bash
set -euo pipefail

if [ -x ".venv/bin/python" ]; then
  PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

HOST="${ORCHESTRATOR_HOST:-127.0.0.1}"
PORT="${ORCHESTRATOR_PORT:-18113}"
BASE_URL="http://${HOST}:${PORT}"
LOG_FILE="${STAGE13_5_LOG_FILE:-/tmp/servicedesk-stage13-5-orchestrator.log}"
STATE_DB="${STAGE13_5_STATE_DB:-/tmp/servicedesk-stage13-5-orchestrator-${PORT}-$$.sqlite}"
INDEX_PATH="${STAGE13_5_INDEX_PATH:-/tmp/servicedesk-stage13-5-knowledge-${PORT}-$$.json}"

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
admin_headers = {"X-ServiceDesk-Actor": "admin-1", "X-ServiceDesk-Session": "stage13_5:admin"}


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

html = request("/admin", parse_json=False)
assert 'data-view="interactionChannels"' in html, html[:500]
assert "Каналы взаимодействия" in html, html[:500]

admin_js = request("/admin/static/app.js", parse_json=False)
operator_js = request("/operator/static/app.js", parse_json=False)
for expected in [
    "renderInteractionChannels",
    "interaction-channel-editor",
    "data-debug-channel-readonly",
    "Системный канал",
    "Канал по умолчанию",
    "Разрешенные каналы",
    "Уточнения у клиента",
    "Действие по умолчанию при эскалации",
]:
    assert expected in admin_js, expected
assert "Что делать с незавершенным уточнением" not in admin_js, admin_js[:500]
for removed in ["агент + Л1", "Л1 + подсказка", "Major Incident", "major_incident", "Пакет Л2", "Пакет Л1"]:
    assert removed not in admin_js, removed
    assert removed not in operator_js, removed
assert "Канал:" in operator_js, operator_js[:500]
assert "Эскалация оператору" in operator_js, operator_js[:500]
assert "debugChannelSelect" in operator_js, operator_js[:500]
assert "debugFlowChannel" in operator_js, operator_js[:500]
assert "channel_parameter_state" in operator_js, operator_js[:500]
print("assets каналов взаимодействия проверены")

domains = request("/admin/config/domains")
domain_ids = {item["domain"] for item in domains["domains"]}
assert "interaction_channels" in domain_ids, domains

channels_active = request("/admin/config/active/interaction_channels")
channels = channels_active["payload"]["channels"]
channel_by_id = {channel["channel_id"]: channel for channel in channels}
assert {"messenger_bot", "service_desk", "debug"} <= set(channel_by_id), channel_by_id
assert channel_by_id["messenger_bot"]["mode"] == "online_interactive", channel_by_id["messenger_bot"]
assert channel_by_id["service_desk"]["waiting_policy"]["sla_elapsed_percent_threshold"] == 30, channel_by_id["service_desk"]
for channel in channels:
    assert "question_delivery" not in channel, channel
    assert "incomplete_discussion_action" not in channel, channel
    assert "escalation_action" not in channel, channel
    assert "action_profiles" not in channel, channel
print("default каналы проверены")

scenario_detail = request("/admin/scenarios/password_reset")
assert scenario_detail["scenario"]["default_channel_id"] == "debug", scenario_detail["scenario"]
assert scenario_detail["interaction_channel"]["channel_id"] == "debug", scenario_detail

simulation = request(
    "/admin/scenarios/password_reset/simulate",
    {
        "operator_id": "admin-stage13_5",
        "text": "Иванов Иван не может войти в доменную учетную запись",
    },
)
assert simulation["interaction_channel"]["channel_id"] == "debug", simulation
assert simulation["client_question"]["delivery"]["mode"] == "debug", simulation
assert simulation["escalation_action"]["action_type"] == "debug_stop", simulation
print("dry-run канала проверен")

service_desk_simulation = request(
    "/admin/scenarios/password_reset/simulate",
    {
        "operator_id": "admin-stage13_5",
        "text": "Иванов Иван не может войти в доменную учетную запись",
        "channel_id": "service_desk",
    },
)
assert service_desk_simulation["interaction_channel"]["channel_id"] == "service_desk", service_desk_simulation
assert service_desk_simulation["escalation_action"]["action_type"] == "create_work_order", service_desk_simulation
assert (
    service_desk_simulation["channel_variables"]["service_desk"]["task_topic"]
    == "public.ittask.serviceDeskDefault.task"
), service_desk_simulation
assert (
    service_desk_simulation["channel_variables"]["service_desk"]["result_topic"]
    == "public.ittask.result"
), service_desk_simulation
parameter_state = {
    parameter["parameter_id"]: parameter["status"]
    for parameter in service_desk_simulation["channel_parameter_state"]
}
assert parameter_state["task_topic"] == "resolved", parameter_state
assert parameter_state["task_key"] == "missing", parameter_state
print("dry-run реального канала ServiceDesk проверен")

scenarios_active = request("/admin/config/active/service_scenarios")
bad_scenarios = copy.deepcopy(scenarios_active["payload"])
bad_scenarios["scenarios"][0]["default_channel_id"] = "missing_channel"
draft = request(
    "/admin/config/drafts",
    {
        "domain": "service_scenarios",
        "payload": bad_scenarios,
        "operator_id": "admin-stage13_5-bad-scenario",
        "base_version_id": scenarios_active["active_version_id"],
    },
)
validated = request(f"/admin/config/drafts/{draft['draft_id']}/validate", {"operator_id": "admin-stage13_5-bad-scenario"})
assert validated["validation"]["status"] == "invalid", validated
assert any("default_channel_id" in error for error in validated["validation"]["errors"]), validated

bad_channels = copy.deepcopy(channels_active["payload"])
bad_channels["channels"] = [channel for channel in bad_channels["channels"] if channel["channel_id"] != "debug"]
draft = request(
    "/admin/config/drafts",
    {
        "domain": "interaction_channels",
        "payload": bad_channels,
        "operator_id": "admin-stage13_5-bad-channel",
        "base_version_id": channels_active["active_version_id"],
    },
)
validated = request(f"/admin/config/drafts/{draft['draft_id']}/validate", {"operator_id": "admin-stage13_5-bad-channel"})
assert validated["validation"]["status"] == "invalid", validated
assert any("debug" in error for error in validated["validation"]["errors"]), validated

bad_channels = copy.deepcopy(channels_active["payload"])
debug = next(channel for channel in bad_channels["channels"] if channel["channel_id"] == "debug")
debug["capabilities"]["supports_async_result"] = True
draft = request(
    "/admin/config/drafts",
    {
        "domain": "interaction_channels",
        "payload": bad_channels,
        "operator_id": "admin-stage13_5-bad-debug-edit",
        "base_version_id": channels_active["active_version_id"],
    },
)
validated = request(f"/admin/config/drafts/{draft['draft_id']}/validate", {"operator_id": "admin-stage13_5-bad-debug-edit"})
assert validated["validation"]["status"] == "invalid", validated
assert any("debug.capabilities" in error for error in validated["validation"]["errors"]), validated
print("валидация связей каналов проверена")

print("Smoke-проверка этапа 13.5 завершена.")
PY
