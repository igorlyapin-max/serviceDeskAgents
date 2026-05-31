from __future__ import annotations

import copy
import json
import random
import re
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .action_gates import DEFAULT_STATE_DB_PATH, utc_now
from .cases import CaseNotFound
from .config_registry import AGENT_OUTCOME_LABELS, AGENT_OUTCOME_NEXT_STEPS, ConfigRegistryError, ConfigStore
from .processing import ProcessingStore
from .workflow import TicketWorkflow


SENSITIVE_KEYWORDS = {
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
}

FULL_NAME_RE = re.compile(r"\b[А-ЯЁ][а-яё]+(?:у|а|ой|ому)?\s+[А-ЯЁ][а-яё]+(?:у|а|ой|ому)?\s+[А-ЯЁ][а-яё]+(?:у|а|ой|ому)?\b")

DEFAULT_SLOT_VALUES = {
    "user_login": "ivanov",
    "account_type": "доменная учетная запись",
    "app_name": "Outlook",
    "error_text": "ошибка входа",
    "device_name": "NB-1024",
    "device_id": "NB-1024",
    "location": "Москва",
    "user_fio": "Иванов Иван Иванович",
    "pre_manager": "Васин Василий Васильевич",
    "manager_email": "ivanov.manager@example.local",
    "employee_number": "100123",
    "department": "финансовый отдел",
    "title": "ведущий специалист",
}


class DebugRuntimeError(ValueError):
    pass


def new_simulation_run_id() -> str:
    return f"sim-{uuid.uuid4().hex[:12]}"


def new_simulation_item_id() -> str:
    return f"simitem-{uuid.uuid4().hex[:12]}"


def new_capture_session_id() -> str:
    return f"capsession-{uuid.uuid4().hex[:12]}"


def new_capture_id() -> str:
    return f"cap-{uuid.uuid4().hex[:12]}"


def value_preview(value: Any, limit: int = 240) -> str:
    if value is None or value == "":
        return "н/д"
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    else:
        text = str(value)
    return text if len(text) <= limit else f"{text[:limit - 1]}..."


def redact_text(value: str) -> str:
    value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-zА-Яа-я]{2,}", "<email>", value)
    value = re.sub(r"(?<!\d)(?:\+?\d[\d ()-]{7,}\d)(?!\d)", "<phone>", value)
    return value


def sanitize_payload(value: Any, *, path: str = "") -> tuple[Any, list[str]]:
    masked_paths: list[str] = []
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            normalized_key = str(key).lower()
            if any(keyword in normalized_key for keyword in SENSITIVE_KEYWORDS):
                result[key] = "<masked>"
                masked_paths.append(child_path)
                continue
            sanitized, nested_paths = sanitize_payload(item, path=child_path)
            result[key] = sanitized
            masked_paths.extend(nested_paths)
        return result, masked_paths
    if isinstance(value, list):
        result = []
        for index, item in enumerate(value):
            sanitized, nested_paths = sanitize_payload(item, path=f"{path}[{index}]")
            result.append(sanitized)
            masked_paths.extend(nested_paths)
        return result, masked_paths
    if isinstance(value, str):
        sanitized = redact_text(value)
        if sanitized != value:
            masked_paths.append(path or "$")
        return sanitized, masked_paths
    return value, masked_paths


class DebugRuntime:
    def __init__(
        self,
        workflow: TicketWorkflow,
        config_store: ConfigStore,
        processing_store: ProcessingStore,
        db_path: str | Path | None = None,
    ):
        self.workflow = workflow
        self.config_store = config_store
        self.processing_store = processing_store
        configured_path = db_path
        self.db_path = Path(configured_path) if configured_path else DEFAULT_STATE_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def simulation_profiles(self) -> dict[str, Any]:
        scenarios = []
        for scenario in self.config_store.scenario_overview()["scenarios"]:
            detail = self.config_store.scenario_detail(scenario["scenario_id"])
            slots = detail.get("slot_schema", {}).get("slots", [])
            launches = detail.get("tool_launches", [])
            scenarios.append(
                {
                    "scenario_id": scenario["scenario_id"],
                    "display_name": scenario["display_name"],
                    "channel_id": scenario.get("channel_id") or "debug",
                    "required_slots": [
                        {"slot_id": slot["slot_id"], "display_name": slot.get("display_name", slot["slot_id"])}
                        for slot in slots
                        if slot.get("required")
                    ],
                    "react_calls": [
                        {
                            "launch_id": launch.get("launch_id"),
                            "display_name": launch.get("display_name") or launch.get("tool_name"),
                            "tool_name": launch.get("tool_name"),
                        }
                        for launch in launches
                    ],
                    "variants": self._scenario_variants(slots, launches),
                }
            )
        return {
            "schema_version": "1.0",
            "profiles": scenarios,
            "system_profiles": [
                {
                    "profile_id": "out_of_scope",
                    "display_name": "Нецелевое обращение / вне зоны поддержки",
                    "variants": [
                        "finance_request_to_it",
                        "hr_request_to_it",
                        "random_noise",
                    ],
                }
            ],
        }

    def prepare_simulation(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = utc_now()
        seed = str(payload.get("seed") or f"seed-{uuid.uuid4().hex[:8]}")
        rng = random.Random(seed)
        scenario_ids = payload.get("scenario_ids") or [
            scenario["scenario_id"]
            for scenario in self.config_store.scenario_overview()["scenarios"][:1]
        ]
        count_per_scenario = max(1, min(int(payload.get("count_per_scenario") or 1), 100))
        run = {
            "schema_version": "1.0",
            "run_id": new_simulation_run_id(),
            "status": "prepared",
            "source": payload.get("source") or "scenario_profiles",
            "seed": seed,
            "channel_id": payload.get("channel_id") or "debug",
            "mode": payload.get("mode") or "dry_run",
            "dry_run": payload.get("dry_run", True) is not False,
            "contains_real_data": payload.get("contains_real_data", False) is True,
            "sanitized": payload.get("sanitized", False) is True,
            "created_at": now,
            "updated_at": now,
            "started_at": None,
            "finished_at": None,
            "counters": {
                "prepared": 0,
                "started": 0,
                "completed": 0,
                "waiting": 0,
                "escalated": 0,
                "failed": 0,
                "excluded": 0,
            },
            "config_versions": {
                domain: self.config_store.active_version_id(domain)
                for domain in ("service_scenarios", "slot_schemas", "tool_launch_matrix", "integration_endpoints")
            },
        }
        items: list[dict[str, Any]] = []
        order = 1
        for scenario_id in scenario_ids:
            detail = self.config_store.scenario_detail(scenario_id)
            for _ in range(count_per_scenario):
                variant = rng.choice(self._scenario_variants(
                    detail.get("slot_schema", {}).get("slots", []),
                    detail.get("tool_launches", []),
                ))
                item = self._build_simulation_item(
                    run,
                    detail,
                    variant=variant,
                    order=order,
                    rng=rng,
                )
                items.append(item)
                order += 1
        if payload.get("include_wrong_department", False):
            items.append(self._build_out_of_scope_item(run, order))

        run["counters"]["prepared"] = len(items)
        with self._connect() as connection:
            self._insert_simulation_run(connection, run)
            for item in items:
                self._insert_simulation_item(connection, item)
        return {"schema_version": "1.0", "run": run, "items": items}

    def list_simulations(self, limit: int = 50) -> dict[str, Any]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                select run_json
                from debug_simulation_runs
                order by updated_at desc, run_id desc
                limit ?
                """,
                (min(max(limit, 1), 200),),
            ).fetchall()
        return {
            "schema_version": "1.0",
            "runs": [json.loads(row["run_json"]) for row in rows],
        }

    def simulation_detail(self, run_id: str) -> dict[str, Any]:
        run = self.require_simulation_run(run_id)
        return {
            "schema_version": "1.0",
            "run": run,
            "items": self.list_simulation_items(run_id)["items"],
        }

    def list_simulation_items(self, run_id: str) -> dict[str, Any]:
        self.require_simulation_run(run_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                select item_json
                from debug_simulation_items
                where run_id = ?
                order by sort_order, item_id
                """,
                (run_id,),
            ).fetchall()
        return {
            "schema_version": "1.0",
            "items": [json.loads(row["item_json"]) for row in rows],
        }

    def patch_simulation_item(self, run_id: str, item_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        run = self.require_simulation_run(run_id)
        if run["status"] not in {"prepared", "paused"}:
            raise DebugRuntimeError("Редактировать поток можно только до запуска или в паузе.")
        item = self.require_simulation_item(run_id, item_id)
        editable_fields = {
            "text",
            "channel_id",
            "scenario_id",
            "expected_outcome",
            "client_behavior",
            "mode",
            "dry_run",
            "excluded",
            "expected_slots",
        }
        for field in editable_fields:
            if field in patch:
                item[field] = copy.deepcopy(patch[field])
        item["updated_at"] = utc_now()
        item["status"] = "excluded" if item.get("excluded") else "prepared"
        self._save_simulation_item(item)
        self._refresh_run_counters(run_id)
        return {"schema_version": "1.0", "item": item}

    def start_simulation(self, run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        run = self.require_simulation_run(run_id)
        if run["status"] not in {"prepared", "paused"}:
            raise DebugRuntimeError(f"Запуск {run_id} нельзя стартовать из статуса {run['status']}.")
        selected = set(payload.get("selected_item_ids") or [])
        now = utc_now()
        run["status"] = "running"
        run["started_at"] = run.get("started_at") or now
        run["updated_at"] = now
        self._save_simulation_run(run)

        stop_on_mismatch = payload.get("stop_on_mismatch", False) is True
        for item in self.list_simulation_items(run_id)["items"]:
            if item.get("excluded"):
                continue
            if selected and item["item_id"] not in selected:
                continue
            try:
                started_item = copy.deepcopy(item)
                started_item["status"] = "running"
                started_item["started_at"] = utc_now()
                started_item["updated_at"] = started_item["started_at"]
                self._save_simulation_item(started_item)

                ticket_input = self._ticket_input_for_item(started_item)
                analysis = self.workflow.analyze(ticket_input)
                processing_detail = self.processing_store.record_analysis(ticket_input, analysis)
                result_status = self._simulation_status_from_analysis(analysis, processing_detail)
                started_item["status"] = result_status
                started_item["case_id"] = analysis["case_id"]
                started_item["ticket_id"] = analysis["ticket_id"]
                started_item["analysis_summary"] = {
                    "workflow_state": analysis.get("workflow_state", {}).get("id"),
                    "decision": analysis.get("ai_decision", {}).get("decision", {}).get("type"),
                    "operator_message": analysis.get("operator_message"),
                }
                agent_outcome = self._agent_outcome_from_analysis(
                    analysis,
                    processing_detail,
                    result_status,
                )
                started_item["agent_outcome"] = self._agent_outcome_with_expectation(
                    started_item,
                    agent_outcome,
                )
                started_item["finished_at"] = utc_now()
                started_item["updated_at"] = started_item["finished_at"]
                self._save_simulation_item(started_item)
                if stop_on_mismatch and self._has_expected_mismatch(started_item, analysis):
                    break
            except Exception as error:  # noqa: BLE001 - debug runtime must preserve item-level failures
                failed = copy.deepcopy(item)
                failed["status"] = "failed"
                failed["error"] = {"message": str(error)}
                failed["agent_outcome"] = self._agent_outcome(
                    "error",
                    "Агент не смог обработать обращение из-за технической ошибки.",
                    AGENT_OUTCOME_NEXT_STEPS["error"],
                    error_message=str(error),
                )
                failed["finished_at"] = utc_now()
                failed["updated_at"] = failed["finished_at"]
                self._save_simulation_item(failed)
                if stop_on_mismatch:
                    break

        run = self._refresh_run_counters(run_id)
        if run["status"] == "running":
            run["status"] = "completed"
            run["finished_at"] = utc_now()
            run["updated_at"] = run["finished_at"]
            self._save_simulation_run(run)
        return self.simulation_detail(run_id)

    def pause_simulation(self, run_id: str) -> dict[str, Any]:
        run = self.require_simulation_run(run_id)
        if run["status"] not in {"running", "prepared"}:
            raise DebugRuntimeError(f"Запуск {run_id} нельзя поставить на паузу из статуса {run['status']}.")
        run["status"] = "paused"
        run["updated_at"] = utc_now()
        self._save_simulation_run(run)
        return {"schema_version": "1.0", "run": run}

    def cancel_simulation(self, run_id: str) -> dict[str, Any]:
        run = self.require_simulation_run(run_id)
        if run["status"] in {"completed", "cancelled"}:
            return {"schema_version": "1.0", "run": run}
        run["status"] = "cancelled"
        run["finished_at"] = utc_now()
        run["updated_at"] = run["finished_at"]
        self._save_simulation_run(run)
        return {"schema_version": "1.0", "run": run}

    def simulation_trace(self, run_id: str) -> dict[str, Any]:
        detail = self.simulation_detail(run_id)
        traces = []
        for item in detail["items"]:
            if item.get("case_id"):
                traces.append(self.case_trace(item["case_id"]))
        return {
            "schema_version": "1.0",
            "run": detail["run"],
            "items": detail["items"],
            "case_traces": traces,
        }

    def case_trace(self, case_id: str) -> dict[str, Any]:
        detail = self.processing_store.case_detail(case_id)
        events = []
        for event in detail.get("timeline", {}).get("events", []):
            events.append(self._trace_event(
                created_at=event.get("created_at"),
                event_type=event.get("event_type"),
                summary=event.get("summary"),
                actor_id=event.get("actor_id"),
                actor_type=event.get("actor_type"),
                payload=event.get("payload"),
                correlation=event.get("correlation"),
            ))
        for run in detail.get("runs", []):
            events.append(self._trace_event(
                created_at=run.get("updated_at") or run.get("started_at"),
                event_type="processing_run",
                summary=f"Запуск обработки: {run.get('status')}",
                actor_id=run.get("extensions", {}).get("agent_id") or "runtime",
                actor_type="system",
                payload=run,
                correlation={"run_id": run.get("run_id")},
                run_id=run.get("run_id"),
                trace_step=run.get("current_step"),
            ))
        for task in detail.get("tasks", []):
            events.append(self._trace_event(
                created_at=task.get("updated_at") or task.get("created_at"),
                event_type="agent_task",
                summary=f"Задача агента: {task.get('status')}",
                actor_id=task.get("worker_id") or "agent-pending",
                actor_type="agent",
                payload=task,
                correlation={"run_id": task.get("run_id"), "task_id": task.get("task_id")},
                run_id=task.get("run_id"),
                task_id=task.get("task_id"),
                agent_id=task.get("worker_id"),
            ))
        for wait in detail.get("waits", []):
            events.append(self._trace_event(
                created_at=wait.get("updated_at") or wait.get("created_at"),
                event_type="wait_state",
                summary=f"Ожидание: {wait.get('wait_type')} / {wait.get('status')}",
                actor_id=wait.get("channel_id") or "runtime",
                actor_type="wait",
                payload=wait,
                correlation={"run_id": wait.get("run_id"), "wait_id": wait.get("wait_id")},
                run_id=wait.get("run_id"),
                trace_step="wait",
            ))
        for message in detail.get("outbox", []):
            events.append(self._trace_event(
                created_at=message.get("created_at"),
                event_type=f"outbox:{message.get('event_type')}",
                summary=f"Outbox {message.get('topic')} / {message.get('status')}",
                actor_id="outbox",
                actor_type="system",
                payload=message,
                correlation={"idempotency_key": message.get("idempotency_key")},
                parent_event_id=message.get("idempotency_key"),
            ))
        events.sort(key=lambda item: (item.get("created_at") or "", item.get("event_type") or ""))
        return {
            "schema_version": "1.0",
            "case_id": case_id,
            "case": detail.get("case"),
            "events": events,
        }

    def start_capture_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        endpoint_id = payload.get("endpoint_id")
        operation_id = payload.get("operation_id")
        self._require_operation(endpoint_id, operation_id)
        now = utc_now()
        session = {
            "schema_version": "1.0",
            "session_id": new_capture_session_id(),
            "endpoint_id": endpoint_id,
            "operation_id": operation_id,
            "status": "active",
            "operator_id": payload.get("operator_id") or "admin-1",
            "created_at": now,
            "updated_at": now,
            "capture_count": 0,
        }
        with self._connect() as connection:
            connection.execute(
                """
                insert into debug_capture_sessions (
                    session_id, endpoint_id, operation_id, status, created_at, updated_at, session_json
                )
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session["session_id"],
                    endpoint_id,
                    operation_id,
                    session["status"],
                    session["created_at"],
                    session["updated_at"],
                    self._to_json(session),
                ),
            )
        return {"schema_version": "1.0", "session": session}

    def stop_capture_session(self, session_id: str) -> dict[str, Any]:
        session = self.require_capture_session(session_id)
        session["status"] = "stopped"
        session["updated_at"] = utc_now()
        self._save_capture_session(session)
        return {"schema_version": "1.0", "session": session}

    def list_captures(self, limit: int = 100) -> dict[str, Any]:
        with self._connect() as connection:
            session_rows = connection.execute(
                """
                select session_json
                from debug_capture_sessions
                order by updated_at desc, session_id desc
                limit ?
                """,
                (min(max(limit, 1), 200),),
            ).fetchall()
            capture_rows = connection.execute(
                """
                select capture_json
                from debug_endpoint_captures
                order by created_at desc, capture_id desc
                limit ?
                """,
                (min(max(limit, 1), 200),),
            ).fetchall()
        return {
            "schema_version": "1.0",
            "sessions": [json.loads(row["session_json"]) for row in session_rows],
            "captures": [json.loads(row["capture_json"]) for row in capture_rows],
        }

    def capture_detail(self, capture_id: str) -> dict[str, Any]:
        return {"schema_version": "1.0", "capture": self.require_capture(capture_id)}

    def record_endpoint_call(
        self,
        *,
        invocation: dict[str, Any],
        endpoint: dict[str, Any],
        operation: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        session = self.active_capture_session(invocation["endpoint_id"], invocation["operation_id"])
        if not session:
            return
        now = utc_now()
        response_payload = result.get("output") if result.get("output") is not None else {"error": result.get("error")}
        validation_errors = self._response_validation_errors(operation, response_payload or {})
        capture = {
            "schema_version": "1.0",
            "capture_id": new_capture_id(),
            "session_id": session["session_id"],
            "endpoint_id": endpoint["endpoint_id"],
            "operation_id": invocation["operation_id"],
            "status": "captured" if not validation_errors else "contract_mismatch",
            "sanitized": False,
            "created_at": now,
            "updated_at": now,
            "case_id": invocation.get("case_id"),
            "ticket_id": invocation.get("ticket_id"),
            "invocation_id": invocation.get("invocation_id"),
            "adapter_type": invocation.get("adapter_type"),
            "request_payload": copy.deepcopy(invocation.get("operation_parameters") or {}),
            "response_payload": copy.deepcopy(response_payload or {}),
            "technical_status": result.get("status"),
            "duration_ms": result.get("duration_ms"),
            "contract_version": operation.get("contract_version"),
            "validation": {
                "status": "valid" if not validation_errors else "invalid",
                "errors": validation_errors,
            },
        }
        with self._connect() as connection:
            self._insert_capture(connection, capture)
        session["capture_count"] = int(session.get("capture_count") or 0) + 1
        session["updated_at"] = now
        self._save_capture_session(session)

    def sanitize_capture(self, capture_id: str) -> dict[str, Any]:
        capture = self.require_capture(capture_id)
        sanitized_response, masked_paths = sanitize_payload(capture.get("response_payload") or {})
        sanitized_request, request_masked_paths = sanitize_payload(capture.get("request_payload") or {})
        capture["sanitized"] = True
        capture["status"] = "sanitized" if capture.get("validation", {}).get("status") == "valid" else "contract_mismatch"
        capture["sanitized_response_payload"] = sanitized_response
        capture["sanitized_request_payload"] = sanitized_request
        capture["masked_paths"] = sorted(set(masked_paths + [f"request.{path}" for path in request_masked_paths]))
        capture["updated_at"] = utc_now()
        self._save_capture(capture)
        return {"schema_version": "1.0", "capture": capture}

    def create_mock_from_capture(self, capture_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        capture = self.require_capture(capture_id)
        if capture.get("validation", {}).get("status") != "valid":
            raise DebugRuntimeError("Нельзя создать mock из ответа, который не проходит response_schema.")
        if not capture.get("sanitized"):
            raise DebugRuntimeError("Перед созданием mock нужно выполнить обезличивание captured response.")
        endpoint_catalog = self.config_store.active_payload("integration_endpoints")
        endpoint, operation = self._find_operation(
            endpoint_catalog,
            capture["endpoint_id"],
            capture["operation_id"],
        )
        mock_output = copy.deepcopy(capture.get("sanitized_response_payload") or {})
        operation["mock_output"] = mock_output
        example = {
            "example_id": f"mock-{capture['capture_id']}",
            "display_name": payload.get("example_name") or f"Captured {capture['capture_id']}",
            "description": payload.get("description") or "Mock создан из захваченного endpoint-вызова.",
            "request_example": copy.deepcopy(capture.get("sanitized_request_payload") or {}),
            "response_example": mock_output,
            "expected_status": capture.get("technical_status") or "success",
            "tags": payload.get("tags") or ["captured"],
            "source": "captured",
            "sanitized": True,
            "captured_at": capture.get("created_at"),
            "captured_from_endpoint": capture.get("endpoint_id"),
            "contract_version": capture.get("contract_version"),
        }
        examples = operation.setdefault("mock_examples", [])
        examples = [item for item in examples if item.get("example_id") != example["example_id"]]
        examples.append(example)
        operation["mock_examples"] = examples

        draft = self.config_store.create_draft(
            domain="integration_endpoints",
            payload=endpoint_catalog,
            created_by=payload.get("operator_id") or "admin-1",
            base_version_id=self.config_store.active_version_id("integration_endpoints"),
        )
        draft = self.config_store.validate_draft(draft["draft_id"])
        if draft.get("validation", {}).get("status") != "valid":
            raise ConfigRegistryError("; ".join(draft.get("validation", {}).get("errors", [])))
        regression = {
            "schema_version": "1.0",
            "status": "skipped",
            "run_at": utc_now(),
            "run_id": f"mock-capture-{capture_id}",
            "summary": {"reason": "Mock создан из валидированного captured response."},
            "gates": [
                {
                    "gate_id": "captured_mock_response_schema",
                    "status": "passed",
                    "message": "Captured response прошел response_schema операции.",
                }
            ],
        }
        self.config_store.save_regression(draft["draft_id"], regression)
        version = self.config_store.activate_draft(draft["draft_id"], payload.get("operator_id") or "admin-1")
        self.workflow.apply_config_payload("integration_endpoints", version["payload"])
        if hasattr(self.workflow.integration_dispatcher, "capture_recorder"):
            self.workflow.integration_dispatcher.capture_recorder = self
        capture["mock_example_id"] = example["example_id"]
        capture["mock_version_id"] = version["version_id"]
        capture["status"] = "mock_created"
        capture["updated_at"] = utc_now()
        self._save_capture(capture)
        return {
            "schema_version": "1.0",
            "capture": capture,
            "mock_example": example,
            "config_version": version,
            "endpoint": {
                "endpoint_id": endpoint["endpoint_id"],
                "operation_id": capture["operation_id"],
            },
        }

    def mark_capture_contract_broken(self, capture_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        capture = self.require_capture(capture_id)
        endpoint_catalog = self.config_store.active_payload("integration_endpoints")
        _, operation = self._find_operation(
            endpoint_catalog,
            capture["endpoint_id"],
            capture["operation_id"],
        )
        operation["contract_status"] = "broken"
        operation["extensions"] = {
            **operation.get("extensions", {}),
            "broken_by_capture_id": capture_id,
            "broken_reason": payload.get("reason") or "Captured response не соответствует контракту.",
        }
        draft = self.config_store.create_draft(
            domain="integration_endpoints",
            payload=endpoint_catalog,
            created_by=payload.get("operator_id") or "admin-1",
            base_version_id=self.config_store.active_version_id("integration_endpoints"),
        )
        draft = self.config_store.validate_draft(draft["draft_id"])
        regression = {
            "schema_version": "1.0",
            "status": "skipped",
            "run_at": utc_now(),
            "run_id": f"contract-broken-{capture_id}",
            "summary": {"reason": "Операция помечена как broken по captured response."},
            "gates": [],
        }
        self.config_store.save_regression(draft["draft_id"], regression)
        version = self.config_store.activate_draft(draft["draft_id"], payload.get("operator_id") or "admin-1")
        self.workflow.apply_config_payload("integration_endpoints", version["payload"])
        capture["status"] = "contract_marked_broken"
        capture["updated_at"] = utc_now()
        self._save_capture(capture)
        return {"schema_version": "1.0", "capture": capture, "config_version": version}

    def active_capture_session(self, endpoint_id: str, operation_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                select session_json
                from debug_capture_sessions
                where endpoint_id = ?
                  and operation_id = ?
                  and status = 'active'
                order by created_at desc, session_id desc
                limit 1
                """,
                (endpoint_id, operation_id),
            ).fetchone()
        return json.loads(row["session_json"]) if row else None

    def require_simulation_run(self, run_id: str) -> dict[str, Any]:
        run = self._get_json_by_id("debug_simulation_runs", "run_id", run_id, "run_json")
        if not run:
            raise DebugRuntimeError(f"Симуляция не найдена: {run_id}")
        return run

    def require_simulation_item(self, run_id: str, item_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                """
                select item_json
                from debug_simulation_items
                where run_id = ? and item_id = ?
                """,
                (run_id, item_id),
            ).fetchone()
        if not row:
            raise DebugRuntimeError(f"Обращение потока не найдено: {item_id}")
        return json.loads(row["item_json"])

    def require_capture_session(self, session_id: str) -> dict[str, Any]:
        session = self._get_json_by_id("debug_capture_sessions", "session_id", session_id, "session_json")
        if not session:
            raise DebugRuntimeError(f"Сессия захвата не найдена: {session_id}")
        return session

    def require_capture(self, capture_id: str) -> dict[str, Any]:
        capture = self._get_json_by_id("debug_endpoint_captures", "capture_id", capture_id, "capture_json")
        if not capture:
            raise DebugRuntimeError(f"Захваченный вызов не найден: {capture_id}")
        return capture

    @staticmethod
    def _scenario_variants(slots: list[dict[str, Any]], launches: list[dict[str, Any]]) -> list[str]:
        variants = ["happy_path"]
        if any(slot.get("required") for slot in slots):
            variants.extend(["missing_required_slot", "conflicting_data", "no_client_reply"])
        if launches:
            variants.extend(["endpoint_error", "external_event_wait"])
        return variants

    def _build_simulation_item(
        self,
        run: dict[str, Any],
        detail: dict[str, Any],
        *,
        variant: str,
        order: int,
        rng: random.Random,
    ) -> dict[str, Any]:
        scenario = detail["scenario"]
        slots = detail.get("slot_schema", {}).get("slots", [])
        generation = self._build_generated_ticket_text(detail, variant=variant, rng=rng)
        expected_slots = self._expected_slots_for_item(slots, generation, rng)
        expected_autofill = self._expected_external_slots(
            slots,
            expected_slots,
            fill_methods={"slot_autofill"},
        )
        expected_resolution = self._expected_external_slots(
            slots,
            expected_slots,
            fill_methods={"resolution_profile"},
        )
        return {
            "schema_version": "1.0",
            "item_id": new_simulation_item_id(),
            "run_id": run["run_id"],
            "sort_order": order,
            "status": "prepared",
            "source": "scenario_profile",
            "scenario_id": scenario["scenario_id"],
            "scenario_display_name": scenario["display_name"],
            "variant": variant,
            "channel_id": run["channel_id"],
            "text": generation["text"],
            "text_slots": generation["text_slots"],
            "expected_slots": expected_slots,
            "expected_autofill": expected_autofill,
            "expected_resolution": expected_resolution,
            "generation_source": generation["source"],
            "generation_notes": generation["notes"],
            "expected_gaps": generation["expected_gaps"],
            "expected_outcome": self._expected_outcome_for_variant(variant),
            "client_behavior": self._client_behavior_for_variant(variant),
            "mode": run["mode"],
            "dry_run": run["dry_run"],
            "excluded": False,
            "created_at": run["created_at"],
            "updated_at": run["updated_at"],
        }

    def _build_out_of_scope_item(self, run: dict[str, Any], order: int) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "item_id": new_simulation_item_id(),
            "run_id": run["run_id"],
            "sort_order": order,
            "status": "prepared",
            "source": "system_profile",
            "scenario_id": "auto",
            "scenario_display_name": "Нецелевое обращение / вне зоны поддержки",
            "variant": "finance_request_to_it",
            "channel_id": run["channel_id"],
            "text": (
                "Контактное лицо: Васин Василий Васильевич. "
                "Мне неверно начислили премию, исправьте расчет Иванову Ивану Ивановичу."
            ),
            "text_slots": {
                "contact_person": "Васин Василий Васильевич",
                "mentioned_person": "Иванову Ивану Ивановичу",
            },
            "expected_slots": {},
            "expected_autofill": {},
            "expected_resolution": {},
            "generation_source": {
                "type": "system_out_of_scope",
                "reason": "Формат похож на обращение с ФИО, но смысл относится к финансовому вопросу.",
            },
            "generation_notes": [
                "Проверяет, что форматное совпадение с ФИО не приводит к запуску сценария сброса пароля.",
            ],
            "expected_gaps": [],
            "expected_outcome": "out_of_scope",
            "client_behavior": {"reply_strategy": "none"},
            "mode": run["mode"],
            "dry_run": run["dry_run"],
            "excluded": False,
            "created_at": run["created_at"],
            "updated_at": run["updated_at"],
        }

    def _build_generated_ticket_text(
        self,
        detail: dict[str, Any],
        *,
        variant: str,
        rng: random.Random,
    ) -> dict[str, Any]:
        slots = detail.get("slot_schema", {}).get("slots", [])
        source = self._ticket_text_source(detail, rng)
        text = source["text"]
        text_slots = self._infer_text_slots(slots, text)
        notes: list[str] = []
        expected_gaps: list[str] = []

        if variant == "missing_required_slot":
            text, text_slots, expected_gaps = self._remove_required_text_slot(text, text_slots, slots, rng)
            notes.append("Из текста намеренно убран обязательный текстовый слот.")
        elif variant == "conflicting_data":
            text = (
                f"{text} Дополнительно указано: пароль нужно отправить Петрову Петру Петровичу, "
                "но непонятно, это получатель или другой сотрудник."
            )
            notes.append("Добавлено конфликтующее ФИО для проверки уточнения или эскалации.")
        elif variant == "no_client_reply":
            notes.append("Если сценарий задаст уточняющий вопрос, синтетический клиент не ответит.")
        elif variant == "endpoint_error":
            notes.append("Ошибка должна моделироваться в mock/capture слое endpoint, а не в тексте заявки.")
        elif variant == "external_event_wait":
            notes.append("Ожидание внешнего события моделируется runtime-событием, текст остается обычным обращением.")

        return {
            "text": text,
            "text_slots": text_slots,
            "source": source,
            "notes": notes,
            "expected_gaps": expected_gaps,
        }

    def _ticket_text_source(self, detail: dict[str, Any], rng: random.Random) -> dict[str, Any]:
        slots = detail.get("slot_schema", {}).get("slots", [])
        example_slots = [
            slot
            for slot in slots
            if slot.get("examples")
        ]
        if example_slots:
            slot = rng.choice(example_slots)
            example = rng.choice(slot["examples"])
            return {
                "type": "slot_example",
                "slot_id": slot["slot_id"],
                "text": example,
            }

        scenario = detail["scenario"]
        instruction_parts = [
            slot.get("extraction_instruction") or slot.get("user_question") or slot.get("fallback_question")
            for slot in slots
            if slot.get("extraction_instruction") or slot.get("user_question") or slot.get("fallback_question")
        ]
        if instruction_parts:
            return {
                "type": "scenario_instructions",
                "text": f"{scenario['description']} {instruction_parts[0]}",
            }
        return {
            "type": "scenario_description",
            "text": scenario.get("description") or f"Нужно обработать обращение: {scenario['display_name']}.",
        }

    def _infer_text_slots(self, slots: list[dict[str, Any]], text: str) -> dict[str, str]:
        names = FULL_NAME_RE.findall(text)
        contact_name = self._extract_contact_name(text)
        target_name = self._extract_password_target_name(text, contact_name, names)
        recipient_name = self._extract_password_recipient_name(text, contact_name, names)
        result: dict[str, str] = {}
        for slot in slots:
            if slot.get("fill_method") != "llm_extraction" and not slot.get("examples"):
                continue
            slot_id = slot["slot_id"]
            instruction = str(slot.get("extraction_instruction") or "").lower()
            value = None
            if slot_id in {"user_fio", "full_name"} or "сбросить пароль" in instruction:
                value = target_name or contact_name or (names[0] if names else None)
            elif slot_id in {"pre_manager", "recipient_fio"} or "отправить" in instruction:
                value = recipient_name or contact_name or target_name or (names[0] if names else None)
            elif names:
                value = names[0]
            if value:
                result[slot_id] = value
        return result

    @staticmethod
    def _extract_contact_name(text: str) -> str | None:
        match = re.search(r"Контактное лицо:\s*([^.\n]+)", text, flags=re.IGNORECASE)
        if not match:
            return None
        names = FULL_NAME_RE.findall(match.group(1))
        return names[0] if names else match.group(1).strip()

    @staticmethod
    def _extract_password_target_name(
        text: str,
        contact_name: str | None,
        names: list[str],
    ) -> str | None:
        password_match = re.search(
            r"(?:сбросьте|сбросить|смените|сменить)\s+(?:мне\s+)?парол[ья]\s+([^.\n]+)",
            text,
            flags=re.IGNORECASE,
        )
        if password_match:
            target_names = FULL_NAME_RE.findall(password_match.group(1))
            if target_names:
                return target_names[0]
            if re.search(r"\bмне\b|\bмой\b|\bмое\b|\bмою\b", password_match.group(0), flags=re.IGNORECASE):
                return contact_name
        if re.search(r"\bмне\b|\bмой\b|\bмое\b|\bмою\b", text, flags=re.IGNORECASE):
            return contact_name
        return names[-1] if names else None

    @staticmethod
    def _extract_password_recipient_name(
        text: str,
        contact_name: str | None,
        names: list[str],
    ) -> str | None:
        if re.search(r"отправьте\s+мне|пришлите\s+мне", text, flags=re.IGNORECASE):
            return contact_name
        send_match = re.search(r"(?:отправьте|пришлите)\s+([^.\n]+)", text, flags=re.IGNORECASE)
        if send_match:
            send_names = FULL_NAME_RE.findall(send_match.group(1))
            if send_names:
                return send_names[0]
        return contact_name if len(names) <= 1 else names[0]

    def _remove_required_text_slot(
        self,
        text: str,
        text_slots: dict[str, str],
        slots: list[dict[str, Any]],
        rng: random.Random,
    ) -> tuple[str, dict[str, str], list[str]]:
        removable_ids = [
            slot["slot_id"]
            for slot in slots
            if slot.get("required") and slot["slot_id"] in text_slots
        ]
        if not removable_ids:
            return text, text_slots, []
        slot_id = rng.choice(removable_ids)
        value = text_slots.get(slot_id)
        if value:
            contact_pattern = rf"Контактное лицо:\s*{re.escape(value)}\.\s*"
            next_text = re.sub(contact_pattern, "", text, count=1, flags=re.IGNORECASE)
            if next_text == text:
                text = text.replace(value, "сотруднику", 1)
            else:
                text = next_text
        return text.strip(), self._infer_text_slots(slots, text), [slot_id]

    def _expected_slots_for_item(
        self,
        slots: list[dict[str, Any]],
        generation: dict[str, Any],
        rng: random.Random,
    ) -> dict[str, Any]:
        text_slots = generation.get("text_slots", {})
        expected_gaps = set(generation.get("expected_gaps") or [])
        expected = dict(text_slots)
        for slot in slots:
            slot_id = slot["slot_id"]
            if slot_id in expected_gaps:
                continue
            if slot_id not in expected:
                if slot.get("fill_method") == "llm_extraction" and not slot.get("required"):
                    continue
                expected[slot_id] = self._sample_slot_value(slot, rng, expected)
        return expected

    @staticmethod
    def _expected_external_slots(
        slots: list[dict[str, Any]],
        expected_slots: dict[str, Any],
        *,
        fill_methods: set[str],
    ) -> dict[str, Any]:
        result = {}
        for slot in slots:
            if slot.get("fill_method") not in fill_methods:
                continue
            slot_id = slot["slot_id"]
            result[slot_id] = {
                "value": expected_slots.get(slot_id),
                "fill_method": slot.get("fill_method"),
                "profile_id": slot.get("resolution_profile_id"),
            }
        return result

    @staticmethod
    def _sample_slot_value(
        slot: dict[str, Any],
        rng: random.Random,
        context: dict[str, Any] | None = None,
    ) -> Any:
        slot_id = slot["slot_id"]
        context = context or {}
        if slot_id == "user_login":
            if not context.get("user_fio"):
                return None
            return DebugRuntime._login_from_full_name(str(context.get("user_fio") or "")) or rng.choice(["ivanov", "petrov", "sidorova"])
        if slot_id == "manager_email":
            if not (context.get("user_login") or context.get("user_fio") or context.get("pre_manager")):
                return None
            login = str(context.get("user_login") or "") or DebugRuntime._login_from_full_name(str(context.get("user_fio") or ""))
            return f"{login or 'ivanov'}.manager@example.local"
        samples = {
            "user_login": ["ivanov", "petrov", "sidorova"],
            "account_type": ["доменная учетная запись", "почта", "VPN"],
            "app_name": ["Outlook", "1C", "VPN"],
            "error_text": ["ошибка входа", "не запускается", "нет доступа"],
            "device_name": ["NB-1024", "PC-2048"],
            "location": ["Москва", "офис 3", "удаленно"],
        }
        values = samples.get(slot_id) or [DEFAULT_SLOT_VALUES.get(slot_id, f"значение для {slot.get('display_name', slot_id).lower()}")]
        return rng.choice(values)

    @staticmethod
    def _login_from_full_name(full_name: str) -> str | None:
        normalized = full_name.lower()
        if "иванов" in normalized or "иванову" in normalized:
            return "ivanov"
        if "васин" in normalized or "васину" in normalized:
            return "vasin"
        if "петров" in normalized or "петрову" in normalized:
            return "petrov"
        if "сидоров" in normalized or "сидорову" in normalized:
            return "sidorova"
        return None

    @staticmethod
    def _expected_outcome_for_variant(variant: str) -> str:
        if variant in {"missing_required_slot", "no_client_reply"}:
            return "wait_or_clarification"
        if variant in {"endpoint_error", "conflicting_data"}:
            return "escalation_or_error"
        if variant == "external_event_wait":
            return "external_wait"
        return "completed"

    @staticmethod
    def _client_behavior_for_variant(variant: str) -> dict[str, Any]:
        if variant == "no_client_reply":
            return {"reply_strategy": "no_reply", "timeout_seconds": 480}
        if variant == "missing_required_slot":
            return {"reply_strategy": "delayed_answer", "delay_seconds": 30}
        return {"reply_strategy": "answer_if_asked", "delay_seconds": 5}

    def _ticket_input_for_item(self, item: dict[str, Any]) -> dict[str, Any]:
        legacy_scenario = self._legacy_workflow_scenario(item.get("scenario_id"))
        return {
            "ticket_id": f"{item['run_id']}-{item['sort_order']}",
            "scenario": legacy_scenario,
            "description": item["text"],
            "service": item.get("scenario_display_name") or item.get("scenario_id") or "debug",
            "priority": "p3",
            "user": item.get("expected_slots", {}).get("user_login") or "debug-user",
            "decision_override": None,
        }

    def _legacy_workflow_scenario(self, scenario_id: str | None) -> str:
        if not scenario_id or scenario_id == "auto":
            return ""
        try:
            detail = self.config_store.scenario_detail(scenario_id)
        except ConfigRegistryError:
            return ""
        route = detail.get("route", {}).get("route")
        if route in {"major_incident", "human_review"}:
            return "escalation"
        active_tool_names = {
            tool.get("tool_name")
            for tool in self.config_store.active_payload("tools").get("tools", [])
        }
        if detail.get("tool_launches") and "start_systemcenter_runbook" in active_tool_names:
            return "runbook"
        return "answer"

    @staticmethod
    def _agent_outcome(
        status: str,
        summary: str,
        next_step: str,
        **extra: Any,
    ) -> dict[str, Any]:
        result = {
            "schema_version": "1.0",
            "status": status,
            "label": AGENT_OUTCOME_LABELS[status],
            "summary": summary,
            "next_step": next_step,
        }
        for key, value in extra.items():
            if value not in (None, "", [], {}):
                result[key] = value
        return result

    @classmethod
    def _agent_outcome_from_analysis(
        cls,
        analysis: dict[str, Any],
        processing_detail: dict[str, Any],
        result_status: str,
    ) -> dict[str, Any]:
        workflow_state = analysis.get("workflow_state") or {}
        ai_decision = analysis.get("ai_decision") or {}
        decision = ai_decision.get("decision") or {}
        tool_trace = list(analysis.get("tool_trace") or [])
        approval_requests = list(analysis.get("approval_requests") or [])
        failed_tools = [
            item
            for item in tool_trace
            if item.get("status") not in {"success", "dry_run_completed", "blocked"}
        ]
        blocked_tools = [
            item
            for item in tool_trace
            if item.get("status") == "blocked"
        ]
        runs = processing_detail.get("runs") or []
        run_status = runs[0].get("status") if runs else result_status
        operator_message = analysis.get("operator_message")

        if analysis.get("failure") or result_status == "failed" or failed_tools:
            return cls._agent_outcome(
                "error",
                operator_message or "Агент не смог завершить обработку из-за ошибки анализа или инструмента.",
                AGENT_OUTCOME_NEXT_STEPS["error"],
                workflow_state=workflow_state.get("id"),
                decision=decision.get("type"),
                failed_tools=[
                    {
                        "tool_name": item.get("tool_name"),
                        "status": item.get("status"),
                        "endpoint_id": item.get("endpoint_id"),
                        "operation_id": item.get("operation_id"),
                    }
                    for item in failed_tools
                ],
            )
        if result_status == "escalated" or decision.get("type") == "escalation_needed" or workflow_state.get("category") == "handoff":
            return cls._agent_outcome(
                "escalated",
                operator_message or "Агент подготовил передачу обращения оператору.",
                AGENT_OUTCOME_NEXT_STEPS["escalated"],
                workflow_state=workflow_state.get("id"),
                decision=decision.get("type"),
            )
        if result_status == "waiting" or workflow_state.get("category") == "waiting" or approval_requests:
            return cls._agent_outcome(
                "waiting",
                operator_message or "Агент ожидает ответ клиента или подтверждение оператора.",
                AGENT_OUTCOME_NEXT_STEPS["waiting"],
                workflow_state=workflow_state.get("id"),
                decision=decision.get("type"),
                approval_count=len(approval_requests),
            )
        if blocked_tools:
            return cls._agent_outcome(
                "needs_review",
                operator_message or "Агент завершил анализ, но часть вызовов была заблокирована политикой.",
                AGENT_OUTCOME_NEXT_STEPS["needs_review"],
                workflow_state=workflow_state.get("id"),
                decision=decision.get("type"),
                blocked_tools=[
                    {
                        "tool_name": item.get("tool_name"),
                        "status": item.get("status"),
                        "endpoint_id": item.get("endpoint_id"),
                        "operation_id": item.get("operation_id"),
                    }
                    for item in blocked_tools
                ],
            )
        return cls._agent_outcome(
            "success",
            operator_message or "Агент завершил обработку обращения без блокирующих проблем.",
            AGENT_OUTCOME_NEXT_STEPS["success"],
            workflow_state=workflow_state.get("id"),
            decision=decision.get("type"),
            run_status=run_status,
            tool_count=len(tool_trace),
        )

    @classmethod
    def _agent_outcome_with_expectation(
        cls,
        item: dict[str, Any],
        outcome: dict[str, Any],
    ) -> dict[str, Any]:
        if cls._expected_outcome_matches(item.get("expected_outcome"), outcome.get("status")):
            return outcome
        expected = item.get("expected_outcome") or "н/д"
        actual = outcome.get("label") or outcome.get("status") or "н/д"
        return cls._agent_outcome(
            "needs_review",
            f"Фактический итог агента отличается от ожидаемой ветки генератора: ожидалось {expected}, получено {actual}.",
            "Проверьте текст обращения, настройки сценария и трассу обработки.",
            expected_outcome=expected,
            actual_outcome=outcome,
            expected_mismatch=True,
        )

    @staticmethod
    def _expected_outcome_matches(expected: str | None, actual_status: str | None) -> bool:
        if not expected or not actual_status:
            return True
        expected_to_actual = {
            "completed": {"success"},
            "wait_or_clarification": {"waiting"},
            "manual_review": {"needs_review", "escalated"},
            "escalation_or_error": {"escalated", "error"},
            "external_wait": {"waiting"},
            "out_of_scope": {"needs_review", "escalated", "error"},
        }
        allowed = expected_to_actual.get(expected)
        if not allowed:
            return True
        return actual_status in allowed

    @staticmethod
    def _simulation_status_from_analysis(
        analysis: dict[str, Any],
        processing_detail: dict[str, Any],
    ) -> str:
        run_status = (processing_detail.get("runs") or [{}])[0].get("status")
        if run_status in {"waiting", "escalated", "failed", "completed"}:
            return run_status
        state_category = analysis.get("workflow_state", {}).get("category")
        if state_category == "waiting":
            return "waiting"
        if state_category == "handoff":
            return "escalated"
        if analysis.get("failure"):
            return "failed"
        return "completed"

    @staticmethod
    def _has_expected_mismatch(item: dict[str, Any], analysis: dict[str, Any]) -> bool:
        outcome = item.get("agent_outcome") or {}
        if outcome.get("expected_mismatch"):
            return True
        expected = item.get("expected_outcome")
        decision_type = analysis.get("ai_decision", {}).get("decision", {}).get("type")
        if expected == "out_of_scope":
            return decision_type == "action_proposed"
        return False

    @staticmethod
    def _trace_event(
        *,
        created_at: str | None,
        event_type: str | None,
        summary: str | None,
        actor_id: str | None,
        actor_type: str | None,
        payload: dict[str, Any] | None,
        correlation: dict[str, Any] | None,
        run_id: str | None = None,
        task_id: str | None = None,
        agent_id: str | None = None,
        parent_event_id: str | None = None,
        trace_step: str | None = None,
    ) -> dict[str, Any]:
        payload = payload or {}
        correlation = correlation or {}
        return {
            "created_at": created_at,
            "event_type": event_type,
            "summary": summary,
            "actor_id": actor_id,
            "actor_type": actor_type,
            "case_id": payload.get("case_id") or correlation.get("case_id"),
            "run_id": run_id or correlation.get("run_id") or payload.get("run_id"),
            "task_id": task_id or correlation.get("task_id") or payload.get("task_id"),
            "agent_id": agent_id,
            "correlation_id": correlation.get("correlation_id") or payload.get("correlation_id"),
            "parent_event_id": parent_event_id,
            "idempotency_key": correlation.get("idempotency_key") or payload.get("idempotency_key"),
            "trace_step": trace_step,
            "payload_summary": value_preview(payload),
            "payload": payload,
            "correlation": correlation,
        }

    def _require_operation(self, endpoint_id: str | None, operation_id: str | None) -> tuple[dict[str, Any], dict[str, Any]]:
        if not endpoint_id or not operation_id:
            raise DebugRuntimeError("Нужно выбрать endpoint и операцию.")
        return self._find_operation(self.config_store.active_payload("integration_endpoints"), endpoint_id, operation_id)

    @staticmethod
    def _find_operation(
        endpoint_catalog: dict[str, Any],
        endpoint_id: str,
        operation_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        for endpoint in endpoint_catalog.get("endpoints", []):
            if endpoint.get("endpoint_id") == endpoint_id:
                operation = endpoint.get("operations", {}).get(operation_id)
                if operation:
                    return endpoint, operation
        raise DebugRuntimeError(f"Endpoint-операция не найдена: {endpoint_id}/{operation_id}")

    @staticmethod
    def _response_validation_errors(operation: dict[str, Any], response_payload: dict[str, Any]) -> list[str]:
        validator = Draft202012Validator(operation.get("response_schema", {"type": "object"}))
        errors = []
        for error in sorted(validator.iter_errors(response_payload), key=lambda item: list(item.path)):
            path = ".".join(str(part) for part in error.path)
            errors.append(f"{path or '$'}: {error.message}")
        return errors

    def _insert_simulation_run(self, connection: sqlite3.Connection, run: dict[str, Any]) -> None:
        connection.execute(
            """
            insert into debug_simulation_runs (
                run_id, status, created_at, updated_at, run_json
            )
            values (?, ?, ?, ?, ?)
            """,
            (run["run_id"], run["status"], run["created_at"], run["updated_at"], self._to_json(run)),
        )

    def _insert_simulation_item(self, connection: sqlite3.Connection, item: dict[str, Any]) -> None:
        connection.execute(
            """
            insert into debug_simulation_items (
                item_id, run_id, status, scenario_id, case_id, sort_order,
                created_at, updated_at, item_json
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item["item_id"],
                item["run_id"],
                item["status"],
                item.get("scenario_id"),
                item.get("case_id"),
                item["sort_order"],
                item["created_at"],
                item["updated_at"],
                self._to_json(item),
            ),
        )

    def _insert_capture(self, connection: sqlite3.Connection, capture: dict[str, Any]) -> None:
        connection.execute(
            """
            insert into debug_endpoint_captures (
                capture_id, session_id, endpoint_id, operation_id, status,
                sanitized, case_id, created_at, updated_at, capture_json
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                capture["capture_id"],
                capture["session_id"],
                capture["endpoint_id"],
                capture["operation_id"],
                capture["status"],
                1 if capture.get("sanitized") else 0,
                capture.get("case_id"),
                capture["created_at"],
                capture["updated_at"],
                self._to_json(capture),
            ),
        )

    def _save_simulation_run(self, run: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                update debug_simulation_runs
                set status = ?, updated_at = ?, run_json = ?
                where run_id = ?
                """,
                (run["status"], run["updated_at"], self._to_json(run), run["run_id"]),
            )

    def _save_simulation_item(self, item: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                update debug_simulation_items
                set status = ?, scenario_id = ?, case_id = ?, updated_at = ?, item_json = ?
                where item_id = ?
                """,
                (
                    item["status"],
                    item.get("scenario_id"),
                    item.get("case_id"),
                    item["updated_at"],
                    self._to_json(item),
                    item["item_id"],
                ),
            )

    def _save_capture_session(self, session: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                update debug_capture_sessions
                set status = ?, updated_at = ?, session_json = ?
                where session_id = ?
                """,
                (session["status"], session["updated_at"], self._to_json(session), session["session_id"]),
            )

    def _save_capture(self, capture: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                update debug_endpoint_captures
                set status = ?, sanitized = ?, updated_at = ?, capture_json = ?
                where capture_id = ?
                """,
                (
                    capture["status"],
                    1 if capture.get("sanitized") else 0,
                    capture["updated_at"],
                    self._to_json(capture),
                    capture["capture_id"],
                ),
            )

    def _refresh_run_counters(self, run_id: str) -> dict[str, Any]:
        run = self.require_simulation_run(run_id)
        counters = {
            "prepared": 0,
            "started": 0,
            "completed": 0,
            "waiting": 0,
            "escalated": 0,
            "failed": 0,
            "excluded": 0,
        }
        for item in self.list_simulation_items(run_id)["items"]:
            if item.get("excluded") or item.get("status") == "excluded":
                counters["excluded"] += 1
                continue
            status = item.get("status") or "prepared"
            if status in counters:
                counters[status] += 1
            if status in {"running", "completed", "waiting", "escalated", "failed"}:
                counters["started"] += 1
        run["counters"] = counters
        run["updated_at"] = utc_now()
        self._save_simulation_run(run)
        return run

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

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                create table if not exists debug_simulation_runs (
                    run_id text primary key,
                    status text not null,
                    created_at text not null,
                    updated_at text not null,
                    run_json text not null
                )
                """
            )
            connection.execute("create index if not exists idx_debug_simulation_runs_status on debug_simulation_runs(status)")
            connection.execute(
                """
                create table if not exists debug_simulation_items (
                    item_id text primary key,
                    run_id text not null,
                    status text not null,
                    scenario_id text,
                    case_id text,
                    sort_order integer not null,
                    created_at text not null,
                    updated_at text not null,
                    item_json text not null
                )
                """
            )
            connection.execute("create index if not exists idx_debug_simulation_items_run_id on debug_simulation_items(run_id)")
            connection.execute("create index if not exists idx_debug_simulation_items_case_id on debug_simulation_items(case_id)")
            connection.execute(
                """
                create table if not exists debug_capture_sessions (
                    session_id text primary key,
                    endpoint_id text not null,
                    operation_id text not null,
                    status text not null,
                    created_at text not null,
                    updated_at text not null,
                    session_json text not null
                )
                """
            )
            connection.execute("create index if not exists idx_debug_capture_sessions_status on debug_capture_sessions(status)")
            connection.execute(
                """
                create table if not exists debug_endpoint_captures (
                    capture_id text primary key,
                    session_id text not null,
                    endpoint_id text not null,
                    operation_id text not null,
                    status text not null,
                    sanitized integer not null,
                    case_id text,
                    created_at text not null,
                    updated_at text not null,
                    capture_json text not null
                )
                """
            )
            connection.execute("create index if not exists idx_debug_endpoint_captures_session_id on debug_endpoint_captures(session_id)")
            connection.execute("create index if not exists idx_debug_endpoint_captures_operation on debug_endpoint_captures(endpoint_id, operation_id)")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _to_json(record: dict[str, Any]) -> str:
        return json.dumps(record, ensure_ascii=False, sort_keys=True)
