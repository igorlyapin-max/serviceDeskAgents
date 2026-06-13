from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .action_gates import (
    ActionGateConflict,
    ActionGateNotFound,
    ActionGateStore,
    new_gate_id,
    utc_now,
)
from .cases import CaseStore, new_case_id
from .config_registry import DEFAULT_EXTERNAL_EVENT_RESULT_TOPIC, ConfigStore, default_model_routing, default_prompt_catalog
from .contracts import CONTRACTS_ROOT, ContractRegistry, load_json
from .feedback import FeedbackStore
from .integrations import IntegrationDispatcher, ToolRegistry
from .knowledge import KnowledgeIndexer, KnowledgeRetriever


REQUIRED_TICKET_FIELDS = ("user", "service", "description", "priority")
POLICY_RULES_PATH = CONTRACTS_ROOT / "execution" / "execution-policy-rules.json"


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: list[str]


class WorkflowStateResolver:
    def __init__(self, contracts: ContractRegistry):
        self.contracts = contracts
        self.catalog = contracts.workflow_state_catalog
        self.transition_rules = contracts.workflow_transition_rules
        self.states_by_id = {
            state["id"]: state
            for state in self.catalog["states"]
        }

    def resolve(self, facts: dict[str, str]) -> dict[str, Any]:
        for rule in self.transition_rules["rules"]:
            when = rule["when"]
            if all(facts.get(key) == expected for key, expected in when.items()):
                state = copy.deepcopy(self.states_by_id[rule["state_id"]])
                self.contracts.require_valid("workflow_state", state)
                return state
        raise ValueError(f"no workflow transition rule matched facts: {facts}")


class ExecutionPolicy:
    def __init__(self, contracts: ContractRegistry, rules_path: Path = POLICY_RULES_PATH):
        self.contracts = contracts
        self.policy = load_json(rules_path)
        self.contracts.require_valid("execution_policy_rules", self.policy)

    def evaluate(self, action: dict[str, Any]) -> dict[str, Any]:
        for rule in self.policy["rules"]:
            if self._matches(rule["match"], action):
                result = self._build_result(rule, action)
                self.contracts.require_valid("execution_policy_result", result)
                return result

        default_rule = {
            "policy_rule_id": self.policy["default_result"]["policy_rule_id"],
            "result": self.policy["default_result"],
        }
        result = self._build_result(default_rule, action)
        self.contracts.require_valid("execution_policy_result", result)
        return result

    @staticmethod
    def _matches(match: dict[str, Any], action: dict[str, Any]) -> bool:
        for key, expected in match.items():
            actual = action.get(key)
            if actual is None:
                actual = action.get("parameters", {}).get(key)
            if actual != expected:
                return False
        return True

    @staticmethod
    def _build_result(rule: dict[str, Any], action: dict[str, Any]) -> dict[str, Any]:
        result = {
            "schema_version": "1.0",
            "action_id": action["action_id"],
            "tool_name": action["tool_name"],
            **rule["result"],
        }
        if "policy_rule_id" not in result:
            result["policy_rule_id"] = rule["policy_rule_id"]
        if "risk_level" not in result and "risk_level" in action:
            result["risk_level"] = action["risk_level"]
        return result


class TicketWorkflow:
    def __init__(
        self,
        contracts: ContractRegistry | None = None,
        action_gate_store: ActionGateStore | None = None,
        knowledge_indexer: KnowledgeIndexer | None = None,
        knowledge_retriever: KnowledgeRetriever | None = None,
        feedback_store: FeedbackStore | None = None,
        case_store: CaseStore | None = None,
        config_store: ConfigStore | None = None,
        processing_store: Any | None = None,
    ):
        self.contracts = contracts or ContractRegistry()
        self.config_store = config_store
        self.policy = ExecutionPolicy(self.contracts)
        self.state_resolver = WorkflowStateResolver(self.contracts)
        self.tool_registry = ToolRegistry(self.contracts)
        self.capture_recorder = None
        self.integration_dispatcher = IntegrationDispatcher(
            self.contracts,
            self.tool_registry,
        )
        self.action_gate_store = action_gate_store or ActionGateStore(self.contracts)
        self.knowledge_indexer = knowledge_indexer or KnowledgeIndexer(self.contracts)
        self.knowledge_retriever = knowledge_retriever or KnowledgeRetriever(self.contracts)
        self.feedback_store = feedback_store or FeedbackStore(self.contracts)
        self.case_store = case_store or CaseStore(self.contracts)
        self.processing_store = processing_store
        if self.config_store:
            self.apply_active_config()

    def analyze(self, ticket: dict[str, Any]) -> dict[str, Any]:
        case_id = ticket.get("case_id") or new_case_id()
        ticket_id = ticket.get("ticket_id") or f"local-{uuid.uuid4().hex[:12]}"
        retrieval_result = self._retrieve_knowledge(ticket)
        ai_decision = self._decision_node(ticket)
        self._apply_retrieval_context(ai_decision, retrieval_result)
        validation = self._validate_ai_decision(ai_decision)
        rag_trace = self._build_rag_trace(retrieval_result)

        if not validation.valid:
            workflow_state = self.state_resolver.resolve(
                {"failure_state": "model_output_invalid"}
            )
            failure = {
                "schema_version": "1.0",
                "workflow_state": workflow_state,
                "can_advance": False,
                "errors": validation.errors,
            }
            self.contracts.require_valid("model_output_invalid", failure)
            analysis = {
                "case_id": case_id,
                "ticket_id": ticket_id,
                "workflow_state": workflow_state,
                "ai_decision": None,
                "execution_policy_results": [],
                "operator_message": "Ответ модели не прошел валидацию и требует ручной проверки.",
                "tool_results": [],
                "tool_trace": [],
                "approval_requests": [],
                "rag_trace": rag_trace,
                "failure": failure,
            }
            self.case_store.create_from_analysis(ticket, analysis)
            return analysis

        proposed_actions = ai_decision.get("proposed_actions", [])
        execution_policy_results = [
            self.policy.evaluate(action)
            for action in proposed_actions
        ]
        workflow_state = self._resolve_workflow_state(ai_decision, execution_policy_results)
        approval_requests = self._create_action_gates(
            case_id,
            ticket_id,
            proposed_actions,
            execution_policy_results,
        )
        gate_by_action_id = {
            request["action_id"]: request["gate_id"]
            for request in approval_requests
        }
        tool_results = self._dispatch_tool_node(
            case_id,
            ticket_id,
            proposed_actions,
            execution_policy_results,
            gate_by_action_id,
        )
        tool_trace = self._build_tool_trace(tool_results)

        analysis = {
            "case_id": case_id,
            "ticket_id": ticket_id,
            "workflow_state": workflow_state,
            "ai_decision": ai_decision,
            "execution_policy_results": execution_policy_results,
            "operator_message": ai_decision["operator_message"],
            "tool_results": tool_results,
            "tool_trace": tool_trace,
            "approval_requests": approval_requests,
            "rag_trace": rag_trace,
        }
        self.case_store.create_from_analysis(ticket, analysis)
        return analysis

    def dispatch_tool(
        self,
        action: dict[str, Any],
        policy_result: dict[str, Any],
        *,
        case_id: str | None = None,
        ticket_id: str | None = None,
        approved_by_operator: bool = False,
        operator_id: str | None = None,
    ) -> dict[str, Any]:
        preferred_launch = self._preferred_launch_for_action(action)
        invocation = self.tool_registry.build_invocation(
            action,
            policy_result,
            case_id=case_id,
            ticket_id=ticket_id,
            approved_by_operator=approved_by_operator,
            operator_id=operator_id,
            endpoint_id=preferred_launch.get("endpoint_id") if preferred_launch else None,
            operation_id=preferred_launch.get("operation_id") if preferred_launch else None,
        )
        completion_policy = self._completion_policy_for_invocation(action, invocation, preferred_launch=preferred_launch)
        if self._should_enqueue_async_tool(invocation, completion_policy):
            preflight_result = self.integration_dispatcher.preflight(invocation)
            if preflight_result:
                return {
                    "invocation": invocation,
                    "tool_result": preflight_result,
                }
            queued = self.processing_store.enqueue_async_tool_command(
                invocation,
                expected_event_type=completion_policy["expected_event_type"],
                result_transport=completion_policy.get("result_transport", "http_callback"),
                result_topic=completion_policy.get("result_topic"),
                contract_snapshot=self._external_event_contract_snapshot(invocation, completion_policy),
                deadline_seconds=completion_policy.get("max_wait_seconds"),
                reason=f"Ожидание результата ReAct-вызова {invocation['tool_name']}.",
            )
            return {
                "invocation": queued["command"]["invocation"],
                "tool_result": self._async_tool_queued_result(invocation, queued, completion_policy),
            }
        result = self.integration_dispatcher.dispatch(invocation)
        return {
            "invocation": invocation,
            "tool_result": result,
        }

    def get_action_gate(self, gate_id: str) -> dict[str, Any]:
        return self.action_gate_store.require(gate_id)

    def list_ticket_action_gates(self, ticket_id: str) -> list[dict[str, Any]]:
        return self.action_gate_store.list_by_ticket(ticket_id)

    def rebuild_knowledge(self, operator_id: str) -> dict[str, Any]:
        return self.knowledge_indexer.rebuild(operator_id)

    def knowledge_status(self) -> dict[str, Any]:
        return self.knowledge_indexer.status()

    def knowledge_sources(self) -> dict[str, Any]:
        return self.knowledge_indexer.source_catalog()

    def knowledge_chunks(self, *, source_id: str | None = None, limit: int = 50) -> dict[str, Any]:
        return self.knowledge_indexer.chunks(source_id=source_id, limit=limit)

    def test_retrieval(self, query: dict[str, Any]) -> dict[str, Any]:
        retrieval_query = {
            key: value
            for key, value in query.items()
            if value is not None
        }
        if "schema_version" not in retrieval_query:
            retrieval_query["schema_version"] = "1.0"
        return self.knowledge_retriever.retrieve(retrieval_query)

    def submit_feedback(self, request: dict[str, Any]) -> dict[str, Any]:
        feedback = self.feedback_store.create(request)
        self.case_store.record_feedback(feedback)
        return feedback

    def list_ticket_feedback(self, ticket_id: str) -> list[dict[str, Any]]:
        return self.feedback_store.list_by_ticket(ticket_id)

    def export_feedback_jsonl(self) -> str:
        return self.feedback_store.export_jsonl()

    def admin_dashboard(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "cases": self.case_store.summary(),
            "approvals": self.action_gate_store.summary(),
            "feedback": self.feedback_store.summary(),
            "knowledge": self.knowledge_status(),
            "tools": {
                "count": len(self.contracts.tool_catalog["tools"]),
                "names": [
                    tool["tool_name"]
                    for tool in self.contracts.tool_catalog["tools"]
                ],
            },
            "integrations": {
                "endpoint_count": len(self.contracts.integration_endpoint_catalog["endpoints"]),
                "enabled_endpoint_count": sum(
                    1
                    for endpoint in self.contracts.integration_endpoint_catalog["endpoints"]
                    if endpoint["enabled"]
                ),
            },
            "models": self.model_config(),
        }

    def catalog_inventory(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "tools": self.contracts.tool_catalog,
            "integration_endpoints": self.contracts.integration_endpoint_catalog,
            "workflow": {
                "state_catalog": self.contracts.workflow_state_catalog,
                "transition_rules": self.contracts.workflow_transition_rules,
            },
            "models": self.model_config(),
        }

    def model_config(self) -> dict[str, Any]:
        if self.config_store:
            return self.config_store.active_payload("model_routing")
        return default_model_routing()

    def prompt_catalog(self) -> dict[str, Any]:
        if self.config_store:
            return self.config_store.active_payload("prompts")
        return default_prompt_catalog()

    def n8n_workflow_catalog(self) -> dict[str, Any]:
        if self.config_store:
            return self.config_store.active_payload("n8n_workflows")
        return self.contracts.n8n_workflow_catalog

    def attach_config_store(self, config_store: ConfigStore) -> None:
        self.config_store = config_store
        self.apply_active_config()

    def attach_processing_store(self, processing_store: Any) -> None:
        self.processing_store = processing_store

    def apply_active_config(self) -> None:
        if not self.config_store:
            return
        for domain in (
            "integration_endpoints",
            "tools",
            "workflow_states",
            "workflow_transitions",
            "n8n_workflows",
        ):
            active_config = self.config_store.active_config(domain)
            if active_config["source"] == "active_version":
                self.apply_config_payload(domain, active_config["payload"])

    def apply_config_payload(self, domain: str, payload: dict[str, Any]) -> None:
        if domain == "tools":
            self.contracts.tool_catalog = copy.deepcopy(payload)
            self.tool_registry = ToolRegistry(self.contracts)
            self.integration_dispatcher = IntegrationDispatcher(
                self.contracts,
                self.tool_registry,
            )
            self.integration_dispatcher.capture_recorder = self.capture_recorder
            return
        if domain == "integration_endpoints":
            self.contracts.integration_endpoint_catalog = copy.deepcopy(payload)
            self.tool_registry = ToolRegistry(self.contracts)
            self.integration_dispatcher = IntegrationDispatcher(
                self.contracts,
                self.tool_registry,
            )
            self.integration_dispatcher.capture_recorder = self.capture_recorder
            return
        if domain == "workflow_states":
            self.contracts.workflow_state_catalog = copy.deepcopy(payload)
            self.state_resolver = WorkflowStateResolver(self.contracts)
            return
        if domain == "workflow_transitions":
            self.contracts.workflow_transition_rules = copy.deepcopy(payload)
            self.state_resolver = WorkflowStateResolver(self.contracts)
            return
        if domain == "n8n_workflows":
            self.contracts.n8n_workflow_catalog = copy.deepcopy(payload)

    def list_feedback(self, limit: int = 100) -> list[dict[str, Any]]:
        records = self.feedback_store.list_all()
        return list(reversed(records))[: max(limit, 0)]

    def list_evaluation_runs(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.feedback_store.list_evaluation_runs(limit=max(limit, 0))

    def promote_feedback_to_evaluation_cases(
        self,
        *,
        operator_id: str,
        feedback_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        return self.feedback_store.promote_to_evaluation_cases(
            feedback_ids=feedback_ids,
            promoted_by=operator_id,
        )

    def list_evaluation_cases(self, case_ids: list[str] | None = None) -> list[dict[str, Any]]:
        return self.feedback_store.list_evaluation_cases(case_ids)

    def run_evaluation(
        self,
        *,
        operator_id: str,
        case_ids: list[str] | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        evaluation_cases = self.feedback_store.list_evaluation_cases(case_ids)
        if limit is not None:
            evaluation_cases = evaluation_cases[: max(limit, 0)]
        run = self.feedback_store.create_evaluation_run(
            operator_id=operator_id,
            case_count=len(evaluation_cases),
            extensions={
                "case_ids": case_ids or [],
                "execution_policy": "mock_or_dry_run",
            },
        )
        results = []
        for index, evaluation_case in enumerate(evaluation_cases, start=1):
            result = self._run_evaluation_case(run["run_id"], index, evaluation_case)
            results.append(self.feedback_store.save_evaluation_result(result))
            self._record_evaluation_event(evaluation_case, result)

        completed_run = self.feedback_store.complete_evaluation_run(run["run_id"], "completed")
        return {
            "schema_version": "1.0",
            "run": completed_run,
            "results": results,
            "summary": self._evaluation_summary(results),
        }

    def get_evaluation_run(self, run_id: str) -> dict[str, Any] | None:
        run = self.feedback_store.get_evaluation_run(run_id)
        if run is None:
            return None
        return {
            "schema_version": "1.0",
            "run": run,
            "results": self.feedback_store.list_evaluation_results(run_id),
        }

    def get_case(self, case_id: str) -> dict[str, Any]:
        return self.case_store.require(case_id)

    def get_case_timeline(self, case_id: str) -> dict[str, Any]:
        return self.case_store.timeline(case_id)

    def handle_integration_callback(self, callback: dict[str, Any]) -> dict[str, Any]:
        callback = copy.deepcopy(callback)
        if "received_at" not in callback:
            callback["received_at"] = utc_now()
        self.contracts.require_valid("integration_callback", callback)
        tool_result = self._tool_result_from_callback(callback)
        self.contracts.require_valid("tool_result", tool_result)
        self.tool_registry.validate_result(tool_result)
        workflow_state = self.state_resolver.resolve({"tool_status": tool_result["status"]})
        case = self.case_store.record_integration_callback(
            callback,
            tool_result,
            workflow_state,
        )
        return {
            "schema_version": "1.0",
            "accepted": True,
            "case": case,
            "workflow_state": workflow_state,
            "tool_result": tool_result,
        }

    def _run_evaluation_case(
        self,
        run_id: str,
        index: int,
        evaluation_case: dict[str, Any],
    ) -> dict[str, Any]:
        now = utc_now()
        try:
            ticket_input = copy.deepcopy(evaluation_case["ticket_input"])
            ticket_input["ticket_id"] = f"{run_id}-{index}"
            ticket_input.setdefault("scenario", ticket_input.get("scenario"))
            actual = self.analyze(ticket_input)
            status, error = self._score_evaluation_case(evaluation_case, actual)
            result = {
                "schema_version": "1.0",
                "run_id": run_id,
                "case_id": evaluation_case["case_id"],
                "status": status,
                "created_at": now,
                "actual": self._evaluation_actual(actual),
            }
            if error:
                result["error"] = error
            return result
        except Exception as error:  # noqa: BLE001 - evaluation records failures per case.
            return {
                "schema_version": "1.0",
                "run_id": run_id,
                "case_id": evaluation_case["case_id"],
                "status": "failed",
                "created_at": now,
                "error": {
                    "code": "evaluation_case_failed",
                    "message": str(error),
                },
            }

    def _score_evaluation_case(
        self,
        evaluation_case: dict[str, Any],
        actual: dict[str, Any],
    ) -> tuple[str, dict[str, str] | None]:
        expected = evaluation_case["expected"]
        rating = expected["rating"]
        if rating == "incorrect":
            return (
                "skipped",
                {
                    "code": "negative_feedback_without_expected_answer",
                    "message": "Оценка incorrect не содержит ожидаемый корректный ответ.",
                },
            )

        if rating == "edited":
            corrected = str(expected.get("corrected_response") or "").strip()
            actual_text = " ".join(
                [
                    str(actual.get("operator_message") or ""),
                    str((actual.get("ai_decision") or {}).get("decision", {}).get("summary") or ""),
                    str((actual.get("ai_decision") or {}).get("decision", {}).get("question") or ""),
                    str((actual.get("ai_decision") or {}).get("decision", {}).get("reason") or ""),
                ]
            )
            if corrected and corrected in actual_text:
                return "passed", None
            return (
                "failed",
                {
                    "code": "corrected_response_not_matched",
                    "message": "Текущий ответ не совпал с исправленным ответом оператора.",
                },
            )

        baseline = evaluation_case.get("analysis_snapshot", {})
        expected_state = baseline.get("workflow_state", {}).get("id")
        expected_decision = (baseline.get("ai_decision") or {}).get("decision", {}).get("type")
        actual_state = actual.get("workflow_state", {}).get("id")
        actual_decision = (actual.get("ai_decision") or {}).get("decision", {}).get("type")
        if expected_state == actual_state and expected_decision == actual_decision:
            return "passed", None
        return (
            "failed",
            {
                "code": "analysis_snapshot_changed",
                "message": "Текущее решение отличается от snapshot, который оператор отметил как correct.",
            },
        )

    @staticmethod
    def _evaluation_actual(actual: dict[str, Any]) -> dict[str, Any]:
        decision = (actual.get("ai_decision") or {}).get("decision", {})
        return {
            "case_id": actual.get("case_id"),
            "ticket_id": actual.get("ticket_id"),
            "workflow_state_id": actual.get("workflow_state", {}).get("id"),
            "decision_type": decision.get("type"),
            "decision_summary": decision.get("summary") or decision.get("question") or decision.get("reason"),
            "operator_message": actual.get("operator_message"),
            "rag_status": actual.get("rag_trace", {}).get("status"),
            "tool_statuses": [
                result.get("status")
                for result in actual.get("tool_results", [])
            ],
        }

    @staticmethod
    def _evaluation_summary(results: list[dict[str, Any]]) -> dict[str, int]:
        summary = {
            "passed": 0,
            "failed": 0,
            "skipped": 0,
        }
        for result in results:
            status = result["status"]
            summary[status] = summary.get(status, 0) + 1
        summary["total"] = len(results)
        return summary

    def _record_evaluation_event(
        self,
        evaluation_case: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        case_id = evaluation_case.get("extensions", {}).get("case_id")
        if not case_id:
            return
        try:
            self.case_store.append_event(
                case_id,
                "evaluation_result_recorded",
                actor_type="system",
                actor_id="evaluation_runner",
                summary=f"Результат оценки записан со статусом {result['status']}.",
                correlation={
                    "feedback_id": evaluation_case["source_feedback_id"],
                },
                payload={
                    "evaluation_case_id": evaluation_case["case_id"],
                    "evaluation_result": copy.deepcopy(result),
                },
            )
        except Exception:
            return

    def decide_action_gate(
        self,
        gate_id: str,
        decision_request: dict[str, Any],
    ) -> dict[str, Any]:
        self.contracts.require_valid("action_gate_decision", decision_request)
        record = copy.deepcopy(self.action_gate_store.require(gate_id))
        if record["gate_type"] != "operator_approval":
            raise ActionGateConflict(
                f"{gate_id} имеет тип {record['gate_type']} и не может быть решен оператором"
            )
        if record["status"] != "pending":
            raise ActionGateConflict(
                f"{gate_id} уже находится в статусе {record['status']} и не может быть решен повторно"
            )

        if decision_request["decision"] == "reject":
            return self._reject_action_gate(record, decision_request)
        return self._approve_action_gate(record, decision_request)

    def _decision_node(self, ticket: dict[str, Any]) -> dict[str, Any]:
        override = ticket.get("decision_override")
        if isinstance(override, dict):
            return override

        missing_fields = self._missing_fields(ticket)
        scenario = (ticket.get("scenario") or "").strip().lower()

        if scenario == "invalid_model_output":
            return {
                "schema_version": "1.0",
                "decision": {
                    "type": "action_proposed",
                    "summary": "Некорректный model output со смешанной execution policy.",
                    "confidence": 0.9,
                },
                "operator_message": "Этот ответ должен не пройти валидацию.",
                "execution_mode": "auto_execute",
                "proposed_actions": [],
            }

        if missing_fields and scenario not in {"answer", "escalation", "runbook", "action"}:
            return self._clarification_decision(missing_fields)

        if scenario == "clarification":
            return self._clarification_decision(missing_fields or ["service"])
        if scenario == "escalation":
            return self._escalation_decision(ticket)
        if scenario in {"runbook", "action"}:
            return self._runbook_decision(ticket)
        if scenario == "answer":
            return self._answer_decision(ticket)

        return self._classify_by_description(ticket)

    def _validate_ai_decision(self, ai_decision: dict[str, Any]) -> ValidationResult:
        errors = self.contracts.validate("ai_decision", ai_decision)
        return ValidationResult(valid=not errors, errors=errors)

    def _retrieve_knowledge(self, ticket: dict[str, Any]) -> dict[str, Any]:
        try:
            query = self.knowledge_retriever.build_query_from_ticket(ticket)
            return self.knowledge_retriever.retrieve(query)
        except Exception as error:  # noqa: BLE001 - RAG must degrade without breaking workflow.
            query = {
                "schema_version": "1.0",
                "query": str(ticket.get("description") or "заявка service desk"),
                "top_k": 3,
            }
            result = {
                "schema_version": "1.0",
                "status": "error",
                "query": query,
                "matches": [],
                "error": {
                    "code": "retrieval_failed",
                    "message": str(error),
                },
            }
            self.contracts.require_valid("retrieval_result", result)
            return result

    @staticmethod
    def _apply_retrieval_context(
        ai_decision: dict[str, Any],
        retrieval_result: dict[str, Any],
    ) -> None:
        matches = retrieval_result.get("matches", [])
        if not matches:
            return

        citations = [
            {
                "source_id": match["source_id"],
                "title": match["title"],
                "url": match["uri"],
            }
            for match in matches
        ]
        ai_decision["citations"] = citations
        extensions = ai_decision.setdefault("extensions", {})
        extensions["retrieval"] = {
            "status": retrieval_result["status"],
            "index_id": retrieval_result.get("index_id"),
            "match_count": len(matches),
        }
        first_title = matches[0]["title"]
        ai_decision["operator_message"] = (
            f"{ai_decision['operator_message']} Связанная статья базы знаний: {first_title}."
        )

    @staticmethod
    def _build_rag_trace(retrieval_result: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": retrieval_result["status"],
            "index_id": retrieval_result.get("index_id"),
            "built_at": retrieval_result.get("built_at"),
            "match_count": len(retrieval_result.get("matches", [])),
            "matches": [
                {
                    "source_id": match["source_id"],
                    "document_id": match["document_id"],
                    "chunk_id": match["chunk_id"],
                    "title": match["title"],
                    "uri": match["uri"],
                    "score": match["score"],
                }
                for match in retrieval_result.get("matches", [])
            ],
            "error_code": retrieval_result.get("error", {}).get("code"),
        }

    def _resolve_workflow_state(
        self,
        ai_decision: dict[str, Any],
        policy_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        decision_type = ai_decision["decision"]["type"]
        facts = {"decision_type": decision_type}
        if policy_results:
            facts["execution_mode"] = self._dominant_execution_mode(policy_results)
        return self.state_resolver.resolve(facts)

    @staticmethod
    def _dominant_execution_mode(policy_results: list[dict[str, Any]]) -> str:
        priority = ["blocked", "operator_approval", "auto_execute", "dry_run", "manual_only"]
        modes = {result["execution_mode"] for result in policy_results}
        for mode in priority:
            if mode in modes:
                return mode
        return policy_results[0]["execution_mode"]

    @staticmethod
    def _missing_fields(ticket: dict[str, Any]) -> list[str]:
        return [
            field
            for field in REQUIRED_TICKET_FIELDS
            if not str(ticket.get(field) or "").strip()
        ]

    def _classify_by_description(self, ticket: dict[str, Any]) -> dict[str, Any]:
        description = str(ticket.get("description") or "").lower()
        priority = str(ticket.get("priority") or "").lower()

        if any(token in description for token in ["runbook", "restart", "перезапуск"]):
            return self._runbook_decision(ticket)
        if (
            any(token in description for token in ["escalat", "эскала", "l2"])
            or priority in {"p1", "critical", "критический"}
            or "down" in description
        ):
            return self._escalation_decision(ticket)
        return self._answer_decision(ticket)

    @staticmethod
    def _answer_decision(ticket: dict[str, Any]) -> dict[str, Any]:
        service = ticket.get("service") or "запрошенный сервис"
        return {
            "schema_version": "1.0",
            "decision": {
                "type": "answer_proposed",
                "summary": f"{service}: можно обработать без внешнего действия.",
                "confidence": 0.72,
            },
            "operator_message": "Передайте подготовленный ответ заявителю.",
            "internal_reasoning_summary": "Детерминированное правило этапа 3 выбрало answer_proposed.",
            "citations": [],
            "proposed_actions": [],
        }

    @staticmethod
    def _clarification_decision(missing_fields: list[str]) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "decision": {
                "type": "clarification_needed",
                "missing_fields": missing_fields,
                "question": "Укажите недостающие поля заявки перед продолжением анализа.",
                "confidence": 0.95,
            },
            "operator_message": "Запросите у заявителя недостающие поля.",
            "internal_reasoning_summary": "В заявке отсутствуют обязательные входные поля.",
            "citations": [],
            "proposed_actions": [],
        }

    @staticmethod
    def _escalation_decision(ticket: dict[str, Any]) -> dict[str, Any]:
        service = ticket.get("service") or "неизвестный сервис"
        return {
            "schema_version": "1.0",
            "decision": {
                "type": "escalation_needed",
                "summary": f"{service}: требуется проверка специалистом.",
                "reason": "Детерминированная политика этапа 3 выбрала эскалацию для этого сценария.",
                "target_team": "configured-escalation-channel",
                "confidence": 0.81,
            },
            "operator_message": "Эскалируйте заявку в настроенный канал с подготовленным описанием.",
            "internal_reasoning_summary": "Сценарий требует эскалации, а не локального решения.",
            "citations": [],
            "proposed_actions": [],
        }

    @staticmethod
    def _runbook_decision(ticket: dict[str, Any]) -> dict[str, Any]:
        service = ticket.get("service") or "billing-worker"
        return {
            "schema_version": "1.0",
            "decision": {
                "type": "action_proposed",
                "summary": f"Запустить ранбук System Center для перезапуска {service}.",
                "confidence": 0.83,
            },
            "operator_message": "Проверьте предложенный ранбук перед выполнением.",
            "internal_reasoning_summary": "Детерминированное правило этапа 3 выбрало предложение ранбука.",
            "citations": [],
            "proposed_actions": [
                {
                    "tool_name": "start_systemcenter_runbook",
                    "action_id": f"restart_{service}".replace("-", "_"),
                    "action_type": "action",
                    "parameters": {
                        "runbook_code": "restart_service",
                        "app_name": service,
                    },
                    "reason": "Заявка соответствует сценарию перезапуска через ранбук.",
                    "risk_level": "medium",
                    "expected_effect": f"Для {service} будет запущена настроенная операция восстановления.",
                    "requires_state_change": True,
                    "risk_notes": "Политика MVP требует согласования оператора перед выполнением.",
                    "extensions": {
                        "endpoint_id": "n8n",
                        "operation_id": "start_systemcenter_runbook",
                        "completion_policy": {
                            "mode": "external_event",
                            "max_wait_seconds": 3600,
                            "timeout_action": "escalate_operator",
                            "expected_event_type": "start_systemcenter_runbook_completed",
                            "result_transport": "kafka_event",
                            "result_topic": DEFAULT_EXTERNAL_EVENT_RESULT_TOPIC,
                        },
                    },
                }
            ],
        }

    def _dispatch_tool_node(
        self,
        case_id: str,
        ticket_id: str,
        actions: list[dict[str, Any]],
        policy_results: list[dict[str, Any]],
        gate_by_action_id: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        results = []
        gate_by_action_id = gate_by_action_id or {}
        policy_by_action_id = {
            result["action_id"]: result
            for result in policy_results
        }
        for action in actions:
            policy = policy_by_action_id[action["action_id"]]
            dispatch_result = self.dispatch_tool(
                action,
                policy,
                case_id=case_id,
                ticket_id=ticket_id,
                approved_by_operator=False,
            )
            tool_result = dispatch_result["tool_result"]
            gate_id = gate_by_action_id.get(action["action_id"])
            if gate_id:
                extensions = tool_result.setdefault("extensions", {})
                extensions["gate_id"] = gate_id
                self.contracts.require_valid("tool_result", tool_result)
            results.append(tool_result)
        return results

    def _completion_policy_for_invocation(
        self,
        action: dict[str, Any],
        invocation: dict[str, Any],
        *,
        preferred_launch: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        extensions = action.get("extensions") or {}
        completion_policy = extensions.get("completion_policy")
        if isinstance(completion_policy, dict):
            return copy.deepcopy(completion_policy)
        if preferred_launch:
            return copy.deepcopy(preferred_launch.get("completion_policy") or {"mode": "sync"})
        return {"mode": "sync", "max_wait_seconds": 0, "timeout_action": "resume_agent"}

    def _preferred_launch_for_action(self, action: dict[str, Any]) -> dict[str, Any] | None:
        extensions = action.get("extensions") or {}
        endpoint_id = extensions.get("endpoint_id")
        operation_id = extensions.get("operation_id")
        completion_policy = extensions.get("completion_policy")
        if endpoint_id or operation_id or isinstance(completion_policy, dict):
            launch = {
                "tool_name": action["tool_name"],
                "endpoint_id": endpoint_id,
                "operation_id": operation_id,
                "completion_policy": copy.deepcopy(completion_policy or {"mode": "sync"}),
            }
            return {key: value for key, value in launch.items() if value not in (None, "", {}, [])}
        return None

    def _should_enqueue_async_tool(self, invocation: dict[str, Any], completion_policy: dict[str, Any]) -> bool:
        return (
            invocation.get("adapter_type") == "n8n_webhook"
            and completion_policy.get("mode") == "external_event"
            and bool(completion_policy.get("expected_event_type"))
            and self.processing_store is not None
        )

    def _external_event_contract_snapshot(
        self,
        invocation: dict[str, Any],
        completion_policy: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not self.config_store:
            return None
        endpoint_id = invocation.get("endpoint_id")
        operation_id = invocation.get("operation_id")
        event_type = completion_policy.get("expected_event_type")
        if not endpoint_id or not operation_id or not event_type:
            return None
        return self.config_store.external_event_contract_snapshot(
            endpoint_id=endpoint_id,
            operation_id=operation_id,
            event_type=event_type,
        )

    def _async_tool_queued_result(
        self,
        invocation: dict[str, Any],
        queued: dict[str, Any],
        completion_policy: dict[str, Any],
    ) -> dict[str, Any]:
        wait = queued["wait"]
        command = queued["command"]
        result = IntegrationDispatcher._base_result(
            invocation,
            "success",
            output={
                "runbook_status": "queued",
                "message": "Асинхронный ReAct-вызов поставлен в очередь выполнения.",
            },
            extensions={
                "mock": False,
                "async_wait": {
                    "wait_id": wait["wait_id"],
                    "run_id": wait["run_id"],
                    "correlation_id": wait["correlation_id"],
                    "event_type": command["expected_event_type"],
                    "callback_url": command["callback_url"],
                    "command_id": command["command_id"],
                    "topic": command["topic"],
                    "completion_policy": copy.deepcopy(completion_policy),
                },
            },
        )
        binding = self.tool_registry.resolve(invocation["tool_name"])
        result = IntegrationDispatcher._with_trace(result, invocation, binding)
        self.contracts.require_valid("tool_result", result)
        self.tool_registry.validate_result(result)
        return result

    @staticmethod
    def _build_tool_trace(tool_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        trace = []
        for result in tool_results:
            trace.append(
                {
                    "invocation_id": result["invocation_id"],
                    "action_id": result["action_id"],
                    "tool_name": result["tool_name"],
                    "endpoint_id": result["endpoint_id"],
                    "adapter_type": result["adapter_type"],
                    "operation_id": result["operation_id"],
                    "status": result["status"],
                    "policy_rule_id": result["policy_rule_id"],
                    "duration_ms": result["duration_ms"],
                    "attempts": result["attempts"],
                    "error_code": result.get("error", {}).get("code"),
                    "gate_id": result.get("extensions", {}).get("gate_id"),
                    "mock": result.get("extensions", {}).get("mock", False),
                }
            )
        return trace

    def _create_action_gates(
        self,
        case_id: str,
        ticket_id: str,
        actions: list[dict[str, Any]],
        policy_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        requests = []
        policy_by_action_id = {
            result["action_id"]: result
            for result in policy_results
        }
        for action in actions:
            policy_result = policy_by_action_id[action["action_id"]]
            gate_type = self._gate_type_for_policy(policy_result)
            if gate_type is None:
                continue
            record = self._build_action_gate_record(
                ticket_id,
                case_id,
                action,
                policy_result,
                gate_type,
            )
            self.action_gate_store.create(record)
            requests.append(self._approval_request_from_record(record))
        return requests

    def _build_action_gate_record(
        self,
        ticket_id: str,
        case_id: str,
        action: dict[str, Any],
        policy_result: dict[str, Any],
        gate_type: str,
    ) -> dict[str, Any]:
        now = utc_now()
        status = "pending" if gate_type == "operator_approval" else "approved"
        record = {
            "schema_version": "1.0",
            "gate_id": new_gate_id(),
            "ticket_id": ticket_id,
            "action_id": action["action_id"],
            "tool_name": action["tool_name"],
            "gate_type": gate_type,
            "status": status,
            "action": action,
            "policy_result": policy_result,
            "created_at": now,
            "updated_at": now,
            "audit": [
                {
                    "event": "gate_created",
                    "actor_type": "system",
                    "actor_id": "workflow",
                    "created_at": now,
                    "message": "Шлюз действия создан на основе политики выполнения.",
                }
            ],
            "extensions": {
                "case_id": case_id,
            },
        }
        if gate_type == "auto_policy":
            record["decision"] = {
                "decision": "approved",
                "actor_type": "system_policy",
                "actor_id": policy_result["policy_rule_id"],
                "decided_at": now,
                "comment": "Автоисполнение разрешено политикой выполнения.",
            }
            record["audit"].append(
                {
                    "event": "auto_policy_approved",
                    "actor_type": "system_policy",
                    "actor_id": policy_result["policy_rule_id"],
                    "created_at": now,
                    "message": "Действие согласовано политикой выполнения.",
                }
            )
        self.contracts.require_valid("action_gate_record", record)
        return record

    @staticmethod
    def _gate_type_for_policy(policy_result: dict[str, Any]) -> str | None:
        if policy_result["execution_mode"] == "operator_approval":
            return "operator_approval"
        if policy_result["execution_mode"] == "auto_execute":
            return "auto_policy"
        return None

    @staticmethod
    def _approval_request_from_record(record: dict[str, Any]) -> dict[str, Any]:
        action = record["action"]
        policy_result = record["policy_result"]
        request = {
            "approval_id": record["gate_id"],
            "gate_id": record["gate_id"],
            "gate_type": record["gate_type"],
            "status": record["status"],
            "ticket_id": record["ticket_id"],
            "action_id": record["action_id"],
            "tool_name": record["tool_name"],
            "parameters": action["parameters"],
            "reason": action["reason"],
            "expected_effect": action["expected_effect"],
            "risk_level": action["risk_level"],
            "risk_notes": action.get("risk_notes"),
            "policy_rule_id": policy_result["policy_rule_id"],
            "policy_reason": policy_result["reason"],
            "created_at": record["created_at"],
        }
        if record.get("extensions", {}).get("case_id"):
            request["case_id"] = record["extensions"]["case_id"]
        return request

    def _reject_action_gate(
        self,
        record: dict[str, Any],
        decision_request: dict[str, Any],
    ) -> dict[str, Any]:
        now = utc_now()
        record["status"] = "rejected"
        record["decision"] = {
            "decision": "rejected",
            "actor_type": "operator",
            "actor_id": decision_request["operator_id"],
            "decided_at": now,
        }
        if decision_request.get("comment"):
            record["decision"]["comment"] = decision_request["comment"]
        record["updated_at"] = now
        record["audit"].append(
            {
                "event": "operator_rejected",
                "actor_type": "operator",
                "actor_id": decision_request["operator_id"],
                "created_at": now,
                "message": decision_request.get("comment")
                or "Оператор отклонил предложенное действие.",
            }
        )
        record = self.action_gate_store.save_if_status(record, "pending")
        workflow_state = self.state_resolver.resolve({"approval_decision": "rejected"})
        result = {
            "schema_version": "1.0",
            "accepted": True,
            "gate": record,
            "workflow_state": workflow_state,
        }
        self.contracts.require_valid("action_gate_result", result)
        self.case_store.record_approval_result(result)
        return result

    def _approve_action_gate(
        self,
        record: dict[str, Any],
        decision_request: dict[str, Any],
    ) -> dict[str, Any]:
        now = utc_now()
        record["status"] = "executing"
        record["decision"] = {
            "decision": "approved",
            "actor_type": "operator",
            "actor_id": decision_request["operator_id"],
            "decided_at": now,
        }
        if decision_request.get("comment"):
            record["decision"]["comment"] = decision_request["comment"]
        record["updated_at"] = now
        record["audit"].append(
            {
                "event": "operator_approved",
                "actor_type": "operator",
                "actor_id": decision_request["operator_id"],
                "created_at": now,
                "message": decision_request.get("comment")
                or "Оператор согласовал предложенное действие.",
            }
        )
        self.action_gate_store.save_if_status(record, "pending")

        dispatch_result = self.dispatch_tool(
            record["action"],
            record["policy_result"],
            case_id=record.get("extensions", {}).get("case_id"),
            ticket_id=record["ticket_id"],
            approved_by_operator=True,
            operator_id=decision_request["operator_id"],
        )
        tool_result = dispatch_result["tool_result"]
        now = utc_now()
        record["status"] = self._gate_status_from_tool_status(tool_result["status"])
        record["tool_result"] = tool_result
        record["updated_at"] = now
        record["audit"].append(
            {
                "event": "tool_dispatched",
                "actor_type": "system",
                "actor_id": "integration_dispatcher",
                "created_at": now,
                "message": f"Диспетчер вернул статус инструмента {tool_result['status']}.",
            }
        )
        record = self.action_gate_store.save_if_status(record, "executing")
        workflow_state = self.state_resolver.resolve({"tool_status": tool_result["status"]})
        result = {
            "schema_version": "1.0",
            "accepted": True,
            "gate": record,
            "workflow_state": workflow_state,
            "tool_result": tool_result,
        }
        self.contracts.require_valid("action_gate_result", result)
        self.case_store.record_approval_result(result)
        return result

    @staticmethod
    def _gate_status_from_tool_status(tool_status: str) -> str:
        if tool_status in {"success", "dry_run_completed"}:
            return "succeeded"
        if tool_status == "blocked":
            return "blocked"
        return "failed"

    @staticmethod
    def _tool_result_from_callback(callback: dict[str, Any]) -> dict[str, Any]:
        result = {
            "schema_version": "1.0",
            "invocation_id": callback["invocation_id"],
            "action_id": callback["action_id"],
            "tool_name": callback["tool_name"],
            "endpoint_id": callback["endpoint_id"],
            "adapter_type": callback["adapter_type"],
            "operation_id": callback["operation_id"],
            "status": callback["status"],
            "policy_rule_id": callback["policy_rule_id"],
            "duration_ms": callback.get("duration_ms", 0),
            "attempts": callback.get("attempts", 0),
        }
        for optional_key in ("output", "error", "extensions"):
            if optional_key in callback:
                result[optional_key] = copy.deepcopy(callback[optional_key])
        return result
