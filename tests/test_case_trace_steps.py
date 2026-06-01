from __future__ import annotations

import unittest

from apps.orchestrator.app.debug_runtime import DebugRuntime
from apps.orchestrator.app.integrations import IntegrationDispatcher


def detail_for_state(
    *,
    workflow_category: str = "terminal",
    workflow_state_id: str = "resolved",
    decision_type: str = "answer_proposed",
    waits: list[dict] | None = None,
    tool_results: list[dict] | None = None,
) -> dict:
    case = {
        "case_id": "case-test",
        "ticket_id": "ticket-test",
        "ticket_input": {
            "user": "ivanov",
            "service": "debug",
            "description": "Сбросьте пароль.",
            "priority": "p3",
        },
        "current_workflow_state": {
            "id": workflow_state_id,
            "category": workflow_category,
            "terminal": workflow_category in {"terminal", "handoff"},
        },
        "ai_decision": {
            "decision": {
                "type": decision_type,
            },
            "proposed_actions": [],
        },
        "analysis_snapshot": {
            "operator_message": "Обработка завершена.",
            "workflow_state": {
                "id": workflow_state_id,
                "category": workflow_category,
                "terminal": workflow_category in {"terminal", "handoff"},
            },
            "ai_decision": {
                "decision": {
                    "type": decision_type,
                }
            },
            "approval_requests": [],
        },
        "tool_trace": [],
        "tool_results": tool_results or [],
    }
    if tool_results:
        case["tool_trace"] = [
            {
                "invocation_id": item["invocation_id"],
                "tool_name": item["tool_name"],
                "endpoint_id": item["endpoint_id"],
                "operation_id": item["operation_id"],
                "status": item["status"],
                "policy_rule_id": item["policy_rule_id"],
            }
            for item in tool_results
        ]
    return {
        "case": case,
        "runs": [
            {
                "run_id": "run-test",
                "status": "completed",
                "current_step": "decision",
                "started_at": "2026-06-01T00:00:00Z",
                "completed_at": "2026-06-01T00:00:01Z",
                "extensions": {},
            }
        ],
        "tasks": [],
        "waits": waits or [],
        "outbox": [],
    }


class CaseTraceStepsTest(unittest.TestCase):
    def test_trace_parameter_redaction_masks_secret_sources_and_sensitive_names(self) -> None:
        redacted = IntegrationDispatcher._redact_trace_parameters(
            {
                "query": "Иванов Иван",
                "api_key": "open-secret",
                "manager_password": "hidden",
                "session": "hidden-too",
            },
            parameter_mapping={"query": "slot:user_login", "api_key": "secret:openai_api_key"},
        )

        self.assertEqual(redacted["query"], "Иванов Иван")
        self.assertEqual(redacted["api_key"], "параметр скрыт")
        self.assertEqual(redacted["manager_password"], "параметр скрыт")
        self.assertEqual(redacted["session"], "параметр скрыт")

    def test_success_case_has_five_steps_and_success_outcome(self) -> None:
        detail = detail_for_state()
        steps = DebugRuntime._build_case_trace_steps(detail, [])
        outcome = DebugRuntime._case_trace_agent_outcome(detail)

        self.assertEqual(len(steps), 5)
        self.assertEqual(steps[4]["status"], "success")
        self.assertEqual(outcome["label"], "Завершено автоматически")

    def test_client_wait_maps_to_question_to_customer(self) -> None:
        detail = detail_for_state(
            workflow_category="waiting",
            workflow_state_id="waiting_for_user",
            decision_type="clarification_needed",
            waits=[
                {
                    "wait_id": "wait-test",
                    "wait_type": "client_wait",
                    "status": "open",
                    "deadline_at": "2026-06-01T00:08:00Z",
                    "reason": "Нужен логин.",
                    "payload": {"question": "Уточните логин пользователя."},
                }
            ],
        )
        steps = DebugRuntime._build_case_trace_steps(detail, [])

        self.assertEqual(steps[0]["status"], "waiting")
        self.assertEqual(steps[4]["status"], "waiting")
        self.assertEqual(DebugRuntime._case_trace_agent_outcome(detail)["label"], "Вопрос клиенту")

    def test_handoff_maps_to_escalation_required(self) -> None:
        detail = detail_for_state(
            workflow_category="handoff",
            workflow_state_id="handoff_required",
            decision_type="escalation_needed",
        )

        self.assertEqual(DebugRuntime._case_trace_agent_outcome(detail)["label"], "Требуется эскалация")

    def test_tool_result_is_rendered_in_step_four(self) -> None:
        detail = detail_for_state(
            tool_results=[
                {
                    "invocation_id": "inv-test",
                    "action_id": "act-test",
                    "tool_name": "find_user",
                    "endpoint_id": "mock",
                    "adapter_type": "mock",
                    "operation_id": "get_user_login",
                    "status": "success",
                    "policy_rule_id": "auto",
                    "duration_ms": 10,
                    "attempts": 1,
                    "output": {"user_login": "ivanov"},
                    "extensions": {
                        "trace": {
                            "react_parameters": {
                                "target_name": "Иванов Иван",
                            },
                            "operation_parameters": {
                                "query": "Иванов Иван",
                                "token": "параметр скрыт",
                            },
                            "parameter_mapping": {
                                "query": "parameters.target_name",
                                "token": "secret:mock_token",
                            },
                        }
                    },
                }
            ],
        )
        steps = DebugRuntime._build_case_trace_steps(detail, [])
        tool_table = steps[3]["tables"][0]

        self.assertEqual(steps[3]["status"], "success")
        self.assertEqual(tool_table["rows"][0][0], "find_user")
        self.assertEqual(tool_table["rows"][0][2], "get_user_login")
        self.assertIn("Иванов Иван", tool_table["rows"][0][4])
        self.assertIn("query", tool_table["rows"][0][5])
        self.assertIn("параметр скрыт", tool_table["rows"][0][5])


if __name__ == "__main__":
    unittest.main()
