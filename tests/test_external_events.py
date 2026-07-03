from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from apps.orchestrator.app.action_gates import utc_now
from apps.orchestrator.app.cases import CaseStore
from apps.orchestrator.app.config_registry import ConfigStore
from apps.orchestrator.app.contracts import ContractRegistry, ContractValidationError
from apps.orchestrator.app.kafka_runtime import AgentTaskWorker, ExternalEventWorker, KafkaCommandRecord
from apps.orchestrator.app.processing import (
    ExternalEventIdempotencyConflict,
    ProcessingConflict,
    ProcessingNotFound,
    ProcessingStore,
)


class AckSpy:
    def __init__(self) -> None:
        self.count = 0

    def __call__(self) -> None:
        self.count += 1


class SlotContinuationConfigStore:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def active_payload(self, domain: str) -> dict[str, Any]:
        if domain == "service_scenarios":
            return {
                "schema_version": "1.0",
                "scenarios": [
                    {
                        "scenario_id": "provider_channel_repair",
                        "slot_schema_id": "slot.provider",
                        "status": "active",
                    }
                ],
            }
        if domain == "attribute_resolution_profiles":
            return {
                "schema_version": "1.0",
                "profiles": [
                    {
                        "profile_id": "profile.provider.mail",
                        "slot_schema_id": "slot.provider",
                        "target_slot_id": "provider_mail_body",
                    }
                ],
            }
        return {"schema_version": "1.0"}

    def simulate_scenario(self, scenario_id: str, **kwargs: Any) -> dict[str, Any]:
        self.calls.append({"scenario_id": scenario_id, **kwargs})
        provider_mail_body = kwargs["provided_slots"]["provider_mail_body"]
        monitor_launch = {
            "launch_id": "profile.provider.mail.step1",
            "profile_id": "profile.provider.mail",
            "profile_name": "Письмо провайдера",
            "slot_schema_id": "slot.provider",
            "target_slot_id": "provider_mail_body",
            "output_slots_order": [
                {
                    "slot_id": "provider_mail_body",
                    "source_hint": "${step.step1.react.n8n_monitor_provider_channel_repair.output.email_result.body}",
                    "required_for_success": True,
                }
            ],
            "step_id": "step1",
            "tool_name": "n8n_monitor_provider_channel_repair",
            "action_type": "action",
            "endpoint_id": "n8n",
            "operation_id": "monitor_provider_channel_repair",
            "status": "ready",
            "parameters": {
                "problem_host": "c2m-ntbook-routerg-047",
                "problemUrl": "http://localhost:8081/tr_events.php?triggerid=61119&eventid=90528",
                "service_request": "ticket-external-1",
            },
            "completion_policy": {
                "mode": "external_event",
                "expected_event_type": "monitor_provider_channel_repair_completed",
                "result_transport": "http_callback",
            },
        }
        zabbix_launch = {
            "launch_id": "profile.provider.mail.step2",
            "profile_id": "profile.provider.mail",
            "profile_name": "Письмо провайдера",
            "slot_schema_id": "slot.provider",
            "target_slot_id": "provider_mail_body",
            "output_slots_order": [],
            "step_id": "step2",
            "tool_name": "n8n_update_zabbix_problem",
            "action_type": "action",
            "endpoint_id": "n8n",
            "operation_id": "update_zabbix_problem",
            "status": "ready",
            "parameters": {
                "problemUrl": "http://localhost:8081/tr_events.php?triggerid=61119&eventid=90528",
                "message": "Провайдер зарегистрировал заявку МТС000000000000001.",
            },
            "completion_policy": {"mode": "sync"},
        }
        zabbix_wait_launch = {
            "launch_id": "profile.provider.mail.step3",
            "profile_id": "profile.provider.mail",
            "profile_name": "Письмо провайдера",
            "slot_schema_id": "slot.provider",
            "target_slot_id": None,
            "output_slots_order": [],
            "step_id": "step3",
            "tool_name": "n8n_wait_zabbix_problem_status",
            "action_type": "action",
            "endpoint_id": "n8n",
            "operation_id": "wait_zabbix_problem_status",
            "status": "ready",
            "parameters": {
                "problem_url": "http://localhost:8081/tr_events.php?triggerid=61119&eventid=90528",
                "poll_interval_minutes": "1",
                "timeout_minutes": "20",
                "request_id": "ticket-external-1",
            },
            "completion_policy": {
                "mode": "external_event",
                "expected_event_type": "wait_zabbix_problem_status_completed",
                "result_transport": "kafka_event",
                "result_topic": "external.events",
                "timeout_action": "escalate_operator",
            },
        }
        actions = []
        for launch in (monitor_launch, zabbix_launch, zabbix_wait_launch):
            actions.append(
                {
                    "tool_name": launch["tool_name"],
                    "action_id": f"{launch['launch_id']}.action",
                    "action_type": launch["action_type"],
                    "parameters": launch["parameters"],
                    "reason": "Проверочный запуск шага профиля.",
                    "risk_level": "medium",
                    "expected_effect": "Будет вызвана интеграция.",
                    "requires_state_change": True,
                    "extensions": {
                        "endpoint_id": launch["endpoint_id"],
                        "operation_id": launch["operation_id"],
                        "completion_policy": launch["completion_policy"],
                        "source_profile_id": launch["profile_id"],
                        "source_step_id": launch["step_id"],
                        "source_slot_schema_id": launch["slot_schema_id"],
                        "source_target_slot_id": launch["target_slot_id"],
                        "source_output_slots_order": launch["output_slots_order"],
                    },
                    "status": "ready",
                }
            )
        return {
            "schema_version": "1.0",
            "scenario_id": scenario_id,
            "slot_values": {
                "provider_mail_body": {
                    "status": "provided",
                    "value": provider_mail_body,
                    "fill_method": "operator_input",
                    "source": "operator_input",
                },
                "incident_number": {
                    "status": "filled_by_model",
                    "value": "МТС000000000000001",
                    "candidate_value": "МТС000000000000001",
                    "fill_method": "llm_extraction",
                    "source": "llm",
                    "confidence": 0.93,
                    "reason": "Номер найден в provider_mail_body.",
                },
            },
            "missing_slots": [],
            "final_decision": "ready_for_react",
            "ready_tool_launches": [monitor_launch, zabbix_launch, zabbix_wait_launch],
            "blocked_tool_launches": [],
            "next_allowed_actions": actions,
            "execution_trace": [
                {
                    "step": "1",
                    "status": "completed",
                    "title": "LLM extraction: incident_number",
                    "message": "Значение принято: МТС000000000000001",
                }
            ],
        }


class FollowupWorkflow:
    def __init__(self, processing_store: ProcessingStore | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.processing_store = processing_store

    def dispatch_tool(
        self,
        action: dict[str, Any],
        policy_result: dict[str, Any],
        *,
        case_id: str | None = None,
        ticket_id: str | None = None,
        approved_by_operator: bool = False,
        operator_id: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "action": action,
                "policy_result": policy_result,
                "case_id": case_id,
                "ticket_id": ticket_id,
                "approved_by_operator": approved_by_operator,
                "operator_id": operator_id,
            }
        )
        extensions: dict[str, Any] = {
            "trace": {
                "react_parameters": action["parameters"],
            }
        }
        if (
            self.processing_store is not None
            and action["extensions"]["operation_id"] == "wait_zabbix_problem_status"
        ):
            policy = action["extensions"].get("completion_policy") or {}
            wait = self.processing_store.open_external_wait(
                case_id or action.get("case_id"),
                source="n8n",
                event_type=policy.get("expected_event_type") or "wait_zabbix_problem_status_completed",
                reason="Ожидание восстановления Zabbix после обновления события.",
                deadline_seconds=policy.get("max_wait_seconds"),
                payload={
                    "result_transport": policy.get("result_transport"),
                    "result_topic": policy.get("result_topic"),
                    "resume_policy": policy.get("timeout_action"),
                },
                origin={
                    "kind": "react_call",
                    "react_call": action["tool_name"],
                    "endpoint_id": action["extensions"]["endpoint_id"],
                    "operation_id": action["extensions"]["operation_id"],
                    "source_profile_id": action["extensions"]["source_profile_id"],
                    "source_step_id": action["extensions"]["source_step_id"],
                    "source_slot_schema_id": action["extensions"]["source_slot_schema_id"],
                    "result_transport": policy.get("result_transport"),
                    "result_topic": policy.get("result_topic"),
                },
            )
            extensions["async_wait"] = {
                "wait_id": wait["wait_id"],
                "correlation_id": wait["correlation_id"],
                "event_type": wait["expected_event_type"],
            }
        return {
            "invocation": {
                "invocation_id": "inv-followup-zabbix",
                "tool_name": action["tool_name"],
            },
            "tool_result": {
                "schema_version": "1.0",
                "invocation_id": "inv-followup-zabbix",
                "action_id": action["action_id"],
                "tool_name": action["tool_name"],
                "endpoint_id": action["extensions"]["endpoint_id"],
                "adapter_type": "n8n_webhook",
                "operation_id": action["extensions"]["operation_id"],
                "status": "success",
                "policy_rule_id": policy_result["policy_rule_id"],
                "duration_ms": 10,
                "attempts": 1,
                "output": {"status": "updated"},
                "extensions": extensions,
            },
        }


def waiting_analysis() -> dict:
    return {
        "ticket_id": "ticket-external-1",
        "workflow_state": {
            "id": "waiting_external_event",
            "category": "waiting",
            "terminal": False,
            "can_advance": False,
            "requires_operator_action": False,
        },
        "ai_decision": {
            "schema_version": "1.0",
            "decision": {
                "type": "answer_proposed",
                "summary": "Ожидается внешнее событие для продолжения.",
                "confidence": 0.8,
            },
            "operator_message": "Ожидается внешнее событие.",
            "internal_reasoning_summary": "Тестовая ветка ожидания external_event.",
            "citations": [],
            "proposed_actions": [],
        },
        "approval_requests": [],
        "rag_trace": {},
        "tool_trace": [],
        "tool_results": [],
    }


class ExternalEventsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "state.sqlite"
        self.contracts = ContractRegistry()
        self.config_store = ConfigStore(self.contracts, db_path=self.db_path)
        self.case_store = CaseStore(self.contracts, db_path=self.db_path)
        self.processing_store = ProcessingStore(self.case_store, db_path=self.db_path)
        self.ticket_input = {
            "ticket_id": "ticket-external-1",
            "user": "ivanov",
            "service": "provider",
            "description": "Написали провайдеру, проверить через час.",
        }
        self.analysis = waiting_analysis()
        self.case = self.case_store.create_from_analysis(self.ticket_input, self.analysis)
        self.processing_store.record_analysis(self.ticket_input, {**self.analysis, "case_id": self.case["case_id"]})

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def external_event(
        self,
        wait: dict,
        *,
        status: str = "success",
        event_id: str = "evt-provider-1",
        event_type: str = "provider_followup_due",
        result: dict | None = None,
    ) -> dict:
        event = {
            "schema_version": "1.0",
            "event_id": event_id,
            "case_id": wait["case_id"],
            "ticket_id": wait["ticket_id"],
            "wait_id": wait["wait_id"],
            "correlation_id": wait["correlation_id"],
            "source": "n8n",
            "event_type": event_type,
            "status": status,
            "received_at": utc_now(),
            "idempotency_key": f"{wait['case_id']}:{event_id}",
        }
        if status == "error":
            event["error"] = {"code": "provider_failed", "message": "Провайдер вернул ошибку."}
        else:
            event["result"] = result or {"provider_status": "resolved"}
        return event

    def servicedesk_wait(
        self,
        *,
        correlation_id: str = "OPERU-42",
        event_type: str = "servicedesk_task_result",
        result_topic: str = "public.ittask.result",
        invalid_topic: str | None = None,
    ) -> dict:
        payload = {
            "result_transport": "kafka_event",
            "result_topic": result_topic,
        }
        if invalid_topic:
            payload["invalid_topic"] = invalid_topic
        return self.processing_store.open_external_wait(
            self.case["case_id"],
            source="service_desk",
            event_type=event_type,
            reason="Ожидание результата задачи из канала Сервисдеск.",
            correlation_id=correlation_id,
            payload=payload,
        )

    def test_external_event_contract_validates_required_fields(self) -> None:
        wait = self.processing_store.open_external_wait(
            self.case["case_id"],
            source="n8n",
            event_type="provider_followup_due",
            reason="Проверить состояние у провайдера через час.",
            wait_type="timer_wait",
            deadline_seconds=3600,
        )
        self.contracts.require_valid("external_event", self.external_event(wait))

        invalid = self.external_event(wait)
        invalid.pop("idempotency_key")
        with self.assertRaises(ContractValidationError):
            self.contracts.require_valid("external_event", invalid)

    def test_external_wait_origin_tracks_react_call_and_redacts_parameters(self) -> None:
        wait = self.processing_store.open_external_wait(
            self.case["case_id"],
            source="n8n",
            event_type="runbook_completed",
            reason="Ожидание завершения ранбука.",
            deadline_seconds=86400,
            origin={
                "kind": "react_call",
                "react_call": "start_systemcenter_runbook",
                "launch_id": "launch.password_reset.runbook",
                "endpoint_id": "n8n",
                "operation_id": "start_systemcenter_runbook",
                "parameters": {
                    "user_login": "ivanov",
                    "api_token": "open-secret",
                },
            },
        )

        self.assertEqual(wait["origin"]["kind"], "react_call")
        self.assertEqual(wait["origin"]["react_call"], "start_systemcenter_runbook")
        self.assertEqual(wait["origin"]["endpoint_id"], "n8n")
        self.assertEqual(wait["origin"]["operation_id"], "start_systemcenter_runbook")
        self.assertEqual(wait["origin"]["parameters"]["user_login"], "ivanov")
        self.assertEqual(wait["origin"]["parameters"]["api_token"], "параметр скрыт")
        self.assertEqual(wait["origin"]["correlation_id"], wait["correlation_id"])

    def test_external_event_result_validates_against_operation_async_contract(self) -> None:
        wait = self.processing_store.open_external_wait(
            self.case["case_id"],
            source="n8n",
            event_type="start_systemcenter_runbook_completed",
            reason="Ожидание завершения ранбука.",
            deadline_seconds=86400,
            origin={
                "kind": "react_call",
                "react_call": "start_systemcenter_runbook",
                "launch_id": "launch.password_reset.runbook",
                "endpoint_id": "n8n",
                "operation_id": "start_systemcenter_runbook",
                "parameters": {
                    "runbook_code": "password_reset",
                    "user_login": "ivanov",
                },
            },
        )
        valid_event = self.external_event(
            wait,
            event_type="start_systemcenter_runbook_completed",
            result={"runbook_status": "completed", "message": "Ранбук завершен."},
        )

        self.config_store.validate_external_event_result_contract(wait, valid_event)

        invalid_event = self.external_event(
            wait,
            event_id="evt-runbook-invalid",
            event_type="start_systemcenter_runbook_completed",
            result={"runbook_status": "completed"},
        )
        with self.assertRaises(ContractValidationError) as context:
            self.config_store.validate_external_event_result_contract(wait, invalid_event)
        self.assertTrue(any("message" in error for error in context.exception.errors))

    def test_progress_event_without_progress_schema_does_not_use_terminal_schema(self) -> None:
        wait = self.processing_store.open_external_wait(
            self.case["case_id"],
            source="n8n",
            event_type="monitor_provider_channel_repair_completed",
            reason="Ожидание результата мониторинга провайдера.",
            deadline_seconds=86400,
            origin={
                "kind": "react_call",
                "react_call": "n8n_monitor_provider_channel_repair",
                "endpoint_id": "n8n",
                "operation_id": "monitor_provider_channel_repair",
                "contract_snapshot": {
                    "schema_version": "1.0",
                    "endpoint_id": "n8n",
                    "operation_id": "monitor_provider_channel_repair",
                    "event_type": "monitor_provider_channel_repair_completed",
                    "async_event_contract": {
                        "contract_status": "valid",
                        "statuses": ["progress", "success", "error", "timeout", "cancelled"],
                        "result_schema": {
                            "type": "object",
                            "required": ["runbook_status", "message", "finished_at"],
                            "properties": {
                                "runbook_status": {"enum": ["OK", "ERROR"]},
                                "message": {"type": "string"},
                                "finished_at": {"type": "string"},
                            },
                        },
                    },
                },
            },
        )
        progress_event = self.external_event(
            wait,
            status="progress",
            event_id="evt-provider-progress",
            event_type="monitor_provider_channel_repair_completed",
            result={
                "runbook_status": "PROGRESS",
                "polling_diagnostic": {"current_status": "polling", "poll_iteration": 1},
            },
        )

        self.config_store.validate_external_event_result_contract(wait, progress_event)

    def test_success_external_event_closes_wait_and_queues_resume_task(self) -> None:
        wait = self.processing_store.open_external_wait(
            self.case["case_id"],
            source="n8n",
            event_type="provider_followup_due",
            reason="Проверить состояние у провайдера через час.",
            wait_type="timer_wait",
            deadline_seconds=3600,
        )
        event = self.external_event(wait)
        self.contracts.require_valid("external_event", event)

        result = self.processing_store.record_external_event(event)

        self.assertFalse(result["duplicate"])
        self.assertEqual(result["wait"]["status"], "completed")
        self.assertEqual(result["resume_task"]["status"], "queued")
        self.assertEqual(self.processing_store.latest_run(self.case["case_id"])["status"], "queued")
        detail = self.processing_store.case_detail(self.case["case_id"])
        self.assertTrue(
            any(item["event_type"] == "processing_external_event_received" for item in detail["timeline"]["events"])
        )
        self.assertTrue(
            any(item["event_type"] == "external_event_resume_requested" for item in detail["outbox"])
        )

        duplicate = self.processing_store.record_external_event(event)
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(duplicate["resume_task"]["task_id"], result["resume_task"]["task_id"])
        self.assertNotIn("case", duplicate)
        self.assertNotIn("external_event", duplicate)

    def test_agent_task_worker_processes_external_event_resume_task(self) -> None:
        wait = self.processing_store.open_external_wait(
            self.case["case_id"],
            source="n8n",
            event_type="provider_followup_due",
            reason="Проверить состояние у провайдера через час.",
        )
        event = self.external_event(wait)
        result = self.processing_store.record_external_event(event)
        resume_task_id = result["resume_task"]["task_id"]

        worker_result = AgentTaskWorker(
            self.processing_store,
            worker_id="test-agent-task-worker",
        ).process_batch(limit=1)

        self.assertEqual(worker_result["processed"], 1)
        self.assertEqual(self.processing_store.require_task(resume_task_id)["status"], "completed")
        run = self.processing_store.require_run(result["resume_task"]["run_id"])
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["current_step"], "external_event_processed")
        detail = self.processing_store.case_detail(self.case["case_id"])
        self.assertTrue(
            any(item["event_type"] == "processing_external_event_resume_processed" for item in detail["timeline"]["events"])
        )

    def test_resume_task_materializes_external_event_output_slots(self) -> None:
        wait = self.processing_store.open_external_wait(
            self.case["case_id"],
            source="n8n",
            event_type="monitor_provider_channel_repair_completed",
            reason="Ожидание результата мониторинга провайдера.",
            origin={
                "kind": "react_call",
                "react_call": "n8n_monitor_provider_channel_repair",
                "endpoint_id": "n8n",
                "operation_id": "monitor_provider_channel_repair",
                "source_profile_id": "profile.provider.mail",
                "source_step_id": "step1",
                "source_slot_schema_id": "slot.provider",
                "source_output_slots_order": [
                    {
                        "slot_id": "provider_mail_body",
                        "source_hint": "${step.step1.react.n8n_monitor_provider_channel_repair.output.email_result.body}",
                        "required_for_success": True,
                    }
                ],
            },
        )
        body = "Ваша заявка зарегистрирована за номером МТС000000000000001"
        event = self.external_event(
            wait,
            event_type="monitor_provider_channel_repair_completed",
            result={
                "runbook_status": "OK",
                "message": "Получено письмо провайдера.",
                "email_result": {"body": body, "subject": "Re: test"},
            },
        )

        result = self.processing_store.record_external_event(event)
        resume_result = self.processing_store.process_external_event_resume_task(
            result["resume_task"],
            worker_id="test-agent-worker",
        )

        run = self.processing_store.require_run(wait["run_id"])
        self.assertEqual(run["slot_values"]["provider_mail_body"]["value"], body)
        self.assertEqual(run["slot_values"]["provider_mail_body"]["status"], "filled_by_external_event")
        self.assertEqual(
            resume_result["filled_slot_values"]["provider_mail_body"]["value"],
            body,
        )

    def test_resume_task_continues_dependent_slots_after_external_event(self) -> None:
        config_store = SlotContinuationConfigStore()
        followup_workflow = FollowupWorkflow(self.processing_store)
        self.processing_store.config_store = config_store
        self.processing_store.attach_workflow(followup_workflow)
        wait = self.processing_store.open_external_wait(
            self.case["case_id"],
            source="n8n",
            event_type="monitor_provider_channel_repair_completed",
            reason="Ожидание результата мониторинга провайдера.",
            origin={
                "kind": "react_call",
                "react_call": "n8n_monitor_provider_channel_repair",
                "endpoint_id": "n8n",
                "operation_id": "monitor_provider_channel_repair",
                "source_profile_id": "profile.provider.mail",
                "source_step_id": "step1",
                "source_slot_schema_id": "slot.provider",
                "source_output_slots_order": [
                    {
                        "slot_id": "provider_mail_body",
                        "source_hint": "${step.step1.react.n8n_monitor_provider_channel_repair.output.email_result.body}",
                        "required_for_success": True,
                    }
                ],
            },
        )
        body = "Ваша заявка зарегистрирована за номером МТС000000000000001"
        event = self.external_event(
            wait,
            event_type="monitor_provider_channel_repair_completed",
            result={
                "runbook_status": "OK",
                "message": "Получено письмо провайдера.",
                "email_result": {"body": body, "subject": "Re: test"},
            },
        )

        result = self.processing_store.record_external_event(event)
        resume_result = self.processing_store.process_external_event_resume_task(
            result["resume_task"],
            worker_id="test-agent-worker",
        )

        run = self.processing_store.require_run(wait["run_id"])
        self.assertEqual(config_store.calls[0]["scenario_id"], "provider_channel_repair")
        self.assertEqual(config_store.calls[0]["provided_slots"]["provider_mail_body"], body)
        self.assertEqual(config_store.calls[0]["run_mode"], "llm")
        self.assertIs(config_store.calls[0]["allow_readonly_integrations"], False)
        self.assertIs(config_store.calls[0]["allow_action_with_approval"], True)
        self.assertEqual(run["slot_values"]["incident_number"]["value"], "МТС000000000000001")
        self.assertEqual(run["slot_values"]["incident_number"]["status"], "filled_by_model")
        self.assertEqual(len(followup_workflow.calls), 2)
        self.assertEqual(
            followup_workflow.calls[0]["action"]["tool_name"],
            "n8n_update_zabbix_problem",
        )
        self.assertEqual(
            followup_workflow.calls[0]["action"]["parameters"]["message"],
            "Провайдер зарегистрировал заявку МТС000000000000001.",
        )
        self.assertTrue(followup_workflow.calls[0]["approved_by_operator"])
        self.assertEqual(
            followup_workflow.calls[1]["action"]["tool_name"],
            "n8n_wait_zabbix_problem_status",
        )
        self.assertEqual(
            followup_workflow.calls[1]["action"]["parameters"]["problem_url"],
            "http://localhost:8081/tr_events.php?triggerid=61119&eventid=90528",
        )
        self.assertTrue(followup_workflow.calls[1]["approved_by_operator"])
        continuation = resume_result["slot_continuation"]
        self.assertEqual(continuation["status"], "completed")
        self.assertEqual(continuation["filled_slot_ids"], ["incident_number"])
        self.assertEqual(continuation["tool_dispatch"]["status"], "dispatched")
        self.assertEqual(len(continuation["tool_dispatch"]["dispatched"]), 2)
        self.assertEqual(len(continuation["tool_dispatch"]["skipped"]), 1)
        self.assertEqual(
            continuation["tool_dispatch"]["dispatched"][0]["tool_name"],
            "n8n_update_zabbix_problem",
        )
        self.assertEqual(
            continuation["tool_dispatch"]["dispatched"][1]["tool_name"],
            "n8n_wait_zabbix_problem_status",
        )
        self.assertTrue(continuation["tool_dispatch"]["dispatched"][1]["wait_id"])
        self.assertEqual(
            continuation["filled_slot_values"]["incident_number"]["value"],
            "МТС000000000000001",
        )
        self.assertEqual(run["status"], "waiting")
        self.assertEqual(run["current_step"], "external_event_wait")
        self.assertIsNone(run["completed_at"])
        self.assertEqual(
            run["extensions"]["slot_continuation"][0]["slot_statuses"]["incident_number"]["status"],
            "filled_by_model",
        )
        summary = self.processing_store.case_runtime_summary(self.case["case_id"])
        self.assertEqual(summary["schema_version"], "1.0")
        self.assertEqual(summary["status"], "open")
        self.assertEqual(summary["latest_run"]["run_id"], run["run_id"])
        self.assertEqual(
            summary["latest_run"]["slot_values"]["provider_mail_body"]["value"],
            body,
        )
        self.assertEqual(
            summary["latest_run"]["slot_values"]["incident_number"]["status"],
            "filled_by_model",
        )
        self.assertEqual(
            summary["latest_run"]["slot_materialization"][0]["slot_ids"],
            ["provider_mail_body"],
        )
        self.assertEqual(
            summary["latest_run"]["slot_continuation"][0]["filled_slot_ids"],
            ["incident_number"],
        )
        self.assertEqual(summary["latest_wait"]["status"], "open")
        self.assertEqual(summary["latest_wait"]["expected_event_type"], "wait_zabbix_problem_status_completed")
        self.assertEqual(summary["latest_task"]["status"], "completed")

    def test_progress_external_event_keeps_wait_open(self) -> None:
        wait = self.processing_store.open_external_wait(
            self.case["case_id"],
            source="n8n",
            event_type="provider_followup_due",
            reason="Проверить состояние у провайдера через час.",
        )
        event = self.external_event(wait, status="progress", event_id="evt-provider-progress")

        result = self.processing_store.record_external_event(event)

        self.assertEqual(result["wait"]["status"], "open")
        self.assertNotIn("resume_task", result)
        self.assertIsNotNone(self.processing_store.active_wait_by_correlation(wait["correlation_id"]))

    def test_large_external_event_result_is_compacted_in_wait_state(self) -> None:
        wait = self.processing_store.open_external_wait(
            self.case["case_id"],
            source="n8n",
            event_type="provider_followup_due",
            reason="Проверить состояние у провайдера через час.",
        )
        event = self.external_event(
            wait,
            status="progress",
            event_id="evt-provider-large-progress",
            result={"raw": "x" * 5000},
        )

        result = self.processing_store.record_external_event(event)

        last_event = result["wait"]["payload"]["last_external_event"]
        self.assertIn("summary", last_event["result"])
        self.assertGreater(last_event["result"]["size_bytes"], 4000)
        receipt = self.processing_store.external_event_receipt(event["idempotency_key"])
        self.assertIn("summary", receipt["result"]["external_event"]["result"])

    def test_external_event_redacts_secret_fields_before_persistence(self) -> None:
        wait = self.processing_store.open_external_wait(
            self.case["case_id"],
            source="n8n",
            event_type="provider_followup_due",
            reason="Проверить состояние у провайдера через час.",
        )
        event = self.external_event(
            wait,
            status="progress",
            event_id="evt-provider-secret-progress",
            result={"api_token": "open-secret", "provider_status": "working"},
        )

        result = self.processing_store.record_external_event(event)

        self.assertEqual(result["external_event"]["result"]["api_token"], "параметр скрыт")
        receipt = self.processing_store.external_event_receipt(event["idempotency_key"])
        self.assertEqual(receipt["result"]["external_event"]["result"]["api_token"], "параметр скрыт")

    def test_external_event_redacts_tokens_inside_generic_strings(self) -> None:
        wait = self.processing_store.open_external_wait(
            self.case["case_id"],
            source="n8n",
            event_type="provider_followup_due",
            reason="Проверить состояние у провайдера через час.",
        )
        event = self.external_event(
            wait,
            status="progress",
            event_id="evt-provider-generic-secret-progress",
            result={
                "message": "provider returned Bearer abcdefghijklmnopqrstuvwxyz012345",
                "url": "https://provider.example/path?token=secret-token-value",
            },
        )

        result = self.processing_store.record_external_event(event)

        stored_result = result["external_event"]["result"]
        self.assertIn("[REDACTED_TOKEN]", stored_result["message"])
        self.assertIn("token=[REDACTED_SECRET]", stored_result["url"])

    def test_external_event_preserves_contact_and_ticket_text_before_persistence(self) -> None:
        wait = self.processing_store.open_external_wait(
            self.case["case_id"],
            source="n8n",
            event_type="provider_followup_due",
            reason="Проверить состояние у провайдера через час.",
        )
        body = (
            "Автоответ тестового стенда получен. "
            "Ваша заявка зарегистрирована за номером МТС000000000000001. "
            "Контакт user@example.com, телефон +7 999 123-45-67."
        )
        event = self.external_event(
            wait,
            status="progress",
            event_id="evt-provider-ticket-body",
            result={"email_result": {"body": body}},
        )

        result = self.processing_store.record_external_event(event)

        stored_body = result["external_event"]["result"]["email_result"]["body"]
        self.assertEqual(stored_body, body)
        receipt = self.processing_store.external_event_receipt(event["idempotency_key"])
        receipt_body = receipt["result"]["external_event"]["result"]["email_result"]["body"]
        self.assertEqual(receipt_body, body)

    def test_external_event_source_must_match_wait_source(self) -> None:
        wait = self.processing_store.open_external_wait(
            self.case["case_id"],
            source="n8n",
            event_type="provider_followup_due",
            reason="Проверить состояние у провайдера через час.",
        )
        event = self.external_event(wait)
        event["source"] = "other-source"

        with self.assertRaises(ProcessingConflict):
            self.processing_store.record_external_event(event)

    def test_external_event_transport_must_match_wait_policy(self) -> None:
        wait = self.processing_store.open_external_wait(
            self.case["case_id"],
            source="n8n",
            event_type="provider_followup_due",
            reason="Проверить состояние у провайдера через час.",
            payload={
                "result_transport": "kafka_event",
                "result_topic": "external.events",
            },
        )
        event = self.external_event(wait)

        with self.assertRaises(ProcessingConflict):
            self.processing_store.record_external_event(event, received_transport="http_callback")

    def test_external_event_idempotency_key_rejects_different_event(self) -> None:
        wait = self.processing_store.open_external_wait(
            self.case["case_id"],
            source="n8n",
            event_type="provider_followup_due",
            reason="Проверить состояние у провайдера через час.",
        )
        event = self.external_event(wait)
        self.processing_store.record_external_event(event)
        changed = self.external_event(wait, event_id="evt-provider-2")
        changed["idempotency_key"] = event["idempotency_key"]

        with self.assertRaises(ExternalEventIdempotencyConflict):
            self.processing_store.record_external_event(changed)

    def test_external_event_idempotency_key_rejects_same_metadata_with_different_payload(self) -> None:
        wait = self.processing_store.open_external_wait(
            self.case["case_id"],
            source="n8n",
            event_type="provider_followup_due",
            reason="Проверить состояние у провайдера через час.",
        )
        event = self.external_event(wait, result={"provider_status": "resolved"})
        self.processing_store.record_external_event(event)
        changed = self.external_event(wait, result={"provider_status": "failed"})
        changed["event_id"] = event["event_id"]
        changed["idempotency_key"] = event["idempotency_key"]

        with self.assertRaises(ExternalEventIdempotencyConflict):
            self.processing_store.record_external_event(changed)

    def test_external_wait_rejects_duplicate_active_correlation(self) -> None:
        correlation_id = f"{self.case['case_id']}:custom-correlation"
        self.processing_store.open_external_wait(
            self.case["case_id"],
            source="n8n",
            event_type="provider_followup_due",
            reason="Проверить состояние у провайдера через час.",
            correlation_id=correlation_id,
        )

        with self.assertRaises(ProcessingConflict):
            self.processing_store.open_external_wait(
                self.case["case_id"],
                source="n8n",
                event_type="provider_followup_due",
                reason="Повторная постановка с тем же correlation_id.",
                correlation_id=correlation_id,
            )

    def test_unknown_correlation_is_rejected(self) -> None:
        wait = self.processing_store.open_external_wait(
            self.case["case_id"],
            source="n8n",
            event_type="provider_followup_due",
            reason="Проверить состояние у провайдера через час.",
        )
        event = self.external_event(wait)
        event["correlation_id"] = "missing-correlation"

        with self.assertRaises(ProcessingNotFound):
            self.processing_store.record_external_event(event)

    def test_servicedesk_kafka_result_uses_message_key_as_correlation(self) -> None:
        wait = self.servicedesk_wait()
        worker = ExternalEventWorker(self.processing_store, self.config_store, self.contracts)
        record = KafkaCommandRecord(
            value={
                "TaskResultCode": "Выполнено",
                "TaskResultMessage": "Задача выполнена.",
            },
            topic="public.ittask.result",
            key="OPERU-42",
            partition=0,
            offset=7,
        )

        result = worker.process_event(
            record,
            received_transport="kafka_event",
            source_topic="public.ittask.result",
        )

        self.assertEqual(result["wait"]["wait_id"], wait["wait_id"])
        self.assertEqual(result["wait"]["status"], "completed")
        self.assertEqual(result["external_event"]["source"], "service_desk")
        self.assertEqual(result["wait"]["case_id"], self.case["case_id"])
        self.assertEqual(result["external_event"]["correlation_id"], "OPERU-42")
        self.assertEqual(result["external_event"]["result"]["result_code"], "Выполнено")

    def test_servicedesk_kafka_failed_result_closes_wait_as_error(self) -> None:
        wait = self.servicedesk_wait(correlation_id="OPERU-43")
        worker = ExternalEventWorker(self.processing_store, self.config_store, self.contracts)

        result = worker.process_event(
            KafkaCommandRecord(
                value={
                    "TaskResultCode": "Не выполнено",
                    "TaskResultMessage": "Исполнитель отказал.",
                },
                topic="public.ittask.result",
                key="OPERU-43",
                partition=0,
                offset=8,
            ),
            received_transport="kafka_event",
            source_topic="public.ittask.result",
        )

        self.assertEqual(result["wait"]["wait_id"], wait["wait_id"])
        self.assertEqual(result["wait"]["status"], "failed")
        self.assertEqual(result["external_event"]["status"], "error")
        self.assertEqual(result["external_event"]["error"]["message"], "Исполнитель отказал.")

    def test_servicedesk_invalid_topic_completes_result_wait_as_error(self) -> None:
        wait = self.servicedesk_wait(correlation_id="OPERU-44", invalid_topic="public.ittask.invalid")
        worker = ExternalEventWorker(self.processing_store, self.config_store, self.contracts)

        result = worker.process_event(
            KafkaCommandRecord(
                value={
                    "reason": "Неверный формат задачи.",
                    "payload": {"task": "bad"},
                },
                topic="public.ittask.invalid",
                key="OPERU-44",
                partition=0,
                offset=9,
            ),
            received_transport="kafka_event",
            source_topic="public.ittask.invalid",
        )

        self.assertEqual(result["wait"]["wait_id"], wait["wait_id"])
        self.assertEqual(result["wait"]["status"], "failed")
        self.assertEqual(result["external_event"]["event_type"], "servicedesk_task_result")
        self.assertEqual(result["external_event"]["error"]["code"], "servicedesk_invalid_task")

    def test_servicedesk_unknown_result_code_goes_to_dead_letter(self) -> None:
        self.servicedesk_wait(correlation_id="OPERU-45")
        ack = AckSpy()
        worker = ExternalEventWorker(self.processing_store, self.config_store, self.contracts)

        result = worker.process_events(
            [
                KafkaCommandRecord(
                    value={
                        "TaskResultCode": "Готово",
                        "TaskResultMessage": "Неподдерживаемый код.",
                    },
                    topic="public.ittask.result",
                    key="OPERU-45",
                    partition=0,
                    offset=10,
                    ack=ack,
                )
            ],
            limit=1,
        )

        self.assertEqual(result["processed"], 0)
        self.assertEqual(result["dead_lettered"], 1)
        self.assertEqual(ack.count, 1)
        self.assertIsNotNone(self.processing_store.active_wait_by_correlation("OPERU-45"))

    def test_servicedesk_duplicate_result_with_new_offset_is_idempotent(self) -> None:
        self.servicedesk_wait(correlation_id="OPERU-46")
        worker = ExternalEventWorker(self.processing_store, self.config_store, self.contracts)
        value = {
            "TaskResultCode": "Выполнено",
            "TaskResultMessage": "Задача выполнена.",
        }

        first = worker.process_event(
            KafkaCommandRecord(value=value, topic="public.ittask.result", key="OPERU-46", partition=0, offset=11),
            received_transport="kafka_event",
            source_topic="public.ittask.result",
        )
        duplicate = worker.process_event(
            KafkaCommandRecord(value=value, topic="public.ittask.result", key="OPERU-46", partition=0, offset=12),
            received_transport="kafka_event",
            source_topic="public.ittask.result",
        )

        self.assertFalse(first["duplicate"])
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(duplicate["wait_id"], first["wait"]["wait_id"])

    def test_servicedesk_temp_password_requires_explicit_correlation(self) -> None:
        self.servicedesk_wait(
            correlation_id="OPERU-47",
            event_type="servicedesk_temp_password",
            result_topic="public.ittask.temp_password",
        )
        ack = AckSpy()
        worker = ExternalEventWorker(self.processing_store, self.config_store, self.contracts)

        result = worker.process_events(
            [
                KafkaCommandRecord(
                    value={
                        "personalID": "100500",
                        "password": "secret-temp-password",
                    },
                    topic="public.ittask.temp_password",
                    key="OPERU-47",
                    partition=0,
                    offset=13,
                    ack=ack,
                )
            ],
            limit=1,
        )

        self.assertEqual(result["processed"], 0)
        self.assertEqual(result["dead_lettered"], 1)
        self.assertEqual(ack.count, 1)
        outbox = self.processing_store.list_outbox()["messages"]
        dead_letters = [message for message in outbox if message["topic"] == "dead-letter"]
        self.assertTrue(dead_letters)
        raw = dead_letters[-1]["payload"]["external_event"]["raw"]
        self.assertEqual(raw["password"], "параметр скрыт")
        self.assertIsNotNone(self.processing_store.active_wait_by_correlation("OPERU-47"))


if __name__ == "__main__":
    unittest.main()
