#!/usr/bin/env bash
set -euo pipefail

if [ -x ".venv/bin/python" ]; then
  PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

HOST="${ORCHESTRATOR_HOST:-127.0.0.1}"
PORT="${ORCHESTRATOR_PORT:-18092}"
BASE_URL="http://${HOST}:${PORT}"
LOG_FILE="${STAGE7_LOG_FILE:-/tmp/servicedesk-stage7-orchestrator.log}"
STATE_DB="${STAGE7_STATE_DB:-/tmp/servicedesk-stage7-orchestrator-${PORT}-$$.sqlite}"
INDEX_PATH="${STAGE7_INDEX_PATH:-/tmp/servicedesk-stage7-knowledge-${PORT}-$$.json}"

ORCHESTRATOR_STATE_DB="${STATE_DB}" \
KNOWLEDGE_INDEX_PATH="${INDEX_PATH}" \
INTEGRATION_ENDPOINT_PROFILE="${INTEGRATION_ENDPOINT_PROFILE:-mock}" \
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


def request(path, payload=None, expected_status=200):
    data = None
    method = "GET"
    headers = {}
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

    parsed = json.loads(body) if body else {}
    if status != expected_status:
        raise SystemExit(f"{path}: expected HTTP {expected_status}, got {status}: {parsed}")
    return parsed


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

ticket = {
    "ticket_id": "stage7-ticket",
    "user": "ivan",
    "service": "billing-worker",
    "environment": "test",
    "description": "restart billing-worker using the runbook",
    "priority": "p3",
    "scenario": "runbook",
}

before = request("/tickets/analyze", ticket)
assert before["rag_trace"]["status"] == "unavailable", before
assert before["ai_decision"]["citations"] == [], before
print("rag graceful unavailable ok")

rebuild = request(
    "/knowledge/rebuild",
    {
        "operator_id": "operator-stage7",
    },
)
assert rebuild["status"] == "success", rebuild
manifest = rebuild["index_manifest"]
assert manifest["requested_by_operator"] == "operator-stage7", manifest
assert manifest["document_count"] >= 1, manifest
assert manifest["chunk_count"] >= 1, manifest
source_status = {source["source_id"]: source["status"] for source in manifest["sources"]}
assert source_status["local.knowledge"] == "success", source_status
assert source_status["corp.wiki"] == "skipped", source_status
print("operator knowledge rebuild ok")

after = request("/tickets/analyze", {**ticket, "ticket_id": "stage7-ticket-after"})
assert after["rag_trace"]["status"] == "success", after
assert after["rag_trace"]["match_count"] >= 1, after
citations = after["ai_decision"]["citations"]
assert citations, after
assert citations[0]["source_id"] == "local.knowledge", citations
assert "Ранбук перезапуска Billing Worker" in citations[0]["title"], citations
assert "Связанная статья базы знаний: Ранбук перезапуска Billing Worker." in after["operator_message"], after
assert after["workflow_state"]["id"] == "pending_approval", after
print("rag citations in analyze ok")

print("Smoke-проверка этапа 7 завершена.")
PY
