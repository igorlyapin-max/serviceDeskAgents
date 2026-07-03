from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from apps.orchestrator.app.action_gates import ActionGateStore
from apps.orchestrator.app.cases import CaseStore
from apps.orchestrator.app.config_registry import (
    ConfigStore,
    new_version_id,
    normalize_simulation_options,
    utc_now,
)
from apps.orchestrator.app.contracts import ContractRegistry
from apps.orchestrator.app.integrations import IntegrationDispatcher
from apps.orchestrator.app.workflow import TicketWorkflow


class FakeDispatcher:
    def __init__(self) -> None:
        self.invocations: list[dict] = []

    def dispatch(self, invocation: dict) -> dict:
        self.invocations.append(invocation)
        return {
            "schema_version": "1.0",
            "invocation_id": invocation["invocation_id"],
            "action_id": invocation["action_id"],
            "tool_name": invocation["tool_name"],
            "endpoint_id": invocation["endpoint_id"],
            "adapter_type": invocation["adapter_type"],
            "operation_id": invocation["operation_id"],
            "status": "success",
            "policy_rule_id": invocation["policy_rule_id"],
            "duration_ms": 1,
            "attempts": 1,
            "extensions": copy.deepcopy(invocation.get("extensions", {})),
            "output": {
                "runbook_status": "accepted",
                "message": "n8n принял запуск ранбука.",
            },
        }


class OperatorFullDebugTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "state.sqlite"
        self.contracts = ContractRegistry()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def workflow(self) -> TicketWorkflow:
        return TicketWorkflow(
            self.contracts,
            action_gate_store=ActionGateStore(self.contracts, db_path=self.db_path),
            case_store=CaseStore(self.contracts, db_path=self.db_path),
        )

    def force_active_payload(self, store: ConfigStore, domain: str, payload: dict) -> None:
        activated_at = utc_now()
        version = {
            "schema_version": "1.0",
            "version_id": new_version_id(),
            "domain": domain,
            "payload": copy.deepcopy(payload),
            "source_draft_id": "test-force-active",
            "activated_by": "test",
            "activated_at": activated_at,
            "validation": {"schema_version": "1.0", "status": "forced"},
            "regression": {"schema_version": "1.0", "status": "skipped"},
        }
        with store._connect() as connection:
            connection.execute(
                """
                insert into config_versions (
                    version_id,
                    domain,
                    version_json,
                    source_draft_id,
                    activated_by,
                    activated_at
                )
                values (?, ?, ?, ?, ?, ?)
                """,
                (
                    version["version_id"],
                    domain,
                    store._to_json(version),
                    version["source_draft_id"],
                    version["activated_by"],
                    version["activated_at"],
                ),
            )
            connection.execute(
                """
                insert or replace into config_active (
                    domain,
                    version_id,
                    activated_at
                )
                values (?, ?, ?)
                """,
                (domain, version["version_id"], activated_at),
            )

    def configure_n8n_operation_without_mock_output(self, store: ConfigStore) -> None:
        self.force_active_payload(
            store,
            "tools",
            {
                "schema_version": "1.0",
                "tools": [
                    {
                        "tool_name": "n8n_wait_for_email_by_ticket",
                        "display_name": "Дождаться письма",
                        "description": "Тестовая n8n операция без mock_output.",
                        "action_type": "action",
                        "endpoint_bindings": [
                            {
                                "endpoint_id": "n8n",
                                "operation_id": "wait_for_email_by_ticket",
                                "parameter_mapping": {
                                    "ticket_number": "react:ticket_number",
                                },
                                "result_mapping": {"ticket_number": "ticket_number"},
                            }
                        ],
                        "parameters_schema": {
                            "type": "object",
                            "required": ["ticket_number"],
                            "properties": {"ticket_number": {"type": "string"}},
                            "additionalProperties": True,
                        },
                        "result_schema": {
                            "type": "object",
                            "required": ["ticket_number"],
                            "properties": {"ticket_number": {"type": "string"}},
                            "additionalProperties": True,
                        },
                        "policy": {
                            "default_timeout_seconds": 30,
                            "retry": {"max_attempts": 1, "backoff_seconds": 0},
                            "approval_required_hint": True,
                            "auto_execution_eligible": False,
                            "max_risk_level": "medium",
                        },
                        "contract_version": "1.0",
                        "contract_status": "valid",
                    }
                ],
            },
        )
        self.force_active_payload(
            store,
            "integration_endpoints",
            {
                "schema_version": "1.0",
                "endpoints": [
                    {
                        "endpoint_id": "n8n",
                        "display_name": "n8n",
                        "adapter_type": "n8n_webhook",
                        "enabled": True,
                        "auth": {"type": "none"},
                        "operations": {
                            "wait_for_email_by_ticket": {
                                "operation_id": "wait_for_email_by_ticket",
                                "display_name": "Дождаться письма",
                                "method": "POST",
                                "path": "/webhook/wait",
                                "timeout_seconds": 30,
                                "contract_status": "valid",
                                "request_schema": {
                                    "type": "object",
                                    "required": ["ticket_number"],
                                    "properties": {"ticket_number": {"type": "string"}},
                                    "additionalProperties": True,
                                },
                                "response_schema": {
                                    "type": "object",
                                    "required": ["ticket_number"],
                                    "properties": {"ticket_number": {"type": "string"}},
                                    "additionalProperties": True,
                                },
                            }
                        },
                    }
                ],
            },
        )

    @staticmethod
    def resolution_profile() -> dict:
        return {
            "profile_id": "profile.test.wait_email",
            "display_name": "Дождаться письма",
            "slot_schema_id": "slot.test",
            "target_slot_id": "incident_number",
            "use_llm_after_steps": False,
            "max_attempts": 1,
            "enrichment_steps": [
                {
                    "step_id": "step1",
                    "step_name": "Дождаться письма",
                    "react_call": "n8n_wait_for_email_by_ticket",
                    "endpoint_id": "n8n",
                    "operation_id": "wait_for_email_by_ticket",
                    "parameter_mapping": {"ticket_number": "constant:T-1"},
                    "completion_policy": {"mode": "sync", "max_wait_seconds": 0, "timeout_action": "resume_agent"},
                }
            ],
            "output_slots_order": [
                {
                    "slot_id": "incident_number",
                    "order": 1,
                    "required_for_success": True,
                    "source_hint": "ticket_number",
                    "fallback": "operator_handoff",
                }
            ],
            "llm_resolution_script": {},
            "human_resolution_policy": {
                "action": "escalate_operator",
                "message_template": "Передать оператору.",
            },
        }

    @staticmethod
    def slot_schema() -> dict:
        return {
            "slot_schema_id": "slot.test",
            "scenario_id": "test",
            "slots": [
                {
                    "slot_id": "incident_number",
                    "display_name": "Номер обращения",
                    "required": True,
                }
            ],
        }

    def test_operator_full_debug_options_enable_all_execution_paths(self) -> None:
        options = normalize_simulation_options(run_mode="operator_full_debug")

        self.assertEqual(options["run_mode"], "operator_full_debug")
        self.assertTrue(options["allow_llm"])
        self.assertTrue(options["allow_readonly_integrations"])
        self.assertTrue(options["allow_mock_integrations"])
        self.assertTrue(options["allow_action_with_approval"])
        self.assertTrue(options["bypass_policy_gates"])

    def test_operator_full_debug_simulation_does_not_stop_on_action_approval(self) -> None:
        store = ConfigStore(self.contracts, db_path=self.db_path)
        launch = {
            "launch_id": "launch.runbook",
            "tool_name": "start_systemcenter_runbook",
            "action_type": "action",
            "endpoint_id": "n8n",
            "operation_id": "start_systemcenter_runbook",
            "endpoint_exists": True,
            "operation_exists": True,
            "required_slots": [],
        }

        ready, blocked, actions = store._simulate_profile_launches(
            [launch],
            slot_values={},
            provided={},
            missing_slots=[],
            simulation_options=normalize_simulation_options(run_mode="operator_full_debug"),
        )

        self.assertEqual(blocked, [])
        self.assertEqual(ready[0]["status"], "ready")
        self.assertEqual(actions[0]["status"], "ready")

    def test_operator_full_debug_resolution_without_mock_output_waits_for_live_execution(self) -> None:
        store = ConfigStore(self.contracts, db_path=self.db_path)
        self.configure_n8n_operation_without_mock_output(store)
        trace: list[dict] = []

        result = store.simulate_attribute_resolution_profile(
            profile=self.resolution_profile(),
            slot_schema=self.slot_schema(),
            provided={},
            simulation_options=normalize_simulation_options(run_mode="operator_full_debug"),
            effective_thresholds=store.system_confidence_defaults(),
            execution_trace=trace,
            slot_values={},
        )

        self.assertEqual(result["status"], "pending_live_execution")
        self.assertEqual(result["decision"], "execute_react_call")
        self.assertEqual(result["reason"], "Операция будет выполнена при анализе заявки.")
        self.assertEqual(trace[-1]["status"], "ready")
        self.assertEqual(
            result["enrichment_step_results"]["step1"]["result"]["status"],
            "ready_for_execution",
        )

    def test_non_debug_resolution_without_mock_output_still_requires_test_response(self) -> None:
        store = ConfigStore(self.contracts, db_path=self.db_path)
        self.configure_n8n_operation_without_mock_output(store)
        trace: list[dict] = []

        result = store.simulate_attribute_resolution_profile(
            profile=self.resolution_profile(),
            slot_schema=self.slot_schema(),
            provided={},
            simulation_options=normalize_simulation_options(run_mode="llm_readonly"),
            effective_thresholds=store.system_confidence_defaults(),
            execution_trace=trace,
            slot_values={},
        )

        self.assertEqual(result["status"], "blocked_by_configuration")
        self.assertEqual(result["decision"], "handoff")
        self.assertEqual(result["reason"], "В режиме проверки без выполнения нужен тестовый ответ операции.")
        self.assertEqual(trace[-1]["status"], "blocked")
        self.assertEqual(
            trace[-1]["details"]["result"]["reason"],
            "В режиме проверки без выполнения нужен тестовый ответ операции.",
        )

    def test_slot_filling_waits_for_slot_dependencies_before_llm_extraction(self) -> None:
        store = ConfigStore(self.contracts, db_path=self.db_path)
        base_scenario = copy.deepcopy(store.active_payload("service_scenarios")["scenarios"][0])
        base_scenario.update(
            {
                "scenario_id": "provider_dependency_test",
                "display_name": "Provider dependency test",
                "slot_schema_id": "slot.provider_dependency_test",
                "allowed_react_call_names": ["n8n_wait_for_email_by_ticket"],
            }
        )
        self.force_active_payload(
            store,
            "service_scenarios",
            {"schema_version": "1.0", "scenarios": [base_scenario]},
        )
        self.force_active_payload(
            store,
            "slot_schemas",
            {
                "schema_version": "1.0",
                "slot_schemas": [
                    {
                        "slot_schema_id": "slot.provider_dependency_test",
                        "display_name": "Provider dependency slots",
                        "required_slots": ["provider_mail_body", "incident_number"],
                        "auto_fill_slots": ["provider_mail_body", "incident_number"],
                        "question_order": [],
                        "slots": [
                            {
                                "slot_id": "provider_mail_body",
                                "display_name": "Тело письма провайдера",
                                "priority_group": "context",
                                "required": True,
                                "fill_method": "resolution_profile",
                                "resolution_profile_id": "profile.provider_dependency.mail",
                            },
                            {
                                "slot_id": "incident_number",
                                "display_name": "Номер заявки провайдера",
                                "priority_group": "what",
                                "required": True,
                                "fill_method": "llm_extraction",
                                "extraction_instruction": "Извлеки номер заявки из ${slot.provider_mail_body}.",
                            },
                        ],
                        "stages": [
                            {
                                "stage_id": "stage.provider",
                                "display_name": "Provider",
                                "order": 1,
                                "slots": [
                                    {
                                        "slot_id": "provider_mail_body",
                                        "display_name": "Тело письма провайдера",
                                        "priority_group": "context",
                                        "required": True,
                                        "fill_method": "resolution_profile",
                                        "resolution_profile_id": "profile.provider_dependency.mail",
                                    }
                                ],
                                "resolution_profile_id": "profile.provider_dependency.mail",
                            },
                            {
                                "stage_id": "stage.incident",
                                "display_name": "Incident",
                                "order": 2,
                                "slots": [
                                    {
                                        "slot_id": "incident_number",
                                        "display_name": "Номер заявки провайдера",
                                        "priority_group": "what",
                                        "required": True,
                                        "fill_method": "llm_extraction",
                                        "extraction_instruction": "Извлеки номер заявки из ${slot.provider_mail_body}.",
                                    }
                                ],
                            },
                        ],
                    }
                ],
            },
        )
        self.force_active_payload(
            store,
            "attribute_resolution_profiles",
            {
                "schema_version": "1.0",
                "profiles": [
                    {
                        "profile_id": "profile.provider_dependency.mail",
                        "display_name": "Получить письмо провайдера",
                        "status": "active",
                        "slot_schema_id": "slot.provider_dependency_test",
                        "target_slot_id": "provider_mail_body",
                        "use_llm_after_steps": False,
                        "max_attempts": 1,
                        "enrichment_steps": [
                            {
                                "step_id": "step1",
                                "step_name": "Дождаться письма",
                                "react_call": "n8n_wait_for_email_by_ticket",
                                "endpoint_id": "mock",
                                "operation_id": "wait_for_email_by_ticket",
                                "parameter_mapping": {"ticket_number": "constant:T-1"},
                                "completion_policy": {"mode": "sync", "max_wait_seconds": 0, "timeout_action": "resume_agent"},
                            }
                        ],
                        "output_slots_order": [
                            {
                                "slot_id": "provider_mail_body",
                                "order": 1,
                                "required_for_success": True,
                                "source_hint": "body",
                                "fallback": "ask_clarification",
                            }
                        ],
                        "llm_resolution_script": {},
                        "human_resolution_policy": {
                            "action": "escalate_operator",
                            "message_template": "Передать оператору.",
                        },
                    }
                ],
            },
        )
        self.force_active_payload(
            store,
            "tools",
            {
                "schema_version": "1.0",
                "tools": [
                    {
                        "tool_name": "n8n_wait_for_email_by_ticket",
                        "display_name": "Дождаться письма",
                        "description": "Тестовая операция.",
                        "action_type": "read_only",
                        "endpoint_bindings": [
                            {
                                "endpoint_id": "mock",
                                "operation_id": "wait_for_email_by_ticket",
                                "parameter_mapping": {"ticket_number": "react:ticket_number"},
                                "result_mapping": {"body": "body"},
                            }
                        ],
                        "parameters_schema": {
                            "type": "object",
                            "required": ["ticket_number"],
                            "properties": {"ticket_number": {"type": "string"}},
                            "additionalProperties": True,
                        },
                        "result_schema": {
                            "type": "object",
                            "required": ["body"],
                            "properties": {"body": {"type": "string"}},
                            "additionalProperties": True,
                        },
                        "policy": {
                            "default_timeout_seconds": 15,
                            "retry": {"max_attempts": 1},
                        },
                    }
                ],
            },
        )
        self.force_active_payload(
            store,
            "integration_endpoints",
            {
                "schema_version": "1.0",
                "endpoints": [
                    {
                        "endpoint_id": "mock",
                        "display_name": "Mock",
                        "adapter_type": "mock",
                        "enabled": True,
                        "operations": {
                            "wait_for_email_by_ticket": {
                                "display_name": "Дождаться письма",
                                "method": "POST",
                                "path": "/wait",
                                "request_schema": {"type": "object", "additionalProperties": True},
                                "response_schema": {
                                    "type": "object",
                                    "properties": {"body": {"type": "string"}},
                                    "additionalProperties": True,
                                },
                                "mock_output": {
                                    "body": "Ваша заявка зарегистрирована за номером МТС000000000000001"
                                },
                            }
                        },
                    }
                ],
            },
        )

        calls: list[dict] = []

        def fake_extract(**kwargs):
            calls.append(kwargs)
            return {
                "status": "success",
                "provider": "fake",
                "model": "fake-model",
                "slots": {
                    "incident_number": {
                        "value": "МТС000000000000001",
                        "confidence": 0.91,
                        "reason": "Номер найден в provider_mail_body.",
                    }
                },
            }

        with patch("apps.orchestrator.app.config_registry.invoke_slot_extraction_model", side_effect=fake_extract):
            result = store.simulate_scenario(
                "provider_dependency_test",
                text="host:c2m-ntbook-routerg-047",
                run_mode="llm_readonly",
            )

        self.assertEqual(len(calls), 1)
        self.assertEqual(
            calls[0]["slot_values"]["provider_mail_body"],
            "Ваша заявка зарегистрирована за номером МТС000000000000001",
        )
        self.assertEqual(result["slot_values"]["provider_mail_body"]["status"], "filled_by_profile")
        self.assertEqual(result["slot_values"]["incident_number"]["status"], "filled_by_model")
        self.assertEqual(result["missing_slots"], [])

    def test_operator_full_debug_bypasses_policy_and_gate_creation(self) -> None:
        workflow = self.workflow()
        dispatcher = FakeDispatcher()
        workflow.integration_dispatcher = dispatcher

        analysis = workflow.analyze(
            {
                "user": "ivanov",
                "service": "billing-worker",
                "description": "Нужно запустить runbook для восстановления сервиса.",
                "priority": "p3",
                "scenario": "runbook",
                "debug_run_mode": "operator_full_debug",
                "debug_bypass_policy_gates": True,
            }
        )

        self.assertEqual(analysis["approval_requests"], [])
        self.assertEqual(analysis["execution_policy_results"][0]["execution_mode"], "auto_execute")
        self.assertTrue(analysis["execution_policy_results"][0]["extensions"]["debug_bypass_policy_gates"])
        self.assertEqual(dispatcher.invocations[0]["execution_mode"], "auto_execute")
        self.assertFalse(dispatcher.invocations[0]["approval_required"])

    def test_execution_policy_modes_are_diagnostic_for_dispatch(self) -> None:
        store = ConfigStore(self.contracts, db_path=self.db_path)
        self.force_active_payload(
            store,
            "tools",
            {
                "schema_version": "1.0",
                "tools": [
                    {
                        "tool_name": "manual_repair_action",
                        "display_name": "Ручное восстановление",
                        "description": "Тестовый action без execution policy rule.",
                        "action_type": "action",
                        "endpoint_bindings": [
                            {
                                "endpoint_id": "mock",
                                "operation_id": "manual_repair_action",
                                "parameter_mapping": {"target": "react:target"},
                                "result_mapping": {"message": "message"},
                            }
                        ],
                        "parameters_schema": {
                            "type": "object",
                            "required": ["target"],
                            "properties": {"target": {"type": "string", "minLength": 1}},
                            "additionalProperties": True,
                        },
                        "result_schema": {
                            "type": "object",
                            "required": ["message"],
                            "properties": {"message": {"type": "string", "minLength": 1}},
                            "additionalProperties": True,
                        },
                        "policy": {
                            "default_timeout_seconds": 5,
                            "retry": {"max_attempts": 1, "backoff_seconds": 0},
                            "approval_required_hint": False,
                            "auto_execution_eligible": False,
                            "max_risk_level": "critical",
                        },
                        "contract_version": "1.0",
                        "contract_status": "valid",
                    }
                ],
            },
        )
        self.force_active_payload(
            store,
            "integration_endpoints",
            {
                "schema_version": "1.0",
                "endpoints": [
                    {
                        "endpoint_id": "mock",
                        "display_name": "Mock",
                        "adapter_type": "mock",
                        "enabled": True,
                        "auth": {"type": "none"},
                        "operations": {
                            "manual_repair_action": {
                                "operation_id": "manual_repair_action",
                                "display_name": "Ручное восстановление",
                                "method": "POST",
                                "path": "/mock/manual-repair",
                                "timeout_seconds": 5,
                                "request_schema": {
                                    "type": "object",
                                    "required": ["target"],
                                    "properties": {"target": {"type": "string", "minLength": 1}},
                                    "additionalProperties": True,
                                },
                                "mock_output": {"message": "Интеграция вызвана; policy mode остался диагностикой."},
                                "response_schema": {
                                    "type": "object",
                                    "required": ["message"],
                                    "properties": {"message": {"type": "string", "minLength": 1}},
                                    "additionalProperties": True,
                                },
                                "contract_version": "1.0",
                                "contract_status": "valid",
                            }
                        },
                    }
                ],
            },
        )
        workflow = TicketWorkflow(
            self.contracts,
            config_store=store,
            action_gate_store=ActionGateStore(self.contracts, db_path=self.db_path),
            case_store=CaseStore(self.contracts, db_path=self.db_path),
        )

        ticket = {
            "user": "ivanov",
            "service": "router-1",
            "description": "Нужно восстановить канал вручную.",
            "priority": "p3",
            "scenario": "action",
            "decision_override": {
                "schema_version": "1.0",
                "decision": {
                    "type": "action_proposed",
                    "summary": "Предложено ручное восстановление.",
                    "confidence": 0.9,
                },
                "operator_message": "Проверьте ручное действие.",
                "internal_reasoning_summary": "Тест policy как диагностического trace.",
                "citations": [],
                "proposed_actions": [
                    {
                        "tool_name": "manual_repair_action",
                        "action_id": "manual_repair_router_1",
                        "action_type": "action",
                        "parameters": {"target": "router-1"},
                        "reason": "Нужен запуск операции.",
                        "risk_level": "medium",
                        "expected_effect": "Интеграция выполнит восстановление.",
                        "requires_state_change": True,
                    }
                ],
            },
        }

        analysis = workflow.analyze(ticket)

        self.assertEqual(analysis["workflow_state"]["id"], "action_execution_requested")
        self.assertEqual(analysis["workflow_state"]["category"], "action")
        self.assertEqual(analysis["execution_policy_results"][0]["execution_mode"], "manual_only")
        self.assertEqual(analysis["execution_policy_results"][0]["policy_rule_id"], "tools.default.manual_only")
        self.assertEqual(analysis["tool_results"][0]["status"], "success")
        self.assertEqual(analysis["tool_results"][0]["policy_rule_id"], "tools.default.manual_only")
        self.assertIn("Интеграция вызвана", analysis["tool_results"][0]["output"]["message"])
        self.assertEqual(analysis["approval_requests"], [])

        critical_ticket = copy.deepcopy(ticket)
        critical_ticket["decision_override"]["proposed_actions"][0]["action_id"] = "manual_repair_router_critical"
        critical_ticket["decision_override"]["proposed_actions"][0]["risk_level"] = "critical"
        critical_analysis = workflow.analyze(critical_ticket)

        self.assertEqual(critical_analysis["workflow_state"]["id"], "action_execution_requested")
        self.assertEqual(critical_analysis["execution_policy_results"][0]["execution_mode"], "blocked")
        self.assertEqual(
            critical_analysis["execution_policy_results"][0]["policy_rule_id"],
            "tools.critical_risk.block",
        )
        self.assertEqual(critical_analysis["tool_results"][0]["status"], "success")
        self.assertEqual(critical_analysis["tool_results"][0]["policy_rule_id"], "tools.critical_risk.block")
        self.assertEqual(critical_analysis["approval_requests"], [])

    def test_operator_full_debug_preserves_profile_trace_metadata(self) -> None:
        workflow = self.workflow()
        dispatcher = FakeDispatcher()
        workflow.integration_dispatcher = dispatcher
        decision_override = workflow._runbook_decision({"service": "billing-worker"})
        decision_override["proposed_actions"][0].setdefault("extensions", {}).update(
            {
                "source_profile_id": "profile.provider.registration",
                "source_step_id": "step1",
                "debug_launch_id": "profile.provider.registration.step1",
            }
        )

        analysis = workflow.analyze(
            {
                "user": "ivanov",
                "service": "billing-worker",
                "description": "Нужно получить номер регистрации от провайдера.",
                "priority": "p3",
                "scenario": "action",
                "decision_override": decision_override,
                "debug_run_mode": "operator_full_debug",
                "debug_bypass_policy_gates": True,
            }
        )

        self.assertEqual(
            dispatcher.invocations[0]["extensions"]["source_profile_id"],
            "profile.provider.registration",
        )
        self.assertEqual(
            analysis["tool_results"][0]["extensions"]["debug_launch_id"],
            "profile.provider.registration.step1",
        )
        self.assertEqual(
            analysis["tool_trace"][0]["source_step_id"],
            "step1",
        )

    def test_workflow_restores_launch_output_slot_metadata_for_debug_action(self) -> None:
        store = ConfigStore(self.contracts, db_path=self.db_path)
        self.force_active_payload(
            store,
            "attribute_resolution_profiles",
            {
                "schema_version": "1.0",
                "profiles": [
                    {
                        "profile_id": "profile.custom.attribute_copy",
                        "display_name": "Получить письмо провайдера",
                        "slot_schema_id": "slot.custom_copy",
                        "status": "active",
                        "use_llm_after_steps": False,
                        "max_attempts": 1,
                        "enrichment_steps": [
                            {
                                "step_id": "step1",
                                "step_name": "Запустить provider monitor",
                                "react_call": "n8n_monitor_provider_channel_repair",
                            }
                        ],
                        "output_slots_order": [
                            {
                                "slot_id": "provider_mail_body",
                                "order": 1,
                                "source_hint": "email_result.body",
                                "fallback": "leave_empty",
                            }
                        ],
                    }
                ],
            },
        )
        workflow = TicketWorkflow(
            self.contracts,
            action_gate_store=ActionGateStore(self.contracts, db_path=self.db_path),
            case_store=CaseStore(self.contracts, db_path=self.db_path),
            config_store=store,
        )
        action = {
            "tool_name": "n8n_monitor_provider_channel_repair",
            "action_id": "profile.custom.attribute_copy.step1.action",
            "action_type": "action",
            "parameters": {},
            "reason": "debug",
            "risk_level": "medium",
            "expected_effect": "debug",
            "requires_state_change": True,
            "extensions": {
                "source_profile_id": "profile.custom.attribute_copy",
                "source_step_id": "step1",
                "debug_launch_id": "profile.custom.attribute_copy.step1",
            },
        }

        enriched = workflow._action_with_launch_source_metadata(action)

        self.assertEqual(enriched["extensions"]["source_slot_schema_id"], "slot.custom_copy")
        self.assertEqual(
            enriched["extensions"]["source_output_slots_order"],
            [
                {
                    "slot_id": "provider_mail_body",
                    "order": 1,
                    "required_for_success": False,
                    "source_hint": "email_result.body",
                    "fallback": "leave_empty",
                }
            ],
        )
        self.assertNotIn("source_output_slots_order", action["extensions"])

    def test_integration_base_result_copies_profile_trace_metadata(self) -> None:
        result = IntegrationDispatcher._base_result(
            {
                "schema_version": "1.0",
                "invocation_id": "inv-test",
                "action_id": "profile.provider.registration.step1.action",
                "tool_name": "n8n_wait_for_email_by_ticket",
                "endpoint_id": "n8n",
                "adapter_type": "n8n_webhook",
                "operation_id": "wait_for_email_by_ticket",
                "policy_rule_id": "debug_operator_full_run",
                "extensions": {
                    "source_profile_id": "profile.provider.registration",
                    "source_step_id": "step1",
                    "debug_launch_id": "profile.provider.registration.step1",
                    "secret_operation_parameters": ["token"],
                },
            },
            "success",
        )

        self.assertEqual(result["extensions"]["source_profile_id"], "profile.provider.registration")
        self.assertEqual(result["extensions"]["source_step_id"], "step1")
        self.assertEqual(result["extensions"]["debug_launch_id"], "profile.provider.registration.step1")
        self.assertNotIn("secret_operation_parameters", result["extensions"])

    def test_operator_full_debug_returns_not_dispatched_result_for_invalid_action(self) -> None:
        workflow = self.workflow()
        decision_override = workflow._runbook_decision({"service": "billing-worker"})
        action = decision_override["proposed_actions"][0]
        action["parameters"] = {}
        action.setdefault("extensions", {}).update(
            {
                "source_profile_id": "profile.provider.registration",
                "source_step_id": "step1",
                "debug_launch_id": "profile.provider.registration.step1",
            }
        )

        analysis = workflow.analyze(
            {
                "user": "ivanov",
                "service": "billing-worker",
                "description": "Нужно получить номер регистрации от провайдера.",
                "priority": "p3",
                "scenario": "action",
                "decision_override": decision_override,
                "debug_run_mode": "operator_full_debug",
                "debug_bypass_policy_gates": True,
            }
        )

        self.assertEqual(analysis["tool_results"][0]["status"], "error")
        self.assertEqual(analysis["tool_results"][0]["error"]["code"], "not_dispatched")
        self.assertEqual(
            analysis["tool_results"][0]["extensions"]["diagnostic_status"],
            "not_dispatched",
        )
        self.assertEqual(
            analysis["tool_trace"][0]["debug_launch_id"],
            "profile.provider.registration.step1",
        )

    def test_debug_policy_bypass_overrides_critical_risk_block(self) -> None:
        workflow = self.workflow()
        action = workflow._runbook_decision({"service": "billing-worker"})["proposed_actions"][0]
        action["risk_level"] = "critical"

        normal = workflow.policy.evaluate(action)
        debug = workflow._execution_policy_results(
            [action],
            {
                "debug_run_mode": "operator_full_debug",
                "debug_bypass_policy_gates": True,
            },
        )[0]

        self.assertEqual(normal["execution_mode"], "blocked")
        self.assertEqual(debug["execution_mode"], "auto_execute")
        self.assertTrue(debug["allowed"])
        self.assertFalse(debug["approval_required"])


if __name__ == "__main__":
    unittest.main()
