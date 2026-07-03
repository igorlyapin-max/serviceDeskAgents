from __future__ import annotations

import os
import copy
import json
import tempfile
import unittest
from pathlib import Path

from apps.orchestrator.app.cases import CaseStore
from apps.orchestrator.app.config_registry import ConfigStore, default_async_completion_policy_for_operation
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
    def __init__(
        self,
        *,
        status: str = "success",
        error_code: str = "webhook_unreachable",
        error_message: str = "n8n webhook недоступен.",
    ):
        self.status = status
        self.error_code = error_code
        self.error_message = error_message
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
                "code": self.error_code,
                "message": self.error_message,
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

    def external_event(
        self,
        queued: dict,
        *,
        status: str = "success",
        event_id: str = "evt-runbook-success",
        result: dict | None = None,
    ) -> dict:
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
            event["result"] = result or {
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

    def test_claim_next_task_reclaims_expired_running_task(self) -> None:
        queued = self.enqueue_command(invocation_id="inv-resume-expired")
        receipt = self.processing_store.record_external_event(self.external_event(queued))
        task_id = receipt["resume_task"]["task_id"]
        claimed = self.processing_store.claim_next_task(
            task_type="langgraph_resume",
            worker_id="worker-a",
            lease_seconds=5,
        )
        self.assertEqual(claimed["task_id"], task_id)
        claimed["lease_until"] = "2020-01-01T00:00:00+00:00"
        with self.processing_store._connect() as connection:
            connection.execute(
                """
                update agent_tasks
                set lease_until = ?,
                    task_json = ?
                where task_id = ?
                """,
                (
                    claimed["lease_until"],
                    self.processing_store._to_json(claimed),
                    task_id,
                ),
            )

        reclaimed = self.processing_store.claim_next_task(
            task_type="langgraph_resume",
            worker_id="worker-b",
            lease_seconds=5,
        )

        self.assertEqual(reclaimed["task_id"], task_id)
        self.assertEqual(reclaimed["worker_id"], "worker-b")
        self.assertEqual(reclaimed["attempt"], 2)
        self.assertTrue(any(item["event"] == "task_lease_reclaimed" for item in reclaimed["audit"]))

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

    def test_runtime_overview_requires_async_worker_heartbeats(self) -> None:
        overview = self.processing_store.overview()

        self.assertEqual(overview["runtime"]["status"], "error")
        self.assertTrue(any("Outbox publisher" in item for item in overview["runtime"]["issues"]))

        self.processing_store.record_runtime_heartbeat(
            role="outbox_publisher",
            display_name="Outbox publisher",
            worker_id="publisher-test",
            topic=DEFAULT_ASYNC_TOOL_COMMAND_TOPIC,
        )
        self.processing_store.record_runtime_heartbeat(
            role="tool_worker",
            display_name="Tool command worker",
            worker_id="tool-worker-test",
            topic=DEFAULT_ASYNC_TOOL_COMMAND_TOPIC,
        )
        self.processing_store.record_runtime_heartbeat(
            role="external_event_worker",
            display_name="External event worker",
            worker_id="event-worker-test",
            topic=DEFAULT_EXTERNAL_EVENT_TOPIC,
        )
        self.processing_store.record_runtime_heartbeat(
            role="agent_task_worker",
            display_name="Agent task worker",
            worker_id="agent-task-worker-test",
            topic="agent.tasks",
        )

        overview = self.processing_store.overview()

        self.assertEqual(overview["runtime"]["status"], "ok")
        self.assertEqual(
            {item["role"]: item["status"] for item in overview["runtime"]["required_components"]},
            {
                "outbox_publisher": "ok",
                "tool_worker": "ok",
                "external_event_worker": "ok",
                "agent_task_worker": "ok",
            },
        )

    def test_async_delivery_snapshot_explains_command_execution_root_cause(self) -> None:
        queued = self.enqueue_command()
        async_wait = {
            "wait_id": queued["wait"]["wait_id"],
            "correlation_id": queued["command"]["idempotency_key"],
            "command_id": queued["command"]["command_id"],
            "topic": DEFAULT_ASYNC_TOOL_COMMAND_TOPIC,
        }

        queued_snapshot = self.processing_store.async_tool_delivery_snapshot(async_wait)

        self.assertEqual(queued_snapshot["status"], "queued_in_outbox")
        self.assertEqual(queued_snapshot["severity"], "pending")
        self.assertIn("ожидает публикации publisher-ом", queued_snapshot["message"])
        self.assertIn("еще не обработал", queued_snapshot["root_cause"])
        self.assertEqual(queued_snapshot["outbox"]["status"], "pending")
        self.assertIsNone(queued_snapshot["tool_command_receipt"])

        producer = FakeProducer()
        OutboxPublisher(self.processing_store, producer, worker_id="test-publisher").publish_batch(
            topics=[DEFAULT_ASYNC_TOOL_COMMAND_TOPIC]
        )

        published_snapshot = self.processing_store.async_tool_delivery_snapshot(async_wait)

        self.assertEqual(published_snapshot["status"], "published_to_kafka")
        self.assertEqual(published_snapshot["outbox"]["status"], "published")
        self.assertIn("ToolCommandWorker", published_snapshot["root_cause"])

        ToolCommandWorker(
            self.processing_store,
            FakeDispatcher(status="success"),
            worker_id="test-worker",
        ).process_command(queued["command"])

        waiting_snapshot = self.processing_store.async_tool_delivery_snapshot(async_wait)

        self.assertEqual(waiting_snapshot["status"], "waiting_external_event")
        self.assertEqual(waiting_snapshot["tool_command_receipt"]["status"], "completed")
        self.assertIn("финальный ExternalEvent еще не получен", waiting_snapshot["root_cause"])

        self.processing_store.record_external_event(
            self.external_event(
                queued,
                status="progress",
                event_id="evt-runbook-progress",
                result={
                    "runbook_status": "PROGRESS",
                    "message": "Проверка продолжается.",
                    "polling_diagnostic": {
                        "current_status": "polling",
                        "checked_resource": "n8n_mail_index",
                        "poll_iteration": 1,
                        "mailbox_indexed_count": 1,
                        "match_count": 0,
                    },
                },
            )
        )

        progress_snapshot = self.processing_store.async_tool_delivery_snapshot(async_wait)

        self.assertEqual(progress_snapshot["status"], "external_event_progress")
        self.assertEqual(progress_snapshot["severity"], "pending")
        self.assertIn("n8n workflow выполняется", progress_snapshot["message"])
        self.assertEqual(progress_snapshot["external_event_receipts"][0]["status"], "progress")
        self.assertEqual(
            progress_snapshot["external_event_receipts"][0]["result"]["polling_diagnostic"]["match_count"],
            0,
        )

        self.processing_store.record_external_event(self.external_event(queued))

        completed_snapshot = self.processing_store.async_tool_delivery_snapshot(async_wait)

        self.assertEqual(completed_snapshot["status"], "external_event_received")
        self.assertEqual(completed_snapshot["external_event_receipts"][0]["status"], "success")

    def test_async_delivery_snapshot_explains_n8n_launch_rejection(self) -> None:
        queued = self.enqueue_command()
        async_wait = {
            "wait_id": queued["wait"]["wait_id"],
            "correlation_id": queued["command"]["idempotency_key"],
            "command_id": queued["command"]["command_id"],
            "topic": DEFAULT_ASYNC_TOOL_COMMAND_TOPIC,
        }

        ToolCommandWorker(
            self.processing_store,
            FakeDispatcher(
                status="error",
                error_code="invalid_callback_url",
                error_message="callback_url не соответствует политике безопасности.",
            ),
            worker_id="test-worker",
        ).process_command(queued["command"])

        snapshot = self.processing_store.async_tool_delivery_snapshot(async_wait)

        self.assertEqual(snapshot["status"], "external_event_failed")
        self.assertEqual(snapshot["severity"], "error")
        self.assertIn("ошибочный внешний результат", snapshot["message"])
        self.assertIn("не завершилось успешно", snapshot["root_cause"])
        self.assertEqual(snapshot["tool_command_receipt"]["tool_result_error"]["code"], "invalid_callback_url")

    def test_async_delivery_snapshot_marks_old_outbox_command_as_stale(self) -> None:
        queued = self.enqueue_command()
        async_wait = {
            "wait_id": queued["wait"]["wait_id"],
            "correlation_id": queued["command"]["idempotency_key"],
            "command_id": queued["command"]["command_id"],
            "topic": DEFAULT_ASYNC_TOOL_COMMAND_TOPIC,
        }
        old_created_at = "2026-01-01T00:00:00Z"
        command = copy.deepcopy(queued["command"])
        command["created_at"] = old_created_at
        command["updated_at"] = old_created_at
        with self.processing_store._connect() as connection:
            connection.execute(
                """
                update processing_outbox
                set created_at = ?,
                    updated_at = ?,
                    payload_json = ?
                where idempotency_key = ?
                """,
                (
                    old_created_at,
                    old_created_at,
                    json.dumps(command, ensure_ascii=False, sort_keys=True),
                    queued["command"]["idempotency_key"],
                ),
            )

        snapshot = self.processing_store.async_tool_delivery_snapshot(async_wait)

        self.assertEqual(snapshot["status"], "queued_in_outbox")
        self.assertEqual(snapshot["severity"], "warning")
        self.assertIn("не опубликована в Kafka более", snapshot["message"])
        self.assertIn("не запущен, остановлен или не обрабатывает", snapshot["root_cause"])
        self.assertGreaterEqual(snapshot["outbox"]["age_seconds"], 10)

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
        self.assertEqual(result["tool_result"]["output"]["runbook_status"], "accepted")
        self.assertTrue(result["tool_result"]["output"]["async_delivery"])
        self.assertEqual(
            result["tool_result"]["output"]["result_transport"],
            "kafka_event",
        )
        self.assertEqual(
            result["tool_result"]["output"]["action_id"],
            "start_systemcenter_runbook",
        )
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

    def test_async_queued_result_matches_openapi_accepted_branch(self) -> None:
        accepted_schema = {
            "type": "object",
            "required": ["runbook_status", "message", "async_delivery"],
            "properties": {
                "runbook_status": {"const": "accepted"},
                "message": {"type": "string"},
                "async_delivery": {"const": True},
            },
            "additionalProperties": True,
        }
        final_schema = {
            "type": "object",
            "required": ["runbook_status", "message"],
            "properties": {
                "runbook_status": {"const": "completed"},
                "message": {"type": "string"},
            },
            "additionalProperties": True,
        }
        for tool in self.contracts.tool_catalog["tools"]:
            if tool["tool_name"] == "start_systemcenter_runbook":
                tool["result_schema"] = {"oneOf": [accepted_schema, final_schema]}
                break

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
                    "result_transport": "http_callback",
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

        self.assertEqual(result["tool_result"]["output"]["runbook_status"], "accepted")
        self.assertTrue(result["tool_result"]["output"]["async_delivery"])
        self.assertIn("async_wait", result["tool_result"]["extensions"])
        self.assertEqual(result["tool_result"]["extensions"]["async_delivery"]["status"], "queued_in_outbox")
        self.assertEqual(result["tool_result"]["extensions"]["diagnostic_status"], "queued_in_outbox")

    def test_analyze_creates_processing_context_before_async_wait(self) -> None:
        workflow = TicketWorkflow(
            contracts=self.contracts,
            case_store=self.case_store,
            config_store=self.config_store,
            processing_store=self.processing_store,
        )
        ticket = {
            "ticket_id": "ticket-analyze-async-n8n",
            "user": "ivanov",
            "service": "account",
            "description": "Нужен сброс пароля через ранбук.",
            "priority": "p3",
            "scenario": "action",
            "debug_bypass_policy_gates": True,
            "debug_run_mode": "operator_full_debug",
            "decision_override": {
                "schema_version": "1.0",
                "decision": {
                    "type": "action_proposed",
                    "summary": "Запустить async n8n ReAct-вызов.",
                    "confidence": 1,
                },
                "operator_message": "Выполняется async n8n ReAct-вызов.",
                "internal_reasoning_summary": "Тест проверяет durable context до external wait.",
                "citations": [],
                "proposed_actions": [
                    {
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
                                "result_transport": "http_callback",
                            },
                        },
                    }
                ],
            },
        }

        analysis = workflow.analyze(ticket)

        wait_id = analysis["tool_results"][0]["extensions"]["async_wait"]["wait_id"]
        case = self.case_store.require(analysis["case_id"])
        run = self.processing_store.latest_run(analysis["case_id"])
        wait = self.processing_store.require_wait(wait_id)
        self.assertEqual(case["tool_results"][0]["output"]["runbook_status"], "accepted")
        self.assertEqual(analysis["tool_results"][0]["extensions"]["async_delivery"]["status"], "queued_in_outbox")
        self.assertEqual(run["status"], "waiting")
        self.assertEqual(wait["status"], "open")

    def test_analyze_operator_approval_policy_still_dispatches_async_action(self) -> None:
        workflow = TicketWorkflow(
            contracts=self.contracts,
            case_store=self.case_store,
            config_store=self.config_store,
            processing_store=self.processing_store,
        )
        ticket = {
            "ticket_id": "ticket-analyze-async-needs-approval",
            "user": "ivanov",
            "service": "account",
            "description": "Нужен сброс пароля через ранбук.",
            "priority": "p3",
            "scenario": "action",
            "decision_override": {
                "schema_version": "1.0",
                "decision": {
                    "type": "action_proposed",
                    "summary": "Запустить async n8n ReAct-вызов.",
                    "confidence": 1,
                },
                "operator_message": "Нужно согласование async n8n ReAct-вызова.",
                "internal_reasoning_summary": "Тест проверяет, что preflight approval не создает external wait.",
                "citations": [],
                "proposed_actions": [
                    {
                        "tool_name": "start_systemcenter_runbook",
                        "action_id": "act-runbook-needs-approval",
                        "action_type": "action",
                        "parameters": {
                            "runbook_code": "password_reset",
                            "user_login": "ivanov",
                        },
                        "reason": "Запустить ранбук.",
                        "risk_level": "medium",
                        "expected_effect": "Ранбук будет поставлен в очередь после согласования.",
                        "requires_state_change": True,
                        "extensions": {
                            "endpoint_id": "n8n",
                            "operation_id": "start_systemcenter_runbook",
                            "completion_policy": {
                                "mode": "external_event",
                                "max_wait_seconds": 3600,
                                "timeout_action": "escalate_operator",
                                "expected_event_type": "start_systemcenter_runbook_completed",
                                "result_transport": "http_callback",
                            },
                        },
                    }
                ],
            },
        }

        analysis = workflow.analyze(ticket)

        run = self.processing_store.latest_run(analysis["case_id"])
        waits = self.processing_store.list_waits(case_id=analysis["case_id"])["waits"]
        outbox = self.processing_store.list_outbox(case_id=analysis["case_id"])["messages"]
        self.assertEqual(analysis["workflow_state"]["id"], "action_execution_requested")
        self.assertEqual(analysis["execution_policy_results"][0]["execution_mode"], "operator_approval")
        self.assertEqual(analysis["tool_results"][0]["status"], "success")
        self.assertEqual(run["status"], "waiting")
        self.assertFalse(any(wait["wait_type"] == "operator_approval" for wait in waits))
        self.assertTrue(any(wait["wait_type"] == "external_event_wait" for wait in waits))
        self.assertTrue(any(message["event_type"] == "async_tool_invocation_requested" for message in outbox))
        self.assertEqual(analysis["approval_requests"], [])

    def test_generated_runbook_action_has_contractual_n8n_launch(self) -> None:
        workflow = TicketWorkflow(
            contracts=self.contracts,
            case_store=self.case_store,
            config_store=self.config_store,
            processing_store=self.processing_store,
        )
        decision = workflow._runbook_decision({"service": "billing-worker"})
        action = decision["proposed_actions"][0]
        policy_result = {
            "schema_version": "1.0",
            "action_id": action["action_id"],
            "tool_name": action["tool_name"],
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

        self.assertEqual(result["invocation"]["endpoint_id"], "n8n")
        self.assertEqual(result["invocation"]["adapter_type"], "n8n_webhook")
        self.assertEqual(
            result["invocation"]["extensions"]["async_callback"]["result_transport"],
            "kafka_event",
        )
        self.assertEqual(
            result["invocation"]["extensions"]["async_callback"]["result_topic"],
            DEFAULT_EXTERNAL_EVENT_TOPIC,
        )

    def test_profile_launch_defaults_to_n8n_workflow_kafka_result_topic(self) -> None:
        profile = {
            "profile_id": "profile.runbook",
            "display_name": "Runbook profile",
            "enrichment_steps": [
                {
                    "step_id": "step1",
                    "step_name": "Runbook",
                    "react_call": "start_systemcenter_runbook",
                    "endpoint_id": "n8n",
                    "operation_id": "start_systemcenter_runbook",
                    "completion_policy": {
                        "mode": "external_event",
                        "max_wait_seconds": 3600,
                        "timeout_action": "escalate_operator",
                        "expected_event_type": "start_systemcenter_runbook_completed",
                    },
                    "parameter_mapping": {"runbook_code": "constant:restart_service"},
                    "on_error": "escalate_operator",
                }
            ],
        }

        launches = self.config_store._profile_tool_launches([profile])

        self.assertEqual(launches[0]["endpoint_id"], "n8n")
        self.assertEqual(launches[0]["completion_policy"]["result_transport"], "kafka_event")
        self.assertEqual(launches[0]["completion_policy"]["result_topic"], DEFAULT_EXTERNAL_EVENT_TOPIC)

    def test_default_async_policy_uses_operation_result_delivery_metadata(self) -> None:
        operation = {
            "async_event_contracts": {
                "monitor_provider_channel_repair_completed": {
                    "contract_status": "valid",
                    "result_schema": {"type": "object", "additionalProperties": True},
                }
            },
            "extensions": {
                "result_delivery": {
                    "default_transport": "kafka_event",
                    "default_result_topic": "external.events",
                }
            },
        }

        policy = default_async_completion_policy_for_operation(
            operation,
            operation_id="monitor_provider_channel_repair",
        )

        self.assertIsNotNone(policy)
        self.assertEqual(policy["mode"], "external_event")
        self.assertEqual(policy["expected_event_type"], "monitor_provider_channel_repair_completed")
        self.assertEqual(policy["result_transport"], "kafka_event")
        self.assertEqual(policy["result_topic"], "external.events")

    def test_profile_launch_infers_external_event_for_async_operation(self) -> None:
        profile = {
            "profile_id": "profile.runbook",
            "display_name": "Runbook profile",
            "enrichment_steps": [
                {
                    "step_id": "step1",
                    "step_name": "Runbook",
                    "react_call": "start_systemcenter_runbook",
                    "endpoint_id": "n8n",
                    "operation_id": "start_systemcenter_runbook",
                    "parameter_mapping": {"runbook_code": "constant:restart_service"},
                    "on_error": "escalate_operator",
                }
            ],
        }

        launches = self.config_store._profile_tool_launches([profile])

        self.assertEqual(launches[0]["completion_policy"]["mode"], "external_event")
        self.assertEqual(
            launches[0]["completion_policy"]["expected_event_type"],
            "start_systemcenter_runbook_completed",
        )
        self.assertEqual(launches[0]["completion_policy"]["result_transport"], "kafka_event")

    def test_runtime_overrides_sync_policy_for_async_operation(self) -> None:
        workflow = TicketWorkflow(
            contracts=self.contracts,
            case_store=self.case_store,
            config_store=self.config_store,
            processing_store=self.processing_store,
        )
        action = {
            "action_id": "act-runbook-sync-policy",
            "tool_name": "start_systemcenter_runbook",
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
                    "mode": "sync",
                    "max_wait_seconds": 0,
                    "timeout_action": "resume_agent",
                },
            },
        }
        policy_result = {
            "schema_version": "1.0",
            "action_id": "act-runbook-sync-policy",
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

        self.assertEqual(result["tool_result"]["status"], "success")
        self.assertTrue(result["tool_result"]["output"]["async_delivery"])
        self.assertIn("async_wait", result["tool_result"]["extensions"])
        self.assertEqual(
            result["tool_result"]["extensions"]["async_wait"]["completion_policy"]["mode"],
            "external_event",
        )
        outbox = self.processing_store.list_outbox(case_id=self.case["case_id"])["messages"]
        self.assertTrue(any(message["event_type"] == "async_tool_invocation_requested" for message in outbox))

    def test_runtime_reports_missing_async_contract_for_ack_like_operation(self) -> None:
        endpoints = copy.deepcopy(self.config_store.active_payload("integration_endpoints"))
        n8n = next(item for item in endpoints["endpoints"] if item["endpoint_id"] == "n8n")
        operation = n8n["operations"]["start_systemcenter_runbook"]
        operation["async_event_contracts"] = {}
        operation["response_schema"] = {
            "type": "object",
            "required": ["runbook_status", "message", "async_delivery"],
            "properties": {
                "runbook_status": {"type": "string"},
                "message": {"type": "string"},
                "async_delivery": {"type": "boolean"},
            },
            "additionalProperties": True,
        }
        workflow = TicketWorkflow(
            contracts=self.contracts,
            case_store=self.case_store,
            config_store=self.config_store,
            processing_store=self.processing_store,
        )
        action = {
            "action_id": "act-runbook-missing-async-contract",
            "tool_name": "start_systemcenter_runbook",
            "action_type": "action",
            "parameters": {
                "runbook_code": "password_reset",
                "user_login": "ivanov",
            },
            "reason": "Запустить ранбук.",
            "risk_level": "medium",
            "expected_effect": "Ранбук должен быть асинхронным.",
            "requires_state_change": True,
            "extensions": {
                "endpoint_id": "n8n",
                "operation_id": "start_systemcenter_runbook",
                "completion_policy": {
                    "mode": "sync",
                    "max_wait_seconds": 0,
                    "timeout_action": "resume_agent",
                },
            },
        }
        policy_result = {
            "schema_version": "1.0",
            "action_id": "act-runbook-missing-async-contract",
            "tool_name": "start_systemcenter_runbook",
            "execution_mode": "operator_approval",
            "allowed": True,
            "approval_required": True,
            "policy_rule_id": "runbooks.mvp.require_operator_approval",
            "risk_level": "medium",
            "reason": "Тестовая политика требует согласования оператора.",
        }

        with self.config_store.active_payload_overrides({"integration_endpoints": endpoints}):
            result = workflow.dispatch_tool(
                action,
                policy_result,
                case_id=self.case["case_id"],
                ticket_id=self.case["ticket_id"],
                approved_by_operator=True,
                operator_id="operator-1",
            )

        self.assertEqual(result["tool_result"]["status"], "error")
        self.assertEqual(result["tool_result"]["error"]["code"], "async_event_contract_missing")
        self.assertEqual(result["tool_result"]["extensions"]["diagnostic_status"], "async_event_contract_missing")
        outbox = self.processing_store.list_outbox(case_id=self.case["case_id"])["messages"]
        self.assertFalse(any(message["event_type"] == "async_tool_invocation_requested" for message in outbox))

    def test_profile_validation_rejects_sync_policy_for_async_operation(self) -> None:
        profile = {
            "profile_id": "profile.runbook",
            "display_name": "Runbook profile",
            "status": "active",
            "description": "Проверочный профиль запуска ранбука.",
            "slot_schema_id": "slot.custom_copy",
            "use_llm_after_steps": False,
            "max_attempts": 1,
            "enrichment_steps": [
                {
                    "step_id": "step1",
                    "step_name": "Runbook",
                    "react_call": "start_systemcenter_runbook",
                    "endpoint_id": "n8n",
                    "operation_id": "start_systemcenter_runbook",
                    "completion_policy": {
                        "mode": "sync",
                        "max_wait_seconds": 0,
                        "timeout_action": "resume_agent",
                    },
                    "parameter_mapping": {"runbook_code": "constant:restart_service"},
                    "on_error": "escalate_operator",
                }
            ],
            "output_slots_order": [],
            "llm_resolution_script": {
                "script_text": "Заполни выходные слоты.",
                "response_contract": {},
            },
            "human_resolution_policy": {
                "action": "escalate_operator",
                "message_template": "Передать оператору.",
            },
        }

        validation = self.config_store.validate_payload(
            "attribute_resolution_profiles",
            {"schema_version": "1.0", "profiles": [profile]},
        )

        self.assertEqual(validation["status"], "invalid")
        self.assertTrue(
            any("completion_policy.mode=sync" in error and "Runbook profile" in error for error in validation["errors"]),
            validation["errors"],
        )

    def test_broken_async_event_contract_is_rejected_when_profile_uses_it(self) -> None:
        endpoints = copy.deepcopy(self.config_store.active_payload("integration_endpoints"))
        n8n = next(item for item in endpoints["endpoints"] if item["endpoint_id"] == "n8n")
        contract = n8n["operations"]["start_systemcenter_runbook"]["async_event_contracts"][
            "start_systemcenter_runbook_completed"
        ]
        contract["contract_status"] = "broken"
        profile_override = {
            "schema_version": "1.0",
            "profiles": [
                {
                    "profile_id": "profile.runbook",
                    "enrichment_steps": [
                        {
                            "step_id": "step1",
                            "react_call": "start_systemcenter_runbook",
                            "endpoint_id": "n8n",
                            "operation_id": "start_systemcenter_runbook",
                            "completion_policy": {
                                "mode": "external_event",
                                "max_wait_seconds": 3600,
                                "timeout_action": "escalate_operator",
                                "expected_event_type": "start_systemcenter_runbook_completed",
                                "result_transport": "kafka_event",
                            },
                        }
                    ],
                }
            ],
        }

        validation = self.config_store.validate_payload(
            "integration_endpoints",
            endpoints,
            active_overrides={"attribute_resolution_profiles": profile_override},
        )

        self.assertEqual(validation["status"], "invalid")
        self.assertTrue(any("profile.runbook.step1" in error for error in validation["errors"]))

    def test_endpoint_transport_security_rejects_delivery_selector(self) -> None:
        payload = copy.deepcopy(self.config_store.active_payload("integration_endpoints"))
        endpoint = next(item for item in payload["endpoints"] if item["endpoint_id"] == "n8n")
        endpoint.setdefault("extensions", {}).setdefault("transport_security", {})["selected_transport"] = "kafka_event"

        validation = self.config_store.validate_payload("integration_endpoints", payload)

        self.assertEqual(validation["status"], "invalid")
        self.assertTrue(
            any("selected_transport" in error or "False schema" in error for error in validation["errors"])
        )

    def test_n8n_endpoint_requires_kafka_security_metadata(self) -> None:
        payload = copy.deepcopy(self.config_store.active_payload("integration_endpoints"))
        endpoint = next(item for item in payload["endpoints"] if item["endpoint_id"] == "n8n")
        endpoint["extensions"]["transport_security"].pop("kafka", None)

        validation = self.config_store.validate_payload("integration_endpoints", payload)

        self.assertEqual(validation["status"], "invalid")
        self.assertTrue(any("transport_security.kafka" in error for error in validation["errors"]))

    def test_n8n_endpoint_accepts_credential_configured_transport_policy(self) -> None:
        payload = copy.deepcopy(self.config_store.active_payload("integration_endpoints"))
        endpoint = next(item for item in payload["endpoints"] if item["endpoint_id"] == "n8n")
        transport = endpoint["extensions"]["transport_security"]
        transport["http"]["policy"] = "credential_configured"
        transport["kafka"]["policy"] = "credential_configured"

        validation = self.config_store.validate_payload("integration_endpoints", payload)

        self.assertEqual(validation["status"], "valid", validation["errors"])

    def test_n8n_endpoint_rejects_unknown_transport_policy(self) -> None:
        payload = copy.deepcopy(self.config_store.active_payload("integration_endpoints"))
        endpoint = next(item for item in payload["endpoints"] if item["endpoint_id"] == "n8n")
        endpoint["extensions"]["transport_security"]["kafka"]["policy"] = "inline_secret"

        validation = self.config_store.validate_payload("integration_endpoints", payload)

        self.assertEqual(validation["status"], "invalid")
        self.assertTrue(any("transport_security.kafka.policy" in error for error in validation["errors"]))

    def test_n8n_workflow_allows_empty_operations_after_endpoint_operation_cleanup(self) -> None:
        payload = copy.deepcopy(self.config_store.active_payload("n8n_workflows"))
        workflow = next(item for item in payload["workflows"] if item["workflow_id"] == "zabbix_problem_processing")
        workflow["operations"] = []

        validation = self.config_store.validate_payload("n8n_workflows", payload)

        self.assertEqual(validation["status"], "valid", validation["errors"])

    def test_n8n_workflow_rejects_unknown_endpoint_operation(self) -> None:
        payload = copy.deepcopy(self.config_store.active_payload("n8n_workflows"))
        workflow = next(item for item in payload["workflows"] if item["workflow_id"] == "zabbix_problem_processing")
        workflow["operations"] = ["missing_legacy_operation"]

        validation = self.config_store.validate_payload("n8n_workflows", payload)

        self.assertEqual(validation["status"], "invalid")
        self.assertTrue(any("missing_legacy_operation" in error for error in validation["errors"]))

    def test_default_catalog_contains_provider_channel_repair_monitor(self) -> None:
        payload = self.config_store.active_payload("n8n_workflows")
        workflow = next(
            item for item in payload["workflows"] if item["workflow_id"] == "provider_channel_repair_monitor"
        )

        self.assertEqual(workflow["endpoint_id"], "n8n")
        self.assertIn("monitor_provider_channel_repair", workflow["operations"])
        self.assertEqual(workflow["result_delivery"]["default_transport"], "kafka_event")
        self.assertEqual(workflow["result_delivery"]["default_result_topic"], DEFAULT_EXTERNAL_EVENT_TOPIC)

    def test_operation_uses_endpoint_level_n8n_result_delivery_defaults(self) -> None:
        workflow = TicketWorkflow(
            contracts=self.contracts,
            case_store=self.case_store,
            config_store=self.config_store,
            processing_store=self.processing_store,
        )
        payload = {
            "schema_version": "1.0",
            "workflows": [
                {
                    "workflow_id": "provider_channel_failure",
                    "display_name": "Сбой канала провайдера",
                    "business_scenario": "provider_channel_failure",
                    "endpoint_id": "n8n",
                    "callback_endpoint_id": "n8n",
                    "enabled": True,
                    "operations": [],
                    "result_delivery": {
                        "canonical_event": "ServiceDesk ExternalEvent",
                        "supported_transports": ["http_callback", "kafka_event", "both"],
                        "default_transport": "kafka_event",
                        "default_result_topic": "external.events",
                    },
                    "management": {
                        "restart_supported": False,
                        "cancel_supported": False,
                        "execution_history_supported": False,
                    },
                }
            ],
        }
        activated_at = "2026-06-29T12:00:00Z"
        version = {
            "schema_version": "1.0",
            "version_id": "cfgver-abcdef123456",
            "domain": "n8n_workflows",
            "payload": payload,
            "source_draft_id": "test",
            "activated_by": "test",
            "activated_at": activated_at,
            "validation": {"schema_version": "1.0", "status": "forced"},
            "regression": {"schema_version": "1.0", "status": "skipped"},
        }
        with self.config_store._connect() as connection:
            connection.execute(
                """
                insert into config_versions (
                    version_id, domain, version_json, source_draft_id, activated_by, activated_at
                )
                values (?, ?, ?, ?, ?, ?)
                """,
                (
                    version["version_id"],
                    version["domain"],
                    self.config_store._to_json(version),
                    version["source_draft_id"],
                    version["activated_by"],
                    version["activated_at"],
                ),
            )
            connection.execute(
                "insert or replace into config_active (domain, version_id, activated_at) values (?, ?, ?)",
                ("n8n_workflows", version["version_id"], activated_at),
            )

        defaults = workflow._delivery_defaults_for_operation("n8n", "monitor_provider_channel_repair")

        self.assertEqual(defaults["result_transport"], "kafka_event")
        self.assertEqual(defaults["result_topic"], "external.events")

    def test_action_completion_policy_preserves_explicit_transport(self) -> None:
        payload = {
            "schema_version": "1.0",
            "workflows": [
                {
                    "workflow_id": "endpoint_delivery_defaults",
                    "display_name": "Endpoint delivery defaults",
                    "business_scenario": "endpoint_delivery_defaults",
                    "endpoint_id": "n8n",
                    "callback_endpoint_id": "n8n",
                    "enabled": True,
                    "operations": [],
                    "result_delivery": {
                        "canonical_event": "ServiceDesk ExternalEvent",
                        "supported_transports": ["http_callback", "kafka_event", "both"],
                        "default_transport": "kafka_event",
                        "default_result_topic": "external.events",
                    },
                    "management": {
                        "restart_supported": False,
                        "cancel_supported": False,
                        "execution_history_supported": False,
                    },
                }
            ],
        }
        activated_at = "2026-06-29T12:05:00Z"
        version = {
            "schema_version": "1.0",
            "version_id": "cfgver-fedcba654321",
            "domain": "n8n_workflows",
            "payload": payload,
            "source_draft_id": "test",
            "activated_by": "test",
            "activated_at": activated_at,
            "validation": {"schema_version": "1.0", "status": "forced"},
            "regression": {"schema_version": "1.0", "status": "skipped"},
        }
        with self.config_store._connect() as connection:
            connection.execute(
                """
                insert into config_versions (
                    version_id, domain, version_json, source_draft_id, activated_by, activated_at
                )
                values (?, ?, ?, ?, ?, ?)
                """,
                (
                    version["version_id"],
                    version["domain"],
                    self.config_store._to_json(version),
                    version["source_draft_id"],
                    version["activated_by"],
                    version["activated_at"],
                ),
            )
            connection.execute(
                "insert or replace into config_active (domain, version_id, activated_at) values (?, ?, ?)",
                ("n8n_workflows", version["version_id"], activated_at),
            )
        workflow = TicketWorkflow(
            contracts=self.contracts,
            case_store=self.case_store,
            config_store=self.config_store,
            processing_store=self.processing_store,
        )
        action = {
            "tool_name": "start_systemcenter_runbook",
            "action_id": "act-runbook-stale-policy",
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
                    "result_transport": "http_callback",
                },
            },
        }
        policy_result = {
            "schema_version": "1.0",
            "action_id": "act-runbook-stale-policy",
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

        wait = self.processing_store.require_wait(result["tool_result"]["extensions"]["async_wait"]["wait_id"])
        self.assertEqual(result["tool_result"]["output"]["result_transport"], "http_callback")
        self.assertEqual(result["invocation"]["extensions"]["async_callback"]["result_transport"], "http_callback")
        self.assertEqual(wait["payload"]["result_transport"], "http_callback")
        self.assertEqual(wait["payload"]["result_topic"], DEFAULT_EXTERNAL_EVENT_TOPIC)

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

    def test_async_delivery_snapshot_reports_external_event_business_error(self) -> None:
        queued = self.enqueue_command(invocation_id="inv-provider-error", result_transport="kafka_event")
        event = self.external_event(
            queued,
            status="error",
            event_id="provider_channel_repair_error",
        )
        event["error"] = {
            "code": "router_not_found",
            "message": "routerG не найден по Description, hostname или Code.",
        }
        event["result"] = {
            "runbook_status": "ERROR",
            "message": "routerG не найден по Description, hostname или Code.",
            "host": "ARM C2M-CITY-20260523-ARM-177-13",
            "email_dispatch": None,
            "provider_email_context": None,
        }

        self.processing_store.record_external_event(
            event,
            received_transport="kafka_event",
            source_topic=DEFAULT_EXTERNAL_EVENT_TOPIC,
        )
        snapshot = self.processing_store.async_tool_delivery_snapshot(
            {
                "wait_id": queued["wait"]["wait_id"],
                "correlation_id": queued["wait"]["correlation_id"],
            }
        )

        self.assertEqual(snapshot["status"], "external_event_failed")
        self.assertIn("router_not_found", snapshot["message"])
        self.assertIn("routerG не найден", snapshot["message"])
        self.assertNotIn("'accepted': True", snapshot["message"])
        self.assertEqual(snapshot["external_event_receipts"][0]["error"]["code"], "router_not_found")
        self.assertIsNone(snapshot["external_event_receipts"][0]["result"]["email_dispatch"])

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
