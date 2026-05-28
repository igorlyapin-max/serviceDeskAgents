#!/usr/bin/env bash
set -euo pipefail

if [ -x ".venv/bin/python" ]; then
  PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

HOST="${ORCHESTRATOR_HOST:-127.0.0.1}"
PORT="${ORCHESTRATOR_PORT:-18106}"
BASE_URL="http://${HOST}:${PORT}"
LOG_FILE="${STAGE13_LOG_FILE:-/tmp/servicedesk-stage13-orchestrator.log}"
STATE_DB="${STAGE13_STATE_DB:-/tmp/servicedesk-stage13-orchestrator-${PORT}-$$.sqlite}"
INDEX_PATH="${STAGE13_INDEX_PATH:-/tmp/servicedesk-stage13-knowledge-${PORT}-$$.json}"
ENV_PATH="${STAGE13_ENV_PATH:-/tmp/servicedesk-stage13-env-${PORT}-$$.env}"

ORCHESTRATOR_STATE_DB="${STATE_DB}" \
KNOWLEDGE_INDEX_PATH="${INDEX_PATH}" \
SERVICE_DESK_ENV_PATH="${ENV_PATH}" \
SECURITY_AUTH_MODE="${SECURITY_AUTH_MODE:-dev_header}" \
SECURITY_DEV_ACTOR="${SECURITY_DEV_ACTOR:-admin-1}" \
SECURITY_RATE_LIMIT_PER_MINUTE="${SECURITY_RATE_LIMIT_PER_MINUTE:-600}" \
INTEGRATION_CALLBACK_TOKEN="${INTEGRATION_CALLBACK_TOKEN:-dev-callback-token}" \
  "${PYTHON_BIN}" -m uvicorn apps.orchestrator.app.main:app --host "${HOST}" --port "${PORT}" >"${LOG_FILE}" 2>&1 &
SERVER_PID="$!"

cleanup() {
  kill "${SERVER_PID}" >/dev/null 2>&1 || true
  rm -f "${ENV_PATH}" >/dev/null 2>&1 || true
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
admin_headers = {"X-ServiceDesk-Actor": "admin-1", "X-ServiceDesk-Session": "stage13:admin"}


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
assert "Изменения конфигурации" not in html, html[:300]
assert 'data-view="config"' not in html, html[:300]
js = request("/admin/static/app.js", parse_json=False)
assert "renderConfig" not in js, js[:300]
print("ручной раздел конфигурации скрыт из UI")

domains = request("/admin/config/domains")
domain_ids = {item["domain"] for item in domains["domains"]}
for expected in {"tools", "integration_endpoints", "workflow_states", "workflow_transitions", "prompts", "model_routing", "n8n_workflows", "attribute_resolution_profiles"}:
    assert expected in domain_ids, domains
print("домены конфигурации проверены")

active = request("/admin/config/active/prompts")
assert active["source"] == "default", active
payload_v1 = copy.deepcopy(active["payload"])
payload_v1["prompts"][0]["description"] = "Stage 13 smoke prompt v1."
draft1 = request(
    "/admin/config/drafts",
    {
        "domain": "prompts",
        "payload": payload_v1,
        "operator_id": "admin-stage13",
    },
)
assert draft1["status"] == "draft", draft1
blocked_activation = request(
    f"/admin/config/drafts/{draft1['draft_id']}/activate",
    {"operator_id": "admin-stage13"},
    expected_status=400,
)
assert blocked_activation["detail"]["code"] == "config_registry_error", blocked_activation
validated1 = request(
    f"/admin/config/drafts/{draft1['draft_id']}/validate",
    {"operator_id": "admin-stage13"},
)
assert validated1["validation"]["status"] == "valid", validated1
regressed1 = request(
    f"/admin/config/drafts/{draft1['draft_id']}/regression",
    {"operator_id": "admin-stage13", "limit": 10},
)
assert regressed1["regression"]["status"] == "skipped", regressed1
version1 = request(
    f"/admin/config/drafts/{draft1['draft_id']}/activate",
    {"operator_id": "admin-stage13"},
)
assert version1["domain"] == "prompts", version1
active_v1 = request("/admin/config/active/prompts")
assert active_v1["active_version_id"] == version1["version_id"], active_v1
assert active_v1["payload"]["prompts"][0]["description"] == "Stage 13 smoke prompt v1.", active_v1
print("черновик, валидация, регрессия и активация проверены")

payload_v2 = copy.deepcopy(active_v1["payload"])
payload_v2["prompts"][0]["description"] = "Stage 13 smoke prompt v2."
draft2 = request(
    "/admin/config/drafts",
    {
        "domain": "prompts",
        "payload": payload_v2,
        "operator_id": "admin-stage13",
    },
)
request(f"/admin/config/drafts/{draft2['draft_id']}/validate", {"operator_id": "admin-stage13"})
request(f"/admin/config/drafts/{draft2['draft_id']}/regression", {"operator_id": "admin-stage13"})
version2 = request(f"/admin/config/drafts/{draft2['draft_id']}/activate", {"operator_id": "admin-stage13"})
assert version2["previous_version_id"] == version1["version_id"], version2
rollback = request(
    f"/admin/config/versions/{version1['version_id']}/rollback",
    {"operator_id": "admin-stage13"},
)
assert rollback["active_version_id"] == version1["version_id"], rollback
active_after_rollback = request("/admin/config/active/prompts")
assert active_after_rollback["payload"]["prompts"][0]["description"] == "Stage 13 smoke prompt v1.", active_after_rollback
versions = request("/admin/config/versions?domain=prompts")
assert versions["version_count"] >= 2, versions
print("откат конфигурации проверен")

model_active = request("/admin/config/active/model_routing")
assert model_active["payload"]["active_provider"] in {"vllm_cpu", "openai"}, model_active
assert "vllm_cpu" in model_active["payload"]["providers"], model_active
assert "openai" in model_active["payload"]["providers"], model_active
assert model_active["payload"]["providers"]["openai"]["api_key_env"] == "OPENAI_API_KEY", model_active
model_payload = copy.deepcopy(model_active["payload"])
model_payload["active_provider"] = "openai"
model_payload["default_model_alias"] = model_payload["providers"]["openai"]["model_alias"]
model_payload["upstream_model"] = model_payload["providers"]["openai"]["model"]
for route_name in list(model_payload["routing"]):
    model_payload["routing"][route_name] = model_payload["providers"]["openai"]["model_alias"]
model_payload["settings"]["context_length"] = model_payload["providers"]["openai"]["context_length"]
model_payload["settings"]["temperature"] = model_payload["providers"]["openai"]["temperature"]
model_payload["settings"]["rate_limits"] = model_payload["providers"]["openai"]["rate_limits"]
model_payload["fallbacks"] = [
    {
        "from": model_payload["providers"]["openai"]["model_alias"],
        "to": model_payload["providers"]["vllm_cpu"]["model_alias"],
    }
]
model_switch_draft = request(
    "/admin/config/drafts",
    {
        "domain": "model_routing",
        "payload": model_payload,
        "operator_id": "admin-stage13",
        "base_version_id": model_active["active_version_id"],
    },
)
model_switch_validated = request(
    f"/admin/config/drafts/{model_switch_draft['draft_id']}/validate",
    {"operator_id": "admin-stage13"},
)
assert model_switch_validated["validation"]["status"] == "valid", model_switch_validated
request(f"/admin/config/drafts/{model_switch_draft['draft_id']}/regression", {"operator_id": "admin-stage13"})
model_switch_version = request(
    f"/admin/config/drafts/{model_switch_draft['draft_id']}/activate",
    {"operator_id": "admin-stage13"},
)
model_after_switch = request("/admin/config/active/model_routing")
assert model_after_switch["payload"]["active_provider"] == "openai", model_after_switch
assert model_after_switch["payload"]["providers"]["vllm_cpu"]["model_alias"] == "local-opt-125m", model_after_switch
assert model_switch_version["domain"] == "model_routing", model_switch_version
print("переключение стабильного профиля модели проверено")

custom_model = copy.deepcopy(model_after_switch["payload"])
custom_model["providers"]["litellm_stage13"] = {
    "enabled": True,
    "provider_type": "litellm",
    "display_name": "LiteLLM smoke подключение",
    "base_url": "http://127.0.0.1:4000/v1",
    "model_alias": "openai/gpt-4.1-mini",
    "model": "openai/gpt-4.1-mini",
    "api_key_env": "OPENAI_API_KEY",
    "api_key_required": True,
    "context_length": 128000,
    "temperature": 0,
    "max_tokens": 4096,
    "timeout_seconds": 60,
    "rate_limits": {
        "requests_per_minute": 60,
        "tokens_per_minute": 120000,
    },
}
custom_model["active_provider"] = "litellm_stage13"
custom_model["default_model_alias"] = "openai/gpt-4.1-mini"
custom_model["upstream_model"] = "openai/gpt-4.1-mini"
for route_name in list(custom_model["routing"]):
    custom_model["routing"][route_name] = "openai/gpt-4.1-mini"
custom_model["fallbacks"] = [
    {
        "from": "openai/gpt-4.1-mini",
        "to": custom_model["providers"]["vllm_cpu"]["model_alias"],
    }
]
custom_model["settings"]["context_length"] = custom_model["providers"]["litellm_stage13"]["context_length"]
custom_model["settings"]["temperature"] = custom_model["providers"]["litellm_stage13"]["temperature"]
custom_model["settings"]["rate_limits"] = custom_model["providers"]["litellm_stage13"]["rate_limits"]
custom_draft = request(
    "/admin/config/drafts",
    {
        "domain": "model_routing",
        "payload": custom_model,
        "operator_id": "admin-stage13",
        "base_version_id": model_after_switch["active_version_id"],
    },
)
custom_validated = request(
    f"/admin/config/drafts/{custom_draft['draft_id']}/validate",
    {"operator_id": "admin-stage13"},
)
assert custom_validated["validation"]["status"] == "valid", custom_validated
request(f"/admin/config/drafts/{custom_draft['draft_id']}/regression", {"operator_id": "admin-stage13"})
request(f"/admin/config/drafts/{custom_draft['draft_id']}/activate", {"operator_id": "admin-stage13"})
model_after_custom = request("/admin/config/active/model_routing")
assert model_after_custom["payload"]["active_provider"] == "litellm_stage13", model_after_custom
assert model_after_custom["payload"]["providers"]["litellm_stage13"]["provider_type"] == "litellm", model_after_custom
print("добавление пользовательского подключения LiteLLM проверено")

secret_update = request(
    "/admin/models/secrets",
    {
        "provider_id": "litellm_stage13",
        "env_name": "OPENAI_API_KEY",
        "secret_value": "stage13-secret-value",
    },
)
assert secret_update["display_value"] == "параметр скрыт", secret_update
model_after_secret = request("/admin/models/config")
assert model_after_secret["runtime"]["provider_key_configured"]["litellm_stage13"] is True, model_after_secret
secret_audit = request("/admin/security/audit?action=admin.models.secret.update&limit=10")
secret_dump = json.dumps(secret_audit, ensure_ascii=False)
assert "stage13-secret-value" not in secret_dump, secret_audit
assert "OPENAI_API_KEY" in secret_dump, secret_audit
print("скрытое сохранение секрета модели проверено")

bad_model = copy.deepcopy(model_active["payload"])
bad_model["default_model_alias"] = "missing-alias"
bad_draft = request(
    "/admin/config/drafts",
    {
        "domain": "model_routing",
        "payload": bad_model,
        "operator_id": "admin-stage13",
    },
)
bad_validated = request(
    f"/admin/config/drafts/{bad_draft['draft_id']}/validate",
    {"operator_id": "admin-stage13"},
)
assert bad_validated["validation"]["status"] == "invalid", bad_validated
assert bad_validated["validation"]["errors"], bad_validated
print("валидация невалидной конфигурации проверена")

n8n = request("/admin/n8n/workflows")
assert n8n["workflows"], n8n
restart = request(
    "/admin/n8n/workflows/provider_channel_failure/restart",
    {"operator_id": "admin-stage13", "execution_id": "exec-stage13"},
)
assert restart["accepted"] is False and restart["status"] == "unsupported", restart
print("защитный режим управления n8n проверен")

audit = request("/admin/security/audit?limit=100")
actions = {event["action"] for event in audit["events"]}
for expected in {
    "admin.config.draft.create",
    "admin.config.draft.validate",
    "admin.config.draft.regression",
    "admin.config.draft.activate",
    "admin.config.version.rollback",
}:
    assert expected in actions, audit
print("аудит конфигурации проверен")

print("Smoke-проверка этапа 13 завершена.")
PY
