#!/usr/bin/env bash
set -euo pipefail

if [ -x ".venv/bin/python" ]; then
  PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

HOST="${ORCHESTRATOR_HOST:-127.0.0.1}"
PORT="${ORCHESTRATOR_PORT:-18094}"
BASE_URL="http://${HOST}:${PORT}"
LOG_FILE="${STAGE8_LOG_FILE:-/tmp/servicedesk-stage8-orchestrator.log}"
STATE_DB="${STAGE8_STATE_DB:-/tmp/servicedesk-stage8-orchestrator-${PORT}-$$.sqlite}"
INDEX_PATH="${STAGE8_INDEX_PATH:-/tmp/servicedesk-stage8-knowledge-${PORT}-$$.json}"

ORCHESTRATOR_STATE_DB="${STATE_DB}" \
KNOWLEDGE_INDEX_PATH="${INDEX_PATH}" \
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


def request(path, payload=None, expected_status=200, parse_json=True, headers_extra=None):
    data = None
    method = "GET"
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        method = "POST"
        headers["Content-Type"] = "application/json"
    if headers_extra:
        headers.update(headers_extra)
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
    return json.loads(body) if parse_json else body


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

html = request("/operator", parse_json=False)
assert "Оператор ServiceDesk" in html, html[:200]
assert "Пять шагов оркестратора" in html, html[:300]
assert "/operator/static/app.js" in html, html[:200]
print("operator html ok")

js = request("/operator/static/app.js", parse_json=False)
css = request("/operator/static/styles.css", parse_json=False)
assert "analyzeTicket" in js, js[:200]
assert "/operator/scenarios" in js, js[:300]
assert ".workspace" in css, css[:200]
print("operator assets ok")

operator_headers = {"X-ServiceDesk-Actor": "operator-1", "X-ServiceDesk-Session": "stage8:operator"}

scenarios = request("/operator/scenarios", headers_extra=operator_headers)
assert scenarios["scenario_count"] >= 6, scenarios
detail = request("/operator/scenarios/password_reset", headers_extra=operator_headers)
assert detail["slot_schema"]["required_slots"] == ["user_login", "account_type"], detail
simulation = request(
    "/operator/scenarios/password_reset/simulate",
    {
        "operator_id": "operator-stage8",
        "text": "Пользователь не может войти, нужен сброс пароля",
        "provided_slots": {"user_login": "ivan", "account_type": "domain"},
    },
    headers_extra=operator_headers,
)
assert simulation["final_decision"] == "ready_for_react", simulation
assert not simulation["missing_slots"], simulation
print("operator scenario API ok")

status_before = request("/knowledge/status", headers_extra=operator_headers)
assert status_before["status"] == "unavailable", status_before
print("knowledge status unavailable ok")

rebuild = request("/knowledge/rebuild", {"operator_id": "operator-stage8"}, headers_extra=operator_headers)
assert rebuild["status"] == "success", rebuild
assert rebuild["index_manifest"]["requested_by_operator"] == "operator-stage8", rebuild
print("knowledge rebuild endpoint ok")

ticket = {
    "ticket_id": "stage8-ticket",
    "user": "ivan",
    "service": "billing-worker",
    "description": "restart billing-worker using the runbook",
    "priority": "p3",
    "scenario": "runbook",
}
analysis = request("/tickets/analyze", ticket)
assert analysis["workflow_state"]["id"] == "pending_approval", analysis
assert analysis["rag_trace"]["status"] == "success", analysis
assert analysis["ai_decision"]["citations"], analysis
approval_id = analysis["approval_requests"][0]["approval_id"]
print("operator analyze API ok")

approved = request(
    f"/approvals/{approval_id}/decision",
    {
        "decision": "approve",
        "operator_id": "operator-stage8",
        "comment": "Smoke-проверка UI этапа 8.",
    },
)
assert approved["workflow_state"]["id"] == "action_execution_succeeded", approved
assert approved["tool_result"]["status"] == "success", approved
print("operator approval API ok")

print("Smoke-проверка этапа 8 завершена.")
PY
