#!/usr/bin/env bash
set -euo pipefail

if [ -x ".venv/bin/python" ]; then
  PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

HOST="${ORCHESTRATOR_HOST:-127.0.0.1}"
PORT="${ORCHESTRATOR_PORT:-18105}"
BASE_URL="http://${HOST}:${PORT}"
LOG_FILE="${STAGE12_5_LOG_FILE:-/tmp/servicedesk-stage12-5-orchestrator.log}"
STATE_DB="${STAGE12_5_STATE_DB:-/tmp/servicedesk-stage12-5-orchestrator-${PORT}-$$.sqlite}"
INDEX_PATH="${STAGE12_5_INDEX_PATH:-/tmp/servicedesk-stage12-5-knowledge-${PORT}-$$.json}"

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
admin_headers = {"X-ServiceDesk-Actor": "admin-1", "X-ServiceDesk-Session": "stage12_5:admin"}


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
assert "Сценарии" in html, html[:300]
assert "Сценарии обработки" in html, html[:300]
for expected_view in [
    'data-view="resolution"',
    'data-view="scenarioSlots"',
    'data-view="scenarioClassification"',
    'data-view="scenarioReact"',
    'data-view="scenarioTools"',
    'data-view="scenarioEscalation"',
]:
    assert expected_view in html, expected_view
assert "0. Разрешение атрибутов" in html, html[:300]
assert 'data-view="scenarioPrompts"' in html, html[:300]
assert "6. Промпты" in html, html[:300]
assert "Реестр промптов" not in html, html[:300]
assert 'data-view="prompts"' not in html, html[:300]
js = request("/admin/static/app.js", parse_json=False)
assert "renderScenarios" in js, js[:300]
for expected_renderer in [
    "renderScenarioSlots",
    "renderScenarioClassification",
    "renderScenarioReact",
    "renderScenarioTools",
    "renderScenarioEscalation",
]:
    assert expected_renderer in js, expected_renderer
assert "renderScenarioPrompts" in js, js[:300]
assert "scenario-operation" in js, js[:300]
assert "prompt-pack-operation" in js, js[:300]
assert "saveScenarioForm" in js, js[:300]
for expected_form in [
    "slot-schema-editor",
    "slot-schema-delete",
    "route-editor",
    "route-delete",
    "policy-editor",
    "policy-delete",
    "tool-launch-editor",
    "tool-matrix-delete",
    "escalation-editor",
    "escalation-delete",
    "prompt-pack-editor",
    "prompt-pack-delete",
]:
    assert expected_form in js, expected_form
for expected_slot_text in [
    "slot-add",
    "slot-remove",
    "slot-card-summary",
    "slot-card-body",
    "Priority group",
    "Способ заполнения",
    "Профиль разрешения атрибута",
    "Технический ключ поля",
    "Служебные списки",
    "Где используется",
    "slot-schema-operation",
    "route-operation",
    "policy-operation",
    "tool-matrix-operation",
    "escalation-operation",
]:
    assert expected_slot_text in js, expected_slot_text
assert "slots_json" not in js, js[:300]
assert "Слоты, JSON" not in js, js[:300]
for hidden_label in [
    "ID сценария",
    "ID схемы",
    "ID маршрута",
    "ID политики",
    "ID запуска",
    "ID пакета",
    "ID слота",
]:
    assert hidden_label not in js, hidden_label
assert "Карта сценариев" not in js, js[:300]
assert "Предпросмотр системного промпта" not in js, js[:300]
assert "Тестовый прогон сценария" not in js, js[:300]
assert "scenarioSimulationResult" not in js, js[:300]
assert "section('Пакет промптов: обязательные блоки', renderPromptPackEditor(detail?.prompt_pack))" not in js, js[:300]
operator_html = request("/operator", parse_json=False)
assert "Тестовый прогон сценария" in operator_html, operator_html[:300]
operator_js = request("/operator/static/app.js", parse_json=False)
assert "dryRunToggle" in operator_js, operator_js[:300]
assert "setDryRunEnabled" in operator_js, operator_js[:300]
print("assets сценарной консоли проверены")

domains = request("/admin/config/domains")
domain_ids = {item["domain"] for item in domains["domains"]}
expected_domains = {
    "service_scenarios",
    "slot_schemas",
    "classification_routes",
    "orchestrator_policy",
    "tool_launch_matrix",
    "prompt_packs",
    "escalation_policies",
    "attribute_resolution_profiles",
}
for expected in expected_domains:
    assert expected in domain_ids, domains
print("домены сценарной модели проверены")

scenarios = request("/admin/scenarios")
assert scenarios["scenario_count"] >= 6, scenarios
password_summary = next(item for item in scenarios["scenarios"] if item["scenario_id"] == "password_reset")
assert password_summary["readiness"]["status"] == "ready", password_summary
detail = request("/admin/scenarios/password_reset")
assert detail["readiness"]["status"] == "ready", detail
assert detail["slot_schema"]["required_slots"] == ["user_login", "account_type"], detail
assert detail["scenario"]["tool_launch_matrix_id"] == "matrix.password_reset", detail
assert detail["tool_launch_matrix"]["display_name"], detail
assert len(detail["prompt_pack"]["blocks"]) == 7, detail
assert "1. Роль и контекст" in detail["prompt_preview"], detail["prompt_preview"]
print("карта сценария проверена")

simulation = request(
    "/admin/scenarios/password_reset/simulate",
    {
        "operator_id": "admin-stage12_5",
        "text": "Пользователь не может войти, нужен сброс пароля",
    },
)
assert simulation["dry_run"] is True, simulation
assert simulation["classification"]["keyword_hits"], simulation
assert "user_login" in simulation["missing_slots"], simulation
assert simulation["final_decision"] == "continue_slot_filling", simulation
print("тестовый прогон сценария проверен")


def activate_service_scenarios(payload, label):
    return activate_config_payload("service_scenarios", payload, label)


def activate_config_payload(domain, payload, label):
    active = request(f"/admin/config/active/{domain}")
    draft = request(
        "/admin/config/drafts",
        {
            "domain": domain,
            "payload": payload,
            "operator_id": f"admin-stage12_5-{label}",
            "base_version_id": active["active_version_id"],
        },
    )
    validated = request(
        f"/admin/config/drafts/{draft['draft_id']}/validate",
        {"operator_id": f"admin-stage12_5-{label}"},
    )
    assert validated["validation"]["status"] == "valid", validated
    checked = request(
        f"/admin/config/drafts/{draft['draft_id']}/regression",
        {"operator_id": f"admin-stage12_5-{label}", "limit": 20},
    )
    assert checked["regression"]["status"] in {"passed", "skipped"}, checked
    return request(
        f"/admin/config/drafts/{draft['draft_id']}/activate",
        {"operator_id": f"admin-stage12_5-{label}"},
    )


active_scenarios = request("/admin/config/active/service_scenarios")
scenario_payload = copy.deepcopy(active_scenarios["payload"])
template = next(item for item in scenario_payload["scenarios"] if item["scenario_id"] == "password_reset")
temporary = copy.deepcopy(template)
temporary["scenario_id"] = "ui_temp_scenario"
temporary["display_name"] = "Временный UI сценарий"
temporary["description"] = "Smoke-проверка создания сценария из меню администратора."
temporary["status"] = "draft"
scenario_payload["scenarios"].append(temporary)
activate_service_scenarios(scenario_payload, "create")
created = request("/admin/scenarios")
assert any(item["scenario_id"] == "ui_temp_scenario" for item in created["scenarios"]), created

active_scenarios = request("/admin/config/active/service_scenarios")
scenario_payload = copy.deepcopy(active_scenarios["payload"])
for scenario in scenario_payload["scenarios"]:
    if scenario["scenario_id"] == "ui_temp_scenario":
        scenario["display_name"] = "Временный UI сценарий изменен"
        scenario["status"] = "planned"
activate_service_scenarios(scenario_payload, "modify")
modified = request("/admin/scenarios/ui_temp_scenario")
assert modified["scenario"]["display_name"] == "Временный UI сценарий изменен", modified
assert modified["scenario"]["status"] == "planned", modified

active_scenarios = request("/admin/config/active/service_scenarios")
scenario_payload = copy.deepcopy(active_scenarios["payload"])
scenario_payload["scenarios"] = [
    scenario for scenario in scenario_payload["scenarios"]
    if scenario["scenario_id"] != "ui_temp_scenario"
]
activate_service_scenarios(scenario_payload, "delete")
deleted = request("/admin/scenarios")
assert not any(item["scenario_id"] == "ui_temp_scenario" for item in deleted["scenarios"]), deleted
print("создание, модификация и удаление сценария проверены")

slot_active = request("/admin/config/active/slot_schemas")
slot_payload = copy.deepcopy(slot_active["payload"])
for schema in slot_payload["slot_schemas"]:
    if schema["slot_schema_id"] == "slot.password_reset":
        schema["display_name"] = "Слоты сброса пароля UI"
        schema["slots"].append(
            {
                "slot_id": "ui_temp_slot",
                "display_name": "Временный слот UI",
                "priority_group": "context",
                "required": False,
                "fill_method": "llm_extraction",
                "examples": ["example"],
            }
        )
        schema["auto_fill_slots"].append("ui_temp_slot")
activate_config_payload("slot_schemas", slot_payload, "slot")
slot_detail = request("/admin/scenarios/password_reset")
assert slot_detail["slot_schema"]["display_name"] == "Слоты сброса пароля UI", slot_detail
assert any(slot["slot_id"] == "ui_temp_slot" for slot in slot_detail["slot_schema"]["slots"]), slot_detail

slot_active = request("/admin/config/active/slot_schemas")
slot_payload = copy.deepcopy(slot_active["payload"])
for schema in slot_payload["slot_schemas"]:
    if schema["slot_schema_id"] == "slot.password_reset":
        for slot in schema["slots"]:
            if slot["slot_id"] == "ui_temp_slot":
                slot["display_name"] = "Временный слот UI изменен"
activate_config_payload("slot_schemas", slot_payload, "slot-modify")
slot_detail = request("/admin/scenarios/password_reset")
edited_slot = next(slot for slot in slot_detail["slot_schema"]["slots"] if slot["slot_id"] == "ui_temp_slot")
assert edited_slot["display_name"] == "Временный слот UI изменен", slot_detail

slot_active = request("/admin/config/active/slot_schemas")
slot_payload = copy.deepcopy(slot_active["payload"])
for schema in slot_payload["slot_schemas"]:
    if schema["slot_schema_id"] == "slot.password_reset":
        schema["slots"] = [slot for slot in schema["slots"] if slot["slot_id"] != "ui_temp_slot"]
        schema["auto_fill_slots"] = [slot_id for slot_id in schema["auto_fill_slots"] if slot_id != "ui_temp_slot"]
activate_config_payload("slot_schemas", slot_payload, "slot-delete")
slot_detail = request("/admin/scenarios/password_reset")
assert not any(slot["slot_id"] == "ui_temp_slot" for slot in slot_detail["slot_schema"]["slots"]), slot_detail

route_active = request("/admin/config/active/classification_routes")
route_payload = copy.deepcopy(route_active["payload"])
for route in route_payload["routes"]:
    if route["route_id"] == "route.password_reset":
        route["top_categories_on_low_confidence"] = 2
activate_config_payload("classification_routes", route_payload, "route")
route_detail = request("/admin/scenarios/password_reset")
assert route_detail["route"]["top_categories_on_low_confidence"] == 2, route_detail

policy_active = request("/admin/config/active/orchestrator_policy")
policy_payload = copy.deepcopy(policy_active["payload"])
for policy in policy_payload["policies"]:
    if policy["policy_id"] == "policy.password_reset":
        policy["max_iterations"] = 7
activate_config_payload("orchestrator_policy", policy_payload, "policy")
policy_detail = request("/admin/scenarios/password_reset")
assert policy_detail["orchestrator_policy"]["max_iterations"] == 7, policy_detail

matrix_active_for_edit = request("/admin/config/active/tool_launch_matrix")
matrix_payload_for_edit = copy.deepcopy(matrix_active_for_edit["payload"])
password_matrix = next(matrix for matrix in matrix_payload_for_edit["matrices"] if matrix["matrix_id"] == "matrix.password_reset")
password_matrix["display_name"] = "Матрица сброса пароля UI"
for launch in password_matrix["launches"]:
    if launch["launch_id"] == "launch.password_reset.runbook":
        launch["stop_on_error"] = False
activate_config_payload("tool_launch_matrix", matrix_payload_for_edit, "matrix")
matrix_detail = request("/admin/scenarios/password_reset")
assert matrix_detail["tool_launch_matrix"]["display_name"] == "Матрица сброса пароля UI", matrix_detail
assert matrix_detail["tool_launches"][0]["stop_on_error"] is False, matrix_detail

prompt_active = request("/admin/config/active/prompt_packs")
prompt_payload = copy.deepcopy(prompt_active["payload"])
for pack in prompt_payload["packs"]:
    if pack["prompt_pack_id"] == "prompt.password_reset":
        pack["blocks"]["role_context"] = "Smoke-проверка редактирования блока роли."
activate_config_payload("prompt_packs", prompt_payload, "prompt")
prompt_detail = request("/admin/scenarios/password_reset")
assert prompt_detail["prompt_pack"]["blocks"]["role_context"] == "Smoke-проверка редактирования блока роли.", prompt_detail

prompt_active = request("/admin/config/active/prompt_packs")
prompt_payload = copy.deepcopy(prompt_active["payload"])
template_pack = next(pack for pack in prompt_payload["packs"] if pack["prompt_pack_id"] == "prompt.password_reset")
temporary_pack = copy.deepcopy(template_pack)
temporary_pack["prompt_pack_id"] = "prompt.ui_temp"
temporary_pack["display_name"] = "Временный пакет промптов UI"
temporary_pack["status"] = "draft"
temporary_pack["scenario_id"] = "password_reset"
prompt_payload["packs"].append(temporary_pack)
activate_config_payload("prompt_packs", prompt_payload, "prompt-create")
created_prompts = request("/admin/config/active/prompt_packs")
assert any(pack["prompt_pack_id"] == "prompt.ui_temp" for pack in created_prompts["payload"]["packs"]), created_prompts

prompt_payload = copy.deepcopy(created_prompts["payload"])
for pack in prompt_payload["packs"]:
    if pack["prompt_pack_id"] == "prompt.ui_temp":
        pack["display_name"] = "Временный пакет промптов UI изменен"
        pack["status"] = "planned"
activate_config_payload("prompt_packs", prompt_payload, "prompt-modify")
modified_prompts = request("/admin/config/active/prompt_packs")
edited_prompt = next(pack for pack in modified_prompts["payload"]["packs"] if pack["prompt_pack_id"] == "prompt.ui_temp")
assert edited_prompt["display_name"] == "Временный пакет промптов UI изменен", modified_prompts
assert edited_prompt["status"] == "planned", modified_prompts

prompt_payload = copy.deepcopy(modified_prompts["payload"])
prompt_payload["packs"] = [
    pack for pack in prompt_payload["packs"]
    if pack["prompt_pack_id"] != "prompt.ui_temp"
]
activate_config_payload("prompt_packs", prompt_payload, "prompt-delete")
deleted_prompts = request("/admin/config/active/prompt_packs")
assert not any(pack["prompt_pack_id"] == "prompt.ui_temp" for pack in deleted_prompts["payload"]["packs"]), deleted_prompts

escalation_active = request("/admin/config/active/escalation_policies")
escalation_payload = copy.deepcopy(escalation_active["payload"])
for policy in escalation_payload["policies"]:
    if policy["policy_id"] == "escalation.password_reset":
        policy["waiting"]["auto_close_after_hours"] = 48
activate_config_payload("escalation_policies", escalation_payload, "escalation")
escalation_detail = request("/admin/scenarios/password_reset")
assert escalation_detail["escalation_policy"]["waiting"]["auto_close_after_hours"] == 48, escalation_detail
print("редактирование пяти шагов и CRUD prompt pack проверены")

for domain in sorted(expected_domains):
    active = request(f"/admin/config/active/{domain}")
    draft = request(
        "/admin/config/drafts",
        {
            "domain": domain,
            "payload": active["payload"],
            "operator_id": "admin-stage12_5",
        },
    )
    validated = request(
        f"/admin/config/drafts/{draft['draft_id']}/validate",
        {"operator_id": "admin-stage12_5"},
    )
    assert validated["validation"]["status"] == "valid", validated
print("валидация сценарных доменов проверена")

matrix_active = request("/admin/config/active/tool_launch_matrix")
bad_matrix = copy.deepcopy(matrix_active["payload"])
bad_matrix["matrices"][0]["launches"][0]["execution_level"] = "auto"
bad_draft = request(
    "/admin/config/drafts",
    {
        "domain": "tool_launch_matrix",
        "payload": bad_matrix,
        "operator_id": "admin-stage12_5",
    },
)
bad_validated = request(
    f"/admin/config/drafts/{bad_draft['draft_id']}/validate",
    {"operator_id": "admin-stage12_5"},
)
assert bad_validated["validation"]["status"] == "invalid", bad_validated
assert any("не может быть auto" in error for error in bad_validated["validation"]["errors"]), bad_validated
print("guard матрицы запуска инструментов проверен")

audit = request("/admin/security/audit?limit=100")
actions = {event["action"] for event in audit["events"]}
assert "admin.scenarios.simulate" in actions, audit
print("аудит сценарного прогона проверен")

print("Smoke-проверка этапа 12.5 завершена.")
PY
