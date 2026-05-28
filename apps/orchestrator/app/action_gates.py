from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .contracts import ContractRegistry, REPO_ROOT


DEFAULT_STATE_DB_PATH = REPO_ROOT / "state" / "orchestrator.sqlite"


class ActionGateNotFound(KeyError):
    pass


class ActionGateConflict(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_gate_id() -> str:
    return f"gate-{uuid.uuid4().hex[:12]}"


class ActionGateStore:
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

    def create(self, record: dict[str, Any]) -> dict[str, Any]:
        self.contracts.require_valid("action_gate_record", record)
        payload = self._to_json(record)
        with self._connect() as connection:
            connection.execute(
                """
                insert into action_gates (
                    gate_id,
                    ticket_id,
                    action_id,
                    tool_name,
                    gate_type,
                    status,
                    record_json,
                    created_at,
                    updated_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["gate_id"],
                    record["ticket_id"],
                    record["action_id"],
                    record["tool_name"],
                    record["gate_type"],
                    record["status"],
                    payload,
                    record["created_at"],
                    record["updated_at"],
                ),
            )
        return record

    def save(self, record: dict[str, Any]) -> dict[str, Any]:
        self.contracts.require_valid("action_gate_record", record)
        payload = self._to_json(record)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                update action_gates
                set status = ?,
                    record_json = ?,
                    updated_at = ?
                where gate_id = ?
                """,
                (
                    record["status"],
                    payload,
                    record["updated_at"],
                    record["gate_id"],
                ),
            )
        if cursor.rowcount != 1:
            raise ActionGateNotFound(record["gate_id"])
        return record

    def save_if_status(
        self,
        record: dict[str, Any],
        expected_status: str,
    ) -> dict[str, Any]:
        self.contracts.require_valid("action_gate_record", record)
        payload = self._to_json(record)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                update action_gates
                set status = ?,
                    record_json = ?,
                    updated_at = ?
                where gate_id = ?
                  and status = ?
                """,
                (
                    record["status"],
                    payload,
                    record["updated_at"],
                    record["gate_id"],
                    expected_status,
                ),
            )
        if cursor.rowcount != 1:
            raise ActionGateConflict(
                f"{record['gate_id']} больше не находится в статусе {expected_status}"
            )
        return record

    def get(self, gate_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "select record_json from action_gates where gate_id = ?",
                (gate_id,),
            ).fetchone()
        if row is None:
            return None
        record = json.loads(row["record_json"])
        self.contracts.require_valid("action_gate_record", record)
        return record

    def require(self, gate_id: str) -> dict[str, Any]:
        record = self.get(gate_id)
        if record is None:
            raise ActionGateNotFound(gate_id)
        return record

    def list_by_ticket(self, ticket_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                select record_json
                from action_gates
                where ticket_id = ?
                order by created_at, gate_id
                """,
                (ticket_id,),
            ).fetchall()
        records = [json.loads(row["record_json"]) for row in rows]
        for record in records:
            self.contracts.require_valid("action_gate_record", record)
        return records

    def list_all(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                select record_json
                from action_gates
                order by created_at desc, gate_id desc
                limit ?
                """,
                (limit,),
            ).fetchall()
        records = [json.loads(row["record_json"]) for row in rows]
        for record in records:
            self.contracts.require_valid("action_gate_record", record)
        return records

    def summary(self) -> dict[str, Any]:
        with self._connect() as connection:
            status_rows = connection.execute(
                """
                select status, count(*) as count
                from action_gates
                group by status
                order by status
                """
            ).fetchall()
            type_rows = connection.execute(
                """
                select gate_type, count(*) as count
                from action_gates
                group by gate_type
                order by gate_type
                """
            ).fetchall()
            tool_rows = connection.execute(
                """
                select tool_name, count(*) as count
                from action_gates
                group by tool_name
                order by tool_name
                """
            ).fetchall()
            total = connection.execute("select count(*) as count from action_gates").fetchone()
        return {
            "total": int(total["count"] if total else 0),
            "by_status": self._counts(status_rows, "status"),
            "by_gate_type": self._counts(type_rows, "gate_type"),
            "by_tool": self._counts(tool_rows, "tool_name"),
        }

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                create table if not exists action_gates (
                    gate_id text primary key,
                    ticket_id text not null,
                    action_id text not null,
                    tool_name text not null,
                    gate_type text not null,
                    status text not null,
                    record_json text not null,
                    created_at text not null,
                    updated_at text not null
                )
                """
            )
            connection.execute(
                """
                create index if not exists idx_action_gates_ticket_id
                on action_gates(ticket_id)
                """
            )
            connection.execute(
                """
                create index if not exists idx_action_gates_status
                on action_gates(status)
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
