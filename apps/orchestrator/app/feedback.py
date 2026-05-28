from __future__ import annotations

import json
import os
import sqlite3
import uuid
import hashlib
from pathlib import Path
from typing import Any

from .action_gates import DEFAULT_STATE_DB_PATH, utc_now
from .contracts import ContractRegistry


def new_feedback_id() -> str:
    return f"fb-{uuid.uuid4().hex[:12]}"


def new_evaluation_run_id() -> str:
    return f"evalrun-{uuid.uuid4().hex[:12]}"


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
        idempotency_key = request.get("extensions", {}).get("idempotency_key")
        if idempotency_key:
            existing = self._feedback_by_idempotency_key(str(idempotency_key))
            if existing:
                return existing

        fingerprint = self._fingerprint(request)
        duplicate_of_feedback_id = self._feedback_id_by_fingerprint(fingerprint)
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
        if duplicate_of_feedback_id:
            extensions = {
                **record.get("extensions", {}),
                "duplicate": True,
                "duplicate_of_feedback_id": duplicate_of_feedback_id,
            }
            record["extensions"] = extensions

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
            if idempotency_key:
                connection.execute(
                    """
                    insert or replace into feedback_idempotency (
                        idempotency_key,
                        feedback_id,
                        created_at
                    )
                    values (?, ?, ?)
                    """,
                    (str(idempotency_key), record["feedback_id"], created_at),
                )
            connection.execute(
                """
                insert or ignore into feedback_fingerprints (
                    fingerprint,
                    feedback_id,
                    created_at
                )
                values (?, ?, ?)
                """,
                (fingerprint, record["feedback_id"], created_at),
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

    def get(self, feedback_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "select record_json from feedback_records where feedback_id = ?",
                (feedback_id,),
            ).fetchone()
        if row is None:
            return None
        record = json.loads(row["record_json"])
        self.contracts.require_valid("feedback_record", record)
        return record

    def summary(self) -> dict[str, Any]:
        records = self.list_all()
        rating_counts: dict[str, int] = {}
        duplicate_count = 0
        for record in records:
            rating = record["rating"]
            rating_counts[rating] = rating_counts.get(rating, 0) + 1
            if record.get("extensions", {}).get("duplicate") is True:
                duplicate_count += 1
        return {
            "total": len(records),
            "by_rating": rating_counts,
            "duplicates": duplicate_count,
            "curated_evaluation_cases": len(self.list_evaluation_cases()),
            "evaluation_runs": len(self.list_evaluation_runs()),
        }

    def export_jsonl(self) -> str:
        lines = []
        for record in self.list_all():
            case = self._evaluation_case(record)
            self.contracts.require_valid("evaluation_case", case)
            lines.append(json.dumps(case, ensure_ascii=False, sort_keys=True))
        return "\n".join(lines) + ("\n" if lines else "")

    def promote_to_evaluation_cases(
        self,
        *,
        feedback_ids: list[str] | None = None,
        promoted_by: str,
    ) -> dict[str, Any]:
        records = self._feedback_records_for_promotion(feedback_ids)
        promoted_cases = []
        skipped_cases = []
        promoted_at = utc_now()
        with self._connect() as connection:
            for record in records:
                case = self._evaluation_case(record)
                self.contracts.require_valid("evaluation_case", case)
                cursor = connection.execute(
                    """
                    insert or ignore into evaluation_cases (
                        case_id,
                        source_feedback_id,
                        case_json,
                        promoted_by,
                        promoted_at
                    )
                    values (?, ?, ?, ?, ?)
                    """,
                    (
                        case["case_id"],
                        case["source_feedback_id"],
                        self._to_json(case),
                        promoted_by,
                        promoted_at,
                    ),
                )
                if cursor.rowcount == 1:
                    promoted_cases.append(case)
                else:
                    skipped_cases.append(case)
        return {
            "schema_version": "1.0",
            "promoted_by": promoted_by,
            "promoted_at": promoted_at,
            "promoted_count": len(promoted_cases),
            "skipped_existing_count": len(skipped_cases),
            "cases": promoted_cases,
            "skipped_existing": skipped_cases,
        }

    def list_evaluation_cases(self, case_ids: list[str] | None = None) -> list[dict[str, Any]]:
        if case_ids:
            placeholders = ",".join("?" for _ in case_ids)
            sql = f"""
                select case_json
                from evaluation_cases
                where case_id in ({placeholders})
                order by promoted_at, case_id
                """
            parameters: tuple[Any, ...] = tuple(case_ids)
        else:
            sql = """
                select case_json
                from evaluation_cases
                order by promoted_at, case_id
                """
            parameters = ()

        with self._connect() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        cases = [json.loads(row["case_json"]) for row in rows]
        for case in cases:
            self.contracts.require_valid("evaluation_case", case)
        return cases

    def create_evaluation_run(
        self,
        *,
        operator_id: str,
        case_count: int,
        extensions: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        run = {
            "schema_version": "1.0",
            "run_id": new_evaluation_run_id(),
            "started_at": utc_now(),
            "case_count": case_count,
            "status": "running",
            "extensions": {
                "operator_id": operator_id,
                **(extensions or {}),
            },
        }
        self.contracts.require_valid("evaluation_run", run)
        with self._connect() as connection:
            connection.execute(
                """
                insert into evaluation_runs (
                    run_id,
                    run_json,
                    status,
                    started_at,
                    updated_at
                )
                values (?, ?, ?, ?, ?)
                """,
                (
                    run["run_id"],
                    self._to_json(run),
                    run["status"],
                    run["started_at"],
                    run["started_at"],
                ),
            )
        return run

    def complete_evaluation_run(self, run_id: str, status: str = "completed") -> dict[str, Any]:
        run = self.get_evaluation_run(run_id)
        if run is None:
            raise KeyError(run_id)
        run["status"] = status
        self.contracts.require_valid("evaluation_run", run)
        with self._connect() as connection:
            connection.execute(
                """
                update evaluation_runs
                set run_json = ?,
                    status = ?,
                    updated_at = ?
                where run_id = ?
                """,
                (self._to_json(run), status, utc_now(), run_id),
            )
        return run

    def get_evaluation_run(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "select run_json from evaluation_runs where run_id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        run = json.loads(row["run_json"])
        self.contracts.require_valid("evaluation_run", run)
        return run

    def list_evaluation_runs(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                select run_json
                from evaluation_runs
                order by started_at desc, run_id desc
                limit ?
                """,
                (limit,),
            ).fetchall()
        runs = [json.loads(row["run_json"]) for row in rows]
        for run in runs:
            self.contracts.require_valid("evaluation_run", run)
        return runs

    def save_evaluation_result(self, result: dict[str, Any]) -> dict[str, Any]:
        self.contracts.require_valid("evaluation_result", result)
        with self._connect() as connection:
            connection.execute(
                """
                insert or replace into evaluation_results (
                    run_id,
                    case_id,
                    result_json,
                    status,
                    created_at
                )
                values (?, ?, ?, ?, ?)
                """,
                (
                    result["run_id"],
                    result["case_id"],
                    self._to_json(result),
                    result["status"],
                    result["created_at"],
                ),
            )
        return result

    def list_evaluation_results(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                select result_json
                from evaluation_results
                where run_id = ?
                order by created_at, case_id
                """,
                (run_id,),
            ).fetchall()
        results = [json.loads(row["result_json"]) for row in rows]
        for result in results:
            self.contracts.require_valid("evaluation_result", result)
        return results

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

    def _feedback_records_for_promotion(
        self,
        feedback_ids: list[str] | None,
    ) -> list[dict[str, Any]]:
        if not feedback_ids:
            return self.list_all()
        records = []
        for feedback_id in feedback_ids:
            record = self.get(feedback_id)
            if record:
                records.append(record)
        return records

    def _feedback_by_idempotency_key(self, idempotency_key: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                select feedback_id
                from feedback_idempotency
                where idempotency_key = ?
                """,
                (idempotency_key,),
            ).fetchone()
        if row is None:
            return None
        return self.get(row["feedback_id"])

    def _feedback_id_by_fingerprint(self, fingerprint: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                select feedback_id
                from feedback_fingerprints
                where fingerprint = ?
                """,
                (fingerprint,),
            ).fetchone()
        return str(row["feedback_id"]) if row else None

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
            connection.execute(
                """
                create table if not exists feedback_idempotency (
                    idempotency_key text primary key,
                    feedback_id text not null,
                    created_at text not null
                )
                """
            )
            connection.execute(
                """
                create table if not exists feedback_fingerprints (
                    fingerprint text primary key,
                    feedback_id text not null,
                    created_at text not null
                )
                """
            )
            connection.execute(
                """
                create table if not exists evaluation_cases (
                    case_id text primary key,
                    source_feedback_id text not null unique,
                    case_json text not null,
                    promoted_by text not null,
                    promoted_at text not null
                )
                """
            )
            connection.execute(
                """
                create table if not exists evaluation_runs (
                    run_id text primary key,
                    run_json text not null,
                    status text not null,
                    started_at text not null,
                    updated_at text not null
                )
                """
            )
            connection.execute(
                """
                create table if not exists evaluation_results (
                    run_id text not null,
                    case_id text not null,
                    result_json text not null,
                    status text not null,
                    created_at text not null,
                    primary key (run_id, case_id)
                )
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
    def _fingerprint(request: dict[str, Any]) -> str:
        payload = {
            "ticket_id": request["ticket_id"],
            "operator_id": request["operator_id"],
            "rating": request["rating"],
            "analysis_ticket_id": request["analysis_snapshot"].get("ticket_id"),
            "analysis_case_id": request["analysis_snapshot"].get("case_id"),
            "corrected_response": request.get("corrected_response"),
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
