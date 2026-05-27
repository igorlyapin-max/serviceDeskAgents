#!/usr/bin/env bash
set -euo pipefail

if [ -x ".venv/bin/python" ]; then
  PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

HOST="${ORCHESTRATOR_HOST:-127.0.0.1}"
PORT="${ORCHESTRATOR_PORT:-18089}"
BASE_URL="http://${HOST}:${PORT}"
LOG_FILE="${STAGE4_LOG_FILE:-/tmp/servicedesk-stage4-orchestrator.log}"

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


def request(path, payload=None):
    data = None
    method = "GET"
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        method = "POST"
        headers["Content-Type"] = "application/json"
    req = Request(f"{base_url}{path}", data=data, headers=headers, method=method)
    with urlopen(req, timeout=5) as response:
        body = response.read().decode("utf-8")
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

ticket = {
    "user": "ivan",
    "service": "billing-worker",
    "environment": "test",
    "description": "restart service through runbook",
    "priority": "p3",
    "scenario": "runbook",
}
analysis = request("/tickets/analyze", ticket)
assert analysis["workflow_state"]["id"] == "pending_approval", analysis
approval_request = analysis["approval_requests"][0]
approval_id = approval_request["approval_id"]
pending_result = analysis["tool_results"][0]
assert pending_result["status"] == "pending_approval", pending_result
assert pending_result["endpoint_id"] == "mock.runbooks", pending_result
assert pending_result["adapter_type"] == "mock", pending_result
assert pending_result["extensions"]["gate_id"] == approval_id, pending_result
print("analyze runbook ok: pending_approval through mock.runbooks")

action = analysis["ai_decision"]["proposed_actions"][0]
policy_result = analysis["execution_policy_results"][0]
dispatch_pending = request(
    "/tools/dispatch",
    {
        "ticket_id": analysis["ticket_id"],
        "action": action,
        "policy_result": policy_result,
        "approved_by_operator": False,
    },
)
assert dispatch_pending["tool_result"]["status"] == "pending_approval", dispatch_pending
print("dispatch gate ok: approval required")

dispatch_approved = request(
    f"/approvals/{approval_id}/decision",
    {
        "decision": "approve",
        "operator_id": "operator-1",
    },
)
approved_result = dispatch_approved["tool_result"]
assert approved_result["status"] == "success", approved_result
assert approved_result["endpoint_id"] == "mock.runbooks", approved_result
assert dispatch_approved["workflow_state"]["id"] == "action_execution_succeeded", dispatch_approved
print("approval approved ok: mock runbook success")

read_only_action = {
    "tool_name": "check_zabbix_status",
    "action_id": "check_billing_worker_test",
    "action_type": "read_only",
    "parameters": {
        "service_name": "billing-worker",
        "environment": "test",
    },
    "reason": "Smoke-проверка этапа 4: read-only диагностика.",
    "risk_level": "low",
    "expected_effect": "Return current service status without changing state.",
    "requires_state_change": False,
}
read_only_policy = {
    "schema_version": "1.0",
    "action_id": "check_billing_worker_test",
    "tool_name": "check_zabbix_status",
    "execution_mode": "dry_run",
    "allowed": True,
    "approval_required": False,
    "policy_rule_id": "tools.read_only.stage4.dry_run",
    "reason": "Smoke-проверка этапа 4: dry-run read-only диагностика.",
    "risk_level": "low",
}
read_only_dispatch = request(
    "/tools/dispatch",
    {
        "ticket_id": analysis["ticket_id"],
        "action": read_only_action,
        "policy_result": read_only_policy,
    },
)
read_only_result = read_only_dispatch["tool_result"]
assert read_only_result["status"] == "dry_run_completed", read_only_result
assert read_only_result["endpoint_id"] == "mock.diagnostics", read_only_result
print("dispatch read-only ok: dry_run_completed through mock.diagnostics")

print("Smoke-проверка этапа 4 завершена.")
PY
