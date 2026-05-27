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
from .contracts import CONTRACTS_ROOT, ContractRegistry, load_json
from .feedback import FeedbackStore
from .integrations import IntegrationDispatcher, ToolRegistry
from .knowledge import KnowledgeIndexer, KnowledgeRetriever


REQUIRED_TICKET_FIELDS = ("user", "service", "environment", "description", "priority")
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
    ):
        self.contracts = contracts or ContractRegistry()
        self.policy = ExecutionPolicy(self.contracts)
        self.state_resolver = WorkflowStateResolver(self.contracts)
        self.tool_registry = ToolRegistry(self.contracts)
        self.integration_dispatcher = IntegrationDispatcher(
            self.contracts,
            self.tool_registry,
        )
        self.action_gate_store = action_gate_store or ActionGateStore(self.contracts)
        self.knowledge_indexer = knowledge_indexer or KnowledgeIndexer(self.contracts)
        self.knowledge_retriever = knowledge_retriever or KnowledgeRetriever(self.contracts)
        self.feedback_store = feedback_store or FeedbackStore(self.contracts)
        self.case_store = case_store or CaseStore(self.contracts)

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
        invocation = self.tool_registry.build_invocation(
            action,
            policy_result,
            case_id=case_id,
            ticket_id=ticket_id,
            approved_by_operator=approved_by_operator,
            operator_id=operator_id,
        )
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

    def submit_feedback(self, request: dict[str, Any]) -> dict[str, Any]:
        feedback = self.feedback_store.create(request)
        self.case_store.record_feedback(feedback)
        return feedback

    def list_ticket_feedback(self, ticket_id: str) -> list[dict[str, Any]]:
        return self.feedback_store.list_by_ticket(ticket_id)

    def export_feedback_jsonl(self) -> str:
        return self.feedback_store.export_jsonl()

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
        environment = str(ticket.get("environment") or "").lower()

        if any(token in description for token in ["runbook", "restart", "перезапуск"]):
            return self._runbook_decision(ticket)
        if (
            any(token in description for token in ["escalat", "эскала", "l2"])
            or priority in {"p1", "critical", "критический"}
            or ("prod" in environment and "down" in description)
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
                "summary": f"{service}: требуется проверка L2.",
                "reason": "Детерминированная политика этапа 3 выбрала эскалацию для этого сценария.",
                "target_team": "L2-platform",
                "confidence": 0.81,
            },
            "operator_message": "Эскалируйте заявку в L2-platform с подготовленным описанием.",
            "internal_reasoning_summary": "Сценарий требует эскалации, а не локального решения.",
            "citations": [],
            "proposed_actions": [],
        }

    @staticmethod
    def _runbook_decision(ticket: dict[str, Any]) -> dict[str, Any]:
        service = ticket.get("service") or "billing-worker"
        environment = ticket.get("environment") or "test"
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
                    "action_id": f"restart_{service}_{environment}".replace("-", "_"),
                    "action_type": "action",
                    "parameters": {
                        "runbook_name": "Restart-Service",
                        "service_name": service,
                        "environment": environment,
                    },
                    "reason": "Заявка соответствует сценарию перезапуска через ранбук.",
                    "risk_level": "medium",
                    "expected_effect": f"{service} будет перезапущен в среде {environment}.",
                    "requires_state_change": True,
                    "risk_notes": "Политика MVP требует согласования оператора перед выполнением.",
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
