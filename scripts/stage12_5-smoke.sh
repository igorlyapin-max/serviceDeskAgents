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
assert "1. Разрешение атрибутов" in html, html[:300]
assert "0. Слоты" in html, html[:300]
assert 'data-view="scenarioPrompts"' in html, html[:300]
assert "6. Промпты" in html, html[:300]
assert "Реестр промптов" not in html, html[:300]
assert 'data-view="prompts"' not in html, html[:300]
js = request("/admin/static/app.js", parse_json=False)
assert "renderScenarios" in js, js[:300]
for expected_renderer in [
    "renderScenarioSlots",
    "renderOrchestrationGraph",
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
    "Как получить значение слота",
    "из данных обращения",
    "data-fill-method-help",
    "Вопрос клиенту",
    "Путь в данных обращения",
    "Инструкция для модели",
    "Запасной вопрос",
    "Подсказка оператору",
    "Системные пороги уверенности",
    "Пороги внутри профиля",
    "Автопринятие от",
    "Минимум извлечения",
    "Значение уже есть в текущем обращении",
    "Профиль разрешения атрибута",
    "Сценарий для выбора слотов",
    "data-resolution-slot-scenario",
    "name=\"slot_schema_id\"",
    "name=\"target_slot_id\"",
    "name=\"clarification_slots\" multiple",
    "name=\"handoff_package\" multiple",
    "enrichment_steps",
    "output_slots_order",
    "llm_resolution_script",
    "Обогащение контекста",
    "Параметр ReAct-вызова",
    "Выходные слоты и порядок заполнения",
    "LLM-правила выбора, заполнения и уточнения",
    "Уточнение у клиента и эскалация оператору",
    "Слоты для уточнения у клиента",
    "Пакет эскалации оператору",
    "Уточнения у клиента",
    "Эскалация оператору",
    "Технический ключ поля",
    "Где используется",
    "slot-schema-operation",
    "route-operation",
    "Правила классификации",
    "До N категорий при низкой уверенности",
    "route-rule-add",
    "route-rule-remove",
    "Тип совпадения",
    "Позитивные признаки",
    "policy-operation",
    "tool-matrix-operation",
    "escalation-operation",
    "data-slot-fill-method",
    "data-endpoint-operations-section",
    "endpoint-operations-toggle",
    "Нельзя удалить: сначала уберите связи",
    "Входные параметры операции",
    "Поля ответа операции",
    "Тестовый ответ mock",
    "JSON контрольная точка",
    "Применить JSON в форму",
    "Входные параметры endpoint",
    "Поля ответа, доступные ReAct",
    "Создать и привязать ReAct-вызов ИИ",
    "operation-binding-create-editor",
    "Нельзя отвязать: сначала уберите связи",
    "Статус контракта",
    "Версия контракта",
    "Имя поля результата ReAct",
    "Совместимость контрактов",
    "result_mapping",
    "response_schema",
    "contract_version",
    "contract_status",
    "Граф оркестрации",
    "graph-zoom-in",
    "graph-zoom-out",
    "graph-zoom-fit",
    "data-graph-canvas",
    "graph-config-link",
    "readonly",
]:
    assert expected_slot_text in js, expected_slot_text
assert "slots_json" not in js, js[:300]
assert "Слоты, JSON" not in js, js[:300]
assert "Ключевые слова" not in js, js[:300]
assert "Негативные ключевые слова" not in js, js[:300]
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
for expected_operator_tab in [
    'class="operator-tabs"',
    'data-main-tab="steps"',
    'data-main-tab="result"',
    'data-main-tab="case"',
    'data-main-tab="approvals"',
    'data-main-tab="knowledge"',
    'data-main-tab="trace"',
    "Диагностика",
]:
    assert expected_operator_tab in operator_html, expected_operator_tab
operator_js = request("/operator/static/app.js", parse_json=False)
assert "dryRunToggle" in operator_js, operator_js[:300]
assert "setDryRunEnabled" in operator_js, operator_js[:300]
assert "activeMainTab" in operator_js, operator_js[:300]
assert "setMainTab" in operator_js, operator_js[:300]
assert "workflowStarted" in operator_js, operator_js[:300]
assert "ticketTextSnapshot" in operator_js, operator_js[:300]
assert "Работа начнется после кнопки" in operator_js, operator_js[:300]
assert "Результат слота" in operator_js, operator_js[:300]
assert "answerableMissingSlotIds" in operator_js, operator_js[:300]
assert "savePendingSlotAnswer" in operator_js, operator_js[:300]
assert "refreshScenarioPreservingInput" in operator_js, operator_js[:300]
assert "Ожидает автоматического заполнения" in operator_js, operator_js[:300]
for expected_operator_text in [
    "testRunMode",
    "allowLlmToggle",
    "С моделью",
    "С моделью и безопасными интеграциями",
    "Отладочный запуск с подтверждениями",
    "execution_trace",
    "Трасса тестового прогона",
]:
    assert expected_operator_text in operator_js or expected_operator_text in operator_html, expected_operator_text
print("assets сценарной консоли проверены")

domains = request("/admin/config/domains")
domain_ids = {item["domain"] for item in domains["domains"]}
expected_domains = {
    "service_scenarios",
    "slot_schemas",
    "classification_routes",
    "orchestrator_policy",
    "tool_launch_matrix",
    "tools",
    "integration_endpoints",
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
assert detail["system_confidence_defaults"]["auto_accept_confidence"] == 0.85, detail
assert "user_login" in detail["slot_confidence_thresholds"], detail
print("карта сценария проверена")

graph = request("/admin/orchestration-graph?scenario_id=password_reset&view=scenario")
assert graph["readonly"] is True, graph
assert graph["view"] == "scenario", graph
assert graph["scenario_id"] == "password_reset", graph
assert graph["nodes"], graph
assert graph["edges"], graph
assert all(node["readonly"] is True for node in graph["nodes"]), graph
titles = {node["title"] for node in graph["nodes"]}
for expected_title in [
    "0. Слоты",
    "1. Разрешение атрибутов",
    "2. Классификация и маршрут",
    "3. ReAct-планирование",
    "4. ReAct-вызовы и матрица запуска",
    "5. Решение и эскалация",
    "Ожидание ответа клиента",
    "Эскалация оператору",
]:
    assert expected_title in titles, expected_title
slot_node = next(node for node in graph["nodes"] if node["id"] == "slot_filling")
assert any(ref["view"] == "scenarioSlots" for ref in slot_node["config_refs"]), slot_node
assert any(edge["from"] == "tool_use" and edge["to"] == "react_planning" for edge in graph["edges"]), graph
assert any(edge["from"] == "waiting" and edge["to"] == "slot_filling" for edge in graph["edges"]), graph
base_graph = request("/admin/orchestration-graph?view=base")
assert base_graph["readonly"] is True, base_graph
assert base_graph["view"] == "base", base_graph
assert base_graph["scenario_id"] is None, base_graph
print("read-only граф оркестрации проверен")

simulation = request(
    "/admin/scenarios/password_reset/simulate",
    {
        "operator_id": "admin-stage12_5",
        "text": "Пользователь не может войти, нужен сброс пароля",
    },
)
assert simulation["dry_run"] is True, simulation
assert simulation["run_mode"] == "config_check", simulation
assert simulation["simulation_options"]["allow_llm"] is False, simulation
assert simulation["execution_trace"], simulation
assert simulation["classification"]["positive_hits"], simulation
assert simulation["classification"]["top_routes"], simulation
assert "user_login" in simulation["missing_slots"], simulation
assert simulation["next_client_question"] == simulation["next_question"], simulation
assert simulation["awaiting_client_response"] is True, simulation
assert simulation["client_question"]["semantic"] == "client_clarification", simulation
assert simulation["operator_escalation"]["required"] is False, simulation
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
                "extraction_instruction": "Извлеки временное значение для smoke-проверки.",
                "confidence_overrides": {"min_extraction_confidence": 0.72},
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
assert edited_slot["confidence_overrides"]["min_extraction_confidence"] == 0.72, slot_detail

slot_active = request("/admin/config/active/slot_schemas")
slot_payload = copy.deepcopy(slot_active["payload"])
for schema in slot_payload["slot_schemas"]:
    if schema["slot_schema_id"] == "slot.password_reset":
        schema["slots"] = [slot for slot in schema["slots"] if slot["slot_id"] != "ui_temp_slot"]
        schema["auto_fill_slots"] = [slot_id for slot_id in schema["auto_fill_slots"] if slot_id != "ui_temp_slot"]
activate_config_payload("slot_schemas", slot_payload, "slot-delete")
slot_detail = request("/admin/scenarios/password_reset")
assert not any(slot["slot_id"] == "ui_temp_slot" for slot in slot_detail["slot_schema"]["slots"]), slot_detail

slot_active = request("/admin/config/active/slot_schemas")
slot_payload = copy.deepcopy(slot_active["payload"])
for schema in slot_payload["slot_schemas"]:
    if schema["slot_schema_id"] == "slot.password_reset":
        schema["slots"] = [slot for slot in schema["slots"] if slot["slot_id"] != "account_type"]
        schema["required_slots"] = [slot_id for slot_id in schema["required_slots"] if slot_id != "account_type"]
        schema["question_order"] = [slot_id for slot_id in schema["question_order"] if slot_id != "account_type"]
account_type_delete_draft = request(
    "/admin/config/drafts",
    {
        "domain": "slot_schemas",
        "payload": slot_payload,
        "operator_id": "admin-stage12_5-slot-delete-account-type",
        "base_version_id": slot_active["active_version_id"],
    },
)
account_type_delete_validated = request(
    f"/admin/config/drafts/{account_type_delete_draft['draft_id']}/validate",
    {"operator_id": "admin-stage12_5-slot-delete-account-type"},
)
assert account_type_delete_validated["validation"]["status"] == "invalid", account_type_delete_validated
assert any("account_type" in error for error in account_type_delete_validated["validation"]["errors"]), account_type_delete_validated
print("удаление slot, используемого профилем, блокируется")

slot_active = request("/admin/config/active/slot_schemas")
llm_slot_payload = copy.deepcopy(slot_active["payload"])
llm_slot_payload["slot_schemas"].append(
    {
        "slot_schema_id": "slot.ui_temp_llm",
        "display_name": "Временная схема LLM",
        "required_slots": ["user_fio"],
        "auto_fill_slots": ["user_fio"],
        "question_order": [],
        "slots": [
            {
                "slot_id": "user_fio",
                "display_name": "Фамилия Имя Отчество",
                "priority_group": "who",
                "required": True,
                "fill_method": "llm_extraction",
                "extraction_instruction": "Извлеки ФИО сотрудника.",
            }
        ],
    }
)
llm_slot_draft = request(
    "/admin/config/drafts",
    {
        "domain": "slot_schemas",
        "payload": llm_slot_payload,
        "operator_id": "admin-stage12_5-llm-slot",
        "base_version_id": slot_active["active_version_id"],
    },
)
llm_slot_validated = request(
    f"/admin/config/drafts/{llm_slot_draft['draft_id']}/validate",
    {"operator_id": "admin-stage12_5-llm-slot"},
)
assert llm_slot_validated["validation"]["status"] == "valid", llm_slot_validated

stale_profile_payload = copy.deepcopy(llm_slot_payload)
for schema in stale_profile_payload["slot_schemas"]:
    if schema["slot_schema_id"] == "slot.ui_temp_llm":
        schema["slots"][0]["resolution_profile_id"] = "profile.password_reset.login_from_ad"
stale_profile_draft = request(
    "/admin/config/drafts",
    {
        "domain": "slot_schemas",
        "payload": stale_profile_payload,
        "operator_id": "admin-stage12_5-stale-profile",
        "base_version_id": slot_active["active_version_id"],
    },
)
stale_profile_validated = request(
    f"/admin/config/drafts/{stale_profile_draft['draft_id']}/validate",
    {"operator_id": "admin-stage12_5-stale-profile"},
)
assert stale_profile_validated["validation"]["status"] == "valid", stale_profile_validated
print("нормализация скрытых полей способа заполнения slot проверена")

route_active = request("/admin/config/active/classification_routes")
legacy_route_payload = copy.deepcopy(route_active["payload"])
legacy_route_payload["routes"][0]["rules"] = {
    "keywords": ["пароль"],
    "negative_keywords": ["vpn"],
}
legacy_route_draft = request(
    "/admin/config/drafts",
    {
        "domain": "classification_routes",
        "payload": legacy_route_payload,
        "operator_id": "admin-stage12_5-legacy-route",
        "base_version_id": route_active["active_version_id"],
    },
)
legacy_route_validated = request(
    f"/admin/config/drafts/{legacy_route_draft['draft_id']}/validate",
    {"operator_id": "admin-stage12_5-legacy-route"},
)
assert legacy_route_validated["validation"]["status"] == "invalid", legacy_route_validated
assert any("keywords" in error or "rule_items" in error for error in legacy_route_validated["validation"]["errors"]), legacy_route_validated
limited_route_payload = copy.deepcopy(route_active["payload"])
limited_route_payload["routes"] = limited_route_payload["routes"][:2]
for route in limited_route_payload["routes"]:
    route["top_categories_on_low_confidence"] = 3
limited_route_draft = request(
    "/admin/config/drafts",
    {
        "domain": "classification_routes",
        "payload": limited_route_payload,
        "operator_id": "admin-stage12_5-limited-routes",
        "base_version_id": route_active["active_version_id"],
    },
)
limited_route_validated = request(
    f"/admin/config/drafts/{limited_route_draft['draft_id']}/validate",
    {"operator_id": "admin-stage12_5-limited-routes"},
)
assert limited_route_validated["validation"]["status"] == "valid", limited_route_validated
route_payload = copy.deepcopy(route_active["payload"])
for route in route_payload["routes"]:
    if route["route_id"] == "route.password_reset":
        route["top_categories_on_low_confidence"] = 2
activate_config_payload("classification_routes", route_payload, "route")
route_detail = request("/admin/scenarios/password_reset")
assert route_detail["route"]["top_categories_on_low_confidence"] == 2, route_detail

policy_active = request("/admin/config/active/orchestrator_policy")
policy_payload = copy.deepcopy(policy_active["payload"])
policy_payload["confidence_defaults"]["min_extraction_confidence"] = 0.72
for policy in policy_payload["policies"]:
    if policy["policy_id"] == "policy.password_reset":
        policy["max_iterations"] = 7
activate_config_payload("orchestrator_policy", policy_payload, "policy")
policy_detail = request("/admin/scenarios/password_reset")
assert policy_detail["orchestrator_policy"]["max_iterations"] == 7, policy_detail
assert policy_detail["system_confidence_defaults"]["min_extraction_confidence"] == 0.72, policy_detail

bad_policy_payload = request("/admin/config/active/orchestrator_policy")["payload"]
bad_policy_payload = copy.deepcopy(bad_policy_payload)
bad_policy_payload["confidence_defaults"]["operator_handoff_confidence"] = 0.8
bad_policy_payload["confidence_defaults"]["clarification_confidence"] = 0.7
bad_draft = request(
    "/admin/config/drafts",
    {
        "domain": "orchestrator_policy",
        "payload": bad_policy_payload,
        "operator_id": "admin-stage12_5-bad-confidence",
    },
)
bad_validated = request(
    f"/admin/config/drafts/{bad_draft['draft_id']}/validate",
    {"operator_id": "admin-stage12_5-bad-confidence"},
)
assert bad_validated["validation"]["status"] == "invalid", bad_validated
assert any("operator_handoff_confidence" in error for error in bad_validated["validation"]["errors"]), bad_validated

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

channels_active = request("/admin/config/active/interaction_channels")
channels_payload = copy.deepcopy(channels_active["payload"])
for channel in channels_payload["channels"]:
    if channel["channel_id"] == "debug":
        channel["waiting_policy"]["client_wait_auto_close_after_hours"] = 48
activate_config_payload("interaction_channels", channels_payload, "channel-waiting")
escalation_detail = request("/admin/scenarios/password_reset")
assert escalation_detail["interaction_channel"]["waiting_policy"]["client_wait_auto_close_after_hours"] == 48, escalation_detail
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

tools_active = request("/admin/config/active/tools")

visible_contract_payload = copy.deepcopy(tools_active["payload"])
search_tool = next(tool for tool in visible_contract_payload["tools"] if tool["tool_name"] == "search_ad_users")
search_tool["parameters_schema"] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["login"],
    "properties": {
        "login": {"type": "string", "minLength": 1},
        "department": {"type": "string", "minLength": 1},
    },
}
search_tool["result_schema"] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["users"],
    "properties": {
        "users": {
            "type": "array",
            "items": {"type": "object", "additionalProperties": True},
        }
    },
}
for binding in search_tool["endpoint_bindings"]:
    if binding["operation_id"] == "search_ad_users":
        binding["parameter_mapping"] = {
            "login": "react:login",
            "department": "react:department",
        }
        binding["result_mapping"] = {"users": "users"}
visible_contract_draft = request(
    "/admin/config/drafts",
    {
        "domain": "tools",
        "payload": visible_contract_payload,
        "operator_id": "admin-stage12_5-visible-react-contract",
    },
)
visible_contract_validated = request(
    f"/admin/config/drafts/{visible_contract_draft['draft_id']}/validate",
    {"operator_id": "admin-stage12_5-visible-react-contract"},
)
assert visible_contract_validated["validation"]["status"] == "valid", visible_contract_validated

bad_tools_payload = copy.deepcopy(tools_active["payload"])
zabbix_tool = next(tool for tool in bad_tools_payload["tools"] if tool["tool_name"] == "check_zabbix_status")
mock_binding = next(binding for binding in zabbix_tool["endpoint_bindings"] if binding["endpoint_id"] == "mock")
mock_binding["result_mapping"].pop("message", None)
bad_tools_draft = request(
    "/admin/config/drafts",
    {
        "domain": "tools",
        "payload": bad_tools_payload,
        "operator_id": "admin-stage12_5-bad-result-mapping",
    },
)
bad_tools_validated = request(
    f"/admin/config/drafts/{bad_tools_draft['draft_id']}/validate",
    {"operator_id": "admin-stage12_5-bad-result-mapping"},
)
assert bad_tools_validated["validation"]["status"] == "invalid", bad_tools_validated
assert any("обязательное поле результата" in error and "message" in error for error in bad_tools_validated["validation"]["errors"]), bad_tools_validated

bad_broken_tool_payload = copy.deepcopy(tools_active["payload"])
broken_tool = next(tool for tool in bad_broken_tool_payload["tools"] if tool["tool_name"] == "check_zabbix_status")
broken_tool["contract_status"] = "broken"
bad_broken_tool_draft = request(
    "/admin/config/drafts",
    {
        "domain": "tools",
        "payload": bad_broken_tool_payload,
        "operator_id": "admin-stage12_5-broken-react-contract",
    },
)
bad_broken_tool_validated = request(
    f"/admin/config/drafts/{bad_broken_tool_draft['draft_id']}/validate",
    {"operator_id": "admin-stage12_5-broken-react-contract"},
)
assert bad_broken_tool_validated["validation"]["status"] == "invalid", bad_broken_tool_validated
assert any("contract_status=broken" in error for error in bad_broken_tool_validated["validation"]["errors"]), bad_broken_tool_validated

endpoints_active = request("/admin/config/active/integration_endpoints")
bad_endpoint_payload = copy.deepcopy(endpoints_active["payload"])
bad_endpoint_operation = next(endpoint for endpoint in bad_endpoint_payload["endpoints"] if endpoint["endpoint_id"] == "mock")["operations"]["check_zabbix_status"]
bad_endpoint_operation["mock_output"]["message"] = 123
bad_endpoint_draft = request(
    "/admin/config/drafts",
    {
        "domain": "integration_endpoints",
        "payload": bad_endpoint_payload,
        "operator_id": "admin-stage12_5-bad-response-schema",
    },
)
bad_endpoint_validated = request(
    f"/admin/config/drafts/{bad_endpoint_draft['draft_id']}/validate",
    {"operator_id": "admin-stage12_5-bad-response-schema"},
)
assert bad_endpoint_validated["validation"]["status"] == "invalid", bad_endpoint_validated
assert any("mock_output не соответствует response_schema" in error for error in bad_endpoint_validated["validation"]["errors"]), bad_endpoint_validated

bad_broken_endpoint_payload = copy.deepcopy(endpoints_active["payload"])
broken_endpoint_operation = next(endpoint for endpoint in bad_broken_endpoint_payload["endpoints"] if endpoint["endpoint_id"] == "mock")["operations"]["check_zabbix_status"]
broken_endpoint_operation["contract_status"] = "broken"
bad_broken_endpoint_draft = request(
    "/admin/config/drafts",
    {
        "domain": "integration_endpoints",
        "payload": bad_broken_endpoint_payload,
        "operator_id": "admin-stage12_5-broken-endpoint-contract",
    },
)
bad_broken_endpoint_validated = request(
    f"/admin/config/drafts/{bad_broken_endpoint_draft['draft_id']}/validate",
    {"operator_id": "admin-stage12_5-broken-endpoint-contract"},
)
assert bad_broken_endpoint_validated["validation"]["status"] == "invalid", bad_broken_endpoint_validated
assert any("contract_status=broken" in error for error in bad_broken_endpoint_validated["validation"]["errors"]), bad_broken_endpoint_validated
print("валидация контрактов ReAct-вызовов и endpoint-операций проверена")

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

audit = request("/admin/security/audit?limit=300")
actions = {event["action"] for event in audit["events"]}
assert "admin.scenarios.simulate" in actions, audit
print("аудит сценарного прогона проверен")

print("Smoke-проверка этапа 12.5 завершена.")
PY
