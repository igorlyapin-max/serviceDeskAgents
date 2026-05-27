from __future__ import annotations

import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from .action_gates import DEFAULT_STATE_DB_PATH, utc_now
from .contracts import ContractRegistry


def new_feedback_id() -> str:
    return f"fb-{uuid.uuid4().hex[:12]}"


class FeedbackStore:
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

    def create(self, request: dict[str, Any]) -> dict[str, Any]:
        self.contracts.require_valid("feedback_request", request)
        created_at = utc_now()
        record = {
            "schema_version": "1.0",
            "feedback_id": new_feedback_id(),
            "ticket_id": request["ticket_id"],
            "operator_id": request["operator_id"],
            "rating": request["rating"],
            "ticket_input": request["ticket_input"],
            "analysis_snapshot": request["analysis_snapshot"],
            "created_at": created_at,
        }
        for optional_key in (
            "approval_snapshot",
            "operator_note",
            "corrected_response",
            "extensions",
        ):
            if optional_key in request:
                record[optional_key] = request[optional_key]

        self.contracts.require_valid("feedback_record", record)
        payload = self._to_json(record)
        with self._connect() as connection:
            connection.execute(
                """
                insert into feedback_records (
                    feedback_id,
                    ticket_id,
                    operator_id,
                    rating,
                    record_json,
                    created_at
                )
                values (?, ?, ?, ?, ?, ?)
                """,
                (
                    record["feedback_id"],
                    record["ticket_id"],
                    record["operator_id"],
                    record["rating"],
                    payload,
                    record["created_at"],
                ),
            )
        return record

    def list_by_ticket(self, ticket_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                select record_json
                from feedback_records
                where ticket_id = ?
                order by created_at, feedback_id
                """,
                (ticket_id,),
            ).fetchall()
        return self._records_from_rows(rows)

    def list_all(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                select record_json
                from feedback_records
                order by created_at, feedback_id
                """
            ).fetchall()
        return self._records_from_rows(rows)

    def export_jsonl(self) -> str:
        lines = []
        for record in self.list_all():
            case = self._evaluation_case(record)
            self.contracts.require_valid("evaluation_case", case)
            lines.append(json.dumps(case, ensure_ascii=False, sort_keys=True))
        return "\n".join(lines) + ("\n" if lines else "")

    def _evaluation_case(self, record: dict[str, Any]) -> dict[str, Any]:
        expected = {
            "rating": record["rating"],
        }
        if record.get("corrected_response"):
            expected["corrected_response"] = record["corrected_response"]
        if record.get("operator_note"):
            expected["operator_note"] = record["operator_note"]

        case = {
            "schema_version": "1.0",
            "case_id": f"case-{record['feedback_id']}",
            "source_feedback_id": record["feedback_id"],
            "ticket_input": record["ticket_input"],
            "expected": expected,
            "analysis_snapshot": record["analysis_snapshot"],
            "created_at": record["created_at"],
            "extensions": {
                "ticket_id": record["ticket_id"],
                "operator_id": record["operator_id"],
            },
        }
        if record.get("approval_snapshot"):
            case["approval_snapshot"] = record["approval_snapshot"]
        if record.get("extensions"):
            case["extensions"].update(record["extensions"])
        return case

    def _records_from_rows(self, rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
        records = [json.loads(row["record_json"]) for row in rows]
        for record in records:
            self.contracts.require_valid("feedback_record", record)
        return records

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                create table if not exists feedback_records (
                    feedback_id text primary key,
                    ticket_id text not null,
                    operator_id text not null,
                    rating text not null,
                    record_json text not null,
                    created_at text not null
                )
                """
            )
            connection.execute(
                """
                create index if not exists idx_feedback_records_ticket_id
                on feedback_records(ticket_id)
                """
            )
            connection.execute(
                """
                create index if not exists idx_feedback_records_rating
                on feedback_records(rating)
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _to_json(record: dict[str, Any]) -> str:
        return json.dumps(record, ensure_ascii=False, sort_keys=True)
