from __future__ import annotations

import copy
import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .action_gates import DEFAULT_STATE_DB_PATH, utc_now
from .cases import CaseNotFound, CaseStore
from .privacy import redact_for_llm


KAFKA_TOPICS = [
    {
        "topic": "case.inbound-events",
        "description": "Входящие сообщения из каналов: чат, портал, email, service desk.",
        "key": "case_id",
    },
    {
        "topic": "case.events",
        "description": "Append-only события кейса и рабочего процесса.",
        "key": "case_id",
    },
    {
        "topic": "agent.tasks",
        "description": "Задачи агентам/LangGraph runtime.",
        "key": "case_id",
    },
    {
        "topic": "agent.results",
        "description": "Результаты обработки агентских задач.",
        "key": "case_id",
    },
    {
        "topic": "tool.commands",
        "description": "Команды на выполнение ReAct-вызовов и интеграций.",
        "key": "case_id",
    },
    {
        "topic": "tool.results",
        "description": "Нормализованные результаты ReAct-вызовов.",
        "key": "case_id",
    },
    {
        "topic": "timer.commands",
        "description": "Команды на постановку таймеров ожидания.",
        "key": "case_id",
    },
    {
        "topic": "timer.events",
        "description": "События таймеров, напоминаний и timeout.",
        "key": "case_id",
    },
    {
        "topic": "integration.events",
        "description": "Callback и события внешних endpoint adapters.",
        "key": "case_id",
    },
    {
        "topic": "external.events",
        "description": "Входящие результаты внешних асинхронных операций в каноническом ExternalEvent contract.",
        "key": "case_id",
    },
    {
        "topic": "audit.events",
        "description": "События аудита административных и runtime-действий.",
        "key": "actor_id",
    },
    {
        "topic": "dead-letter",
        "description": "Сообщения, которые не удалось обработать без потери контекста.",
        "key": "case_id",
    },
]

ACTIVE_RUN_STATUSES = {"queued", "running", "waiting"}
TERMINAL_RUN_STATUSES = {"completed", "failed", "cancelled", "escalated", "timed_out"}
ACTIVE_TASK_STATUSES = {"queued", "running", "leased"}
RETRYABLE_TASK_STATUSES = {"failed", "expired", "cancelled", "blocked"}
ACTIVE_WAIT_STATUSES = {"open", "reminded"}
EXTERNAL_EVENT_TERMINAL_STATUSES = {"success", "error", "timeout", "cancelled"}
EXTERNAL_EVENT_WAIT_STATUS = {
    "success": "completed",
    "error": "failed",
    "timeout": "timed_out",
    "cancelled": "cancelled",
}
WAIT_ORIGIN_KINDS = {"react_call", "client_question", "approval", "timer", "system_policy", "unknown"}
DEFAULT_ASYNC_TOOL_COMMAND_TOPIC = "tool.commands"
DEFAULT_EXTERNAL_EVENT_TOPIC = "external.events"
DEFAULT_EXTERNAL_EVENT_SOURCE = "n8n"
ASYNC_OUTBOX_STALE_SECONDS = 10
RUNTIME_HEARTBEAT_STALE_SECONDS = 30
RUNTIME_REQUIRED_COMPONENTS = (
    {
        "role": "outbox_publisher",
        "display_name": "Outbox publisher",
        "topic_env": "TOOL_COMMAND_TOPIC",
        "default_topic": DEFAULT_ASYNC_TOOL_COMMAND_TOPIC,
    },
    {
        "role": "tool_worker",
        "display_name": "Tool command worker",
        "topic_env": "TOOL_COMMAND_TOPIC",
        "default_topic": DEFAULT_ASYNC_TOOL_COMMAND_TOPIC,
    },
    {
        "role": "external_event_worker",
        "display_name": "External event worker",
        "topic_env": "EXTERNAL_EVENT_TOPIC",
        "default_topic": DEFAULT_EXTERNAL_EVENT_TOPIC,
    },
    {
        "role": "agent_task_worker",
        "display_name": "Agent task worker",
        "topic_env": "AGENT_TASK_TOPIC",
        "default_topic": "agent.tasks",
    },
)
EXTERNAL_EVENT_RESULT_TRANSPORTS = {"http_callback", "kafka_event", "both"}
EXTERNAL_EVENT_TRANSPORT_ALLOWLIST = {
    "http_callback": {"http_callback"},
    "kafka_event": {"kafka_event"},
    "both": {"http_callback", "kafka_event"},
}
SENSITIVE_ORIGIN_KEYWORDS = (
    "token",
    "password",
    "passwd",
    "pwd",
    "secret",
    "key",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "session",
    "токен",
    "пароль",
    "секрет",
    "ключ",
    "авторизация",
    "куки",
    "сессия",
)


class ProcessingNotFound(KeyError):
    pass


class ProcessingConflict(ValueError):
    pass


class ExternalEventIdempotencyConflict(ProcessingConflict):
    pass


def new_run_id() -> str:
    return f"run-{uuid.uuid4().hex[:12]}"


def new_task_id() -> str:
    return f"task-{uuid.uuid4().hex[:12]}"


def new_wait_id() -> str:
    return f"wait-{uuid.uuid4().hex[:12]}"


def new_message_id() -> str:
    return f"msg-{uuid.uuid4().hex[:12]}"


def new_command_id() -> str:
    return f"cmd-{uuid.uuid4().hex[:12]}"


def parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def add_seconds(value: str, seconds: int) -> str:
    base = parse_utc(value) or datetime.now(UTC).replace(microsecond=0)
    return (base + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


class ProcessingStore:
    def __init__(
        self,
        case_store: CaseStore,
        db_path: str | Path | None = None,
    ):
        self.case_store = case_store
        configured_path = db_path or os.getenv("ORCHESTRATOR_STATE_DB")
        self.db_path = Path(configured_path) if configured_path else DEFAULT_STATE_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.kafka_bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "127.0.0.1:19092")
        self._ensure_schema()

    def record_analysis(
        self,
        ticket_input: dict[str, Any],
        analysis: dict[str, Any],
    ) -> dict[str, Any]:
        case_id = analysis["case_id"]
        case = self.case_store.require(case_id)
        existing_run = self.latest_run(case_id)
        if existing_run:
            if existing_run.get("extensions", {}).get("async_dispatch_in_progress"):
                return self.finalize_analysis_run(ticket_input, analysis, run=existing_run)
            return self.case_detail(case_id)

        now = utc_now()
        run_status = self._run_status_from_analysis(analysis)
        run = {
            "schema_version": "1.0",
            "run_id": new_run_id(),
            "case_id": case_id,
            "ticket_id": analysis["ticket_id"],
            "status": run_status,
            "scenario_id": ticket_input.get("scenario") or "auto",
            "current_step": self._current_step_from_analysis(analysis),
            "source": "tickets.analyze",
            "config_versions": {},
            "started_at": now,
            "updated_at": now,
            "completed_at": now if run_status in TERMINAL_RUN_STATUSES else None,
            "extensions": {
                "workflow_state_id": analysis.get("workflow_state", {}).get("id"),
                "decision_type": analysis.get("ai_decision", {}).get("decision", {}).get("type"),
            },
        }
        task = self._build_task_from_analysis(run, analysis, now)
        wait = self._build_wait_from_analysis(run, analysis, now)

        with self._connect() as connection:
            self._insert_run(connection, run)
            self._insert_task(connection, task)
            if wait:
                self._insert_wait(connection, wait)

        self._append_case_event(
            case_id,
            "processing_run_started",
            "Запуск обработки зарегистрирован в потоке обработки.",
            {
                "run_id": run["run_id"],
                "run_status": run["status"],
                "scenario_id": run["scenario_id"],
            },
        )
        self._append_case_event(
            case_id,
            "processing_task_completed",
            "Задача анализа завершена текущим синхронным исполнителем.",
            {
                "run_id": run["run_id"],
                "task_id": task["task_id"],
                "task_status": task["status"],
            },
        )
        self._enqueue(
            "case.events",
            case_id,
            "processing_run_started",
            {
                "case_id": case_id,
                "ticket_id": analysis["ticket_id"],
                "run": run,
            },
            idempotency_key=f"{case_id}:processing_run_started:{run['run_id']}",
        )
        self._enqueue(
            "agent.results",
            case_id,
            "agent_task_completed",
            {
                "case_id": case_id,
                "ticket_id": analysis["ticket_id"],
                "run_id": run["run_id"],
                "task": task,
            },
            idempotency_key=task["idempotency_key"],
        )
        if wait:
            self._append_case_event(
                case_id,
                "processing_wait_opened",
                self._wait_summary(wait),
                {
                    "run_id": run["run_id"],
                    "wait_id": wait["wait_id"],
                    "wait_type": wait["wait_type"],
                    "deadline_at": wait.get("deadline_at"),
                },
            )
            self._enqueue(
                "timer.commands" if wait["wait_type"] == "client_wait" else "case.events",
                case_id,
                "wait_opened",
                {
                    "case_id": case_id,
                    "ticket_id": analysis["ticket_id"],
                    "run_id": run["run_id"],
                    "wait": wait,
                },
                idempotency_key=f"{case_id}:wait_opened:{wait['wait_id']}",
            )

        return self.case_detail(case["case_id"])

    def record_integration_callback(self, result: dict[str, Any]) -> None:
        case = result.get("case") or {}
        case_id = case.get("case_id")
        if not case_id:
            return
        run = self.latest_run(case_id)
        now = utc_now()
        self._append_case_event(
            case_id,
            "processing_external_event_received",
            "Получено внешнее событие от integration endpoint.",
            {
                "run_id": run.get("run_id") if run else None,
                "endpoint_id": result.get("tool_result", {}).get("endpoint_id"),
                "operation_id": result.get("tool_result", {}).get("operation_id"),
                "tool_status": result.get("tool_result", {}).get("status"),
            },
        )
        self._enqueue(
            "integration.events",
            case_id,
            "integration_callback_received",
            {
                "case_id": case_id,
                "ticket_id": case.get("ticket_id"),
                "received_at": now,
                "tool_result": result.get("tool_result"),
                "workflow_state": result.get("workflow_state"),
            },
            idempotency_key=f"{case_id}:integration:{result.get('tool_result', {}).get('invocation_id', now)}",
        )

    def record_approval_decision(self, result: dict[str, Any]) -> None:
        gate = result.get("gate") or {}
        case_id = gate.get("extensions", {}).get("case_id")
        if not case_id:
            return
        run = self.latest_run(case_id)
        decision = gate.get("decision", {})
        self._append_case_event(
            case_id,
            "processing_operator_decision_received",
            "Получено решение оператора по согласованию.",
            {
                "run_id": run.get("run_id") if run else None,
                "gate_id": gate.get("gate_id"),
                "gate_status": gate.get("status"),
                "operator_id": decision.get("actor_id"),
            },
        )

    def open_external_wait(
        self,
        case_id: str,
        *,
        source: str,
        event_type: str,
        reason: str,
        wait_type: str = "external_event_wait",
        deadline_seconds: int | None = None,
        correlation_id: str | None = None,
        payload: dict[str, Any] | None = None,
        origin: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        case = self.case_store.require(case_id)
        run = self.latest_run(case_id)
        if not run:
            raise ProcessingNotFound(f"У кейса {case_id} нет processing run для ожидания.")
        if run["status"] in TERMINAL_RUN_STATUSES:
            raise ProcessingConflict(f"Запуск {run['run_id']} уже завершен в статусе {run['status']}.")

        now = utc_now()
        wait_id = new_wait_id()
        wait_payload = copy.deepcopy(payload or {})
        origin_payload = origin if origin is not None else wait_payload.pop("origin", None)
        wait_payload.setdefault("expected_event_type", event_type)
        wait_payload.setdefault("resume_policy", "resume_agent")
        wait_payload.setdefault("source", source)
        wait_correlation_id = correlation_id or f"{case_id}:{wait_type}:{run['run_id']}:{wait_id}"
        if self.active_wait_by_correlation(wait_correlation_id, case_id=case_id):
            raise ProcessingConflict(
                f"У кейса {case_id} уже есть активное ожидание с correlation_id={wait_correlation_id}."
            )
        wait_origin = self._normalize_wait_origin(
            origin_payload,
            default_kind="timer" if wait_type == "timer_wait" else "system_policy",
            reason=reason,
            wait_type=wait_type,
        )
        wait_origin.setdefault("source", source)
        wait_origin.setdefault("correlation_id", wait_correlation_id)
        wait = {
            "schema_version": "1.0",
            "wait_id": wait_id,
            "run_id": run["run_id"],
            "case_id": case_id,
            "ticket_id": case["ticket_id"],
            "wait_type": wait_type,
            "status": "open",
            "channel_id": source,
            "deadline_at": add_seconds(now, deadline_seconds) if deadline_seconds else None,
            "correlation_id": wait_correlation_id,
            "created_at": now,
            "updated_at": now,
            "reason": reason,
            "expected_event_type": event_type,
            "resume_policy": "resume_agent",
            "origin": wait_origin,
            "payload": wait_payload,
        }

        run["status"] = "waiting"
        run["current_step"] = wait_type
        run["updated_at"] = now
        run["completed_at"] = None
        self._save_run(run)
        with self._connect() as connection:
            self._insert_wait(connection, wait)

        self._append_case_event(
            case_id,
            "processing_wait_opened",
            self._wait_summary(wait),
            {
                "run_id": run["run_id"],
                "wait_id": wait_id,
                "wait_type": wait_type,
                "correlation_id": wait["correlation_id"],
                "expected_event_type": event_type,
                "source": source,
                "deadline_at": wait.get("deadline_at"),
                "origin": wait.get("origin"),
            },
        )
        self._enqueue(
            "timer.commands" if wait_type == "timer_wait" else "integration.events",
            case_id,
            "wait_opened",
            {
                "case_id": case_id,
                "ticket_id": case["ticket_id"],
                "run_id": run["run_id"],
                "wait": wait,
            },
            idempotency_key=f"{case_id}:wait_opened:{wait_id}",
        )
        return wait

    def enqueue_async_tool_command(
        self,
        invocation: dict[str, Any],
        *,
        expected_event_type: str,
        source: str = DEFAULT_EXTERNAL_EVENT_SOURCE,
        topic: str | None = None,
        result_transport: str = "http_callback",
        result_topic: str | None = None,
        contract_snapshot: dict[str, Any] | None = None,
        deadline_seconds: int | None = None,
        reason: str | None = None,
        callback_base_url: str | None = None,
    ) -> dict[str, Any]:
        case_id = invocation.get("case_id")
        if not case_id:
            raise ProcessingConflict("Асинхронный ReAct-вызов требует case_id.")
        if invocation.get("adapter_type") != "n8n_webhook":
            raise ProcessingConflict("Асинхронный worker сейчас поддерживает только adapter_type=n8n_webhook.")

        command_topic = topic or os.getenv("TOOL_COMMAND_TOPIC", DEFAULT_ASYNC_TOOL_COMMAND_TOPIC)
        if result_transport not in EXTERNAL_EVENT_RESULT_TRANSPORTS:
            raise ProcessingConflict(f"Неподдерживаемый result_transport для ExternalEvent: {result_transport}.")
        event_topic = result_topic or os.getenv("EXTERNAL_EVENT_TOPIC", DEFAULT_EXTERNAL_EVENT_TOPIC)
        command_idempotency_key = f"{case_id}:tool_command:{invocation['invocation_id']}"
        existing_message = self.outbox_message_by_idempotency_key(command_idempotency_key)
        if existing_message:
            existing_command = existing_message.get("payload") or {}
            return {
                "schema_version": "1.0",
                "wait": self.require_wait(existing_command["wait_id"]),
                "command": existing_command,
                "duplicate": True,
            }
        wait_payload = {
            "expected_event_type": expected_event_type,
            "result_transport": result_transport,
            "result_topic": event_topic,
        }
        if contract_snapshot:
            wait_payload["contract_snapshot"] = copy.deepcopy(contract_snapshot)
        wait_origin = {
            "kind": "react_call",
            "react_call": invocation.get("tool_name"),
            "endpoint_id": invocation.get("endpoint_id"),
            "operation_id": invocation.get("operation_id"),
            "parameters": invocation.get("parameters", {}),
            "result_transport": result_transport,
            "result_topic": event_topic,
        }
        if contract_snapshot:
            wait_origin["contract_snapshot"] = copy.deepcopy(contract_snapshot)
        wait = self.open_external_wait(
            case_id,
            source=source,
            event_type=expected_event_type,
            reason=reason or f"Ожидание результата ReAct-вызова {invocation.get('tool_name')}.",
            wait_type="external_event_wait",
            deadline_seconds=deadline_seconds,
            correlation_id=command_idempotency_key,
            payload=wait_payload,
            origin=wait_origin,
        )
        callback_url = self.external_event_callback_url(source, base_url=callback_base_url)
        command_id = new_command_id()
        command_invocation = copy.deepcopy(invocation)
        command_invocation.setdefault("extensions", {})
        command_invocation["extensions"]["async_callback"] = {
            "source": source,
            "callback_url": callback_url,
            "case_id": wait["case_id"],
            "ticket_id": wait["ticket_id"],
            "run_id": wait["run_id"],
            "wait_id": wait["wait_id"],
            "correlation_id": wait["correlation_id"],
            "event_type": expected_event_type,
            "idempotency_key_base": command_idempotency_key,
            "result_transport": result_transport,
            "result_topic": event_topic,
        }
        self._prepare_async_invocation_for_storage(command_invocation)
        command = {
            "schema_version": "1.0",
            "command_id": command_id,
            "command_type": "async_tool_invocation",
            "topic": command_topic,
            "case_id": wait["case_id"],
            "ticket_id": wait["ticket_id"],
            "run_id": wait["run_id"],
            "wait_id": wait["wait_id"],
            "correlation_id": wait["correlation_id"],
            "source": source,
            "expected_event_type": expected_event_type,
            "callback_url": callback_url,
            "result_transport": result_transport,
            "result_topic": event_topic,
            "idempotency_key": command_idempotency_key,
            "invocation": command_invocation,
        }
        outbox_message = self._enqueue(
            command_topic,
            wait["case_id"],
            "async_tool_invocation_requested",
            command,
            idempotency_key=command["idempotency_key"],
        )
        if (outbox_message.get("payload") or {}).get("wait_id") != wait["wait_id"]:
            raise ProcessingConflict(
                f"Команда {command['idempotency_key']} уже связана с другим ожиданием."
            )
        return {
            "schema_version": "1.0",
            "wait": wait,
            "command": command,
            "duplicate": False,
        }

    def external_event_callback_url(self, source: str, *, base_url: str | None = None) -> str:
        root = (
            base_url
            or os.getenv("ORCHESTRATOR_PUBLIC_URL")
            or f"http://127.0.0.1:{os.getenv('ORCHESTRATOR_PORT', '18088')}"
        )
        return f"{root.rstrip('/')}/external-events/{source}"

    def external_event_receipt(self, idempotency_key: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                select receipt_json
                from external_event_receipts
                where idempotency_key = ?
                """,
                (idempotency_key,),
            ).fetchone()
        return json.loads(row["receipt_json"]) if row else None

    def record_external_event(
        self,
        event: dict[str, Any],
        *,
        received_transport: str = "internal",
        source_topic: str | None = None,
    ) -> dict[str, Any]:
        event = copy.deepcopy(event)
        event.setdefault("received_at", utc_now())
        receipt = self.external_event_receipt(event["idempotency_key"])
        if receipt:
            self._ensure_external_event_receipt_matches(receipt, event)
            if receipt.get("receipt_status") == "processing":
                raise ExternalEventIdempotencyConflict(
                    "external_event_idempotency_conflict: idempotency_key уже обрабатывается другим worker."
                )
            return self._external_event_duplicate_result(receipt)

        wait = self.active_wait_by_correlation(
            event["correlation_id"],
            case_id=event.get("case_id"),
        )
        if not wait:
            raise ProcessingNotFound(event["correlation_id"])
        self._ensure_external_event_source_matches(wait, event)
        self._ensure_external_event_transport_matches(
            wait,
            received_transport=received_transport,
            source_topic=source_topic,
        )
        if event.get("wait_id") and event["wait_id"] != wait["wait_id"]:
            raise ProcessingConflict(
                f"wait_id {event['wait_id']} не совпадает с активным ожиданием {wait['wait_id']}."
            )
        expected_event_type = wait.get("expected_event_type") or (wait.get("payload") or {}).get("expected_event_type")
        if expected_event_type and expected_event_type != event["event_type"]:
            raise ProcessingConflict(
                f"event_type {event['event_type']} не совпадает с ожидаемым {expected_event_type}."
            )
        self._claim_external_event_receipt(event)

        now = utc_now()
        event["received_at"] = event.get("received_at") or now
        safe_event = self._external_event_for_storage(event)
        event_summary = self._external_event_summary(safe_event)
        wait.setdefault("external_events", []).append(copy.deepcopy(event_summary))
        wait.setdefault("payload", {})["last_external_event"] = event_summary
        wait["updated_at"] = now

        resume_task = None
        run = self.latest_run(wait["case_id"])
        if event["status"] in EXTERNAL_EVENT_TERMINAL_STATUSES:
            wait["status"] = EXTERNAL_EVENT_WAIT_STATUS[event["status"]]
            wait["completed_at"] = now
            wait["completion_event_id"] = event["event_id"]
            if run and run.get("run_id") == wait.get("run_id") and run.get("status") not in TERMINAL_RUN_STATUSES:
                run["status"] = "queued"
                run["current_step"] = "external_event_received"
                run["updated_at"] = now
                run["completed_at"] = None
                run.setdefault("resume_events", []).append(copy.deepcopy(event_summary))
                self._save_run(run)
                resume_task = self._build_external_event_resume_task(run, wait, safe_event, now)
                with self._connect() as connection:
                    self._insert_task(connection, resume_task)

        self._save_wait(wait)
        self._append_case_event(
            wait["case_id"],
            "processing_external_event_received",
            f"Получено внешнее событие {event['event_type']} со статусом {event['status']}.",
            {
                "run_id": wait["run_id"],
                "wait_id": wait["wait_id"],
                "wait_type": wait["wait_type"],
                "correlation_id": event["correlation_id"],
                "source": event["source"],
                "event_type": event["event_type"],
                "event_status": event["status"],
                "external_event": safe_event,
                "origin": wait.get("origin"),
            },
        )
        self._enqueue(
            "integration.events",
            wait["case_id"],
            "external_event_received",
            {
                "case_id": wait["case_id"],
                "ticket_id": wait["ticket_id"],
                "run_id": wait["run_id"],
                "wait_id": wait["wait_id"],
                "origin": wait.get("origin"),
                "external_event": safe_event,
            },
            idempotency_key=event["idempotency_key"],
        )
        if resume_task:
            self._enqueue(
                "agent.tasks",
                wait["case_id"],
                "external_event_resume_requested",
                {
                    "case_id": wait["case_id"],
                    "ticket_id": wait["ticket_id"],
                    "run_id": wait["run_id"],
                    "wait": wait,
                    "external_event": safe_event,
                    "task": resume_task,
                },
                idempotency_key=resume_task["idempotency_key"],
            )

        result = {
            "schema_version": "1.0",
            "accepted": True,
            "duplicate": False,
            "external_event": safe_event,
            "wait": wait,
            "case": self.case_store.require(wait["case_id"]),
        }
        if resume_task:
            result["resume_task"] = resume_task
        self._complete_external_event_receipt(event, result)
        return result

    def overview(self) -> dict[str, Any]:
        with self._connect() as connection:
            run_rows = connection.execute(
                """
                select status, count(*) as count
                from processing_runs
                group by status
                order by status
                """
            ).fetchall()
            task_rows = connection.execute(
                """
                select status, count(*) as count
                from agent_tasks
                group by status
                order by status
                """
            ).fetchall()
            wait_rows = connection.execute(
                """
                select wait_type, status, count(*) as count
                from wait_states
                group by wait_type, status
                order by wait_type, status
                """
            ).fetchall()
            outbox_total = connection.execute(
                "select count(*) as count from processing_outbox where status = 'pending'"
            ).fetchone()
            outbox_rows = connection.execute(
                """
                select topic, status, count(*) as count, min(created_at) as oldest_created_at
                from processing_outbox
                group by topic, status
                order by topic, status
                """
            ).fetchall()
            oldest_pending = connection.execute(
                """
                select topic, message_id, message_key, event_type, created_at, attempts, last_error
                from processing_outbox
                where status = 'pending'
                order by created_at asc, message_id asc
                limit 1
                """
            ).fetchone()
            heartbeat_rows = connection.execute(
                """
                select component_id, role, display_name, worker_id, topic, status,
                       last_seen_at, last_error, details_json
                from runtime_heartbeats
                order by role, topic, component_id
                """
            ).fetchall()
        waits_by_type: dict[str, dict[str, int]] = {}
        for row in wait_rows:
            waits_by_type.setdefault(str(row["wait_type"]), {})[str(row["status"])] = int(row["count"])
        runtime = self._runtime_overview(heartbeat_rows, outbox_rows, oldest_pending)
        return {
            "schema_version": "1.0",
            "kafka": {
                "bootstrap_servers": self.kafka_bootstrap_servers,
                "topics": copy.deepcopy(KAFKA_TOPICS),
                "outbox_pending": int(outbox_total["count"] if outbox_total else 0),
                "outbox_by_topic": self._outbox_counts(outbox_rows),
                "oldest_pending": self._oldest_pending_summary(oldest_pending),
            },
            "runtime": runtime,
            "runs_by_status": self._counts(run_rows, "status"),
            "tasks_by_status": self._counts(task_rows, "status"),
            "waits_by_type": waits_by_type,
            "active": {
                "runs": self._count_statuses("processing_runs", ACTIVE_RUN_STATUSES),
                "tasks": self._count_statuses("agent_tasks", ACTIVE_TASK_STATUSES),
                "waits": self._count_statuses("wait_states", ACTIVE_WAIT_STATUSES),
                "stale_tasks": self.stale_task_count(),
            },
        }

    def record_runtime_heartbeat(
        self,
        *,
        role: str,
        worker_id: str,
        display_name: str | None = None,
        topic: str | None = None,
        status: str = "ok",
        details: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        normalized_topic = str(topic or "*")
        component_id = f"{role}:{normalized_topic}"
        record = {
            "schema_version": "1.0",
            "component_id": component_id,
            "role": role,
            "display_name": display_name or role,
            "worker_id": worker_id,
            "topic": normalized_topic,
            "status": status,
            "last_seen_at": now,
            "last_error": self._sanitize_error_text(error) if error else None,
            "details": details or {},
        }
        with self._connect() as connection:
            connection.execute(
                """
                insert into runtime_heartbeats (
                    component_id, role, display_name, worker_id, topic, status,
                    last_seen_at, last_error, details_json, created_at, updated_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(component_id) do update set
                    display_name = excluded.display_name,
                    worker_id = excluded.worker_id,
                    status = excluded.status,
                    last_seen_at = excluded.last_seen_at,
                    last_error = excluded.last_error,
                    details_json = excluded.details_json,
                    updated_at = excluded.updated_at
                """,
                (
                    component_id,
                    role,
                    record["display_name"],
                    worker_id,
                    normalized_topic,
                    status,
                    now,
                    record["last_error"],
                    self._to_json(record["details"]),
                    now,
                    now,
                ),
            )
        return record

    def _runtime_overview(
        self,
        heartbeat_rows: list[sqlite3.Row],
        outbox_rows: list[sqlite3.Row],
        oldest_pending: sqlite3.Row | None,
    ) -> dict[str, Any]:
        stale_seconds = self._runtime_heartbeat_stale_seconds()
        heartbeats = [self._runtime_heartbeat_summary(row, stale_seconds) for row in heartbeat_rows]
        required: list[dict[str, Any]] = []
        issues: list[str] = []
        for requirement in RUNTIME_REQUIRED_COMPONENTS:
            topic = os.getenv(str(requirement["topic_env"]), str(requirement["default_topic"]))
            matching = [
                heartbeat
                for heartbeat in heartbeats
                if heartbeat["role"] == requirement["role"]
                and heartbeat.get("topic") in {topic, "*", None, ""}
            ]
            selected = max(matching, key=lambda item: item.get("last_seen_at") or "", default=None)
            if not selected:
                status = "error"
                message = f"{requirement['display_name']} не запускался или не записал heartbeat."
            elif selected.get("stale"):
                status = "error"
                message = (
                    f"{requirement['display_name']} не обновлял heartbeat более "
                    f"{stale_seconds} сек."
                )
            elif selected.get("status") not in {"ok", "running"}:
                status = "error"
                message = selected.get("last_error") or f"{requirement['display_name']} имеет статус {selected.get('status')}."
            else:
                status = "ok"
                message = f"{requirement['display_name']} работает."
            component = {
                "role": requirement["role"],
                "display_name": requirement["display_name"],
                "topic": topic,
                "status": status,
                "message": message,
                "heartbeat": selected,
            }
            required.append(component)
            if status != "ok":
                issues.append(message)

        tool_topic = os.getenv("TOOL_COMMAND_TOPIC", DEFAULT_ASYNC_TOOL_COMMAND_TOPIC)
        stale_tool_outbox = self._stale_pending_topic_summary(outbox_rows, tool_topic)
        if stale_tool_outbox:
            issues.append(
                (
                    f"В topic {tool_topic} есть неопубликованный outbox старше "
                    f"{ASYNC_OUTBOX_STALE_SECONDS} сек."
                )
            )

        return {
            "schema_version": "1.0",
            "status": "error" if issues else "ok",
            "heartbeat_stale_seconds": stale_seconds,
            "required_components": required,
            "components": heartbeats,
            "issues": issues,
            "stale_tool_outbox": stale_tool_outbox,
            "oldest_pending": self._oldest_pending_summary(oldest_pending),
        }

    @staticmethod
    def _runtime_heartbeat_stale_seconds() -> int:
        try:
            value = int(os.getenv("ASYNC_RUNTIME_HEARTBEAT_STALE_SECONDS", str(RUNTIME_HEARTBEAT_STALE_SECONDS)))
        except ValueError:
            return RUNTIME_HEARTBEAT_STALE_SECONDS
        return max(5, value)

    @classmethod
    def _runtime_heartbeat_summary(cls, row: sqlite3.Row, stale_seconds: int) -> dict[str, Any]:
        age_seconds = cls._age_seconds(row["last_seen_at"])
        try:
            details = json.loads(row["details_json"] or "{}")
        except json.JSONDecodeError:
            details = {}
        return {
            "component_id": row["component_id"],
            "role": row["role"],
            "display_name": row["display_name"],
            "worker_id": row["worker_id"],
            "topic": row["topic"],
            "status": row["status"],
            "last_seen_at": row["last_seen_at"],
            "age_seconds": age_seconds,
            "stale": age_seconds is None or age_seconds > stale_seconds,
            "last_error": row["last_error"],
            "details": details,
        }

    @classmethod
    def _outbox_counts(cls, rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for row in rows:
            result.append(
                {
                    "topic": row["topic"],
                    "status": row["status"],
                    "count": int(row["count"]),
                    "oldest_created_at": row["oldest_created_at"],
                    "oldest_age_seconds": cls._age_seconds(row["oldest_created_at"]),
                }
            )
        return result

    @classmethod
    def _stale_pending_topic_summary(cls, rows: list[sqlite3.Row], topic: str) -> dict[str, Any] | None:
        for row in rows:
            if row["topic"] != topic or row["status"] not in {"pending", "publishing"}:
                continue
            age_seconds = cls._age_seconds(row["oldest_created_at"])
            if age_seconds is None or age_seconds < ASYNC_OUTBOX_STALE_SECONDS:
                continue
            return {
                "topic": topic,
                "status": row["status"],
                "count": int(row["count"]),
                "oldest_created_at": row["oldest_created_at"],
                "oldest_age_seconds": age_seconds,
            }
        return None

    @classmethod
    def _oldest_pending_summary(cls, row: sqlite3.Row | None) -> dict[str, Any] | None:
        if not row:
            return None
        return {
            "topic": row["topic"],
            "message_id": row["message_id"],
            "message_key": row["message_key"],
            "event_type": row["event_type"],
            "created_at": row["created_at"],
            "age_seconds": cls._age_seconds(row["created_at"]),
            "attempts": int(row["attempts"] or 0),
            "last_error": row["last_error"],
        }

    def list_cases(self, limit: int = 100) -> dict[str, Any]:
        cases = self.case_store.list_all(limit=limit)
        rows = []
        for case in cases:
            run = self.latest_run(case["case_id"])
            wait = self.active_wait(case["case_id"])
            rows.append(
                {
                    "case_id": case["case_id"],
                    "ticket_id": case["ticket_id"],
                    "workflow_state_id": case.get("current_workflow_state", {}).get("id"),
                    "updated_at": case.get("updated_at"),
                    "event_count": case.get("event_count", 0),
                    "processing": {
                        "run_id": run.get("run_id") if run else None,
                        "run_status": run.get("status") if run else "missing",
                        "current_step": run.get("current_step") if run else None,
                        "active_wait_id": wait.get("wait_id") if wait else None,
                        "active_wait_type": wait.get("wait_type") if wait else None,
                    },
                }
            )
        return {
            "schema_version": "1.0",
            "cases": rows,
        }

    def case_detail(self, case_id: str) -> dict[str, Any]:
        case = self.enrich_async_tool_results(self.case_store.require(case_id))
        return {
            "schema_version": "1.0",
            "case": case,
            "timeline": self.case_events(case_id=case_id, limit=200),
            "runs": self.list_runs(case_id=case_id, limit=50)["runs"],
            "tasks": self.list_tasks(case_id=case_id, limit=100)["tasks"],
            "waits": self.list_waits(case_id=case_id, limit=100)["waits"],
            "outbox": self.list_outbox(case_id=case_id, limit=50)["messages"],
        }

    def async_delivery_for_case(self, case_id: str) -> dict[str, Any]:
        case = self.enrich_async_tool_results(self.case_store.require(case_id))
        snapshots = []
        for result in case.get("tool_results", []):
            if not isinstance(result, dict):
                continue
            extensions = result.get("extensions")
            if not isinstance(extensions, dict):
                continue
            delivery = extensions.get("async_delivery")
            if not isinstance(delivery, dict):
                continue
            snapshots.append(
                {
                    "action_id": result.get("action_id"),
                    "invocation_id": result.get("invocation_id"),
                    "tool_name": result.get("tool_name"),
                    "endpoint_id": result.get("endpoint_id"),
                    "operation_id": result.get("operation_id"),
                    "source_profile_id": extensions.get("source_profile_id"),
                    "source_step_id": extensions.get("source_step_id"),
                    "debug_launch_id": extensions.get("debug_launch_id"),
                    "delivery": delivery,
                }
            )
        return {
            "schema_version": "1.0",
            "case_id": case_id,
            "snapshots": snapshots,
        }

    def async_delivery_for_wait(self, wait_id: str) -> dict[str, Any]:
        wait = self.require_wait(wait_id)
        snapshot = self.async_tool_delivery_snapshot(
            {
                "wait_id": wait_id,
                "correlation_id": wait.get("correlation_id"),
            }
        )
        return {
            "schema_version": "1.0",
            "case_id": wait.get("case_id"),
            "wait_id": wait_id,
            "snapshot": snapshot,
        }

    def enrich_async_tool_results(self, payload: dict[str, Any]) -> dict[str, Any]:
        enriched = copy.deepcopy(payload)
        self._enrich_async_tool_result_list(enriched.get("tool_results"))
        snapshot = enriched.get("analysis_snapshot")
        if isinstance(snapshot, dict):
            self._enrich_async_tool_result_list(snapshot.get("tool_results"))
        return enriched

    def _enrich_async_tool_result_list(self, tool_results: Any) -> None:
        if not isinstance(tool_results, list):
            return
        for result in tool_results:
            if not isinstance(result, dict):
                continue
            extensions = result.get("extensions")
            if not isinstance(extensions, dict):
                continue
            async_wait = extensions.get("async_wait")
            snapshot = self.async_tool_delivery_snapshot(async_wait)
            if not snapshot:
                continue
            extensions["async_delivery"] = snapshot
            extensions["diagnostic_status"] = snapshot["status"]

    def list_runs(self, *, case_id: str | None = None, limit: int = 100) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "runs": self._list_json_rows(
                "processing_runs",
                "run_json",
                case_id=case_id,
                limit=limit,
            ),
        }

    def list_tasks(self, *, case_id: str | None = None, limit: int = 100) -> dict[str, Any]:
        tasks = self._list_json_rows(
            "agent_tasks",
            "task_json",
            case_id=case_id,
            limit=limit,
        )
        now = datetime.now(UTC)
        for task in tasks:
            lease_until = parse_utc(task.get("lease_until"))
            if task.get("status") in {"running", "leased"} and lease_until and lease_until < now:
                task["stale"] = True
        return {
            "schema_version": "1.0",
            "tasks": tasks,
        }

    def list_waits(self, *, case_id: str | None = None, limit: int = 100) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "waits": self._list_json_rows(
                "wait_states",
                "wait_json",
                case_id=case_id,
                limit=limit,
            ),
        }

    def list_outbox(self, *, case_id: str | None = None, limit: int = 100) -> dict[str, Any]:
        where = ""
        parameters: list[Any] = []
        if case_id:
            where = "where message_key = ?"
            parameters.append(case_id)
        parameters.append(min(max(limit, 0), 500))
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                select payload_json
                from processing_outbox
                {where}
                order by created_at desc, message_id desc
                limit ?
                """,
                parameters,
            ).fetchall()
        return {
            "schema_version": "1.0",
            "messages": [json.loads(row["payload_json"]) for row in rows],
        }

    def outbox_message_by_idempotency_key(self, idempotency_key: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                select payload_json
                from processing_outbox
                where idempotency_key = ?
                """,
                (idempotency_key,),
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def claim_outbox_batch(
        self,
        *,
        worker_id: str,
        limit: int = 50,
        lease_seconds: int = 60,
        topics: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        limit = min(max(limit, 1), 500)
        now = utc_now()
        locked_until = add_seconds(now, lease_seconds)
        parameters: list[Any] = [now]
        topic_clause = ""
        if topics:
            placeholders = ", ".join("?" for _ in topics)
            topic_clause = f"and topic in ({placeholders})"
            parameters.extend(topics)
        parameters.append(limit)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                select message_id, payload_json
                from processing_outbox
                where (
                    status = 'pending'
                    or (status = 'publishing' and locked_until is not null and locked_until < ?)
                )
                {topic_clause}
                order by created_at asc, message_id asc
                limit ?
                """,
                parameters,
            ).fetchall()
            claimed: list[dict[str, Any]] = []
            for row in rows:
                message = json.loads(row["payload_json"])
                message["status"] = "publishing"
                message["locked_by"] = worker_id
                message["locked_until"] = locked_until
                message["updated_at"] = now
                cursor = connection.execute(
                    """
                    update processing_outbox
                    set status = 'publishing',
                        locked_by = ?,
                        locked_until = ?,
                        updated_at = ?,
                        payload_json = ?
                    where message_id = ?
                      and (
                        status = 'pending'
                        or (status = 'publishing' and locked_until is not null and locked_until < ?)
                      )
                    """,
                    (
                        worker_id,
                        locked_until,
                        now,
                        self._to_json(message),
                        row["message_id"],
                        now,
                    ),
                )
                if cursor.rowcount:
                    claimed.append(message)
        return claimed

    def mark_outbox_published(self, message_id: str, *, worker_id: str | None = None) -> dict[str, Any]:
        now = utc_now()
        with self._connect() as connection:
            row = connection.execute(
                """
                select payload_json
                from processing_outbox
                where message_id = ?
                """,
                (message_id,),
            ).fetchone()
            if not row:
                raise ProcessingNotFound(message_id)
            message = json.loads(row["payload_json"])
            message["status"] = "published"
            message["published_at"] = now
            message["updated_at"] = now
            message.pop("locked_by", None)
            message.pop("locked_until", None)
            worker_clause = "and locked_by = ?" if worker_id is not None else ""
            parameters: list[Any] = [now, now, self._to_json(message), message_id]
            if worker_id is not None:
                parameters.append(worker_id)
            cursor = connection.execute(
                f"""
                update processing_outbox
                set status = 'published',
                    locked_by = null,
                    locked_until = null,
                    published_at = ?,
                    updated_at = ?,
                    payload_json = ?
                where message_id = ?
                  and status = 'publishing'
                  {worker_clause}
                """,
                parameters,
            )
            if not cursor.rowcount:
                raise ProcessingConflict(f"Outbox message {message_id} больше не принадлежит publisher {worker_id}.")
        return message

    def mark_outbox_publish_failed(self, message_id: str, error: str, *, worker_id: str | None = None) -> dict[str, Any]:
        now = utc_now()
        with self._connect() as connection:
            row = connection.execute(
                """
                select attempts, payload_json
                from processing_outbox
                where message_id = ?
                """,
                (message_id,),
            ).fetchone()
            if not row:
                raise ProcessingNotFound(message_id)
            attempts = int(row["attempts"] or 0) + 1
            message = json.loads(row["payload_json"])
            message["status"] = "pending"
            message["attempts"] = attempts
            message["last_error"] = error[:1000]
            message["updated_at"] = now
            message.pop("locked_by", None)
            message.pop("locked_until", None)
            worker_clause = "and locked_by = ?" if worker_id is not None else ""
            parameters = [attempts, error[:1000], now, self._to_json(message), message_id]
            if worker_id is not None:
                parameters.append(worker_id)
            cursor = connection.execute(
                f"""
                update processing_outbox
                set status = 'pending',
                    locked_by = null,
                    locked_until = null,
                    attempts = ?,
                    last_error = ?,
                    updated_at = ?,
                    payload_json = ?
                where message_id = ?
                  and status = 'publishing'
                  {worker_clause}
                """,
                parameters,
            )
            if not cursor.rowcount:
                raise ProcessingConflict(f"Outbox message {message_id} больше не принадлежит publisher {worker_id}.")
        return message

    def record_tool_command_result(
        self,
        result: dict[str, Any],
        *,
        case_id: str,
        idempotency_key: str,
    ) -> None:
        self._enqueue(
            "tool.results",
            case_id,
            "tool_command_result_recorded",
            {
                "case_id": case_id,
                "tool_result": result,
            },
            idempotency_key=idempotency_key,
        )

    def verify_tool_command(self, command: dict[str, Any]) -> None:
        wait = self.require_wait(command["wait_id"])
        expected = {
            "case_id": wait["case_id"],
            "ticket_id": wait.get("ticket_id"),
            "run_id": wait["run_id"],
            "wait_id": wait["wait_id"],
            "correlation_id": wait["correlation_id"],
            "source": wait.get("channel_id"),
            "expected_event_type": wait.get("expected_event_type"),
        }
        mismatched = [
            key
            for key, value in expected.items()
            if value not in (None, "") and command.get(key) != value
        ]
        if mismatched:
            raise ProcessingConflict(
                f"tool command не совпадает с wait_state: {', '.join(sorted(mismatched))}."
            )
        message = self.outbox_message_by_idempotency_key(command["idempotency_key"])
        if not message:
            raise ProcessingNotFound(command["idempotency_key"])
        if message.get("topic") != command.get("topic", DEFAULT_ASYNC_TOOL_COMMAND_TOPIC):
            raise ProcessingConflict("tool command topic не совпадает с outbox.")
        stored_command = message.get("payload") or {}
        for key in ("command_id", "case_id", "wait_id", "correlation_id", "idempotency_key"):
            if stored_command.get(key) != command.get(key):
                raise ProcessingConflict(f"tool command {key} не совпадает с persisted outbox payload.")

    def tool_command_receipt(self, idempotency_key: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                select receipt_json
                from tool_command_receipts
                where idempotency_key = ?
                """,
                (idempotency_key,),
            ).fetchone()
        return json.loads(row["receipt_json"]) if row else None

    def external_event_receipts_for_wait(
        self,
        *,
        case_id: str | None = None,
        wait_id: str | None = None,
        correlation_id: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        parameters: list[Any] = []
        if case_id:
            clauses.append("case_id = ?")
            parameters.append(case_id)
        if correlation_id:
            clauses.append("correlation_id = ?")
            parameters.append(correlation_id)
        where = f"where {' and '.join(clauses)}" if clauses else ""
        parameters.append(min(max(limit, 0), 200))
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                select receipt_json
                from external_event_receipts
                {where}
                order by updated_at desc, created_at desc, idempotency_key desc
                limit ?
                """,
                parameters,
            ).fetchall()
        receipts = [json.loads(row["receipt_json"]) for row in rows]
        if wait_id:
            receipts = [
                receipt
                for receipt in receipts
                if receipt.get("wait_id") in (None, "", wait_id)
            ]
        return receipts

    def async_tool_delivery_snapshot(self, async_wait: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(async_wait, dict):
            return None
        wait_id = async_wait.get("wait_id")
        idempotency_key = async_wait.get("correlation_id")
        wait = None
        if wait_id:
            try:
                wait = self.require_wait(wait_id)
            except ProcessingNotFound:
                wait = None
        if not idempotency_key and wait:
            idempotency_key = wait.get("correlation_id")
        outbox_message = self.outbox_message_by_idempotency_key(idempotency_key) if idempotency_key else None
        receipt = self.tool_command_receipt(idempotency_key) if idempotency_key else None
        dead_letter = self.outbox_message_by_idempotency_key(f"{idempotency_key}:dead_letter") if idempotency_key else None
        receipts = self.external_event_receipts_for_wait(
            case_id=(wait or {}).get("case_id") or outbox_message and outbox_message.get("key"),
            wait_id=wait_id,
            correlation_id=idempotency_key,
        )
        status, message, root_cause, severity = self._async_delivery_state(
            async_wait=async_wait,
            wait=wait,
            outbox_message=outbox_message,
            receipt=receipt,
            dead_letter=dead_letter,
            external_event_receipts=receipts,
        )
        return {
            "schema_version": "1.0",
            "status": status,
            "severity": severity,
            "message": message,
            "root_cause": root_cause,
            "checked_at": utc_now(),
            "idempotency_key": idempotency_key,
            "command_id": async_wait.get("command_id"),
            "wait_id": wait_id,
            "topic": async_wait.get("topic") or (outbox_message or {}).get("topic"),
            "outbox": self._async_delivery_outbox_summary(outbox_message),
            "tool_command_receipt": self._async_delivery_receipt_summary(receipt),
            "dead_letter": self._async_delivery_outbox_summary(dead_letter),
            "wait": self._async_delivery_wait_summary(wait),
            "external_event_receipts": [
                self._async_delivery_external_receipt_summary(receipt)
                for receipt in receipts
            ],
        }

    @staticmethod
    def _async_delivery_outbox_summary(message: dict[str, Any] | None) -> dict[str, Any] | None:
        if not message:
            return None
        return {
            "message_id": message.get("message_id"),
            "topic": message.get("topic"),
            "event_type": message.get("event_type"),
            "status": message.get("status"),
            "idempotency_key": message.get("idempotency_key"),
            "created_at": message.get("created_at"),
            "updated_at": message.get("updated_at"),
            "published_at": message.get("published_at"),
            "attempts": message.get("attempts", 0),
            "last_error": message.get("last_error"),
            "locked_by": message.get("locked_by"),
            "locked_until": message.get("locked_until"),
            "age_seconds": ProcessingStore._age_seconds(message.get("created_at")),
        }

    @staticmethod
    def _age_seconds(value: str | None) -> int | None:
        moment = parse_utc(value)
        if moment is None:
            return None
        return max(0, int((datetime.now(UTC).replace(microsecond=0) - moment).total_seconds()))

    @staticmethod
    def _async_delivery_receipt_summary(receipt: dict[str, Any] | None) -> dict[str, Any] | None:
        if not receipt:
            return None
        result = receipt.get("result") or {}
        tool_result = result.get("tool_result") if isinstance(result, dict) else None
        tool_extensions = (tool_result or {}).get("extensions") if isinstance((tool_result or {}).get("extensions"), dict) else {}
        return {
            "command_id": receipt.get("command_id"),
            "status": receipt.get("status"),
            "worker_id": receipt.get("worker_id"),
            "created_at": receipt.get("created_at"),
            "updated_at": receipt.get("updated_at"),
            "tool_name": (tool_result or {}).get("tool_name"),
            "endpoint_id": (tool_result or {}).get("endpoint_id"),
            "operation_id": (tool_result or {}).get("operation_id"),
            "tool_result_status": (tool_result or {}).get("status"),
            "tool_result_error": (tool_result or {}).get("error"),
            "tool_result_output": (tool_result or {}).get("output"),
            "endpoint_url": tool_extensions.get("endpoint_url"),
            "n8n_ack_body": tool_extensions.get("n8n_ack_body"),
        }

    @staticmethod
    def _async_delivery_wait_summary(wait: dict[str, Any] | None) -> dict[str, Any] | None:
        if not wait:
            return None
        return {
            "wait_id": wait.get("wait_id"),
            "run_id": wait.get("run_id"),
            "case_id": wait.get("case_id"),
            "ticket_id": wait.get("ticket_id"),
            "status": wait.get("status"),
            "wait_type": wait.get("wait_type"),
            "channel_id": wait.get("channel_id"),
            "expected_event_type": wait.get("expected_event_type"),
            "deadline_at": wait.get("deadline_at"),
            "created_at": wait.get("created_at"),
            "updated_at": wait.get("updated_at"),
            "completed_at": wait.get("completed_at"),
        }

    @staticmethod
    def _external_event_from_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
        external_event = receipt.get("external_event")
        if isinstance(external_event, dict):
            return external_event
        result = receipt.get("result") if isinstance(receipt.get("result"), dict) else {}
        external_event = result.get("external_event") if isinstance(result.get("external_event"), dict) else {}
        return external_event

    @staticmethod
    def _async_delivery_external_receipt_summary(receipt: dict[str, Any]) -> dict[str, Any]:
        external_event = ProcessingStore._external_event_from_receipt(receipt)
        return {
            "idempotency_key": receipt.get("idempotency_key"),
            "event_id": receipt.get("event_id"),
            "event_type": receipt.get("event_type"),
            "status": external_event.get("status") or receipt.get("status"),
            "receipt_status": receipt.get("receipt_status"),
            "source": external_event.get("source") or receipt.get("source"),
            "created_at": receipt.get("created_at"),
            "updated_at": receipt.get("updated_at"),
            "error": external_event.get("error"),
            "result": ProcessingStore._compact_external_event_value(external_event.get("result")),
        }

    @staticmethod
    def _async_delivery_state(
        *,
        async_wait: dict[str, Any],
        wait: dict[str, Any] | None,
        outbox_message: dict[str, Any] | None,
        receipt: dict[str, Any] | None,
        dead_letter: dict[str, Any] | None,
        external_event_receipts: list[dict[str, Any]],
    ) -> tuple[str, str, str, str]:
        if dead_letter:
            error = ((dead_letter.get("payload") or {}).get("error") or dead_letter.get("last_error") or "н/д")
            return (
                "worker_failed",
                f"Команда попала в dead-letter: {error}",
                "ToolCommandWorker не смог обработать команду и записал ее в dead-letter.",
                "error",
            )
        terminal_receipts = [
            item for item in external_event_receipts
            if item.get("receipt_status") == "completed"
        ]
        if terminal_receipts:
            latest = terminal_receipts[0]
            external_event = ProcessingStore._external_event_from_receipt(latest)
            event_status = external_event.get("status") or latest.get("status")
            event_result = external_event.get("result") if isinstance(external_event.get("result"), dict) else {}
            if event_status == "progress":
                diagnostic = event_result.get("polling_diagnostic") if isinstance(event_result.get("polling_diagnostic"), dict) else {}
                message = event_result.get("message") if isinstance(event_result, dict) else None
                current_status = diagnostic.get("current_status") or event_result.get("runbook_status") or "progress"
                checked_resource = diagnostic.get("checked_resource")
                match_count = diagnostic.get("match_count")
                mailbox_count = diagnostic.get("mailbox_indexed_count")
                detail_parts = [
                    f"статус={current_status}",
                    f"ресурс={checked_resource}" if checked_resource else "",
                    f"совпадений={match_count}" if match_count is not None else "",
                    f"писем в индексе={mailbox_count}" if mailbox_count is not None else "",
                ]
                detail = "; ".join(part for part in detail_parts if part)
                return (
                    "external_event_progress",
                    f"n8n workflow выполняется: {message or detail or 'получено промежуточное состояние polling.'}",
                    "Workflow был запущен и вернул промежуточный progress ExternalEvent; terminal результат еще ожидается.",
                    "pending",
                )
            if event_status == "success":
                message = event_result.get("message") if isinstance(event_result, dict) else None
                return (
                    "external_event_received",
                    f"Получен успешный внешний результат n8n: {message}" if message else "Получен успешный внешний результат n8n.",
                    "Команда была доставлена до n8n, workflow вернул terminal ExternalEvent со статусом success.",
                    "ok",
                )
            if event_status == "timeout":
                message = event_result.get("message") if isinstance(event_result, dict) else None
                return (
                    "external_event_timeout",
                    f"n8n вернул timeout по асинхронному workflow: {message}" if message else "n8n вернул timeout по асинхронному workflow.",
                    "Workflow был запущен, но завершился timeout ExternalEvent; требуется разбор результата или эскалация.",
                    "warning",
                )
            if event_status in {"error", "cancelled"}:
                error = external_event.get("error") if isinstance(external_event.get("error"), dict) else {}
                result_error = event_result.get("error") if isinstance(event_result.get("error"), dict) else {}
                error_code = error.get("code") or result_error.get("code") or event_status
                error_message = (
                    error.get("message")
                    or result_error.get("message")
                    or event_result.get("message")
                    or event_status
                    or "н/д"
                )
                error_text = f"{error_code}: {error_message}" if error_code and error_code != error_message else str(error_message)
                return (
                    "external_event_failed",
                    f"n8n вернул ошибочный внешний результат: {error_text}",
                    "Workflow был запущен, но terminal ExternalEvent сообщил ошибку; бизнес-действие не завершилось успешно.",
                    "error",
                )
            return (
                "external_event_received",
                f"Получен внешний результат n8n со статусом {latest.get('status')}.",
                "Команда была доставлена до n8n, внешний результат вернулся в оркестратор.",
                "ok",
            )
        if wait and wait.get("status") not in ACTIVE_WAIT_STATUSES:
            return (
                f"wait_{wait.get('status')}",
                f"Ожидание завершено со статусом {wait.get('status')}.",
                "Асинхронное ожидание завершилось без активного ожидания результата.",
                "ok",
            )
        if receipt:
            receipt_status = receipt.get("status")
            result = receipt.get("result") or {}
            tool_result = result.get("tool_result") if isinstance(result, dict) else None
            tool_status = (tool_result or {}).get("status")
            if receipt_status == "completed" and tool_status in {"success", "dry_run_completed"}:
                return (
                    "waiting_external_event",
                    "Worker обработал команду и n8n-вызов принят; ожидается внешний результат.",
                    "Исполнение дошло до n8n, но финальный ExternalEvent еще не получен.",
                    "ok",
                )
            if receipt_status == "completed":
                tool_error = (tool_result or {}).get("error") or {}
                error_code = tool_error.get("code") or tool_status or "unknown_error"
                error_message = tool_error.get("message") or tool_status or "н/д"
                if error_code in {
                    "invalid_callback_url",
                    "missing_callback_url",
                    "missing_result_topic",
                    "invalid_result_transport",
                    "unauthorized",
                    "http_400",
                    "http_401",
                    "http_403",
                    "endpoint_response_contract_violation",
                }:
                    return (
                        "n8n_launch_rejected",
                        f"n8n отклонил запуск workflow: {error_code}: {error_message}",
                        "ToolCommandWorker вызвал n8n endpoint, но webhook вернул ошибку до accepted; письмо и дальнейший мониторинг не выполнялись.",
                        "error",
                    )
                return (
                    "worker_failed",
                    f"Worker завершил команду с ошибкой: {error_code}: {error_message}",
                    "ToolCommandWorker вызвал endpoint, но получил ошибочный результат.",
                    "error",
                )
            return (
                "worker_started",
                "ToolCommandWorker начал обработку команды, но завершение еще не записано.",
                "Команда уже взята worker-ом; нужно дождаться завершения или проверить зависший worker.",
                "pending",
            )
        if outbox_message:
            outbox_status = outbox_message.get("status")
            if outbox_status == "published":
                return (
                    "published_to_kafka",
                    "Команда опубликована в Kafka, но ToolCommandWorker еще не записал receipt.",
                    "Сообщение дошло до Kafka; ToolCommandWorker для topic tool.commands не обработал его или еще не завершил обработку.",
                    "pending",
                )
            if outbox_status == "publishing":
                return (
                    "publishing_to_kafka",
                    "Команда взята outbox publisher-ом для публикации в Kafka.",
                    "Outbox publisher держит lease на сообщение; нужно дождаться публикации или истечения lease.",
                    "pending",
                )
            if int(outbox_message.get("attempts") or 0) > 0 or outbox_message.get("last_error"):
                return (
                    "publish_failed_retrying",
                    f"Публикация в Kafka не удалась, команда оставлена для повтора: {outbox_message.get('last_error') or 'ошибка не указана'}.",
                    "Outbox publisher пытался отправить команду, но Kafka publish завершился ошибкой.",
                    "warning",
                )
            age_seconds = ProcessingStore._age_seconds(outbox_message.get("created_at"))
            if age_seconds is not None and age_seconds >= ASYNC_OUTBOX_STALE_SECONDS:
                return (
                    "queued_in_outbox",
                    (
                        f"Команда создана в outbox, но не опубликована в Kafka более "
                        f"{ASYNC_OUTBOX_STALE_SECONDS} сек.; фактический вызов n8n не запускался."
                    ),
                    "Outbox publisher не запущен, остановлен или не обрабатывает topic tool.commands.",
                    "warning",
                )
            return (
                "queued_in_outbox",
                "Команда создана в outbox и ожидает публикации publisher-ом; фактический вызов n8n еще не запускался.",
                "Outbox publisher еще не обработал pending сообщение.",
                "pending",
            )
        if async_wait.get("command_id") or async_wait.get("wait_id"):
            return (
                "missing_async_command",
                "Async wait есть в tool_result, но outbox-команда не найдена.",
                "Состояние wait/tool_result рассинхронизировано с processing_outbox.",
                "error",
            )
        return (
            "unknown",
            "Нет данных о доставке async-команды.",
            "Недостаточно данных для диагностики исполнения.",
            "warning",
        )

    def begin_tool_command(self, command: dict[str, Any], *, worker_id: str) -> dict[str, Any]:
        self.verify_tool_command(command)
        existing = self.tool_command_receipt(command["idempotency_key"])
        if existing:
            return {
                "schema_version": "1.0",
                "duplicate": True,
                "status": existing["status"],
                "receipt": existing,
            }
        now = utc_now()
        receipt = {
            "schema_version": "1.0",
            "idempotency_key": command["idempotency_key"],
            "command_id": command["command_id"],
            "case_id": command["case_id"],
            "wait_id": command["wait_id"],
            "correlation_id": command["correlation_id"],
            "status": "processing",
            "worker_id": worker_id,
            "created_at": now,
            "updated_at": now,
        }
        with self._connect() as connection:
            cursor = connection.execute(
                """
                insert or ignore into tool_command_receipts (
                    idempotency_key, command_id, case_id, wait_id, correlation_id,
                    status, worker_id, receipt_json, created_at, updated_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    receipt["idempotency_key"],
                    receipt["command_id"],
                    receipt["case_id"],
                    receipt["wait_id"],
                    receipt["correlation_id"],
                    receipt["status"],
                    receipt["worker_id"],
                    self._to_json(receipt),
                    now,
                    now,
                ),
            )
        if not cursor.rowcount:
            existing = self.tool_command_receipt(command["idempotency_key"])
            return {
                "schema_version": "1.0",
                "duplicate": True,
                "status": (existing or {}).get("status", "processing"),
                "receipt": existing,
            }
        return {
            "schema_version": "1.0",
            "duplicate": False,
            "status": "processing",
            "receipt": receipt,
        }

    def complete_tool_command(
        self,
        command: dict[str, Any],
        result: dict[str, Any],
        *,
        worker_id: str,
    ) -> dict[str, Any]:
        now = utc_now()
        receipt = {
            "schema_version": "1.0",
            "idempotency_key": command["idempotency_key"],
            "command_id": command["command_id"],
            "case_id": command["case_id"],
            "wait_id": command["wait_id"],
            "correlation_id": command["correlation_id"],
            "status": "completed",
            "worker_id": worker_id,
            "result": result,
            "updated_at": now,
        }
        with self._connect() as connection:
            cursor = connection.execute(
                """
                update tool_command_receipts
                set status = 'completed',
                    worker_id = ?,
                    receipt_json = ?,
                    updated_at = ?
                where idempotency_key = ?
                  and status = 'processing'
                """,
                (worker_id, self._to_json(receipt), now, command["idempotency_key"]),
            )
        if not cursor.rowcount:
            existing = self.tool_command_receipt(command["idempotency_key"])
            if existing and existing.get("status") == "completed":
                return existing
            raise ProcessingConflict(f"tool command receipt не найден или уже завершен: {command['idempotency_key']}")
        return receipt

    def record_tool_command_dead_letter(
        self,
        command: dict[str, Any],
        error: str,
        *,
        worker_id: str,
    ) -> dict[str, Any]:
        dead_letter = {
            "schema_version": "1.0",
            "source_topic": command.get("topic", DEFAULT_ASYNC_TOOL_COMMAND_TOPIC),
            "event_type": "tool_command_failed",
            "case_id": command.get("case_id", "unknown"),
            "wait_id": command.get("wait_id"),
            "correlation_id": command.get("correlation_id"),
            "command_id": command.get("command_id"),
            "idempotency_key": command.get("idempotency_key"),
            "worker_id": worker_id,
            "error": self._sanitize_error_text(error),
            "command": self._sanitize_external_event_payload(command),
        }
        self._enqueue(
            "dead-letter",
            str(command.get("case_id") or "unknown"),
            "tool_command_failed",
            dead_letter,
            idempotency_key=f"{command.get('idempotency_key') or command.get('command_id')}:dead_letter",
        )
        return dead_letter

    def record_external_event_dead_letter(
        self,
        event: dict[str, Any],
        error: str,
        *,
        worker_id: str,
        source_topic: str | None = None,
    ) -> dict[str, Any]:
        event_id = event.get("event_id") or f"invalid-{uuid.uuid4().hex[:12]}"
        idempotency_key = event.get("idempotency_key") or event_id
        dead_letter = {
            "schema_version": "1.0",
            "source_topic": source_topic or event.get("topic") or DEFAULT_EXTERNAL_EVENT_TOPIC,
            "event_type": "external_event_failed",
            "case_id": event.get("case_id", "unknown"),
            "wait_id": event.get("wait_id"),
            "correlation_id": event.get("correlation_id"),
            "external_event_id": event.get("event_id"),
            "external_event_type": event.get("event_type"),
            "idempotency_key": event.get("idempotency_key"),
            "worker_id": worker_id,
            "error": self._sanitize_error_text(error),
            "external_event": self._sanitize_external_event_payload(event),
        }
        self._enqueue(
            "dead-letter",
            str(event.get("case_id") or "unknown"),
            "external_event_failed",
            dead_letter,
            idempotency_key=f"{idempotency_key}:external_event_dead_letter",
        )
        return dead_letter

    def case_events(self, *, case_id: str | None = None, limit: int = 100) -> dict[str, Any]:
        where = ""
        parameters: list[Any] = []
        if case_id:
            where = "where case_id = ?"
            parameters.append(case_id)
        parameters.append(min(max(limit, 0), 500))
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                select event_json
                from case_events
                {where}
                order by created_at desc, event_id desc
                limit ?
                """,
                parameters,
            ).fetchall()
        return {
            "schema_version": "1.0",
            "events": [json.loads(row["event_json"]) for row in rows],
        }

    def cancel_run(self, run_id: str, *, actor_id: str, reason: str | None = None) -> dict[str, Any]:
        run = self.require_run(run_id)
        if run["status"] in TERMINAL_RUN_STATUSES:
            raise ProcessingConflict(f"Запуск {run_id} уже находится в статусе {run['status']}.")
        now = utc_now()
        run["status"] = "cancelled"
        run["updated_at"] = now
        run["completed_at"] = now
        run.setdefault("audit", []).append(self._audit_item("run_cancelled", actor_id, reason))
        self._save_run(run)
        self._set_related_active_items(run, "cancelled", actor_id, reason)
        self._append_case_event(
            run["case_id"],
            "processing_run_cancelled",
            "Администратор отменил запуск обработки.",
            {"run_id": run_id, "actor_id": actor_id, "reason": reason},
        )
        self._enqueue(
            "agent.results",
            run["case_id"],
            "processing_run_cancelled",
            {"case_id": run["case_id"], "run_id": run_id, "actor_id": actor_id, "reason": reason},
            idempotency_key=f"{run_id}:cancelled",
        )
        return run

    def retry_task(self, task_id: str, *, actor_id: str, reason: str | None = None) -> dict[str, Any]:
        task = self.require_task(task_id)
        if task["status"] not in RETRYABLE_TASK_STATUSES:
            raise ProcessingConflict(f"Задачу {task_id} нельзя повторить из статуса {task['status']}.")
        now = utc_now()
        task["status"] = "queued"
        task["attempt"] = int(task.get("attempt", 0)) + 1
        task["worker_id"] = None
        task["lease_until"] = None
        task["heartbeat_at"] = None
        task["updated_at"] = now
        task.setdefault("audit", []).append(self._audit_item("task_retry_queued", actor_id, reason))
        task["idempotency_key"] = f"{task['case_id']}:{task['task_id']}:attempt:{task['attempt']}"
        self._save_task(task)
        self._append_case_event(
            task["case_id"],
            "processing_task_retry_queued",
            "Администратор поставил задачу на повторную обработку.",
            {"run_id": task["run_id"], "task_id": task_id, "attempt": task["attempt"]},
        )
        self._enqueue(
            "agent.tasks",
            task["case_id"],
            "agent_task_retry_queued",
            {"case_id": task["case_id"], "run_id": task["run_id"], "task": task},
            idempotency_key=task["idempotency_key"],
        )
        return task

    def release_task_lease(self, task_id: str, *, actor_id: str, reason: str | None = None) -> dict[str, Any]:
        task = self.require_task(task_id)
        if task["status"] not in {"running", "leased"}:
            raise ProcessingConflict(f"У задачи {task_id} нет активного lease в статусе {task['status']}.")
        now = utc_now()
        task["status"] = "queued"
        task["worker_id"] = None
        task["lease_until"] = None
        task["heartbeat_at"] = None
        task["updated_at"] = now
        task.setdefault("audit", []).append(self._audit_item("task_lease_released", actor_id, reason))
        self._save_task(task)
        self._append_case_event(
            task["case_id"],
            "processing_task_lease_released",
            "Администратор освободил lease задачи.",
            {"run_id": task["run_id"], "task_id": task_id},
        )
        self._enqueue(
            "agent.tasks",
            task["case_id"],
            "agent_task_lease_released",
            {"case_id": task["case_id"], "run_id": task["run_id"], "task": task},
            idempotency_key=f"{task_id}:lease_released:{task['updated_at']}",
        )
        return task

    def claim_next_task(
        self,
        *,
        task_type: str,
        worker_id: str,
        lease_seconds: int = 60,
    ) -> dict[str, Any] | None:
        now = utc_now()
        lease_until = add_seconds(now, max(5, lease_seconds))
        with self._connect() as connection:
            row = connection.execute(
                """
                select task_json
                from agent_tasks
                where task_type = ?
                  and (
                    status = 'queued'
                    or (
                      status in ('running', 'leased')
                      and lease_until is not null
                      and lease_until < ?
                    )
                  )
                order by
                  case when status in ('running', 'leased') then 0 else 1 end,
                  created_at,
                  task_id
                limit 1
                """,
                (task_type, now),
            ).fetchone()
            if not row:
                return None
            task = json.loads(row["task_json"])
            previous_status = task.get("status")
            previous_worker_id = task.get("worker_id")
            previous_lease_until = task.get("lease_until")
            if previous_status in {"running", "leased"}:
                task["attempt"] = int(task.get("attempt") or 0) + 1
                task.setdefault("audit", []).append(
                    self._audit_item(
                        "task_lease_reclaimed",
                        worker_id,
                        (
                            f"Истекший lease worker={previous_worker_id or 'unknown'} "
                            f"до {previous_lease_until or 'unknown'} переарендован."
                        ),
                    )
                )
            task["status"] = "running"
            task["worker_id"] = worker_id
            task["lease_until"] = lease_until
            task["heartbeat_at"] = now
            task["updated_at"] = now
            cursor = connection.execute(
                """
                update agent_tasks
                set status = ?,
                    worker_id = ?,
                    lease_until = ?,
                    heartbeat_at = ?,
                    updated_at = ?,
                    task_json = ?
                where task_id = ?
                  and (
                    status = 'queued'
                    or (
                      status in ('running', 'leased')
                      and lease_until is not null
                      and lease_until < ?
                    )
                  )
                """,
                (
                    task["status"],
                    task["worker_id"],
                    task["lease_until"],
                    task["heartbeat_at"],
                    task["updated_at"],
                    self._to_json(task),
                    task["task_id"],
                    now,
                ),
            )
            if cursor.rowcount != 1:
                return None
        self._append_case_event(
            task["case_id"],
            "processing_task_started",
            "Задача продолжения обработки взята runtime worker-ом.",
            {
                "run_id": task["run_id"],
                "task_id": task["task_id"],
                "task_type": task["task_type"],
                "worker_id": worker_id,
            },
        )
        return task

    def complete_task(
        self,
        task_id: str,
        *,
        worker_id: str,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        task = self.require_task(task_id)
        if task.get("worker_id") not in {None, worker_id}:
            raise ProcessingConflict(f"Задача {task_id} принадлежит worker {task.get('worker_id')}.")
        now = utc_now()
        task["status"] = "completed"
        task["worker_id"] = worker_id
        task["lease_until"] = None
        task["heartbeat_at"] = now
        task["updated_at"] = now
        task["completed_at"] = now
        if result is not None:
            task["result"] = copy.deepcopy(result)
        self._save_task(task)
        self._append_case_event(
            task["case_id"],
            "processing_task_completed",
            "Задача продолжения обработки завершена runtime worker-ом.",
            {
                "run_id": task["run_id"],
                "task_id": task_id,
                "task_type": task.get("task_type"),
                "worker_id": worker_id,
                "result": copy.deepcopy(result or {}),
            },
        )
        self._enqueue(
            "agent.results",
            task["case_id"],
            "agent_task_completed",
            {
                "case_id": task["case_id"],
                "ticket_id": task["ticket_id"],
                "run_id": task["run_id"],
                "task": task,
            },
            idempotency_key=f"{task_id}:completed:{now}",
        )
        return task

    def fail_task(
        self,
        task_id: str,
        *,
        worker_id: str,
        error: str,
    ) -> dict[str, Any]:
        task = self.require_task(task_id)
        if task.get("worker_id") not in {None, worker_id}:
            raise ProcessingConflict(f"Задача {task_id} принадлежит worker {task.get('worker_id')}.")
        now = utc_now()
        task["status"] = "failed"
        task["worker_id"] = worker_id
        task["lease_until"] = None
        task["heartbeat_at"] = now
        task["updated_at"] = now
        task["error"] = self._sanitize_error_text(error)
        self._save_task(task)
        self._append_case_event(
            task["case_id"],
            "processing_task_failed",
            "Задача продолжения обработки завершилась ошибкой.",
            {
                "run_id": task["run_id"],
                "task_id": task_id,
                "task_type": task.get("task_type"),
                "worker_id": worker_id,
                "error": task["error"],
            },
        )
        self._enqueue(
            "dead-letter",
            task["case_id"],
            "agent_task_failed",
            {
                "case_id": task["case_id"],
                "ticket_id": task["ticket_id"],
                "run_id": task["run_id"],
                "task": task,
            },
            idempotency_key=f"{task_id}:failed:{now}",
        )
        return task

    def process_external_event_resume_task(
        self,
        task: dict[str, Any],
        *,
        worker_id: str,
    ) -> dict[str, Any]:
        if task.get("task_type") != "langgraph_resume":
            raise ProcessingConflict(f"Задача {task.get('task_id')} не является langgraph_resume.")
        extensions = task.get("extensions") if isinstance(task.get("extensions"), dict) else {}
        wait_id = extensions.get("wait_id")
        correlation_id = extensions.get("correlation_id")
        event_id = extensions.get("external_event_id")
        if not wait_id or not correlation_id:
            raise ProcessingConflict("langgraph_resume не содержит wait_id или correlation_id.")

        wait = self.require_wait(str(wait_id))
        receipts = self.external_event_receipts_for_wait(
            case_id=task.get("case_id"),
            wait_id=str(wait_id),
            correlation_id=str(correlation_id),
            limit=50,
        )
        selected_receipt = next(
            (
                receipt
                for receipt in receipts
                if not event_id
                or receipt.get("event_id") == event_id
                or self._external_event_from_receipt(receipt).get("event_id") == event_id
            ),
            None,
        )
        if not selected_receipt and event_id:
            terminal_receipts = [
                receipt
                for receipt in receipts
                if (
                    self._external_event_from_receipt(receipt).get("status")
                    or receipt.get("status")
                ) in EXTERNAL_EVENT_TERMINAL_STATUSES
            ]
            if len(terminal_receipts) == 1:
                selected_receipt = terminal_receipts[0]
        if not selected_receipt:
            raise ProcessingConflict(
                f"Для langgraph_resume {task.get('task_id')} не найден receipt external event {event_id or correlation_id}."
            )
        external_event = self._external_event_from_receipt(selected_receipt)
        event_status = external_event.get("status") or selected_receipt.get("status")
        if event_status not in EXTERNAL_EVENT_TERMINAL_STATUSES:
            raise ProcessingConflict(f"ExternalEvent {event_id or correlation_id} не terminal: {event_status}.")

        now = utc_now()
        run = self.require_run(task["run_id"])
        run["status"] = EXTERNAL_EVENT_WAIT_STATUS.get(str(event_status), "failed")
        run["current_step"] = "external_event_processed"
        run["updated_at"] = now
        run["completed_at"] = now
        run.setdefault("resume_results", []).append(
            {
                "processed_at": now,
                "task_id": task["task_id"],
                "wait_id": wait_id,
                "correlation_id": correlation_id,
                "event_id": external_event.get("event_id") or event_id,
                "event_type": external_event.get("event_type") or selected_receipt.get("event_type"),
                "event_status": event_status,
                "result": self._compact_external_event_value(external_event.get("result")),
                "error": external_event.get("error"),
            }
        )
        self._save_run(run)
        self._append_case_event(
            task["case_id"],
            "processing_external_event_resume_processed",
            f"Продолжение обработки после ExternalEvent завершено со статусом {event_status}.",
            {
                "run_id": run["run_id"],
                "task_id": task["task_id"],
                "wait_id": wait_id,
                "wait_status": wait.get("status"),
                "correlation_id": correlation_id,
                "event_id": external_event.get("event_id") or event_id,
                "event_type": external_event.get("event_type") or selected_receipt.get("event_type"),
                "event_status": event_status,
                "result": self._compact_external_event_value(external_event.get("result")),
                "error": external_event.get("error"),
            },
        )
        result = {
            "schema_version": "1.0",
            "run_id": run["run_id"],
            "run_status": run["status"],
            "wait_id": wait_id,
            "wait_status": wait.get("status"),
            "event_id": external_event.get("event_id") or event_id,
            "event_type": external_event.get("event_type") or selected_receipt.get("event_type"),
            "event_status": event_status,
        }
        self.complete_task(task["task_id"], worker_id=worker_id, result=result)
        return result

    def force_wait_timeout(self, wait_id: str, *, actor_id: str, reason: str | None = None) -> dict[str, Any]:
        wait = self.require_wait(wait_id)
        if wait["status"] not in ACTIVE_WAIT_STATUSES:
            raise ProcessingConflict(f"Ожидание {wait_id} уже находится в статусе {wait['status']}.")
        now = utc_now()
        wait["status"] = "timed_out"
        wait["updated_at"] = now
        wait["completed_at"] = now
        wait.setdefault("audit", []).append(self._audit_item("wait_force_timed_out", actor_id, reason))
        self._save_wait(wait)
        run = self.latest_run(wait["case_id"])
        if run and run.get("run_id") == wait.get("run_id") and run.get("status") == "waiting":
            run["status"] = "timed_out"
            run["updated_at"] = now
            run["completed_at"] = now
            self._save_run(run)
        self._append_case_event(
            wait["case_id"],
            "processing_wait_timed_out",
            "Администратор принудительно завершил ожидание по timeout.",
            {"run_id": wait["run_id"], "wait_id": wait_id, "wait_type": wait["wait_type"]},
        )
        self._enqueue(
            "timer.events",
            wait["case_id"],
            "wait_timed_out",
            {"case_id": wait["case_id"], "run_id": wait["run_id"], "wait": wait},
            idempotency_key=f"{wait_id}:timed_out",
        )
        return wait

    def escalate_case(self, case_id: str, *, actor_id: str, reason: str | None = None) -> dict[str, Any]:
        self.case_store.require(case_id)
        now = utc_now()
        run = self.latest_run(case_id)
        if run and run.get("status") not in TERMINAL_RUN_STATUSES:
            run["status"] = "escalated"
            run["updated_at"] = now
            run["completed_at"] = now
            run.setdefault("audit", []).append(self._audit_item("case_escalated", actor_id, reason))
            self._save_run(run)
        wait = self.active_wait(case_id)
        if wait:
            wait["status"] = "escalated"
            wait["updated_at"] = now
            wait["completed_at"] = now
            wait.setdefault("audit", []).append(self._audit_item("case_escalated", actor_id, reason))
            self._save_wait(wait)
        self._append_case_event(
            case_id,
            "processing_case_escalated",
            "Администратор передал кейс в эскалацию.",
            {"run_id": run.get("run_id") if run else None, "actor_id": actor_id, "reason": reason},
        )
        self._enqueue(
            "case.events",
            case_id,
            "case_escalated",
            {"case_id": case_id, "run_id": run.get("run_id") if run else None, "actor_id": actor_id, "reason": reason},
            idempotency_key=f"{case_id}:manual_escalation:{now}",
        )
        return self.case_detail(case_id)

    def begin_analysis_run_for_async_dispatch(
        self,
        ticket_input: dict[str, Any],
        analysis: dict[str, Any],
    ) -> dict[str, Any]:
        case_id = analysis["case_id"]
        if self.latest_run(case_id):
            return self.case_detail(case_id)
        now = utc_now()
        run = {
            "schema_version": "1.0",
            "run_id": new_run_id(),
            "case_id": case_id,
            "ticket_id": analysis["ticket_id"],
            "status": "running",
            "scenario_id": ticket_input.get("scenario") or "auto",
            "current_step": "tool_use",
            "source": "tickets.analyze",
            "config_versions": {},
            "started_at": now,
            "updated_at": now,
            "completed_at": None,
            "extensions": {
                "workflow_state_id": analysis.get("workflow_state", {}).get("id"),
                "decision_type": analysis.get("ai_decision", {}).get("decision", {}).get("type"),
                "async_dispatch_in_progress": True,
            },
        }
        with self._connect() as connection:
            self._insert_run(connection, run)
        self._append_case_event(
            case_id,
            "processing_run_started",
            "Запуск обработки зарегистрирован перед асинхронной постановкой команды.",
            {
                "run_id": run["run_id"],
                "run_status": run["status"],
                "scenario_id": run["scenario_id"],
            },
        )
        self._enqueue(
            "case.events",
            case_id,
            "processing_run_started",
            {
                "case_id": case_id,
                "ticket_id": analysis["ticket_id"],
                "run": run,
            },
            idempotency_key=f"{case_id}:run_started:{run['run_id']}",
        )
        return self.case_detail(case_id)

    def finalize_analysis_run(
        self,
        ticket_input: dict[str, Any],
        analysis: dict[str, Any],
        *,
        run: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        case_id = analysis["case_id"]
        run = run or self.latest_run(case_id)
        if not run:
            return self.record_analysis(ticket_input, analysis)
        if not run.get("extensions", {}).get("async_dispatch_in_progress"):
            return self.case_detail(case_id)

        now = utc_now()
        active_wait = self.active_wait(case_id)
        wait = None
        if active_wait and active_wait.get("run_id") == run["run_id"]:
            run["status"] = "waiting"
            run["current_step"] = active_wait.get("wait_type") or "external_event_wait"
            run["completed_at"] = None
        else:
            run["status"] = self._run_status_from_analysis(analysis)
            run["current_step"] = self._current_step_from_analysis(analysis)
            run["completed_at"] = now if run["status"] in TERMINAL_RUN_STATUSES else None
            wait = self._build_wait_from_analysis(run, analysis, now)
        run["updated_at"] = now
        extensions = run.setdefault("extensions", {})
        extensions.pop("async_dispatch_in_progress", None)
        extensions.update(
            {
                "workflow_state_id": analysis.get("workflow_state", {}).get("id"),
                "decision_type": analysis.get("ai_decision", {}).get("decision", {}).get("type"),
                "tool_result_count": len(analysis.get("tool_results", [])),
                "approval_request_count": len(analysis.get("approval_requests", [])),
            }
        )
        task = self._build_task_from_analysis(run, analysis, now)
        self._save_run(run)
        with self._connect() as connection:
            if wait:
                self._insert_wait(connection, wait)
            self._insert_task(connection, task)
        self._append_case_event(
            case_id,
            "processing_task_completed",
            "Задача анализа завершена текущим синхронным исполнителем.",
            {
                "run_id": run["run_id"],
                "task_id": task["task_id"],
                "task_status": task["status"],
            },
        )
        return self.case_detail(case_id)

    def latest_run(self, case_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                select run_json
                from processing_runs
                where case_id = ?
                order by started_at desc, run_id desc
                limit 1
                """,
                (case_id,),
            ).fetchone()
        return json.loads(row["run_json"]) if row else None

    def active_wait(self, case_id: str) -> dict[str, Any] | None:
        placeholders = ", ".join("?" for _ in ACTIVE_WAIT_STATUSES)
        with self._connect() as connection:
            row = connection.execute(
                f"""
                select wait_json
                from wait_states
                where case_id = ?
                  and status in ({placeholders})
                order by created_at desc, wait_id desc
                limit 1
                """,
                [case_id, *sorted(ACTIVE_WAIT_STATUSES)],
            ).fetchone()
        return json.loads(row["wait_json"]) if row else None

    def active_wait_by_correlation(
        self,
        correlation_id: str,
        *,
        case_id: str | None = None,
    ) -> dict[str, Any] | None:
        placeholders = ", ".join("?" for _ in ACTIVE_WAIT_STATUSES)
        parameters: list[Any] = [correlation_id, *sorted(ACTIVE_WAIT_STATUSES)]
        case_filter = ""
        if case_id:
            case_filter = "and case_id = ?"
            parameters.append(case_id)
        with self._connect() as connection:
            row = connection.execute(
                f"""
                select wait_json
                from wait_states
                where correlation_id = ?
                  and status in ({placeholders})
                  {case_filter}
                order by created_at desc, wait_id desc
                limit 1
                """,
                parameters,
            ).fetchone()
        return json.loads(row["wait_json"]) if row else None

    def stale_task_count(self) -> int:
        now = utc_now()
        with self._connect() as connection:
            row = connection.execute(
                """
                select count(*) as count
                from agent_tasks
                where status in ('running', 'leased')
                  and lease_until is not null
                  and lease_until < ?
                """,
                (now,),
            ).fetchone()
        return int(row["count"] if row else 0)

    def require_run(self, run_id: str) -> dict[str, Any]:
        row = self._get_json_by_id("processing_runs", "run_id", run_id, "run_json")
        if row is None:
            raise ProcessingNotFound(run_id)
        return row

    def require_task(self, task_id: str) -> dict[str, Any]:
        row = self._get_json_by_id("agent_tasks", "task_id", task_id, "task_json")
        if row is None:
            raise ProcessingNotFound(task_id)
        return row

    def require_wait(self, wait_id: str) -> dict[str, Any]:
        row = self._get_json_by_id("wait_states", "wait_id", wait_id, "wait_json")
        if row is None:
            raise ProcessingNotFound(wait_id)
        return row

    def _build_task_from_analysis(
        self,
        run: dict[str, Any],
        analysis: dict[str, Any],
        now: str,
    ) -> dict[str, Any]:
        status = "failed" if run["status"] == "failed" else "completed"
        return {
            "schema_version": "1.0",
            "task_id": new_task_id(),
            "run_id": run["run_id"],
            "case_id": run["case_id"],
            "ticket_id": run["ticket_id"],
            "task_type": "langgraph_run",
            "topic": "agent.tasks",
            "status": status,
            "worker_id": "sync-fastapi",
            "attempt": 1,
            "lease_until": None,
            "heartbeat_at": now,
            "idempotency_key": f"{run['case_id']}:{run['run_id']}:attempt:1",
            "created_at": now,
            "updated_at": now,
            "completed_at": now,
            "extensions": {
                "workflow_state_id": analysis.get("workflow_state", {}).get("id"),
                "tool_result_count": len(analysis.get("tool_results", [])),
                "approval_request_count": len(analysis.get("approval_requests", [])),
            },
        }

    @staticmethod
    def _build_external_event_resume_task(
        run: dict[str, Any],
        wait: dict[str, Any],
        event: dict[str, Any],
        now: str,
    ) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "task_id": new_task_id(),
            "run_id": run["run_id"],
            "case_id": run["case_id"],
            "ticket_id": run["ticket_id"],
            "task_type": "langgraph_resume",
            "topic": "agent.tasks",
            "status": "queued",
            "worker_id": None,
            "attempt": 1,
            "lease_until": None,
            "heartbeat_at": None,
            "idempotency_key": f"{run['case_id']}:{wait['wait_id']}:{event['event_id']}:resume",
            "created_at": now,
            "updated_at": now,
            "extensions": {
                "wait_id": wait["wait_id"],
                "correlation_id": event["correlation_id"],
                "external_event_id": event["event_id"],
                "external_event_type": event["event_type"],
                "external_event_status": event["status"],
                "source": event["source"],
                "origin": copy.deepcopy(wait.get("origin")),
            },
        }

    @staticmethod
    def _build_wait_from_analysis(
        run: dict[str, Any],
        analysis: dict[str, Any],
        now: str,
    ) -> dict[str, Any] | None:
        decision = analysis.get("ai_decision", {}).get("decision", {})
        workflow_state_id = analysis.get("workflow_state", {}).get("id")
        wait_type = None
        reason = None
        payload: dict[str, Any] = {}
        if decision.get("type") == "clarification_needed":
            wait_type = "client_wait"
            reason = "Оркестратор запросил уточнение у клиента."
            payload = {
                "question": decision.get("question"),
                "expected_slots": decision.get("missing_fields", []),
            }
            origin = {
                "kind": "client_question",
                "question": decision.get("question"),
                "slot_ids": decision.get("missing_fields", []),
                "channel_id": "debug",
            }
        elif analysis.get("approval_requests"):
            wait_type = "operator_approval"
            reason = "Ожидается решение оператора по согласованию действия."
            approval_ids = [
                item.get("gate_id") or item.get("approval_id")
                for item in analysis.get("approval_requests", [])
                if item.get("gate_id") or item.get("approval_id")
            ]
            payload = {
                "approval_ids": approval_ids,
            }
            origin = {
                "kind": "approval",
                "approval_ids": approval_ids,
                "channel_id": "debug",
            }
        elif workflow_state_id == "waiting_for_user":
            wait_type = "client_wait"
            reason = "Workflow находится в ожидании ответа клиента."
            origin = {
                "kind": "client_question",
                "workflow_state_id": workflow_state_id,
                "channel_id": "debug",
            }
        if not wait_type:
            return None

        deadline_seconds = 8 * 60 if wait_type == "client_wait" else 30 * 60
        return {
            "schema_version": "1.0",
            "wait_id": new_wait_id(),
            "run_id": run["run_id"],
            "case_id": run["case_id"],
            "ticket_id": run["ticket_id"],
            "wait_type": wait_type,
            "status": "open",
            "channel_id": "debug",
            "deadline_at": add_seconds(now, deadline_seconds),
            "correlation_id": f"{run['case_id']}:{wait_type}:{run['run_id']}",
            "created_at": now,
            "updated_at": now,
            "reason": reason,
            "origin": ProcessingStore._normalize_wait_origin(
                origin,
                default_kind="client_question" if wait_type == "client_wait" else "approval",
                reason=reason,
                wait_type=wait_type,
            ),
            "payload": payload,
        }

    @staticmethod
    def _run_status_from_analysis(analysis: dict[str, Any]) -> str:
        state = analysis.get("workflow_state", {})
        category = state.get("category")
        decision_type = analysis.get("ai_decision", {}).get("decision", {}).get("type")
        if analysis.get("failure") or category in {"error", "blocked"}:
            return "failed"
        if decision_type == "escalation_needed" or category == "handoff":
            return "escalated"
        for result in analysis.get("tool_results", []):
            extensions = result.get("extensions") if isinstance(result.get("extensions"), dict) else {}
            if isinstance(extensions.get("async_wait"), dict):
                return "waiting"
        for result in analysis.get("tool_results", []):
            if result.get("status") == "error":
                return "failed"
        if category == "waiting" or analysis.get("approval_requests"):
            return "waiting"
        return "completed"

    @staticmethod
    def _current_step_from_analysis(analysis: dict[str, Any]) -> str:
        decision_type = analysis.get("ai_decision", {}).get("decision", {}).get("type")
        if decision_type == "clarification_needed":
            return "waiting"
        if decision_type == "action_proposed":
            return "tool_use"
        if decision_type == "escalation_needed":
            return "decision"
        if analysis.get("failure"):
            return "error"
        return "decision"

    def _insert_run(self, connection: sqlite3.Connection, run: dict[str, Any]) -> None:
        connection.execute(
            """
            insert into processing_runs (
                run_id, case_id, ticket_id, status, scenario_id, current_step,
                started_at, updated_at, completed_at, run_json
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run["run_id"],
                run["case_id"],
                run["ticket_id"],
                run["status"],
                run["scenario_id"],
                run["current_step"],
                run["started_at"],
                run["updated_at"],
                run.get("completed_at"),
                self._to_json(run),
            ),
        )

    def _insert_task(self, connection: sqlite3.Connection, task: dict[str, Any]) -> None:
        connection.execute(
            """
            insert into agent_tasks (
                task_id, run_id, case_id, ticket_id, task_type, status, topic,
                worker_id, attempt, lease_until, heartbeat_at, idempotency_key,
                created_at, updated_at, task_json
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task["task_id"],
                task["run_id"],
                task["case_id"],
                task["ticket_id"],
                task["task_type"],
                task["status"],
                task["topic"],
                task.get("worker_id"),
                task.get("attempt", 0),
                task.get("lease_until"),
                task.get("heartbeat_at"),
                task["idempotency_key"],
                task["created_at"],
                task["updated_at"],
                self._to_json(task),
            ),
        )

    def _insert_wait(self, connection: sqlite3.Connection, wait: dict[str, Any]) -> None:
        connection.execute(
            """
            insert into wait_states (
                wait_id, run_id, case_id, ticket_id, wait_type, status, channel_id,
                deadline_at, correlation_id, created_at, updated_at, wait_json
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                wait["wait_id"],
                wait["run_id"],
                wait["case_id"],
                wait["ticket_id"],
                wait["wait_type"],
                wait["status"],
                wait.get("channel_id"),
                wait.get("deadline_at"),
                wait.get("correlation_id"),
                wait["created_at"],
                wait["updated_at"],
                self._to_json(wait),
            ),
        )

    def _save_run(self, run: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                update processing_runs
                set status = ?,
                    current_step = ?,
                    updated_at = ?,
                    completed_at = ?,
                    run_json = ?
                where run_id = ?
                """,
                (
                    run["status"],
                    run.get("current_step"),
                    run["updated_at"],
                    run.get("completed_at"),
                    self._to_json(run),
                    run["run_id"],
                ),
            )

    def _save_task(self, task: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                update agent_tasks
                set status = ?,
                    worker_id = ?,
                    attempt = ?,
                    lease_until = ?,
                    heartbeat_at = ?,
                    idempotency_key = ?,
                    updated_at = ?,
                    task_json = ?
                where task_id = ?
                """,
                (
                    task["status"],
                    task.get("worker_id"),
                    task.get("attempt", 0),
                    task.get("lease_until"),
                    task.get("heartbeat_at"),
                    task["idempotency_key"],
                    task["updated_at"],
                    self._to_json(task),
                    task["task_id"],
                ),
            )

    def _save_wait(self, wait: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                update wait_states
                set status = ?,
                    deadline_at = ?,
                    updated_at = ?,
                    wait_json = ?
                where wait_id = ?
                """,
                (
                    wait["status"],
                    wait.get("deadline_at"),
                    wait["updated_at"],
                    self._to_json(wait),
                    wait["wait_id"],
                ),
            )

    def _set_related_active_items(
        self,
        run: dict[str, Any],
        status: str,
        actor_id: str,
        reason: str | None,
    ) -> None:
        for task in self.list_tasks(case_id=run["case_id"], limit=500)["tasks"]:
            if task.get("run_id") == run["run_id"] and task.get("status") in ACTIVE_TASK_STATUSES:
                task["status"] = status
                task["updated_at"] = utc_now()
                task.setdefault("audit", []).append(self._audit_item(f"task_{status}", actor_id, reason))
                self._save_task(task)
        for wait in self.list_waits(case_id=run["case_id"], limit=500)["waits"]:
            if wait.get("run_id") == run["run_id"] and wait.get("status") in ACTIVE_WAIT_STATUSES:
                wait["status"] = status
                wait["updated_at"] = utc_now()
                wait["completed_at"] = wait["updated_at"]
                wait.setdefault("audit", []).append(self._audit_item(f"wait_{status}", actor_id, reason))
                self._save_wait(wait)

    def _enqueue(
        self,
        topic: str,
        key: str,
        event_type: str,
        payload: dict[str, Any],
        *,
        idempotency_key: str,
    ) -> dict[str, Any]:
        now = utc_now()
        message = {
            "schema_version": "1.0",
            "message_id": new_message_id(),
            "topic": topic,
            "key": key,
            "event_type": event_type,
            "idempotency_key": idempotency_key,
            "status": "pending",
            "created_at": now,
            "updated_at": now,
            "attempts": 0,
            "payload": payload,
        }
        with self._connect() as connection:
            cursor = connection.execute(
                """
                insert or ignore into processing_outbox (
                    message_id, topic, message_key, event_type, status,
                    idempotency_key, payload_json, created_at, updated_at, attempts
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message["message_id"],
                    topic,
                    key,
                    event_type,
                    "pending",
                    idempotency_key,
                    self._to_json(message),
                    now,
                    now,
                    0,
                ),
            )
            if cursor.rowcount:
                return message
            row = connection.execute(
                """
                select payload_json
                from processing_outbox
                where idempotency_key = ?
                """,
                (idempotency_key,),
            ).fetchone()
        if row:
            return json.loads(row["payload_json"])
        raise ProcessingConflict(f"Не удалось поставить outbox message: {idempotency_key}")

    def _append_case_event(
        self,
        case_id: str,
        event_type: str,
        summary: str,
        payload: dict[str, Any],
    ) -> None:
        clean_payload = {
            key: value
            for key, value in payload.items()
            if value is not None
        }
        try:
            self.case_store.append_event(
                case_id,
                event_type,
                actor_type="system",
                actor_id="processing_store",
                summary=summary,
                payload=clean_payload,
            )
        except CaseNotFound:
            raise

    def _list_json_rows(
        self,
        table: str,
        json_column: str,
        *,
        case_id: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        where = ""
        parameters: list[Any] = []
        if case_id:
            where = "where case_id = ?"
            parameters.append(case_id)
        parameters.append(min(max(limit, 0), 500))
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                select {json_column}
                from {table}
                {where}
                order by updated_at desc, rowid desc
                limit ?
                """,
                parameters,
            ).fetchall()
        return [json.loads(row[json_column]) for row in rows]

    def _get_json_by_id(
        self,
        table: str,
        id_column: str,
        item_id: str,
        json_column: str,
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                f"select {json_column} from {table} where {id_column} = ?",
                (item_id,),
            ).fetchone()
        return json.loads(row[json_column]) if row else None

    def _count_statuses(self, table: str, statuses: set[str]) -> int:
        placeholders = ", ".join("?" for _ in statuses)
        with self._connect() as connection:
            row = connection.execute(
                f"select count(*) as count from {table} where status in ({placeholders})",
                sorted(statuses),
            ).fetchone()
        return int(row["count"] if row else 0)

    @staticmethod
    def _audit_item(event: str, actor_id: str, reason: str | None) -> dict[str, Any]:
        item = {
            "event": event,
            "actor_id": actor_id,
            "created_at": utc_now(),
        }
        if reason:
            item["reason"] = reason
        return item

    @staticmethod
    def _wait_summary(wait: dict[str, Any]) -> str:
        if wait["wait_type"] == "client_wait":
            return "Открыто ожидание ответа клиента."
        if wait["wait_type"] == "operator_approval":
            return "Открыто ожидание согласования оператора."
        return "Открыто ожидание внешнего события."

    @staticmethod
    def _normalize_wait_origin(
        origin: dict[str, Any] | None,
        *,
        default_kind: str,
        reason: str | None = None,
        wait_type: str | None = None,
    ) -> dict[str, Any]:
        cleaned = copy.deepcopy(origin) if isinstance(origin, dict) else {}
        kind = str(cleaned.get("kind") or default_kind or "unknown")
        if kind not in WAIT_ORIGIN_KINDS:
            kind = "unknown"
        cleaned["kind"] = kind
        if reason and not cleaned.get("reason"):
            cleaned["reason"] = reason
        if wait_type and not cleaned.get("wait_type"):
            cleaned["wait_type"] = wait_type
        return ProcessingStore._sanitize_wait_origin(cleaned)

    @staticmethod
    def _sanitize_wait_origin(value: Any) -> Any:
        if isinstance(value, dict):
            result: dict[str, Any] = {}
            for key, item in value.items():
                normalized_key = str(key).lower()
                if any(keyword in normalized_key for keyword in SENSITIVE_ORIGIN_KEYWORDS):
                    result[key] = "параметр скрыт"
                else:
                    result[key] = ProcessingStore._sanitize_wait_origin(item)
            return result
        if isinstance(value, list):
            return [ProcessingStore._sanitize_wait_origin(item) for item in value]
        return copy.deepcopy(value)

    @staticmethod
    def _external_event_summary(event: dict[str, Any]) -> dict[str, Any]:
        summary = {
            "event_id": event["event_id"],
            "correlation_id": event["correlation_id"],
            "source": event["source"],
            "event_type": event["event_type"],
            "status": event["status"],
            "received_at": event["received_at"],
        }
        for key in ("result", "error", "raw_reference", "metadata"):
            if key in event:
                summary[key] = ProcessingStore._compact_external_event_value(event[key])
        return summary

    @staticmethod
    def _compact_external_event_value(value: Any, *, limit: int = 4000) -> Any:
        serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
        if len(serialized) <= limit:
            return copy.deepcopy(value)
        return {
            "summary": "payload слишком большой для wait_state; полный payload хранится в receipt события.",
            "size_bytes": len(serialized.encode("utf-8")),
            "preview": serialized[: min(500, len(serialized))],
        }

    @staticmethod
    def _prepare_async_invocation_for_storage(invocation: dict[str, Any]) -> None:
        extensions = invocation.get("extensions") if isinstance(invocation.get("extensions"), dict) else {}
        secret_parameters = extensions.get("secret_operation_parameters")
        if not isinstance(secret_parameters, dict):
            return
        operation_parameters = invocation.get("operation_parameters")
        if not isinstance(operation_parameters, dict):
            return
        for parameter in secret_parameters:
            if parameter in operation_parameters:
                operation_parameters[parameter] = "параметр скрыт"

    @staticmethod
    def _sanitize_external_event_payload(value: Any) -> Any:
        if isinstance(value, dict):
            result: dict[str, Any] = {}
            for key, item in value.items():
                normalized_key = str(key).lower()
                if any(keyword in normalized_key for keyword in SENSITIVE_ORIGIN_KEYWORDS):
                    result[key] = "параметр скрыт"
                else:
                    result[key] = ProcessingStore._sanitize_external_event_payload(item)
            return result
        if isinstance(value, list):
            return [ProcessingStore._sanitize_external_event_payload(item) for item in value]
        if isinstance(value, (bytes, bytearray)):
            return value.decode("utf-8", errors="replace")
        if isinstance(value, str):
            return redact_for_llm(value).text
        return copy.deepcopy(value)

    @staticmethod
    def _external_event_for_storage(event: dict[str, Any]) -> dict[str, Any]:
        safe_event = ProcessingStore._sanitize_external_event_payload(event)
        for key in ("result", "error", "raw_reference", "metadata"):
            if key in safe_event:
                safe_event[key] = ProcessingStore._compact_external_event_value(safe_event[key])
        return safe_event

    @staticmethod
    def _sanitize_error_text(error: str) -> str:
        return redact_for_llm(str(error)).text[:1000]

    @staticmethod
    def _external_event_payload_hash(event: dict[str, Any]) -> str:
        payload = {
            key: ProcessingStore._sanitize_external_event_payload(event[key])
            for key in ("result", "error", "raw_reference", "metadata", "attachments")
            if key in event
        }
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def _external_event_duplicate_result(receipt: dict[str, Any]) -> dict[str, Any]:
        result = receipt.get("result") or {}
        wait = result.get("wait") if isinstance(result, dict) else None
        resume_task = result.get("resume_task") if isinstance(result, dict) else None
        response: dict[str, Any] = {
            "schema_version": "1.0",
            "accepted": True,
            "duplicate": True,
            "idempotency_key": receipt.get("idempotency_key"),
            "event_id": receipt.get("event_id"),
            "source": receipt.get("source"),
            "case_id": receipt.get("case_id"),
            "correlation_id": receipt.get("correlation_id"),
            "wait_id": receipt.get("wait_id"),
            "event_type": receipt.get("event_type"),
            "status": receipt.get("status"),
        }
        if isinstance(wait, dict):
            response["wait"] = {
                key: wait.get(key)
                for key in (
                    "wait_id",
                    "case_id",
                    "ticket_id",
                    "wait_type",
                    "status",
                    "correlation_id",
                    "expected_event_type",
                )
                if wait.get(key) not in (None, "", [], {})
            }
        if isinstance(resume_task, dict):
            response["resume_task"] = {
                key: resume_task.get(key)
                for key in ("task_id", "run_id", "case_id", "status", "topic", "idempotency_key")
                if resume_task.get(key) not in (None, "", [], {})
            }
        return response

    @staticmethod
    def _ensure_external_event_receipt_matches(receipt: dict[str, Any], event: dict[str, Any]) -> None:
        expected = {
            "event_id": event.get("event_id"),
            "source": event.get("source"),
            "case_id": event.get("case_id"),
            "correlation_id": event.get("correlation_id"),
            "wait_id": event.get("wait_id"),
            "event_type": event.get("event_type"),
            "status": event.get("status"),
        }
        mismatched = [
            key
            for key, value in expected.items()
            if value not in (None, "") and receipt.get(key) not in (None, "", value)
        ]
        if mismatched:
            raise ExternalEventIdempotencyConflict(
                "external_event_idempotency_conflict: idempotency_key уже использован для другого события "
                f"({', '.join(sorted(mismatched))})."
            )
        expected_hash = receipt.get("payload_hash")
        actual_hash = ProcessingStore._external_event_payload_hash(event)
        if expected_hash and expected_hash != actual_hash:
            raise ExternalEventIdempotencyConflict(
                "external_event_idempotency_conflict: idempotency_key уже использован для события с другим payload."
            )

    @staticmethod
    def _ensure_external_event_source_matches(wait: dict[str, Any], event: dict[str, Any]) -> None:
        expected_sources = {
            str(value)
            for value in (
                wait.get("channel_id"),
                (wait.get("payload") or {}).get("source"),
                (wait.get("origin") or {}).get("source"),
                (wait.get("origin") or {}).get("endpoint_id"),
            )
            if value
        }
        if expected_sources and event.get("source") not in expected_sources:
            raise ProcessingConflict(
                f"source {event.get('source')} не совпадает с ожидаемым источником ожидания: "
                f"{', '.join(sorted(expected_sources))}."
            )

    @staticmethod
    def _wait_result_transport(wait: dict[str, Any]) -> str | None:
        payload = wait.get("payload") or {}
        origin = wait.get("origin") or {}
        value = payload.get("result_transport") or origin.get("result_transport")
        return str(value) if value else None

    @staticmethod
    def _wait_result_topic(wait: dict[str, Any]) -> str | None:
        payload = wait.get("payload") or {}
        origin = wait.get("origin") or {}
        value = payload.get("result_topic") or origin.get("result_topic")
        return str(value) if value else None

    @staticmethod
    def _wait_result_topics(wait: dict[str, Any]) -> set[str]:
        payload = wait.get("payload") or {}
        origin = wait.get("origin") or {}
        topics: set[str] = set()

        def add_topic(value: Any) -> None:
            if isinstance(value, list):
                for item in value:
                    add_topic(item)
                return
            if isinstance(value, str) and value.strip():
                topics.add(value.strip())

        for source in (payload, origin):
            add_topic(source.get("result_topic"))
            add_topic(source.get("invalid_topic"))
            add_topic(source.get("result_topics"))
            add_topic(source.get("allowed_result_topics"))
        return topics

    @staticmethod
    def _ensure_external_event_transport_matches(
        wait: dict[str, Any],
        *,
        received_transport: str,
        source_topic: str | None = None,
    ) -> None:
        if received_transport == "internal":
            return
        expected_transport = ProcessingStore._wait_result_transport(wait)
        if not expected_transport:
            return
        allowed = EXTERNAL_EVENT_TRANSPORT_ALLOWLIST.get(expected_transport, set())
        if received_transport not in allowed:
            raise ProcessingConflict(
                f"ExternalEvent получен через {received_transport}, но ожидание разрешает {expected_transport}."
            )
        if received_transport == "kafka_event":
            expected_topics = ProcessingStore._wait_result_topics(wait)
            if expected_topics and source_topic and source_topic not in expected_topics:
                raise ProcessingConflict(
                    f"ExternalEvent получен из topic {source_topic}, но ожидание ожидает "
                    f"{', '.join(sorted(expected_topics))}."
                )

    def _claim_external_event_receipt(
        self,
        event: dict[str, Any],
    ) -> dict[str, Any]:
        now = utc_now()
        receipt = {
            "schema_version": "1.0",
            "receipt_status": "processing",
            "idempotency_key": event["idempotency_key"],
            "event_id": event["event_id"],
            "wait_id": event.get("wait_id"),
            "event_type": event["event_type"],
            "source": event["source"],
            "case_id": event["case_id"],
            "correlation_id": event["correlation_id"],
            "status": event["status"],
            "payload_hash": self._external_event_payload_hash(event),
            "created_at": now,
            "updated_at": now,
            "result": {
                "schema_version": "1.0",
                "accepted": True,
                "duplicate": True,
                "idempotency_key": event["idempotency_key"],
            },
        }
        with self._connect() as connection:
            cursor = connection.execute(
                """
                insert into external_event_receipts (
                    idempotency_key,
                    source,
                    case_id,
                    correlation_id,
                    status,
                    receipt_json,
                    created_at,
                    updated_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(idempotency_key) do nothing
                """,
                (
                    receipt["idempotency_key"],
                    receipt["source"],
                    receipt["case_id"],
                    receipt["correlation_id"],
                    receipt["status"],
                    self._to_json(receipt),
                    receipt["created_at"],
                    receipt["updated_at"],
                ),
            )
        if cursor.rowcount:
            return receipt
        existing = self.external_event_receipt(event["idempotency_key"])
        if existing:
            self._ensure_external_event_receipt_matches(existing, event)
            raise ExternalEventIdempotencyConflict(
                "external_event_idempotency_conflict: idempotency_key уже обрабатывается другим worker."
            )
        raise ProcessingConflict(f"Не удалось зафиксировать idempotency claim: {event['idempotency_key']}")

    def _complete_external_event_receipt(
        self,
        event: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        now = utc_now()
        receipt = {
            "schema_version": "1.0",
            "receipt_status": "completed",
            "idempotency_key": event["idempotency_key"],
            "event_id": event["event_id"],
            "wait_id": event.get("wait_id"),
            "event_type": event["event_type"],
            "source": event["source"],
            "case_id": event["case_id"],
            "correlation_id": event["correlation_id"],
            "status": event["status"],
            "payload_hash": self._external_event_payload_hash(event),
            "created_at": now,
            "updated_at": now,
            "result": copy.deepcopy(result),
        }
        with self._connect() as connection:
            cursor = connection.execute(
                """
                update external_event_receipts
                set status = ?,
                    receipt_json = ?,
                    updated_at = ?
                where idempotency_key = ?
                """,
                (
                    receipt["status"],
                    self._to_json(receipt),
                    receipt["updated_at"],
                    receipt["idempotency_key"],
                ),
            )
        if not cursor.rowcount:
            raise ProcessingConflict(f"external event receipt не найден: {event['idempotency_key']}")
        return receipt

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                create table if not exists processing_runs (
                    run_id text primary key,
                    case_id text not null,
                    ticket_id text not null,
                    status text not null,
                    scenario_id text not null,
                    current_step text,
                    started_at text not null,
                    updated_at text not null,
                    completed_at text,
                    run_json text not null
                )
                """
            )
            connection.execute("create index if not exists idx_processing_runs_case_id on processing_runs(case_id)")
            connection.execute("create index if not exists idx_processing_runs_status on processing_runs(status)")
            connection.execute(
                """
                create table if not exists agent_tasks (
                    task_id text primary key,
                    run_id text not null,
                    case_id text not null,
                    ticket_id text not null,
                    task_type text not null,
                    status text not null,
                    topic text not null,
                    worker_id text,
                    attempt integer not null,
                    lease_until text,
                    heartbeat_at text,
                    idempotency_key text not null unique,
                    created_at text not null,
                    updated_at text not null,
                    task_json text not null
                )
                """
            )
            connection.execute("create index if not exists idx_agent_tasks_case_id on agent_tasks(case_id)")
            connection.execute("create index if not exists idx_agent_tasks_status on agent_tasks(status)")
            connection.execute("create index if not exists idx_agent_tasks_run_id on agent_tasks(run_id)")
            connection.execute(
                """
                create table if not exists wait_states (
                    wait_id text primary key,
                    run_id text not null,
                    case_id text not null,
                    ticket_id text not null,
                    wait_type text not null,
                    status text not null,
                    channel_id text,
                    deadline_at text,
                    correlation_id text,
                    created_at text not null,
                    updated_at text not null,
                    wait_json text not null
                )
                """
            )
            connection.execute("create index if not exists idx_wait_states_case_id on wait_states(case_id)")
            connection.execute("create index if not exists idx_wait_states_status on wait_states(status)")
            connection.execute("create index if not exists idx_wait_states_correlation_id on wait_states(correlation_id)")
            connection.execute(
                """
                create table if not exists processing_outbox (
                    message_id text primary key,
                    topic text not null,
                    message_key text not null,
                    event_type text not null,
                    status text not null,
                    idempotency_key text not null unique,
                    payload_json text not null,
                    created_at text not null,
                    published_at text
                )
                """
            )
            self._ensure_outbox_columns(connection)
            connection.execute("create index if not exists idx_processing_outbox_topic on processing_outbox(topic)")
            connection.execute("create index if not exists idx_processing_outbox_key on processing_outbox(message_key)")
            connection.execute("create index if not exists idx_processing_outbox_status on processing_outbox(status)")
            connection.execute(
                """
                create table if not exists external_event_receipts (
                    idempotency_key text primary key,
                    source text not null,
                    case_id text not null,
                    correlation_id text not null,
                    status text not null,
                    receipt_json text not null,
                    created_at text not null,
                    updated_at text not null
                )
                """
            )
            connection.execute(
                """
                create index if not exists idx_external_event_receipts_case_id
                on external_event_receipts(case_id)
                """
            )
            connection.execute(
                """
                create index if not exists idx_external_event_receipts_correlation_id
                on external_event_receipts(correlation_id)
                """
            )
            connection.execute(
                """
                create table if not exists tool_command_receipts (
                    idempotency_key text primary key,
                    command_id text not null,
                    case_id text not null,
                    wait_id text not null,
                    correlation_id text not null,
                    status text not null,
                    worker_id text,
                    receipt_json text not null,
                    created_at text not null,
                    updated_at text not null
                )
                """
            )
            connection.execute(
                """
                create index if not exists idx_tool_command_receipts_case_id
                on tool_command_receipts(case_id)
                """
            )
            connection.execute(
                """
                create index if not exists idx_tool_command_receipts_wait_id
                on tool_command_receipts(wait_id)
                """
            )
            connection.execute(
                """
                create table if not exists runtime_heartbeats (
                    component_id text primary key,
                    role text not null,
                    display_name text not null,
                    worker_id text not null,
                    topic text,
                    status text not null,
                    last_seen_at text not null,
                    last_error text,
                    details_json text not null,
                    created_at text not null,
                    updated_at text not null
                )
                """
            )
            connection.execute(
                """
                create index if not exists idx_runtime_heartbeats_role
                on runtime_heartbeats(role)
                """
            )
            connection.execute(
                """
                create index if not exists idx_runtime_heartbeats_last_seen
                on runtime_heartbeats(last_seen_at)
                """
            )

    @staticmethod
    def _ensure_outbox_columns(connection: sqlite3.Connection) -> None:
        columns = {
            str(row["name"])
            for row in connection.execute("pragma table_info(processing_outbox)").fetchall()
        }
        additions = {
            "locked_by": "alter table processing_outbox add column locked_by text",
            "locked_until": "alter table processing_outbox add column locked_until text",
            "attempts": "alter table processing_outbox add column attempts integer not null default 0",
            "last_error": "alter table processing_outbox add column last_error text",
            "updated_at": "alter table processing_outbox add column updated_at text",
        }
        for name, statement in additions.items():
            if name not in columns:
                connection.execute(statement)
        connection.execute(
            """
            update processing_outbox
            set updated_at = created_at
            where updated_at is null
            """
        )

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _to_json(record: dict[str, Any]) -> str:
        return json.dumps(record, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _counts(rows: list[sqlite3.Row], key: str) -> dict[str, int]:
        return {
            str(row[key]): int(row["count"])
            for row in rows
        }
