#!/usr/bin/env bash
set -euo pipefail

if [ -x ".venv/bin/python" ]; then
  PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

HOST="${ORCHESTRATOR_HOST:-127.0.0.1}"
PORT="${ORCHESTRATOR_PORT:-18107}"
BASE_URL="http://${HOST}:${PORT}"
LOG_FILE="${STAGE12_6_LOG_FILE:-/tmp/servicedesk-stage12-6-orchestrator.log}"
STATE_DB="${STAGE12_6_STATE_DB:-/tmp/servicedesk-stage12-6-orchestrator-${PORT}-$$.sqlite}"
INDEX_PATH="${STAGE12_6_INDEX_PATH:-/tmp/servicedesk-stage12-6-knowledge-${PORT}-$$.json}"

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
admin_headers = {"X-ServiceDesk-Actor": "admin-1", "X-ServiceDesk-Session": "stage12_6:admin"}


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
assert "Разрешение слотов" in html, html[:300]
assert "1. Разрешение слотов" in html, html[:300]
assert "0. Слоты" in html, html[:300]
assert "Сценарии обработки" in html, html[:300]
js = request("/admin/static/app.js", parse_json=False)
for expected in [
    "renderResolutionProfiles",
    "resolution-operation",
    "resolution-profile-editor",
    "attribute_resolution_profiles",
    "Как получить значение слота",
    "из данных обращения",
    "Значение уже есть в текущем обращении",
    "Путь в данных обращения",
    "Инструкция для модели",
    "Подсказка оператору",
    "Профиль разрешения атрибута",
    "Пороги внутри профиля",
    "Обогащение контекста",
    "Параметр ReAct-вызова",
    "Добавить шаг обогащения",
    "enrichment-step-table",
    "enrichment-step-edit",
    "Параметры шагов",
    "Доступные ссылки на результаты",
    "refreshEnrichmentStepCard",
    "Выходные слоты и порядок заполнения",
    "LLM-правила выбора, заполнения и уточнения",
]:
    assert expected in js, expected
for removed in [
    "Имя сущности результата",
    "entity:&lt;сущность&gt;.&lt;поле&gt;",
    "Контракт результата",
    "Упорядоченные шаги, JSON",
    "Сводка профилей",
    "renderResolutionStepCard",
    "resolution-step-add",
    "resolution-step-remove",
]:
    assert removed not in js, removed
print("assets разрешения атрибутов проверены")

domains = request("/admin/config/domains")
domain_ids = {item["domain"] for item in domains["domains"]}
assert "attribute_resolution_profiles" in domain_ids, domains

profiles_active = request("/admin/config/active/attribute_resolution_profiles")
profiles = profiles_active["payload"]["profiles"]
assert any(profile["profile_id"] == "profile.password_reset.login_from_ad" for profile in profiles), profiles_active
login_profile = next(profile for profile in profiles if profile["profile_id"] == "profile.password_reset.login_from_ad")
assert login_profile["enrichment_steps"][0]["react_call"] == "search_ad_users", login_profile
assert login_profile["enrichment_steps"][0]["step_id"] == "step1", login_profile
assert "result_entity_name" not in login_profile["enrichment_steps"][0], login_profile
assert any(rule["slot_id"] == "user_id" for rule in login_profile["output_slots_order"]), login_profile
assert login_profile["llm_resolution_script"]["script_text"], login_profile
print("default-профили проверены")

detail = request("/admin/scenarios/password_reset")
assert detail["attribute_resolution_profiles"], detail
user_login = next(slot for slot in detail["slot_schema"]["slots"] if slot["slot_id"] == "user_login")
assert user_login["fill_method"] == "resolution_profile", user_login
assert user_login["resolution_profile_id"] == "profile.password_reset.login_from_ad", user_login

simulation = request(
    "/admin/scenarios/password_reset/simulate",
    {
        "operator_id": "admin-stage12_6",
        "text": "Иванов Иван не может войти в доменную учетную запись",
    },
)
assert simulation["attribute_resolution"], simulation
assert simulation["slot_values"]["user_login"]["status"] == "question_required", simulation
assert simulation["slot_values"]["user_login"]["effective_confidence_thresholds"]["auto_accept_confidence"] >= 0.75, simulation
assert simulation["resolution_state"]["user_login"]["effective_confidence_thresholds"]["operator_handoff_confidence"] == 0.5, simulation
assert "user_login" in simulation["missing_slots"], simulation
assert "должность" in simulation["next_question"].lower() or "табель" in simulation["next_question"].lower(), simulation
print("dry-run разрешения атрибутов проверен")


def activate_config_payload(domain, payload, label):
    active = request(f"/admin/config/active/{domain}")
    draft = request(
        "/admin/config/drafts",
        {
            "domain": domain,
            "payload": payload,
            "operator_id": f"admin-stage12_6-{label}",
            "base_version_id": active["active_version_id"],
        },
    )
    validated = request(
        f"/admin/config/drafts/{draft['draft_id']}/validate",
        {"operator_id": f"admin-stage12_6-{label}"},
    )
    assert validated["validation"]["status"] == "valid", validated
    checked = request(
        f"/admin/config/drafts/{draft['draft_id']}/regression",
        {"operator_id": f"admin-stage12_6-{label}", "limit": 20},
    )
    assert checked["regression"]["status"] in {"passed", "skipped"}, checked
    return request(
        f"/admin/config/drafts/{draft['draft_id']}/activate",
        {"operator_id": f"admin-stage12_6-{label}"},
    )


two_step_payload = copy.deepcopy(request("/admin/config/active/attribute_resolution_profiles")["payload"])
two_step_profile = next(profile for profile in two_step_payload["profiles"] if profile["profile_id"] == "profile.password_reset.login_from_ad")
two_step_profile["enrichment_steps"] = [
    two_step_profile["enrichment_steps"][0],
    {
        "step_id": "step2",
        "step_name": "Проверить логин повторным поиском",
        "react_call": "search_ad_users",
        "parameter_mapping": {
            "login": "step:step1.react.search_ad_users.output.users.0.login"
        },
        "on_error": "continue_to_llm",
    },
]
activate_config_payload("attribute_resolution_profiles", two_step_payload, "two-step")
two_step_simulation = request(
    "/admin/scenarios/password_reset/simulate",
    {
        "operator_id": "admin-stage12_6",
        "text": "Иванов Иван не может войти в доменную учетную запись",
        "run_mode": "llm_readonly",
    },
)
two_step_state = two_step_simulation["resolution_state"]["user_login"]
assert two_step_state["enrichment_step_results"]["step2"]["parameters"]["login"] == "ivanov", two_step_state
assert two_step_state["enrichment_step_results"]["step2"]["result"]["users"][0]["login"] == "ivanov", two_step_state
print("step-ссылка между шагами разрешения атрибута проверена")

slot_active = request("/admin/config/active/slot_schemas")
slot_payload = copy.deepcopy(slot_active["payload"])
for schema in slot_payload["slot_schemas"]:
    if schema["slot_schema_id"] == "slot.password_reset":
        schema["slots"] = [
            slot for slot in schema["slots"]
            if slot["slot_id"] != "user_id"
        ]
        schema["auto_fill_slots"] = [
            slot_id for slot_id in schema["auto_fill_slots"]
            if slot_id != "user_id"
        ]
slot_remove_draft = request(
    "/admin/config/drafts",
    {
        "domain": "slot_schemas",
        "payload": slot_payload,
        "operator_id": "admin-stage12_6-slot-profile-output",
        "base_version_id": slot_active["active_version_id"],
    },
)
slot_remove_validated = request(
    f"/admin/config/drafts/{slot_remove_draft['draft_id']}/validate",
    {"operator_id": "admin-stage12_6-slot-profile-output"},
)
assert slot_remove_validated["validation"]["status"] == "invalid", slot_remove_validated
assert any("user_id" in error for error in slot_remove_validated["validation"]["errors"]), slot_remove_validated
print("output профиля должен входить в выбранную схему слотов")

payload = copy.deepcopy(profiles_active["payload"])
temporary = copy.deepcopy(login_profile)
temporary["profile_id"] = "profile.ui_temp.resolution"
temporary["display_name"] = "Временный профиль UI"
temporary["status"] = "draft"
temporary["target_slot_id"] = "user_login"
payload["profiles"].append(temporary)
activate_config_payload("attribute_resolution_profiles", payload, "create")
created = request("/admin/config/active/attribute_resolution_profiles")
assert any(profile["profile_id"] == "profile.ui_temp.resolution" for profile in created["payload"]["profiles"]), created

payload = copy.deepcopy(created["payload"])
for profile in payload["profiles"]:
    if profile["profile_id"] == "profile.ui_temp.resolution":
        profile["display_name"] = "Временный профиль UI изменен"
        profile["status"] = "planned"
activate_config_payload("attribute_resolution_profiles", payload, "modify")
modified = request("/admin/config/active/attribute_resolution_profiles")
edited = next(profile for profile in modified["payload"]["profiles"] if profile["profile_id"] == "profile.ui_temp.resolution")
assert edited["display_name"] == "Временный профиль UI изменен", modified
assert edited["status"] == "active", modified

payload = copy.deepcopy(modified["payload"])
payload["profiles"] = [
    profile for profile in payload["profiles"]
    if profile["profile_id"] != "profile.ui_temp.resolution"
]
activate_config_payload("attribute_resolution_profiles", payload, "delete")
deleted = request("/admin/config/active/attribute_resolution_profiles")
assert not any(profile["profile_id"] == "profile.ui_temp.resolution" for profile in deleted["payload"]["profiles"]), deleted
print("создание, модификация и удаление профилей проверены")

bad_payload = copy.deepcopy(deleted["payload"])
profile_with_step = next(profile for profile in bad_payload["profiles"] if profile.get("enrichment_steps"))
profile_with_step["enrichment_steps"][0]["react_call"] = "unknown_tool"
bad_draft = request(
    "/admin/config/drafts",
    {
        "domain": "attribute_resolution_profiles",
        "payload": bad_payload,
        "operator_id": "admin-stage12_6",
    },
)
bad_validated = request(
    f"/admin/config/drafts/{bad_draft['draft_id']}/validate",
    {"operator_id": "admin-stage12_6"},
)
assert bad_validated["validation"]["status"] == "invalid", bad_validated
assert any("unknown_tool" in error for error in bad_validated["validation"]["errors"]), bad_validated
print("валидация профилей проверена")

empty_payload = copy.deepcopy(deleted["payload"])
empty_payload["profiles"] = []
activate_config_payload("attribute_resolution_profiles", empty_payload, "delete-all")
empty_profiles = request("/admin/config/active/attribute_resolution_profiles")
assert empty_profiles["payload"]["profiles"] == [], empty_profiles
print("пустой список профилей разрешения атрибутов разрешен")

audit = request("/admin/security/audit?limit=100")
actions = {event["action"] for event in audit["events"]}
assert "admin.config.draft.activate" in actions, audit
print("аудит разрешения атрибутов проверен")

print("Smoke-проверка этапа 12.6 завершена.")
PY
