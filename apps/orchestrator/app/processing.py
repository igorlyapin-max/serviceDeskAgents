from __future__ import annotations

import copy
import json
import os
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .action_gates import DEFAULT_STATE_DB_PATH, utc_now
from .cases import CaseNotFound, CaseStore


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
        if self.latest_run(case_id):
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

    def record_external_event(self, event: dict[str, Any]) -> dict[str, Any]:
        event = copy.deepcopy(event)
        event.setdefault("received_at", utc_now())
        receipt = self.external_event_receipt(event["idempotency_key"])
        if receipt:
            self._ensure_external_event_receipt_matches(receipt, event)
            return self._external_event_duplicate_result(receipt)

        wait = self.active_wait_by_correlation(
            event["correlation_id"],
            case_id=event.get("case_id"),
        )
        if not wait:
            raise ProcessingNotFound(event["correlation_id"])
        self._ensure_external_event_source_matches(wait, event)
        if event.get("wait_id") and event["wait_id"] != wait["wait_id"]:
            raise ProcessingConflict(
                f"wait_id {event['wait_id']} не совпадает с активным ожиданием {wait['wait_id']}."
            )
        expected_event_type = wait.get("expected_event_type") or (wait.get("payload") or {}).get("expected_event_type")
        if expected_event_type and expected_event_type != event["event_type"]:
            raise ProcessingConflict(
                f"event_type {event['event_type']} не совпадает с ожидаемым {expected_event_type}."
            )

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
        self._record_external_event_receipt(event, result)
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
        waits_by_type: dict[str, dict[str, int]] = {}
        for row in wait_rows:
            waits_by_type.setdefault(str(row["wait_type"]), {})[str(row["status"])] = int(row["count"])
        return {
            "schema_version": "1.0",
            "kafka": {
                "bootstrap_servers": self.kafka_bootstrap_servers,
                "topics": copy.deepcopy(KAFKA_TOPICS),
                "outbox_pending": int(outbox_total["count"] if outbox_total else 0),
            },
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
        case = self.case_store.require(case_id)
        return {
            "schema_version": "1.0",
            "case": case,
            "timeline": self.case_events(case_id=case_id, limit=200),
            "runs": self.list_runs(case_id=case_id, limit=50)["runs"],
            "tasks": self.list_tasks(case_id=case_id, limit=100)["tasks"],
            "waits": self.list_waits(case_id=case_id, limit=100)["waits"],
            "outbox": self.list_outbox(case_id=case_id, limit=50)["messages"],
        }

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
    ) -> None:
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
            "payload": payload,
        }
        with self._connect() as connection:
            connection.execute(
                """
                insert or ignore into processing_outbox (
                    message_id, topic, message_key, event_type, status,
                    idempotency_key, payload_json, created_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?)
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
                ),
            )

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
        return copy.deepcopy(value)

    @staticmethod
    def _external_event_for_storage(event: dict[str, Any]) -> dict[str, Any]:
        safe_event = ProcessingStore._sanitize_external_event_payload(event)
        for key in ("result", "error", "raw_reference", "metadata"):
            if key in safe_event:
                safe_event[key] = ProcessingStore._compact_external_event_value(safe_event[key])
        return safe_event

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

    def _record_external_event_receipt(
        self,
        event: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        now = utc_now()
        receipt = {
            "schema_version": "1.0",
            "idempotency_key": event["idempotency_key"],
            "event_id": event["event_id"],
            "wait_id": event.get("wait_id"),
            "event_type": event["event_type"],
            "source": event["source"],
            "case_id": event["case_id"],
            "correlation_id": event["correlation_id"],
            "status": event["status"],
            "created_at": now,
            "updated_at": now,
            "result": copy.deepcopy(result),
        }
        with self._connect() as connection:
            connection.execute(
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

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _to_json(record: dict[str, Any]) -> str:
        return json.dumps(record, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _counts(rows: list[sqlite3.Row], key: str) -> dict[str, int]:
        return {
            str(row[key]): int(row["count"])
            for row in rows
        }
