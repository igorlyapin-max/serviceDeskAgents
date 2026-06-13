from __future__ import annotations

import os
import copy
import json
import tempfile
import unittest
from pathlib import Path

from apps.orchestrator.app.cases import CaseStore
from apps.orchestrator.app.config_registry import ConfigStore
from apps.orchestrator.app.contracts import ContractRegistry
from apps.orchestrator.app.kafka_runtime import (
    ExternalEventWorker,
    KafkaCommandRecord,
    OutboxPublisher,
    ToolCommandWorker,
)
from apps.orchestrator.app.processing import (
    DEFAULT_ASYNC_TOOL_COMMAND_TOPIC,
    DEFAULT_EXTERNAL_EVENT_TOPIC,
    ProcessingConflict,
    ProcessingStore,
)
from apps.orchestrator.app.workflow import TicketWorkflow


def waiting_analysis() -> dict:
    return {
        "ticket_id": "ticket-async-n8n-1",
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
                "summary": "Запустить ранбук и дождаться результата.",
                "confidence": 0.82,
            },
            "operator_message": "Ранбук будет запущен после согласования.",
            "internal_reasoning_summary": "Тестовый async n8n runbook.",
            "citations": [],
            "proposed_actions": [],
        },
        "approval_requests": [],
        "rag_trace": {},
        "tool_trace": [],
        "tool_results": [],
    }


def runbook_invocation(case: dict, *, invocation_id: str = "inv-async-runbook-1") -> dict:
    return {
        "schema_version": "1.0",
        "invocation_id": invocation_id,
        "action_id": "act-runbook-1",
        "tool_name": "start_systemcenter_runbook",
        "action_type": "action",
        "endpoint_id": "n8n",
        "adapter_type": "n8n_webhook",
        "operation_id": "start_systemcenter_runbook",
        "parameters": {
            "runbook_code": "password_reset",
            "user_login": "ivanov",
        },
        "operation_parameters": {
            "runbook_code": "password_reset",
            "login": "ivanov",
        },
        "execution_mode": "operator_approval",
        "allowed": True,
        "approval_required": True,
        "approved_by_operator": True,
        "policy_rule_id": "runbooks.mvp.require_operator_approval",
        "timeout_seconds": 15,
        "retry_policy": {
            "max_attempts": 1,
            "backoff_seconds": 0,
        },
        "case_id": case["case_id"],
        "ticket_id": case["ticket_id"],
    }


class FakeProducer:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.published: list[tuple[str, str, dict]] = []

    def publish(self, topic: str, key: str, value: dict) -> None:
        if self.fail:
            raise RuntimeError("kafka unavailable")
        self.published.append((topic, key, value))


class FakeDispatcher:
    def __init__(self, *, status: str = "success"):
        self.status = status
        self.invocations: list[dict] = []

    def dispatch(self, invocation: dict) -> dict:
        self.invocations.append(invocation)
        result = {
            "schema_version": "1.0",
            "invocation_id": invocation["invocation_id"],
            "action_id": invocation["action_id"],
            "tool_name": invocation["tool_name"],
            "endpoint_id": invocation["endpoint_id"],
            "adapter_type": invocation["adapter_type"],
            "operation_id": invocation["operation_id"],
            "status": self.status,
            "policy_rule_id": invocation["policy_rule_id"],
            "duration_ms": 10,
            "attempts": 1,
        }
        if self.status == "success":
            result["output"] = {
                "runbook_status": "accepted",
                "message": "n8n принял запуск ранбука.",
            }
        else:
            result["error"] = {
                "code": "webhook_unreachable",
                "message": "n8n webhook недоступен.",
            }
        return result


class RaisingDispatcher:
    def dispatch(self, invocation: dict) -> dict:
        raise RuntimeError("temporary dispatcher failure")


class AckSpy:
    def __init__(self) -> None:
        self.count = 0

    def __call__(self) -> None:
        self.count += 1


class AsyncN8nKafkaTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "state.sqlite"
        self.contracts = ContractRegistry()
        self.config_store = ConfigStore(self.contracts, db_path=self.db_path)
        self.case_store = CaseStore(self.contracts, db_path=self.db_path)
        self.processing_store = ProcessingStore(self.case_store, db_path=self.db_path)
        self.ticket_input = {
            "ticket_id": "ticket-async-n8n-1",
            "user": "ivanov",
            "service": "account",
            "description": "Нужен сброс пароля через ранбук.",
        }
        self.analysis = waiting_analysis()
        self.case = self.case_store.create_from_analysis(self.ticket_input, self.analysis)
        self.processing_store.record_analysis(self.ticket_input, {**self.analysis, "case_id": self.case["case_id"]})

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def enqueue_command(
        self,
        *,
        invocation_id: str = "inv-async-runbook-1",
        result_transport: str = "http_callback",
    ) -> dict:
        return self.processing_store.enqueue_async_tool_command(
            runbook_invocation(self.case, invocation_id=invocation_id),
            expected_event_type="start_systemcenter_runbook_completed",
            result_transport=result_transport,
            deadline_seconds=3600,
            callback_base_url="http://127.0.0.1:18088",
        )

    def external_event(self, queued: dict, *, status: str = "success", event_id: str = "evt-runbook-success") -> dict:
        event = {
            "schema_version": "1.0",
            "event_id": event_id,
            "case_id": queued["wait"]["case_id"],
            "ticket_id": queued["wait"]["ticket_id"],
            "wait_id": queued["wait"]["wait_id"],
            "correlation_id": queued["wait"]["correlation_id"],
            "source": queued["command"]["source"],
            "event_type": queued["command"]["expected_event_type"],
            "status": status,
            "received_at": "2026-06-13T10:00:00+00:00",
            "idempotency_key": f"{queued['command']['idempotency_key']}:{event_id}",
        }
        if status == "error":
            event["error"] = {
                "code": "runbook_failed",
                "message": "Ранбук завершился ошибкой.",
            }
        else:
            event["result"] = {
                "runbook_status": status,
                "message": "Ранбук вернул внешний результат.",
            }
        return event

    def test_enqueue_async_tool_command_opens_wait_and_outbox_command(self) -> None:
        result = self.enqueue_command()

        self.assertEqual(result["wait"]["status"], "open")
        self.assertEqual(result["command"]["callback_url"], "http://127.0.0.1:18088/external-events/n8n")
        async_callback = result["command"]["invocation"]["extensions"]["async_callback"]
        self.assertEqual(async_callback["case_id"], self.case["case_id"])
        self.assertEqual(async_callback["ticket_id"], self.case["ticket_id"])
        self.assertEqual(async_callback["run_id"], result["wait"]["run_id"])
        self.assertEqual(async_callback["wait_id"], result["wait"]["wait_id"])
        self.assertEqual(async_callback["correlation_id"], result["wait"]["correlation_id"])
        self.assertEqual(async_callback["event_type"], "start_systemcenter_runbook_completed")
        self.assertEqual(async_callback["callback_url"], "http://127.0.0.1:18088/external-events/n8n")
        self.assertEqual(async_callback["idempotency_key_base"], result["command"]["idempotency_key"])
        self.assertNotIn("idempotency_key", async_callback)
        self.assertEqual(async_callback["result_transport"], "http_callback")
        self.assertEqual(async_callback["result_topic"], DEFAULT_EXTERNAL_EVENT_TOPIC)
        outbox = self.processing_store.list_outbox(case_id=self.case["case_id"])["messages"]
        command_messages = [item for item in outbox if item["event_type"] == "async_tool_invocation_requested"]
        self.assertEqual(len(command_messages), 1)
        self.assertEqual(command_messages[0]["topic"], DEFAULT_ASYNC_TOOL_COMMAND_TOPIC)

    def test_duplicate_enqueue_returns_existing_wait_without_orphan(self) -> None:
        first = self.enqueue_command(invocation_id="inv-repeat")
        second = self.enqueue_command(invocation_id="inv-repeat")

        self.assertTrue(second["duplicate"])
        self.assertEqual(second["wait"]["wait_id"], first["wait"]["wait_id"])
        self.assertEqual(second["command"]["command_id"], first["command"]["command_id"])
        waits = self.processing_store.list_waits(case_id=self.case["case_id"], limit=50)["waits"]
        async_waits = [
            wait
            for wait in waits
            if wait["wait_type"] == "external_event_wait"
            and wait["expected_event_type"] == "start_systemcenter_runbook_completed"
        ]
        self.assertEqual(len(async_waits), 1)

    def test_outbox_publisher_marks_tool_command_published(self) -> None:
        self.enqueue_command()
        producer = FakeProducer()

        result = OutboxPublisher(self.processing_store, producer, worker_id="test-publisher").publish_batch(
            topics=[DEFAULT_ASYNC_TOOL_COMMAND_TOPIC]
        )

        self.assertEqual(result["published"], 1)
        self.assertEqual(len(producer.published), 1)
        outbox = self.processing_store.list_outbox(case_id=self.case["case_id"])["messages"]
        command_message = next(item for item in outbox if item["event_type"] == "async_tool_invocation_requested")
        self.assertEqual(command_message["status"], "published")
        self.assertIn("published_at", command_message)

    def test_outbox_publisher_keeps_failed_publish_retryable(self) -> None:
        self.enqueue_command()

        result = OutboxPublisher(self.processing_store, FakeProducer(fail=True), worker_id="test-publisher").publish_batch(
            topics=[DEFAULT_ASYNC_TOOL_COMMAND_TOPIC]
        )

        self.assertEqual(result["failed"], 1)
        outbox = self.processing_store.list_outbox(case_id=self.case["case_id"])["messages"]
        command_message = next(item for item in outbox if item["event_type"] == "async_tool_invocation_requested")
        self.assertEqual(command_message["status"], "pending")
        self.assertEqual(command_message["attempts"], 1)
        self.assertIn("kafka unavailable", command_message["last_error"])

    def test_tool_command_worker_invokes_dispatcher_and_keeps_wait_open_for_n8n_callback(self) -> None:
        queued = self.enqueue_command()
        dispatcher = FakeDispatcher(status="success")

        result = ToolCommandWorker(self.processing_store, dispatcher, worker_id="test-worker").process_command(
            queued["command"]
        )

        self.assertEqual(result["tool_result"]["status"], "success")
        self.assertEqual(dispatcher.invocations[0]["extensions"]["async_callback"]["wait_id"], queued["wait"]["wait_id"])
        self.assertEqual(self.processing_store.require_wait(queued["wait"]["wait_id"])["status"], "open")
        outbox = self.processing_store.list_outbox(case_id=self.case["case_id"])["messages"]
        self.assertTrue(any(item["event_type"] == "tool_command_result_recorded" for item in outbox))

    def test_tool_command_worker_accepts_published_outbox_envelope(self) -> None:
        self.enqueue_command(invocation_id="inv-envelope")
        producer = FakeProducer()
        OutboxPublisher(self.processing_store, producer, worker_id="test-publisher").publish_batch(
            topics=[DEFAULT_ASYNC_TOOL_COMMAND_TOPIC]
        )
        _, _, envelope = producer.published[0]
        dispatcher = FakeDispatcher(status="success")

        result = ToolCommandWorker(self.processing_store, dispatcher, worker_id="test-worker").process_command(envelope)

        self.assertEqual(result["tool_result"]["status"], "success")
        self.assertEqual(dispatcher.invocations[0]["invocation_id"], envelope["payload"]["invocation"]["invocation_id"])

    def test_tool_command_worker_skips_duplicate_receipt_without_second_dispatch(self) -> None:
        queued = self.enqueue_command(invocation_id="inv-worker-repeat")
        dispatcher = FakeDispatcher(status="success")
        worker = ToolCommandWorker(self.processing_store, dispatcher, worker_id="test-worker")

        first = worker.process_command(queued["command"])
        duplicate = worker.process_command(queued["command"])

        self.assertEqual(first["tool_result"]["status"], "success")
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(len(dispatcher.invocations), 1)

    def test_process_commands_does_not_commit_transient_failure(self) -> None:
        queued = self.enqueue_command(invocation_id="inv-transient")
        ack = AckSpy()
        record = KafkaCommandRecord(value=queued["command"], topic=DEFAULT_ASYNC_TOOL_COMMAND_TOPIC, ack=ack)

        result = ToolCommandWorker(
            self.processing_store,
            RaisingDispatcher(),
            worker_id="test-worker",
        ).process_commands([record], limit=1)

        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["dead_lettered"], 0)
        self.assertEqual(ack.count, 0)

    def test_process_commands_commits_poison_message_after_dead_letter(self) -> None:
        ack = AckSpy()
        record = KafkaCommandRecord(value={"schema_version": "1.0"}, topic=DEFAULT_ASYNC_TOOL_COMMAND_TOPIC, ack=ack)

        result = ToolCommandWorker(
            self.processing_store,
            FakeDispatcher(status="success"),
            worker_id="test-worker",
        ).process_commands([record], limit=1)

        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["dead_lettered"], 1)
        self.assertEqual(ack.count, 1)
        outbox = self.processing_store.list_outbox()["messages"]
        self.assertTrue(any(message["topic"] == "dead-letter" for message in outbox))

    def test_outbox_mark_requires_current_worker_lease(self) -> None:
        self.enqueue_command(invocation_id="inv-cas")
        claimed = self.processing_store.claim_outbox_batch(
            worker_id="publisher-a",
            topics=[DEFAULT_ASYNC_TOOL_COMMAND_TOPIC],
        )

        with self.assertRaises(ProcessingConflict):
            self.processing_store.mark_outbox_published(claimed[0]["message_id"], worker_id="publisher-b")

    def test_secret_operation_parameters_are_not_stored_but_restored_for_worker(self) -> None:
        previous = os.environ.get("ASYNC_TEST_SECRET")
        os.environ["ASYNC_TEST_SECRET"] = "real-secret-value"
        try:
            invocation = runbook_invocation(self.case, invocation_id="inv-secret")
            invocation["operation_parameters"]["api_token"] = "real-secret-value"
            invocation.setdefault("extensions", {})["secret_operation_parameters"] = {"api_token": "ASYNC_TEST_SECRET"}

            queued = self.processing_store.enqueue_async_tool_command(
                invocation,
                expected_event_type="start_systemcenter_runbook_completed",
                callback_base_url="http://127.0.0.1:18088",
            )

            stored_operation_parameters = queued["command"]["invocation"]["operation_parameters"]
            self.assertEqual(stored_operation_parameters["api_token"], "параметр скрыт")
            dispatcher = FakeDispatcher(status="success")
            ToolCommandWorker(self.processing_store, dispatcher, worker_id="test-worker").process_command(queued["command"])
            self.assertEqual(dispatcher.invocations[0]["operation_parameters"]["api_token"], "real-secret-value")
        finally:
            if previous is None:
                os.environ.pop("ASYNC_TEST_SECRET", None)
            else:
                os.environ["ASYNC_TEST_SECRET"] = previous

    def test_workflow_dispatch_tool_queues_external_event_n8n_action(self) -> None:
        workflow = TicketWorkflow(
            contracts=self.contracts,
            case_store=self.case_store,
            config_store=self.config_store,
            processing_store=self.processing_store,
        )
        action = {
            "tool_name": "start_systemcenter_runbook",
            "action_id": "act-runbook-workflow",
            "action_type": "action",
            "parameters": {
                "runbook_code": "password_reset",
                "user_login": "ivanov",
            },
            "reason": "Запустить ранбук.",
            "risk_level": "medium",
            "expected_effect": "Ранбук будет поставлен в очередь.",
            "requires_state_change": True,
            "extensions": {
                "endpoint_id": "n8n",
                "operation_id": "start_systemcenter_runbook",
                "completion_policy": {
                    "mode": "external_event",
                    "max_wait_seconds": 3600,
                    "timeout_action": "escalate_operator",
                    "expected_event_type": "start_systemcenter_runbook_completed",
                    "result_transport": "kafka_event",
                },
            },
        }
        policy_result = {
            "schema_version": "1.0",
            "action_id": "act-runbook-workflow",
            "tool_name": "start_systemcenter_runbook",
            "execution_mode": "operator_approval",
            "allowed": True,
            "approval_required": True,
            "policy_rule_id": "runbooks.mvp.require_operator_approval",
            "risk_level": "medium",
            "reason": "Тестовая политика требует согласования оператора.",
        }

        result = workflow.dispatch_tool(
            action,
            policy_result,
            case_id=self.case["case_id"],
            ticket_id=self.case["ticket_id"],
            approved_by_operator=True,
            operator_id="operator-1",
        )

        self.assertEqual(result["invocation"]["adapter_type"], "n8n_webhook")
        self.assertEqual(result["tool_result"]["status"], "success")
        self.assertEqual(result["tool_result"]["output"]["runbook_status"], "queued")
        self.assertIn("async_wait", result["tool_result"]["extensions"])
        self.assertEqual(
            result["invocation"]["extensions"]["async_callback"]["result_transport"],
            "kafka_event",
        )
        self.assertEqual(
            result["tool_result"]["extensions"]["async_wait"]["completion_policy"]["result_transport"],
            "kafka_event",
        )
        wait = self.processing_store.require_wait(result["tool_result"]["extensions"]["async_wait"]["wait_id"])
        self.assertEqual(wait["payload"]["result_transport"], "kafka_event")
        self.assertEqual(wait["payload"]["result_topic"], DEFAULT_EXTERNAL_EVENT_TOPIC)
        self.assertEqual(
            wait["payload"]["contract_snapshot"]["event_type"],
            "start_systemcenter_runbook_completed",
        )
        outbox = self.processing_store.list_outbox(case_id=self.case["case_id"])["messages"]
        self.assertTrue(any(message["event_type"] == "async_tool_invocation_requested" for message in outbox))

    def test_invalid_result_transport_fails_config_validation(self) -> None:
        payload = copy.deepcopy(self.config_store.active_payload("tool_launch_matrix"))
        launch = payload["matrices"][0]["launches"][0]
        launch.setdefault("completion_policy", {})
        launch["completion_policy"].update(
            {
                "mode": "external_event",
                "max_wait_seconds": 3600,
                "timeout_action": "escalate_operator",
                "expected_event_type": "start_systemcenter_runbook_completed",
                "result_transport": "kafka_events",
            }
        )

        validation = self.config_store.validate_payload("tool_launch_matrix", payload)

        self.assertEqual(validation["status"], "invalid")
        self.assertTrue(any("result_transport" in error for error in validation["errors"]))

    def test_hr_find_manager_workflow_requires_servicedesk_token(self) -> None:
        workflow_path = Path("infra/n8n/workflows/hr-find-manager.json")
        workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
        validate_node = next(node for node in workflow["nodes"] if node["id"] == "hr-validate-input")
        code = validate_node["parameters"]["jsCode"]

        self.assertIn("N8N_WEBHOOK_TOKEN", code)
        self.assertIn("x-servicedesk-token", code)
        self.assertIn("unauthorized", code)

    def test_tool_command_worker_records_dispatch_failure_as_external_error(self) -> None:
        queued = self.enqueue_command(invocation_id="inv-async-runbook-error")

        result = ToolCommandWorker(
            self.processing_store,
            FakeDispatcher(status="error"),
            worker_id="test-worker",
        ).process_command(queued["command"])

        self.assertEqual(result["tool_result"]["status"], "error")
        self.assertEqual(result["external_event_result"]["wait"]["status"], "failed")
        self.assertEqual(self.processing_store.require_wait(queued["wait"]["wait_id"])["status"], "failed")
        self.assertEqual(self.processing_store.latest_run(self.case["case_id"])["status"], "queued")

    def test_external_event_worker_records_kafka_result_and_commits(self) -> None:
        queued = self.enqueue_command(invocation_id="inv-result-kafka", result_transport="kafka_event")
        ack = AckSpy()
        record = KafkaCommandRecord(
            value=self.external_event(queued),
            topic=DEFAULT_EXTERNAL_EVENT_TOPIC,
            ack=ack,
        )

        result = ExternalEventWorker(
            self.processing_store,
            self.config_store,
            self.contracts,
            worker_id="test-event-worker",
        ).process_events([record], limit=1)

        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["dead_lettered"], 0)
        self.assertEqual(ack.count, 1)
        self.assertEqual(self.processing_store.require_wait(queued["wait"]["wait_id"])["status"], "completed")
        outbox = self.processing_store.list_outbox(case_id=self.case["case_id"])["messages"]
        self.assertTrue(any(message["topic"] == "integration.events" for message in outbox))
        self.assertTrue(any(message["topic"] == "agent.tasks" for message in outbox))

    def test_external_event_worker_dead_letters_kafka_event_for_http_only_wait(self) -> None:
        queued = self.enqueue_command(invocation_id="inv-result-http-only", result_transport="http_callback")
        ack = AckSpy()
        record = KafkaCommandRecord(
            value=self.external_event(queued, event_id="evt-http-only-over-kafka"),
            topic=DEFAULT_EXTERNAL_EVENT_TOPIC,
            ack=ack,
        )

        result = ExternalEventWorker(
            self.processing_store,
            self.config_store,
            self.contracts,
            worker_id="test-event-worker",
        ).process_events([record], limit=1)

        self.assertEqual(result["processed"], 0)
        self.assertEqual(result["dead_lettered"], 1)
        self.assertEqual(ack.count, 1)
        self.assertEqual(self.processing_store.require_wait(queued["wait"]["wait_id"])["status"], "open")

    def test_external_event_worker_dead_letters_wrong_kafka_topic(self) -> None:
        queued = self.enqueue_command(invocation_id="inv-result-wrong-topic", result_transport="kafka_event")
        ack = AckSpy()
        record = KafkaCommandRecord(
            value=self.external_event(queued, event_id="evt-wrong-topic"),
            topic="other.events",
            ack=ack,
        )

        result = ExternalEventWorker(
            self.processing_store,
            self.config_store,
            self.contracts,
            worker_id="test-event-worker",
        ).process_events([record], limit=1)

        self.assertEqual(result["processed"], 0)
        self.assertEqual(result["dead_lettered"], 1)
        self.assertEqual(ack.count, 1)
        self.assertEqual(self.processing_store.require_wait(queued["wait"]["wait_id"])["status"], "open")

    def test_external_event_worker_dead_letters_raw_invalid_json_and_respects_limit(self) -> None:
        first_ack = AckSpy()
        second_ack = AckSpy()
        records = [
            KafkaCommandRecord(
                value=b"{not-json",
                topic=DEFAULT_EXTERNAL_EVENT_TOPIC,
                partition=0,
                offset=10,
                ack=first_ack,
            ),
            KafkaCommandRecord(
                value=b"{also-not-json",
                topic=DEFAULT_EXTERNAL_EVENT_TOPIC,
                partition=0,
                offset=11,
                ack=second_ack,
            ),
        ]

        result = ExternalEventWorker(
            self.processing_store,
            self.config_store,
            self.contracts,
            worker_id="test-event-worker",
        ).process_events(records, limit=1)

        self.assertEqual(result["processed"], 0)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["dead_lettered"], 1)
        self.assertEqual(first_ack.count, 1)
        self.assertEqual(second_ack.count, 0)

    def test_external_event_worker_accepts_progress_then_success_with_distinct_event_keys(self) -> None:
        queued = self.enqueue_command(invocation_id="inv-progress-success", result_transport="kafka_event")
        progress = self.external_event(queued, status="progress", event_id="evt-progress")
        success = self.external_event(queued, status="success", event_id="evt-success")
        progress_ack = AckSpy()
        success_ack = AckSpy()

        result = ExternalEventWorker(
            self.processing_store,
            self.config_store,
            self.contracts,
            worker_id="test-event-worker",
        ).process_events(
            [
                KafkaCommandRecord(value=progress, topic=DEFAULT_EXTERNAL_EVENT_TOPIC, ack=progress_ack),
                KafkaCommandRecord(value=success, topic=DEFAULT_EXTERNAL_EVENT_TOPIC, ack=success_ack),
            ],
            limit=2,
        )

        self.assertEqual(result["processed"], 2)
        self.assertEqual(result["dead_lettered"], 0)
        self.assertEqual(progress_ack.count, 1)
        self.assertEqual(success_ack.count, 1)
        self.assertEqual(self.processing_store.require_wait(queued["wait"]["wait_id"])["status"], "completed")

    def test_external_event_worker_accepts_outbox_envelope_shape(self) -> None:
        queued = self.enqueue_command(invocation_id="inv-result-envelope", result_transport="kafka_event")
        event = self.external_event(queued, event_id="evt-envelope")
        envelope = {
            "schema_version": "1.0",
            "topic": DEFAULT_EXTERNAL_EVENT_TOPIC,
            "key": queued["wait"]["case_id"],
            "event_type": "external_event",
            "payload": event,
        }

        result = ExternalEventWorker(
            self.processing_store,
            self.config_store,
            self.contracts,
            worker_id="test-event-worker",
        ).process_event(envelope)

        self.assertTrue(result["accepted"])
        self.assertEqual(self.processing_store.require_wait(queued["wait"]["wait_id"])["status"], "completed")

    def test_external_event_worker_keeps_duplicate_idempotent(self) -> None:
        queued = self.enqueue_command(invocation_id="inv-result-duplicate", result_transport="kafka_event")
        event = self.external_event(queued, event_id="evt-duplicate")
        worker = ExternalEventWorker(
            self.processing_store,
            self.config_store,
            self.contracts,
            worker_id="test-event-worker",
        )

        first = worker.process_event(event)
        duplicate = worker.process_event(event)

        self.assertTrue(first["accepted"])
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(self.processing_store.require_wait(queued["wait"]["wait_id"])["status"], "completed")

    def test_external_event_worker_dead_letters_poison_payload_and_commits(self) -> None:
        ack = AckSpy()
        record = KafkaCommandRecord(
            value={"schema_version": "1.0"},
            topic=DEFAULT_EXTERNAL_EVENT_TOPIC,
            ack=ack,
        )

        result = ExternalEventWorker(
            self.processing_store,
            self.config_store,
            self.contracts,
            worker_id="test-event-worker",
        ).process_events([record], limit=1)

        self.assertEqual(result["processed"], 0)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["dead_lettered"], 1)
        self.assertEqual(ack.count, 1)
        outbox = self.processing_store.list_outbox()["messages"]
        self.assertTrue(any(message["topic"] == "dead-letter" for message in outbox))

    def test_external_event_worker_dead_letters_wrong_event_type_without_case_change(self) -> None:
        queued = self.enqueue_command(invocation_id="inv-result-wrong-type", result_transport="kafka_event")
        event = self.external_event(queued, event_id="evt-wrong-type")
        event["event_type"] = "wrong_completed"
        ack = AckSpy()
        record = KafkaCommandRecord(value=event, topic=DEFAULT_EXTERNAL_EVENT_TOPIC, ack=ack)

        result = ExternalEventWorker(
            self.processing_store,
            self.config_store,
            self.contracts,
            worker_id="test-event-worker",
        ).process_events([record], limit=1)

        self.assertEqual(result["processed"], 0)
        self.assertEqual(result["dead_lettered"], 1)
        self.assertEqual(ack.count, 1)
        self.assertEqual(self.processing_store.require_wait(queued["wait"]["wait_id"])["status"], "open")


if __name__ == "__main__":
    unittest.main()
