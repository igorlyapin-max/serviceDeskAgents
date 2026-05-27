#!/usr/bin/env bash
set -euo pipefail

if [ -x ".venv/bin/python" ]; then
  PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

HOST="${ORCHESTRATOR_HOST:-127.0.0.1}"
PORT="${ORCHESTRATOR_PORT:-18098}"
BASE_URL="http://${HOST}:${PORT}"
LOG_FILE="${STAGE10_LOG_FILE:-/tmp/servicedesk-stage10-orchestrator.log}"
STATE_DB="${STAGE10_STATE_DB:-/tmp/servicedesk-stage10-orchestrator-${PORT}-$$.sqlite}"
INDEX_PATH="${STAGE10_INDEX_PATH:-/tmp/servicedesk-stage10-knowledge-${PORT}-$$.json}"

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

html = request("/operator", parse_json=False)
assert "caseStatus" in html, html[:300]
js = request("/operator/static/app.js", parse_json=False)
assert "refreshCase" in js, js[:300]
print("operator case UI assets ok")

request("/knowledge/rebuild", {"operator_id": "operator-stage10"})
ticket_input = {
    "ticket_id": "stage10-ticket",
    "user": "ivan",
    "service": "billing-worker",
    "environment": "test",
    "description": "restart billing-worker using the runbook",
    "priority": "p3",
    "scenario": "runbook",
}
created = request("/cases", ticket_input)
analysis = created["analysis"]
case = created["case"]
case_id = analysis["case_id"]
assert case_id.startswith("case-"), created
assert case["case_id"] == case_id, case
assert case["ticket_id"] == "stage10-ticket", case
assert case["current_workflow_state"]["id"] == "pending_approval", case
assert case["action_gate_ids"] == [analysis["approval_requests"][0]["gate_id"]], case
assert case["tool_results"][0]["status"] == "pending_approval", case
print("case create/analyze ok")

loaded_case = request(f"/cases/{case_id}")
assert loaded_case["case_id"] == case_id, loaded_case
timeline = request(f"/cases/{case_id}/timeline")
event_types = [event["event_type"] for event in timeline["events"]]
for expected in [
    "case_created",
    "analysis_completed",
    "action_gate_created",
    "tool_result_recorded",
]:
    assert expected in event_types, timeline
print("case read and initial timeline ok")

mismatch = request(
    "/integrations/callbacks/not-the-endpoint",
    {
        "schema_version": "1.0",
        "case_id": case_id,
        "ticket_id": analysis["ticket_id"],
        "invocation_id": analysis["tool_results"][0]["invocation_id"],
        "action_id": analysis["tool_results"][0]["action_id"],
        "tool_name": analysis["tool_results"][0]["tool_name"],
        "endpoint_id": analysis["tool_results"][0]["endpoint_id"],
        "adapter_type": analysis["tool_results"][0]["adapter_type"],
        "operation_id": analysis["tool_results"][0]["operation_id"],
        "status": "success",
        "policy_rule_id": analysis["tool_results"][0]["policy_rule_id"],
        "output": {
            "runbook_status": "accepted",
            "message": "Should be rejected before callback handling.",
        },
    },
    expected_status=400,
)
assert mismatch["detail"]["code"] == "endpoint_id_mismatch", mismatch
print("callback endpoint mismatch rejected ok")

approval_id = analysis["approval_requests"][0]["approval_id"]
approval = request(
    f"/approvals/{approval_id}/decision",
    {
        "decision": "approve",
        "operator_id": "operator-stage10",
        "comment": "Smoke-проверка этапа 10: согласование перед callback.",
    },
)
assert approval["tool_result"]["status"] == "success", approval
case_after_approval = request(f"/cases/{case_id}")
assert case_after_approval["current_workflow_state"]["id"] == "action_execution_succeeded", case_after_approval
assert case_after_approval["outcome"]["workflow_state_id"] == "action_execution_succeeded", case_after_approval
print("approval updates case ok")

approved_tool_result = approval["tool_result"]
callback = request(
    f"/integrations/callbacks/{approved_tool_result['endpoint_id']}",
    {
        "schema_version": "1.0",
        "case_id": case_id,
        "ticket_id": analysis["ticket_id"],
        "invocation_id": approved_tool_result["invocation_id"],
        "action_id": approved_tool_result["action_id"],
        "tool_name": approved_tool_result["tool_name"],
        "endpoint_id": approved_tool_result["endpoint_id"],
        "adapter_type": approved_tool_result["adapter_type"],
        "operation_id": approved_tool_result["operation_id"],
        "status": "success",
        "policy_rule_id": approved_tool_result["policy_rule_id"],
        "duration_ms": 120,
        "attempts": 1,
        "output": {
            "runbook_status": "completed",
            "message": "Async-style callback completed.",
        },
        "extensions": {
            "smoke": "stage10"
        },
    },
)
assert callback["accepted"] is True, callback
assert callback["case"]["case_id"] == case_id, callback
assert callback["tool_result"]["output"]["runbook_status"] == "completed", callback
print("integration callback updates case ok")

feedback = request(
    "/feedback",
    {
        "schema_version": "1.0",
        "ticket_id": analysis["ticket_id"],
        "operator_id": "operator-stage10",
        "rating": "correct",
        "ticket_input": ticket_input,
        "analysis_snapshot": analysis,
        "approval_snapshot": approval,
        "operator_note": "Smoke-проверка этапа 10: обратная связь по кейсу.",
        "extensions": {
            "case_id": case_id,
            "smoke": "stage10"
        },
    },
)
case_after_feedback = request(f"/cases/{case_id}")
assert feedback["feedback_id"] in case_after_feedback["feedback_ids"], case_after_feedback
timeline = request(f"/cases/{case_id}/timeline")
event_types = [event["event_type"] for event in timeline["events"]]
for expected in [
    "approval_decisioned",
    "integration_callback_received",
    "feedback_recorded",
]:
    assert expected in event_types, timeline
print("feedback and final timeline ok")

print("Smoke-проверка этапа 10 завершена.")
PY
