#!/usr/bin/env bash
set -euo pipefail

if [ -x ".venv/bin/python" ]; then
  PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

"${PYTHON_BIN}" - <<'PY'
import os

from apps.orchestrator.app.contracts import ContractRegistry, ContractValidationError
from apps.orchestrator.app.integrations import IntegrationDispatcher, ToolRegistry
from apps.orchestrator.app.workflow import ExecutionPolicy


contracts = ContractRegistry()
policy = ExecutionPolicy(contracts)


def action(tool_name, action_type, parameters, risk_level="low", requires_state_change=False):
    return {
        "tool_name": tool_name,
        "action_id": f"{tool_name}_stage5",
        "action_type": action_type,
        "parameters": parameters,
        "reason": f"Smoke-проверка этапа 5 для {tool_name}.",
        "risk_level": risk_level,
        "expected_effect": "Return a normalized tool result.",
        "requires_state_change": requires_state_change,
    }


def dispatch(endpoint_id, tool_action, policy_result=None, approved=False):
    local_contracts = ContractRegistry()
    tool = next(
        (
            item
            for item in local_contracts.tool_catalog["tools"]
            if item["tool_name"] == tool_action["tool_name"]
        ),
        None,
    )
    if tool:
        binding = next(
            (
                item
                for item in tool["endpoint_bindings"]
                if item["endpoint_id"] == endpoint_id
            ),
            None,
        )
        if binding:
            tool["endpoint_bindings"] = [binding]
    registry = ToolRegistry(local_contracts)
    dispatcher = IntegrationDispatcher(local_contracts, registry)
    effective_policy = policy_result or policy.evaluate(tool_action)
    invocation = registry.build_invocation(
        tool_action,
        effective_policy,
        ticket_id="stage5-smoke",
        approved_by_operator=approved,
        operator_id="operator-1" if approved else None,
    )
    return dispatcher.dispatch(invocation)


def expect_contract_error(label, func):
    try:
        func()
    except ContractValidationError:
        print(f"{label} ok")
        return
    raise SystemExit(f"{label}: expected ContractValidationError")


read_only_cases = [
    action(
        "check_zabbix_status",
        "read_only",
        {"target_ref": "billing-worker"},
    ),
    action(
        "query_cmdb_object",
        "read_only",
        {"object_ref": "billing-worker"},
    ),
    action(
        "get_service_owner",
        "read_only",
        {"target_ref": "billing-worker"},
    ),
    action(
        "search_known_incidents",
        "read_only",
        {"query": "billing worker lag"},
    ),
]

for tool_action in read_only_cases:
    result = dispatch("mock", tool_action)
    if result["status"] != "dry_run_completed":
        raise SystemExit(f"{tool_action['tool_name']}: expected dry_run_completed, got {result}")
    if result["attempts"] != 1 or result["duration_ms"] < 0:
        raise SystemExit(f"{tool_action['tool_name']}: trace fields missing: {result}")
    print(f"{tool_action['tool_name']} ok: {result['status']}")

runbook_action = action(
    "start_systemcenter_runbook",
    "action",
    {
        "runbook_code": "restart_service",
        "app_name": "billing-worker",
    },
    risk_level="medium",
    requires_state_change=True,
)
runbook_policy = policy.evaluate(runbook_action)
pending_result = dispatch("mock", runbook_action, runbook_policy, approved=False)
if pending_result["status"] != "pending_approval":
    raise SystemExit(f"runbook approval gate failed: {pending_result}")
print("runbook approval gate ok")

approved_result = dispatch("mock", runbook_action, runbook_policy, approved=True)
if approved_result["status"] != "success":
    raise SystemExit(f"approved runbook dispatch failed: {approved_result}")
print("approved runbook mock dispatch ok")

blocked_policy = {
    "schema_version": "1.0",
    "action_id": "check_zabbix_status_stage5",
    "tool_name": "check_zabbix_status",
    "execution_mode": "blocked",
    "allowed": False,
    "approval_required": False,
    "policy_rule_id": "stage5.test.blocked",
    "reason": "Smoke-проверка этапа 5: blocked-policy.",
    "risk_level": "low",
}
blocked_result = dispatch("mock", read_only_cases[0], blocked_policy)
if blocked_result["status"] != "blocked":
    raise SystemExit(f"blocked policy failed: {blocked_result}")
print("blocked policy ok")

disabled_result = dispatch("direct.zabbix.disabled", read_only_cases[0])
if disabled_result["status"] != "error" or disabled_result["error"]["code"] != "endpoint_disabled":
    raise SystemExit(f"disabled endpoint failed: {disabled_result}")
print("disabled endpoint ok")

queue_action = action(
    "search_known_incidents",
    "read_only",
    {"query": "billing worker lag"},
)
unsupported_result = dispatch("queue.known_incidents", queue_action)
if unsupported_result["status"] != "error" or unsupported_result["error"]["code"] != "adapter_not_supported":
    raise SystemExit(f"unsupported adapter failed: {unsupported_result}")
print("unsupported adapter ok")

expect_contract_error(
    "missing parameter",
    lambda: dispatch(
        "mock",
        action("check_zabbix_status", "read_only", {}),
    ),
)

expect_contract_error(
    "unknown tool",
    lambda: dispatch(
        "mock",
        action("restart_everything", "action", {"target_ref": "billing-worker"}, requires_state_change=True),
    ),
)

def dispatch_with_missing_operation_mapping():
    local_contracts = ContractRegistry()
    tool = next(item for item in local_contracts.tool_catalog["tools"] if item["tool_name"] == "start_systemcenter_runbook")
    binding = next(item for item in tool["endpoint_bindings"] if item["endpoint_id"] == "mock")
    binding["parameter_mapping"].pop("runbook_code", None)
    tool["endpoint_bindings"] = [binding]
    registry = ToolRegistry(local_contracts)
    dispatcher = IntegrationDispatcher(local_contracts, registry)
    invocation = registry.build_invocation(
        runbook_action,
        runbook_policy,
        ticket_id="stage5-smoke",
        approved_by_operator=True,
        operator_id="operator-1",
    )
    return dispatcher.dispatch(invocation)


expect_contract_error(
    "missing operation parameter mapping",
    dispatch_with_missing_operation_mapping,
)

previous_token = os.environ.pop("N8N_WEBHOOK_TOKEN", None)
try:
    n8n_result = dispatch("n8n", runbook_action, runbook_policy, approved=True)
finally:
    if previous_token is not None:
        os.environ["N8N_WEBHOOK_TOKEN"] = previous_token
if n8n_result["status"] != "error" or n8n_result["error"]["code"] != "auth_token_missing":
    raise SystemExit(f"n8n missing token failed: {n8n_result}")
print("n8n missing token ok")

print("Smoke-проверка этапа 5 завершена.")
PY
