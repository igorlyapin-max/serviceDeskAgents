#!/usr/bin/env bash
set -euo pipefail

if [ -x ".venv/bin/python" ]; then
  PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

HOST="${ORCHESTRATOR_HOST:-127.0.0.1}"
PORT="${ORCHESTRATOR_PORT:-18104}"
BASE_URL="http://${HOST}:${PORT}"
LOG_FILE="${STAGE12_LOG_FILE:-/tmp/servicedesk-stage12-orchestrator.log}"
STATE_DB="${STAGE12_STATE_DB:-/tmp/servicedesk-stage12-orchestrator-${PORT}-$$.sqlite}"
INDEX_PATH="${STAGE12_INDEX_PATH:-/tmp/servicedesk-stage12-knowledge-${PORT}-$$.json}"

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
admin_headers = {"X-ServiceDesk-Actor": "admin-1", "X-ServiceDesk-Session": "stage12:admin"}


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
assert "Консоль администратора" in html, html[:300]
assert "Вызовы и интеграции" in html, html[:300]
assert "data-view=\"integrations\"" in html, html[:300]
assert "data-view=\"reactCalls\"" in html, html[:300]
assert "data-view=\"operationBindings\"" in html, html[:300]
assert "/admin/static/app.js" in html, html[:300]
js = request("/admin/static/app.js", parse_json=False)
assert "renderDashboard" in js, js[:300]
assert "Перенести обратную связь в оценку" in js, js[:300]
assert "OpenAI API" in js, js[:300]
assert "vLLM CPU" in js, js[:300]
assert "Добавить подключение" in js, js[:300]
assert "Удалить подключение" in js, js[:300]
assert "endpoint-operation-remove" in js, js[:300]
assert "data-endpoint-operations-section" in js, js[:300]
assert "endpoint-operations-toggle" in js, js[:300]
assert "Нельзя удалить: сначала уберите связи" in js, js[:300]
assert "if (!card || target.disabled) return;" not in js, js[:300]
assert "Входные параметры операции" in js, js[:300]
assert "Поля ответа операции" in js, js[:300]
assert "Тестовый ответ mock" in js, js[:300]
assert "JSON контрольная точка" in js, js[:300]
assert "Применить JSON в форму" in js, js[:300]
assert "Входные параметры endpoint" in js, js[:300]
assert "Поля ответа, доступные ReAct" in js, js[:300]
assert "Создать и привязать ReAct-вызов ИИ" in js, js[:300]
assert "operation-binding-create-editor" in js, js[:300]
assert "Нельзя отвязать: сначала уберите связи" in js, js[:300]
assert "Ключ нового слота" in js, js[:300]
assert "Ключ нового выходного слота" in js, js[:300]
assert "Обогащение контекста" in js, js[:300]
assert "Добавить шаг обогащения" in js, js[:300]
assert "enrichment-step-table" in js, js[:300]
assert "Параметры шагов" in js, js[:300]
assert "Доступные ссылки на результаты" in js, js[:300]
assert "Имя сущности результата" not in js, js[:300]
assert "entity:&lt;сущность&gt;.&lt;поле&gt;" not in js, js[:300]
assert "система создаст черновик профиля" in js, js[:300]
assert "параметр скрыт" in js, js[:300]
assert "параметр не заполнен" in js, js[:300]
assert "Значение секрета" in js, js[:300]
assert "model-routing-editor" in js, js[:300]
css = request("/admin/static/styles.css", parse_json=False)
assert ".admin-shell" in css, css[:300]
assert ".sidebar" in css and "position: sticky" in css, css[:300]
assert ".topbar" in css and ".notice" in css and "top: 72px" in css, css[:300]
print("assets консоли администратора проверены")

session = request("/admin/security/session")
assert session["actor_id"] == "admin-1", session
dashboard = request("/admin/dashboard")
assert dashboard["schema_version"] == "1.0", dashboard
print("api панели обзора проверен")

prompts = request("/admin/prompts/catalog")
assert prompts["status"] == "config_ready", prompts
assert len(prompts["prompts"]) >= 5, prompts
models = request("/admin/models/config")
assert models["default_model_alias"], models
print("представления промптов и моделей проверены")

catalog = request("/admin/catalog")
assert catalog["tools"]["tools"], catalog
tools = request("/admin/catalog/tools")
endpoints = request("/admin/catalog/integration-endpoints")
workflow = request("/admin/catalog/workflow")
assert tools["tools"], tools
assert endpoints["endpoints"], endpoints
assert workflow["state_catalog"]["states"], workflow
print("представления каталогов проверены")

rebuild = request("/admin/knowledge/rebuild", {"operator_id": "admin-stage12"})
assert rebuild["status"] == "success", rebuild
chunks = request("/admin/knowledge/chunks?limit=2")
assert chunks["chunks"], chunks
retrieval = request(
    "/admin/knowledge/retrieval/test",
    {"query": "billing-worker restart runbook", "top_k": 2},
)
assert retrieval["status"] == "success", retrieval
print("административные действия базы знаний проверены")

feedback = request("/admin/feedback?limit=5")
assert feedback["schema_version"] == "1.0", feedback
evaluation_cases = request("/admin/evaluations/cases")
evaluation_runs = request("/admin/evaluations/runs")
assert evaluation_cases["schema_version"] == "1.0", evaluation_cases
assert evaluation_runs["schema_version"] == "1.0", evaluation_runs
print("представления контроля качества проверены")

audit = request("/admin/security/audit?limit=20")
summary = request("/admin/security/audit/summary")
assert audit["events"], audit
assert summary["total"] >= len(audit["events"]), summary
secrets = request("/admin/security/secret-references")
assert "secret_references" in secrets, secrets
print("представления аудита и безопасности проверены")

print("Smoke-проверка этапа 12 завершена.")
PY
