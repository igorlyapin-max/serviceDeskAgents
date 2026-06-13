from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request

from apps.orchestrator.app.action_gates import utc_now
from apps.orchestrator.app.cases import CaseStore
from apps.orchestrator.app.config_registry import ConfigStore
from apps.orchestrator.app.contracts import ContractRegistry
from apps.orchestrator.app.debug_runtime import DebugRuntime
from apps.orchestrator.app.processing import ProcessingStore
from apps.orchestrator.app.security import AuditStore, SecurityManager
from apps.orchestrator.app.workflow import TicketWorkflow


def waiting_analysis() -> dict:
    return {
        "ticket_id": "ticket-external-api-1",
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
                "summary": "Ожидается внешний результат.",
                "confidence": 0.8,
            },
            "operator_message": "Ожидается внешний результат.",
            "internal_reasoning_summary": "API-тест ожидания external_event.",
            "citations": [],
            "proposed_actions": [],
        },
        "approval_requests": [],
        "rag_trace": {},
        "tool_trace": [],
        "tool_results": [],
    }


class ExternalEventsApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "state.sqlite"
        self.env_patch = patch.dict(
            os.environ,
            {
                "APP_ENV": "test",
                "INTEGRATION_CALLBACK_TOKEN__N8N": "api-callback-token",
                "SECURITY_RATE_LIMIT_PER_MINUTE": "0",
                "ORCHESTRATOR_STATE_DB": str(self.db_path),
                "LOG_SINKS": "stdout",
            },
            clear=False,
        )
        self.env_patch.start()
        self.main_app = importlib.import_module("apps.orchestrator.app.main")
        self.old_globals = {
            "workflow": self.main_app.workflow,
            "config_store": self.main_app.config_store,
            "processing_store": self.main_app.processing_store,
            "debug_runtime": self.main_app.debug_runtime,
            "security": self.main_app.security,
            "audit_store": self.main_app.audit_store,
        }
        self.contracts = ContractRegistry()
        self.config_store = ConfigStore(self.contracts, db_path=self.db_path)
        self.case_store = CaseStore(self.contracts, db_path=self.db_path)
        self.processing_store = ProcessingStore(self.case_store, db_path=self.db_path)
        self.workflow = TicketWorkflow(
            contracts=self.contracts,
            case_store=self.case_store,
            config_store=self.config_store,
            processing_store=self.processing_store,
        )
        self.debug_runtime = DebugRuntime(self.workflow, self.config_store, self.processing_store)
        self.workflow.capture_recorder = self.debug_runtime
        self.workflow.integration_dispatcher.capture_recorder = self.debug_runtime
        self.main_app.workflow = self.workflow
        self.main_app.config_store = self.config_store
        self.main_app.processing_store = self.processing_store
        self.main_app.debug_runtime = self.debug_runtime
        self.main_app.security = SecurityManager(self.contracts)
        self.main_app.audit_store = AuditStore(self.contracts, db_path=self.db_path)
        self.ticket_input = {
            "ticket_id": "ticket-external-api-1",
            "user": "ivanov",
            "service": "provider",
            "description": "Проверить состояние у провайдера после внешнего события.",
        }
        self.analysis = waiting_analysis()
        self.case = self.case_store.create_from_analysis(self.ticket_input, self.analysis)
        self.processing_store.record_analysis(self.ticket_input, {**self.analysis, "case_id": self.case["case_id"]})

    def tearDown(self) -> None:
        for name, value in self.old_globals.items():
            setattr(self.main_app, name, value)
        self.env_patch.stop()
        self.tempdir.cleanup()

    def open_wait(self, *, result_transport: str) -> dict:
        return self.processing_store.open_external_wait(
            self.case["case_id"],
            source="n8n",
            event_type="provider_followup_due",
            reason="Проверить состояние у провайдера через внешний endpoint.",
            wait_type="external_event_wait",
            deadline_seconds=3600,
            payload={
                "result_transport": result_transport,
                "result_topic": "external.events",
            },
        )

    @staticmethod
    def external_event(wait: dict, *, event_id: str) -> dict:
        return {
            "schema_version": "1.0",
            "event_id": event_id,
            "case_id": wait["case_id"],
            "ticket_id": wait["ticket_id"],
            "wait_id": wait["wait_id"],
            "correlation_id": wait["correlation_id"],
            "source": "n8n",
            "event_type": "provider_followup_due",
            "status": "success",
            "received_at": utc_now(),
            "idempotency_key": f"{wait['case_id']}:{event_id}",
            "result": {"provider_status": "resolved"},
        }

    @staticmethod
    def callback_request() -> Request:
        return Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/external-events/n8n",
                "headers": [(b"x-servicedesk-callback-token", b"api-callback-token")],
                "query_string": b"",
                "client": ("127.0.0.1", 50000),
                "server": ("testserver", 80),
                "scheme": "http",
            }
        )

    def post_external_event(self, event: dict) -> dict:
        request = self.callback_request()
        context = self.main_app.external_event_context_dependency("n8n", request)
        return self.main_app.external_event(
            "n8n",
            self.main_app.ExternalEventRequest(**event),
            request,
            context,
        )

    def test_http_external_event_rejected_for_kafka_only_wait(self) -> None:
        wait = self.open_wait(result_transport="kafka_event")

        with self.assertRaises(HTTPException) as error:
            self.post_external_event(self.external_event(wait, event_id="evt-http-for-kafka"))

        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(error.exception.detail["code"], "external_event_conflict")
        self.assertEqual(self.processing_store.require_wait(wait["wait_id"])["status"], "open")

    def test_http_external_event_accepted_for_http_callback_wait(self) -> None:
        wait = self.open_wait(result_transport="http_callback")

        body = self.post_external_event(self.external_event(wait, event_id="evt-http-ok"))

        self.assertFalse(body.get("duplicate", False))
        self.assertEqual(body["wait"]["status"], "completed")
        self.assertEqual(self.processing_store.require_wait(wait["wait_id"])["status"], "completed")

    def test_http_external_event_accepted_for_both_wait(self) -> None:
        wait = self.open_wait(result_transport="both")

        body = self.post_external_event(self.external_event(wait, event_id="evt-both-http-ok"))

        self.assertEqual(body["wait"]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
