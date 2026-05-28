#!/usr/bin/env bash
set -euo pipefail

if [ -x ".venv/bin/python" ]; then
  PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

HOST="${ORCHESTRATOR_HOST:-127.0.0.1}"
PORT="${ORCHESTRATOR_PORT:-18090}"
BASE_URL="http://${HOST}:${PORT}"
LOG_FILE="${STAGE6_LOG_FILE:-/tmp/servicedesk-stage6-orchestrator.log}"
STATE_DB="${STAGE6_STATE_DB:-/tmp/servicedesk-stage6-orchestrator-${PORT}-$$.sqlite}"

ORCHESTRATOR_STATE_DB="${STATE_DB}" \
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
        raise SystemExit(
            f"{path}: expected HTTP {expected_status}, got {status}: {parsed}"
        )
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
    "ticket_id": "stage6-approve-ticket",
    "user": "ivan",
    "service": "billing-worker",
    "description": "restart service through runbook",
    "priority": "p3",
    "scenario": "runbook",
}
analysis = request("/tickets/analyze", ticket)
assert analysis["workflow_state"]["id"] == "pending_approval", analysis
assert len(analysis["approval_requests"]) == 1, analysis
approval = analysis["approval_requests"][0]
approval_id = approval["approval_id"]
assert approval["gate_type"] == "operator_approval", approval
assert approval["status"] == "pending", approval
assert analysis["tool_results"][0]["status"] == "pending_approval", analysis
assert analysis["tool_results"][0]["extensions"]["gate_id"] == approval_id, analysis
print("approval request ok: pending operator gate")

stored_gate = request(f"/approvals/{approval_id}")
assert stored_gate["gate_id"] == approval_id, stored_gate
assert stored_gate["status"] == "pending", stored_gate
assert stored_gate["action"]["parameters"]["runbook_code"] == "restart_service", stored_gate
print("approval lookup ok")

action = analysis["ai_decision"]["proposed_actions"][0]
policy_result = analysis["execution_policy_results"][0]
client_side_approval = request(
    "/tools/dispatch",
    {
        "ticket_id": analysis["ticket_id"],
        "operator_id": "operator-1",
        "action": action,
        "policy_result": policy_result,
        "approved_by_operator": True,
    },
    expected_status=400,
)
assert client_side_approval["detail"]["code"] == "approval_endpoint_required", client_side_approval
print("client-side approved dispatch blocked ok")

approved = request(
    f"/approvals/{approval_id}/decision",
    {
        "decision": "approve",
        "operator_id": "operator-1",
        "comment": "Smoke-проверка этапа 6: согласование.",
    },
)
assert approved["accepted"] is True, approved
assert approved["workflow_state"]["id"] == "action_execution_succeeded", approved
assert approved["gate"]["status"] == "succeeded", approved
assert approved["gate"]["decision"]["actor_id"] == "operator-1", approved
assert approved["tool_result"]["status"] == "success", approved
assert approved["tool_result"]["endpoint_id"] == "mock", approved
print("approval decision ok: mock runbook executed")

duplicate = request(
    f"/approvals/{approval_id}/decision",
    {
        "decision": "approve",
        "operator_id": "operator-1",
    },
    expected_status=409,
)
assert duplicate["detail"]["code"] == "approval_conflict", duplicate
print("duplicate approval blocked ok")

approvals = request(f"/tickets/{ticket['ticket_id']}/approvals")
assert len(approvals["approvals"]) == 1, approvals
assert approvals["approvals"][0]["status"] == "succeeded", approvals
print("ticket approval list ok")

reject_ticket = {
    "ticket_id": "stage6-reject-ticket",
    "user": "ivan",
    "service": "billing-worker",
    "description": "restart service through runbook",
    "priority": "p3",
    "scenario": "runbook",
}
reject_analysis = request("/tickets/analyze", reject_ticket)
reject_approval_id = reject_analysis["approval_requests"][0]["approval_id"]
rejected = request(
    f"/approvals/{reject_approval_id}/decision",
    {
        "decision": "reject",
        "operator_id": "operator-2",
        "comment": "Smoke-проверка этапа 6: отклонение.",
    },
)
assert rejected["accepted"] is True, rejected
assert rejected["workflow_state"]["id"] == "approval_rejected", rejected
assert rejected["gate"]["status"] == "rejected", rejected
assert "tool_result" not in rejected, rejected
print("approval rejection ok: dispatcher not invoked")

rejected_approve = request(
    f"/approvals/{reject_approval_id}/decision",
    {
        "decision": "approve",
        "operator_id": "operator-2",
    },
    expected_status=409,
)
assert rejected_approve["detail"]["code"] == "approval_conflict", rejected_approve
print("rejected approval cannot execute ok")

unknown = request("/approvals/gate-does-not-exist", expected_status=404)
assert unknown["detail"]["code"] == "approval_not_found", unknown
print("unknown approval ok")

invalid_decision = request(
    f"/approvals/{reject_approval_id}/decision",
    {
        "decision": "maybe",
        "operator_id": "operator-2",
    },
    expected_status=400,
)
assert invalid_decision["detail"]["contract_name"] == "action_gate_decision", invalid_decision
print("invalid approval decision ok")

print("Smoke-проверка этапа 6 завершена.")
PY
