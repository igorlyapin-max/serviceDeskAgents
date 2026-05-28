from __future__ import annotations

import copy
import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from .action_gates import DEFAULT_STATE_DB_PATH, utc_now
from .contracts import ContractRegistry


class CaseNotFound(KeyError):
    pass


def new_case_id() -> str:
    return f"case-{uuid.uuid4().hex[:12]}"


def new_event_id() -> str:
    return f"evt-{uuid.uuid4().hex[:12]}"


class CaseStore:
    def __init__(
        self,
        contracts: ContractRegistry,
        db_path: str | Path | None = None,
    ):
        self.contracts = contracts
        configured_path = db_path or os.getenv("ORCHESTRATOR_STATE_DB")
        self.db_path = Path(configured_path) if configured_path else DEFAULT_STATE_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def create_from_analysis(
        self,
        ticket_input: dict[str, Any],
        analysis: dict[str, Any],
    ) -> dict[str, Any]:
        now = utc_now()
        case_id = analysis.get("case_id") or new_case_id()
        ticket_id = analysis["ticket_id"]
        analysis_snapshot = copy.deepcopy(analysis)
        analysis_snapshot["case_id"] = case_id
        action_gate_ids = [
            request["gate_id"]
            for request in analysis.get("approval_requests", [])
            if request.get("gate_id")
        ]
        record = {
            "schema_version": "1.0",
            "case_id": case_id,
            "ticket_id": ticket_id,
            "ticket_input": copy.deepcopy(ticket_input),
            "current_workflow_state": copy.deepcopy(analysis["workflow_state"]),
            "ai_decision": copy.deepcopy(analysis.get("ai_decision")),
            "analysis_snapshot": analysis_snapshot,
            "rag_trace": copy.deepcopy(analysis.get("rag_trace", {})),
            "tool_trace": copy.deepcopy(analysis.get("tool_trace", [])),
            "tool_results": copy.deepcopy(analysis.get("tool_results", [])),
            "action_gate_ids": action_gate_ids,
            "feedback_ids": [],
            "created_at": now,
            "updated_at": now,
            "event_count": 0,
            "extensions": {
                "source": "tickets.analyze",
            },
        }
        self._apply_outcome(record, now)
        self.contracts.require_valid("case_record", record)

        with self._connect() as connection:
            connection.execute(
                """
                insert into cases (
                    case_id,
                    ticket_id,
                    workflow_state_id,
                    record_json,
                    created_at,
                    updated_at
                )
                values (?, ?, ?, ?, ?, ?)
                """,
                (
                    record["case_id"],
                    record["ticket_id"],
                    record["current_workflow_state"]["id"],
                    self._to_json(record),
                    record["created_at"],
                    record["updated_at"],
                ),
            )

        self._record_analysis_correlations(record)
        self.append_event(
            case_id,
            "case_created",
            actor_type="system",
            actor_id="case_store",
            summary="Кейс создан из анализа заявки.",
            payload={"ticket_input": copy.deepcopy(ticket_input)},
        )
        self.append_event(
            case_id,
            "analysis_completed",
            actor_type="system",
            actor_id="workflow",
            summary=f"Анализ завершен в состоянии {analysis['workflow_state']['id']}.",
            payload={
                "workflow_state": copy.deepcopy(analysis["workflow_state"]),
                "ai_decision": copy.deepcopy(analysis.get("ai_decision")),
                "rag_trace": copy.deepcopy(analysis.get("rag_trace", {})),
            },
        )
        for request in analysis.get("approval_requests", []):
            self.append_event(
                case_id,
                "action_gate_created",
                actor_type="system",
                actor_id="execution_policy",
                summary=f"Создано согласование действия {request['gate_id']}.",
                correlation={
                    "action_id": request["action_id"],
                    "gate_id": request["gate_id"],
                },
                payload={"approval_request": copy.deepcopy(request)},
            )
        for result in analysis.get("tool_results", []):
            self.append_event(
                case_id,
                "tool_result_recorded",
                actor_type="system",
                actor_id="integration_dispatcher",
                summary=f"Результат инструмента записан со статусом {result['status']}.",
                correlation=self._correlation_from_tool_result(result),
                payload={"tool_result": copy.deepcopy(result)},
            )
        return self.require(case_id)

    def get(self, case_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "select record_json from cases where case_id = ?",
                (case_id,),
            ).fetchone()
        if row is None:
            return None
        record = json.loads(row["record_json"])
        self.contracts.require_valid("case_record", record)
        return record

    def require(self, case_id: str) -> dict[str, Any]:
        record = self.get(case_id)
        if record is None:
            raise CaseNotFound(case_id)
        return record

    def latest_by_ticket(self, ticket_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                select record_json
                from cases
                where ticket_id = ?
                order by created_at desc, case_id desc
                limit 1
                """,
                (ticket_id,),
            ).fetchone()
        if row is None:
            return None
        record = json.loads(row["record_json"])
        self.contracts.require_valid("case_record", record)
        return record

    def list_all(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                select record_json
                from cases
                order by created_at desc, case_id desc
                limit ?
                """,
                (limit,),
            ).fetchall()
        records = [json.loads(row["record_json"]) for row in rows]
        for record in records:
            self.contracts.require_valid("case_record", record)
        return records

    def summary(self) -> dict[str, Any]:
        with self._connect() as connection:
            total = connection.execute("select count(*) as count from cases").fetchone()
            state_rows = connection.execute(
                """
                select workflow_state_id, count(*) as count
                from cases
                group by workflow_state_id
                order by workflow_state_id
                """
            ).fetchall()
            event_rows = connection.execute(
                """
                select event_type, count(*) as count
                from case_events
                group by event_type
                order by event_type
                """
            ).fetchall()
        records = self.list_all(limit=10000)
        terminal_count = sum(
            1
            for record in records
            if record.get("current_workflow_state", {}).get("terminal") is True
        )
        tool_status_counts: dict[str, int] = {}
        for record in records:
            for result in record.get("tool_results", []):
                status = str(result.get("status") or "unknown")
                tool_status_counts[status] = tool_status_counts.get(status, 0) + 1

        return {
            "total": int(total["count"] if total else 0),
            "terminal": terminal_count,
            "non_terminal": max(int(total["count"] if total else 0) - terminal_count, 0),
            "by_workflow_state": self._counts(state_rows, "workflow_state_id"),
            "by_event_type": self._counts(event_rows, "event_type"),
            "tool_results_by_status": tool_status_counts,
        }

    def by_correlation(self, key: str, value: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                select c.record_json
                from case_correlations cc
                join cases c on c.case_id = cc.case_id
                where cc.correlation_key = ?
                  and cc.correlation_value = ?
                order by cc.created_at desc
                limit 1
                """,
                (key, value),
            ).fetchone()
        if row is None:
            return None
        record = json.loads(row["record_json"])
        self.contracts.require_valid("case_record", record)
        return record

    def timeline(self, case_id: str) -> dict[str, Any]:
        record = self.require(case_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                select event_json
                from case_events
                where case_id = ?
                order by created_at, event_id
                """,
                (case_id,),
            ).fetchall()
        events = [json.loads(row["event_json"]) for row in rows]
        timeline = {
            "schema_version": "1.0",
            "case_id": record["case_id"],
            "ticket_id": record["ticket_id"],
            "events": events,
        }
        self.contracts.require_valid("case_timeline", timeline)
        return timeline

    def append_event(
        self,
        case_id: str,
        event_type: str,
        *,
        actor_type: str,
        actor_id: str,
        summary: str | None = None,
        correlation: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        record = self.require(case_id)
        now = utc_now()
        event = {
            "schema_version": "1.0",
            "event_id": new_event_id(),
            "case_id": record["case_id"],
            "ticket_id": record["ticket_id"],
            "event_type": event_type,
            "actor_type": actor_type,
            "actor_id": actor_id,
            "created_at": now,
        }
        if summary:
            event["summary"] = summary
        if correlation:
            event["correlation"] = {
                key: value
                for key, value in correlation.items()
                if value is not None and value != ""
            }
        if payload:
            event["payload"] = payload

        self.contracts.require_valid("case_event", event)
        with self._connect() as connection:
            connection.execute(
                """
                insert into case_events (
                    event_id,
                    case_id,
                    ticket_id,
                    event_type,
                    correlation_json,
                    event_json,
                    created_at
                )
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["event_id"],
                    event["case_id"],
                    event["ticket_id"],
                    event["event_type"],
                    self._to_json(event.get("correlation", {})),
                    self._to_json(event),
                    event["created_at"],
                ),
            )

        record["last_event_id"] = event["event_id"]
        record["event_count"] = int(record.get("event_count", 0)) + 1
        record["updated_at"] = now
        self._save(record)
        return event

    def record_approval_result(self, approval_result: dict[str, Any]) -> dict[str, Any] | None:
        gate = approval_result["gate"]
        record = self._case_for_gate(gate)
        if record is None:
            return None

        now = utc_now()
        record["current_workflow_state"] = copy.deepcopy(approval_result["workflow_state"])
        self._append_unique(record["action_gate_ids"], gate["gate_id"])
        tool_result = approval_result.get("tool_result")
        if tool_result:
            self._upsert_tool_result(record, tool_result)
            self._record_tool_result_correlations(record, tool_result)
        record["updated_at"] = now
        self._apply_outcome(record, now)
        self._save(record)

        decision = gate.get("decision", {})
        self.append_event(
            record["case_id"],
            "approval_decisioned",
            actor_type=decision.get("actor_type", "operator"),
            actor_id=decision.get("actor_id", "unknown"),
            summary=f"Согласование {gate['gate_id']} перешло в статус {gate['status']}.",
            correlation={
                "action_id": gate["action_id"],
                "gate_id": gate["gate_id"],
            },
            payload={
                "gate": copy.deepcopy(gate),
                "workflow_state": copy.deepcopy(approval_result["workflow_state"]),
            },
        )
        if tool_result:
            self.append_event(
                record["case_id"],
                "tool_result_recorded",
                actor_type="system",
                actor_id="integration_dispatcher",
                summary=f"Результат инструмента записан со статусом {tool_result['status']}.",
                correlation=self._correlation_from_tool_result(tool_result),
                payload={"tool_result": copy.deepcopy(tool_result)},
            )
        return self.require(record["case_id"])

    def record_feedback(self, feedback: dict[str, Any]) -> dict[str, Any] | None:
        record = self._case_for_feedback(feedback)
        if record is None:
            return None

        now = utc_now()
        if feedback["feedback_id"] in record.get("feedback_ids", []):
            return self.require(record["case_id"])
        self._append_unique(record["feedback_ids"], feedback["feedback_id"])
        record["updated_at"] = now
        self._save(record)
        self._record_correlation(
            record["case_id"],
            record["ticket_id"],
            "feedback_id",
            feedback["feedback_id"],
        )
        self.append_event(
            record["case_id"],
            "feedback_recorded",
            actor_type="operator",
            actor_id=feedback["operator_id"],
            summary=f"Обратная связь записана с оценкой {feedback['rating']}.",
            correlation={"feedback_id": feedback["feedback_id"]},
            payload={"feedback": copy.deepcopy(feedback)},
        )
        return self.require(record["case_id"])

    def record_integration_callback(
        self,
        callback: dict[str, Any],
        tool_result: dict[str, Any],
        workflow_state: dict[str, Any],
    ) -> dict[str, Any]:
        record = self._case_for_callback(callback)
        if record is None:
            raise CaseNotFound(
                callback.get("case_id")
                or callback.get("invocation_id")
                or callback.get("ticket_id")
                or "integration_callback"
            )

        now = utc_now()
        record["current_workflow_state"] = copy.deepcopy(workflow_state)
        self._upsert_tool_result(record, tool_result)
        record["updated_at"] = now
        self._apply_outcome(record, now)
        self._save(record)
        self._record_tool_result_correlations(record, tool_result)
        self.append_event(
            record["case_id"],
            "integration_callback_received",
            actor_type="endpoint",
            actor_id=callback["endpoint_id"],
            summary=f"Получен callback интеграции со статусом {callback['status']}.",
            correlation=self._correlation_from_tool_result(tool_result),
            payload={
                "callback": copy.deepcopy(callback),
                "tool_result": copy.deepcopy(tool_result),
                "workflow_state": copy.deepcopy(workflow_state),
            },
        )
        return self.require(record["case_id"])

    def _case_for_gate(self, gate: dict[str, Any]) -> dict[str, Any] | None:
        case_id = gate.get("extensions", {}).get("case_id")
        if case_id:
            return self.get(case_id)
        record = self.by_correlation("gate_id", gate["gate_id"])
        if record:
            return record
        return self.latest_by_ticket(gate["ticket_id"])

    def _case_for_feedback(self, feedback: dict[str, Any]) -> dict[str, Any] | None:
        case_id = feedback.get("extensions", {}).get("case_id")
        if case_id:
            return self.get(case_id)
        record = self.by_correlation("feedback_id", feedback["feedback_id"])
        if record:
            return record
        return self.latest_by_ticket(feedback["ticket_id"])

    def _case_for_callback(self, callback: dict[str, Any]) -> dict[str, Any] | None:
        case_id = callback.get("case_id")
        if case_id:
            return self.get(case_id)
        invocation_id = callback.get("invocation_id")
        if invocation_id:
            record = self.by_correlation("invocation_id", invocation_id)
            if record:
                return record
        ticket_id = callback.get("ticket_id")
        if ticket_id:
            return self.latest_by_ticket(ticket_id)
        return None

    def _record_analysis_correlations(self, record: dict[str, Any]) -> None:
        self._record_correlation(record["case_id"], record["ticket_id"], "case_id", record["case_id"])
        self._record_correlation(record["case_id"], record["ticket_id"], "ticket_id", record["ticket_id"])
        for gate_id in record.get("action_gate_ids", []):
            self._record_correlation(record["case_id"], record["ticket_id"], "gate_id", gate_id)
        for result in record.get("tool_results", []):
            self._record_tool_result_correlations(record, result)

    def _record_tool_result_correlations(
        self,
        record: dict[str, Any],
        tool_result: dict[str, Any],
    ) -> None:
        for key in ("invocation_id", "action_id", "endpoint_id", "operation_id"):
            value = tool_result.get(key)
            if value:
                self._record_correlation(record["case_id"], record["ticket_id"], key, value)
        gate_id = tool_result.get("extensions", {}).get("gate_id")
        if gate_id:
            self._record_correlation(record["case_id"], record["ticket_id"], "gate_id", gate_id)

    def _record_correlation(
        self,
        case_id: str,
        ticket_id: str,
        key: str,
        value: str,
    ) -> None:
        now = utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                insert or replace into case_correlations (
                    correlation_key,
                    correlation_value,
                    case_id,
                    ticket_id,
                    created_at
                )
                values (?, ?, ?, ?, ?)
                """,
                (key, value, case_id, ticket_id, now),
            )

    def _save(self, record: dict[str, Any]) -> dict[str, Any]:
        self.contracts.require_valid("case_record", record)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                update cases
                set workflow_state_id = ?,
                    record_json = ?,
                    updated_at = ?
                where case_id = ?
                """,
                (
                    record["current_workflow_state"]["id"],
                    self._to_json(record),
                    record["updated_at"],
                    record["case_id"],
                ),
            )
        if cursor.rowcount != 1:
            raise CaseNotFound(record["case_id"])
        return record

    def _upsert_tool_result(
        self,
        record: dict[str, Any],
        tool_result: dict[str, Any],
    ) -> None:
        updated = False
        for index, existing in enumerate(record["tool_results"]):
            if existing["invocation_id"] == tool_result["invocation_id"]:
                record["tool_results"][index] = copy.deepcopy(tool_result)
                updated = True
                break
        if not updated:
            record["tool_results"].append(copy.deepcopy(tool_result))

        trace_item = self._tool_trace_item(tool_result)
        updated = False
        for index, existing in enumerate(record["tool_trace"]):
            if existing.get("invocation_id") == tool_result["invocation_id"]:
                record["tool_trace"][index] = trace_item
                updated = True
                break
        if not updated:
            record["tool_trace"].append(trace_item)

    @staticmethod
    def _tool_trace_item(tool_result: dict[str, Any]) -> dict[str, Any]:
        return {
            "invocation_id": tool_result["invocation_id"],
            "action_id": tool_result["action_id"],
            "tool_name": tool_result["tool_name"],
            "endpoint_id": tool_result["endpoint_id"],
            "adapter_type": tool_result["adapter_type"],
            "operation_id": tool_result["operation_id"],
            "status": tool_result["status"],
            "policy_rule_id": tool_result["policy_rule_id"],
            "duration_ms": tool_result["duration_ms"],
            "attempts": tool_result["attempts"],
            "error_code": tool_result.get("error", {}).get("code"),
            "gate_id": tool_result.get("extensions", {}).get("gate_id"),
            "mock": tool_result.get("extensions", {}).get("mock", False),
        }

    @staticmethod
    def _correlation_from_tool_result(tool_result: dict[str, Any]) -> dict[str, Any]:
        correlation = {
            "action_id": tool_result["action_id"],
            "invocation_id": tool_result["invocation_id"],
            "endpoint_id": tool_result["endpoint_id"],
            "operation_id": tool_result["operation_id"],
        }
        gate_id = tool_result.get("extensions", {}).get("gate_id")
        if gate_id:
            correlation["gate_id"] = gate_id
        return correlation

    @staticmethod
    def _append_unique(values: list[str], value: str) -> None:
        if value not in values:
            values.append(value)

    @staticmethod
    def _apply_outcome(record: dict[str, Any], now: str) -> None:
        state = record["current_workflow_state"]
        should_record_outcome = state["terminal"] or state["category"] in {
            "blocked",
            "error",
            "handoff",
        }
        if not should_record_outcome:
            record.pop("outcome", None)
            return

        record["outcome"] = {
            "workflow_state_id": state["id"],
            "category": state["category"],
            "terminal": state["terminal"],
            "updated_at": now,
        }
        if state.get("description"):
            record["outcome"]["summary"] = state["description"]

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                create table if not exists cases (
                    case_id text primary key,
                    ticket_id text not null,
                    workflow_state_id text not null,
                    record_json text not null,
                    created_at text not null,
                    updated_at text not null
                )
                """
            )
            connection.execute(
                """
                create index if not exists idx_cases_ticket_id
                on cases(ticket_id)
                """
            )
            connection.execute(
                """
                create index if not exists idx_cases_workflow_state_id
                on cases(workflow_state_id)
                """
            )
            connection.execute(
                """
                create table if not exists case_events (
                    event_id text primary key,
                    case_id text not null,
                    ticket_id text not null,
                    event_type text not null,
                    correlation_json text not null,
                    event_json text not null,
                    created_at text not null
                )
                """
            )
            connection.execute(
                """
                create index if not exists idx_case_events_case_id
                on case_events(case_id)
                """
            )
            connection.execute(
                """
                create index if not exists idx_case_events_ticket_id
                on case_events(ticket_id)
                """
            )
            connection.execute(
                """
                create table if not exists case_correlations (
                    correlation_key text not null,
                    correlation_value text not null,
                    case_id text not null,
                    ticket_id text not null,
                    created_at text not null,
                    primary key (correlation_key, correlation_value)
                )
                """
            )
            connection.execute(
                """
                create index if not exists idx_case_correlations_case_id
                on case_correlations(case_id)
                """
            )
            connection.execute(
                """
                create index if not exists idx_case_correlations_ticket_id
                on case_correlations(ticket_id)
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
