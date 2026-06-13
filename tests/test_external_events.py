from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from apps.orchestrator.app.action_gates import utc_now
from apps.orchestrator.app.cases import CaseStore
from apps.orchestrator.app.config_registry import ConfigStore
from apps.orchestrator.app.contracts import ContractRegistry, ContractValidationError
from apps.orchestrator.app.processing import (
    ExternalEventIdempotencyConflict,
    ProcessingConflict,
    ProcessingNotFound,
    ProcessingStore,
)


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


if __name__ == "__main__":
    unittest.main()
