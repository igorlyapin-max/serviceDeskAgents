#!/usr/bin/env bash
set -euo pipefail

if [ -x ".venv/bin/python" ]; then
  PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

HOST="${ORCHESTRATOR_HOST:-127.0.0.1}"
PORT="${ORCHESTRATOR_PORT:-18096}"
BASE_URL="http://${HOST}:${PORT}"
LOG_FILE="${STAGE9_LOG_FILE:-/tmp/servicedesk-stage9-orchestrator.log}"
STATE_DB="${STAGE9_STATE_DB:-/tmp/servicedesk-stage9-orchestrator-${PORT}-$$.sqlite}"
INDEX_PATH="${STAGE9_INDEX_PATH:-/tmp/servicedesk-stage9-knowledge-${PORT}-$$.json}"

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


def request(path, payload=None, expected_status=200, parse_json=True):
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

request("/knowledge/rebuild", {"operator_id": "operator-stage9"})
ticket_input = {
    "ticket_id": "stage9-ticket",
    "user": "ivan",
    "service": "billing-worker",
    "environment": "test",
    "description": "restart billing-worker using the runbook",
    "priority": "p3",
    "scenario": "runbook",
}
analysis = request("/tickets/analyze", ticket_input)
assert analysis["workflow_state"]["id"] == "pending_approval", analysis
approval_id = analysis["approval_requests"][0]["approval_id"]
approval = request(
    f"/approvals/{approval_id}/decision",
    {
        "decision": "approve",
        "operator_id": "operator-stage9",
        "comment": "Smoke-проверка этапа 9: согласование перед обратной связью.",
    },
)
assert approval["tool_result"]["status"] == "success", approval
print("stage9 analyze and approval ok")

invalid_feedback = request(
    "/feedback",
    {
        "schema_version": "1.0",
        "ticket_id": analysis["ticket_id"],
        "operator_id": "operator-stage9",
        "rating": "edited",
        "ticket_input": ticket_input,
        "analysis_snapshot": analysis,
    },
    expected_status=400,
)
assert invalid_feedback["detail"]["contract_name"] == "feedback_request", invalid_feedback
print("invalid edited feedback ok")

feedback = request(
    "/feedback",
    {
        "schema_version": "1.0",
        "ticket_id": analysis["ticket_id"],
        "operator_id": "operator-stage9",
        "rating": "edited",
        "ticket_input": ticket_input,
        "analysis_snapshot": analysis,
        "approval_snapshot": approval,
        "operator_note": "Runbook proposal was useful; wording was adjusted.",
        "corrected_response": "Restart accepted for billing-worker in test. Monitor service health after execution.",
        "extensions": {
            "smoke": "stage9"
        },
    },
)
assert feedback["feedback_id"].startswith("fb-"), feedback
assert feedback["rating"] == "edited", feedback
assert feedback["analysis_snapshot"]["ticket_id"] == analysis["ticket_id"], feedback
print("feedback save ok")

feedback_list = request(f"/tickets/{analysis['ticket_id']}/feedback")
assert len(feedback_list["feedback"]) == 1, feedback_list
assert feedback_list["feedback"][0]["feedback_id"] == feedback["feedback_id"], feedback_list
print("ticket feedback list ok")

exported = request("/feedback/export", parse_json=False)
lines = [line for line in exported.splitlines() if line.strip()]
assert len(lines) == 1, exported
case = json.loads(lines[0])
assert case["source_feedback_id"] == feedback["feedback_id"], case
assert case["expected"]["rating"] == "edited", case
assert case["ticket_input"]["service"] == "billing-worker", case
print("feedback export jsonl ok")

print("Smoke-проверка этапа 9 завершена.")
PY
