from __future__ import annotations

import copy
import json
import os
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, SchemaError

from .action_gates import DEFAULT_STATE_DB_PATH, utc_now
from .contracts import CONTRACTS_ROOT, ContractRegistry, ContractValidationError, load_json


class ConfigRegistryError(ValueError):
    pass


class ConfigDraftNotFound(KeyError):
    pass


class ConfigVersionNotFound(KeyError):
    pass


LEGACY_SLOT_SOURCE_METHODS = {
    "user_question": "user_question",
    "case": "case",
    "llm": "llm_extraction",
}

SECRET_PLACEHOLDER_PREFIXES = (
    "replace_",
    "replace-with-",
    "replace with ",
    "changeme",
    "change_me",
    "todo",
    "example",
)


def slot_fill_method(slot: dict[str, Any]) -> str:
    if slot.get("fill_method"):
        return slot["fill_method"]
    return LEGACY_SLOT_SOURCE_METHODS.get(slot.get("source"), "resolution_profile")


def next_slot_question(
    slot: dict[str, Any],
    profile_by_id: dict[str, dict[str, Any]],
) -> str | None:
    if slot_fill_method(slot) == "resolution_profile":
        profile = profile_by_id.get(slot.get("resolution_profile_id", ""))
        if profile:
            return resolution_profile_question(profile) or slot.get("question")
    if slot.get("question"):
        return slot["question"]
    return None


def resolution_profile_question(profile: dict[str, Any]) -> str | None:
    ambiguity_policy = profile.get("ambiguity_policy", {})
    if ambiguity_policy.get("question"):
        return ambiguity_policy["question"]
    clarification = next(
        (
            step
            for step in profile.get("steps", [])
            if step["type"] == "clarification"
            and step.get("clarification_question")
        ),
        None,
    )
    if clarification:
        return clarification["clarification_question"]
    return profile.get("fallback", {}).get("question")


def resolution_profile_current_step(profile: dict[str, Any]) -> dict[str, Any] | None:
    for step in profile.get("steps", []):
        if step["type"] in {"clarification", "operator_handoff", "escalate"}:
            return step
    return profile.get("steps", [None])[-1]


def root_attribute(attribute_ref: str | None) -> str | None:
    if not attribute_ref:
        return None
    return attribute_ref.split(".", 1)[0]


def secret_env_configured(env_name: str | None) -> bool:
    if not env_name:
        return False
    value = os.getenv(env_name, "").strip()
    if not value:
        return False
    lowered = value.lower()
    return not lowered.startswith(SECRET_PLACEHOLDER_PREFIXES)


def new_draft_id() -> str:
    return f"cfgdraft-{uuid.uuid4().hex[:12]}"


def new_version_id() -> str:
    return f"cfgver-{uuid.uuid4().hex[:12]}"


@dataclass(frozen=True)
class ConfigDomain:
    domain: str
    title: str
    contract_name: str
    read_permission: str
    manage_permission: str


CONFIG_DOMAINS: dict[str, ConfigDomain] = {
    "service_scenarios": ConfigDomain(
        domain="service_scenarios",
        title="Сценарии обращений",
        contract_name="service_scenarios",
        read_permission="workflow.read",
        manage_permission="workflow.manage",
    ),
    "slot_schemas": ConfigDomain(
        domain="slot_schemas",
        title="Схемы слотов",
        contract_name="slot_schemas",
        read_permission="workflow.read",
        manage_permission="workflow.manage",
    ),
    "classification_routes": ConfigDomain(
        domain="classification_routes",
        title="Классификация и маршруты",
        contract_name="classification_routes",
        read_permission="workflow.read",
        manage_permission="workflow.manage",
    ),
    "orchestrator_policy": ConfigDomain(
        domain="orchestrator_policy",
        title="Политики оркестратора",
        contract_name="orchestrator_policy",
        read_permission="workflow.read",
        manage_permission="workflow.manage",
    ),
    "tool_launch_matrix": ConfigDomain(
        domain="tool_launch_matrix",
        title="Матрица запуска инструментов",
        contract_name="tool_launch_matrix",
        read_permission="tools.read",
        manage_permission="tools.manage",
    ),
    "prompt_packs": ConfigDomain(
        domain="prompt_packs",
        title="Prompt packs",
        contract_name="prompt_packs",
        read_permission="prompts.read",
        manage_permission="prompts.manage",
    ),
    "escalation_policies": ConfigDomain(
        domain="escalation_policies",
        title="Политики эскалации",
        contract_name="escalation_policies",
        read_permission="workflow.read",
        manage_permission="workflow.manage",
    ),
    "tools": ConfigDomain(
        domain="tools",
        title="Каталог инструментов",
        contract_name="tool_catalog",
        read_permission="tools.read",
        manage_permission="tools.manage",
    ),
    "integration_endpoints": ConfigDomain(
        domain="integration_endpoints",
        title="Каталог точек интеграции",
        contract_name="integration_endpoint_catalog",
        read_permission="tools.read",
        manage_permission="tools.manage",
    ),
    "workflow_states": ConfigDomain(
        domain="workflow_states",
        title="Каталог состояний рабочего процесса",
        contract_name="workflow_state_catalog",
        read_permission="workflow.read",
        manage_permission="workflow.manage",
    ),
    "workflow_transitions": ConfigDomain(
        domain="workflow_transitions",
        title="Правила переходов рабочего процесса",
        contract_name="workflow_transition_rules",
        read_permission="workflow.read",
        manage_permission="workflow.manage",
    ),
    "prompts": ConfigDomain(
        domain="prompts",
        title="Каталог промптов",
        contract_name="prompt_catalog",
        read_permission="prompts.read",
        manage_permission="prompts.manage",
    ),
    "model_routing": ConfigDomain(
        domain="model_routing",
        title="Маршрутизация моделей",
        contract_name="model_routing",
        read_permission="models.read",
        manage_permission="models.manage",
    ),
    "n8n_workflows": ConfigDomain(
        domain="n8n_workflows",
        title="Каталог workflow n8n",
        contract_name="n8n_workflow_catalog",
        read_permission="tools.read",
        manage_permission="tools.manage",
    ),
    "attribute_resolution_profiles": ConfigDomain(
        domain="attribute_resolution_profiles",
        title="Профили разрешения атрибутов",
        contract_name="attribute_resolution_profiles",
        read_permission="workflow.read",
        manage_permission="workflow.manage",
    ),
}


class ConfigStore:
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

    def domains(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "domains": [
                {
                    "domain": domain.domain,
                    "title": domain.title,
                    "contract_name": domain.contract_name,
                    "read_permission": domain.read_permission,
                    "manage_permission": domain.manage_permission,
                    "active_version_id": self.active_version_id(domain.domain),
                }
                for domain in CONFIG_DOMAINS.values()
            ],
        }

    def default_config(self, domain: str) -> dict[str, Any]:
        self._require_domain(domain)
        if domain == "tools":
            return copy.deepcopy(self.contracts.tool_catalog)
        if domain == "integration_endpoints":
            return copy.deepcopy(self.contracts.integration_endpoint_catalog)
        if domain == "workflow_states":
            return copy.deepcopy(self.contracts.workflow_state_catalog)
        if domain == "workflow_transitions":
            return copy.deepcopy(self.contracts.workflow_transition_rules)
        if domain == "prompts":
            return default_prompt_catalog()
        if domain == "model_routing":
            return default_model_routing()
        if domain == "n8n_workflows":
            return load_json(CONTRACTS_ROOT / "config" / "n8n-workflow-catalog.json")
        if domain == "attribute_resolution_profiles":
            return default_attribute_resolution_profiles()
        if domain == "service_scenarios":
            return default_service_scenarios()
        if domain == "slot_schemas":
            return default_slot_schemas()
        if domain == "classification_routes":
            return default_classification_routes()
        if domain == "orchestrator_policy":
            return default_orchestrator_policy()
        if domain == "tool_launch_matrix":
            return default_tool_launch_matrix()
        if domain == "prompt_packs":
            return default_prompt_packs()
        if domain == "escalation_policies":
            return default_escalation_policies()
        raise ConfigRegistryError(f"Неизвестный домен конфигурации: {domain}")

    def active_config(self, domain: str) -> dict[str, Any]:
        self._require_domain(domain)
        active_version = self.active_version(domain)
        if active_version:
            return {
                "schema_version": "1.0",
                "domain": domain,
                "source": "active_version",
                "active_version_id": active_version["version_id"],
                "payload": self._normalize_payload(domain, active_version["payload"]),
                "version": active_version,
            }
        return {
            "schema_version": "1.0",
            "domain": domain,
            "source": "default",
            "active_version_id": None,
            "payload": self._normalize_payload(domain, self.default_config(domain)),
        }

    def active_payload(self, domain: str) -> dict[str, Any]:
        return self.active_config(domain)["payload"]

    def _normalize_payload(self, domain: str, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = copy.deepcopy(payload)
        scenario_names = {
            item["scenario_id"]: item["display_name"]
            for item in DEFAULT_SCENARIOS
        }
        if domain == "service_scenarios":
            for scenario in normalized.get("scenarios", []):
                scenario.setdefault("tool_launch_matrix_id", f"matrix.{scenario['scenario_id']}")
        elif domain == "attribute_resolution_profiles":
            for profile in normalized.get("profiles", []):
                profile.pop("allowed_scenarios", None)
        elif domain == "slot_schemas":
            for slot_schema in normalized.get("slot_schemas", []):
                slot_schema.pop("scenario_id", None)
        elif domain == "classification_routes":
            for route in normalized.get("routes", []):
                scenario_id = route.pop("scenario_id", None)
                route.setdefault("display_name", f"Маршрут: {scenario_names.get(scenario_id or '', route['route_id'])}")
        elif domain == "orchestrator_policy":
            for policy in normalized.get("policies", []):
                scenario_id = policy.pop("scenario_id", None)
                policy.setdefault("display_name", f"ReAct-политика: {scenario_names.get(scenario_id or '', policy['policy_id'])}")
        elif domain == "tool_launch_matrix" and "launches" in normalized:
            grouped_launches: dict[str, list[dict[str, Any]]] = {}
            for launch in normalized.get("launches", []):
                launch_copy = copy.deepcopy(launch)
                scenario_id = launch_copy.pop("scenario_id", "custom")
                grouped_launches.setdefault(scenario_id, []).append(launch_copy)
            normalized = {
                "schema_version": normalized.get("schema_version", "1.0"),
                "matrices": [
                    {
                        "matrix_id": f"matrix.{scenario_id}",
                        "display_name": f"Матрица инструментов: {scenario_names.get(scenario_id, scenario_id)}",
                        "launches": launches,
                    }
                    for scenario_id, launches in grouped_launches.items()
                ],
            }
        elif domain == "tool_launch_matrix":
            for matrix in normalized.get("matrices", []):
                matrix.setdefault("display_name", f"Матрица инструментов: {matrix['matrix_id']}")
                for launch in matrix.get("launches", []):
                    launch.pop("scenario_id", None)
        elif domain == "escalation_policies":
            for policy in normalized.get("policies", []):
                scenario_id = policy.pop("scenario_id", None)
                policy.setdefault("display_name", f"Решение и эскалация: {scenario_names.get(scenario_id or '', policy['policy_id'])}")
        elif domain == "model_routing":
            providers = normalized.get("providers", {})
            provider_key_configured = {
                provider_id: secret_env_configured(provider.get("api_key_env"))
                for provider_id, provider in providers.items()
                if provider.get("api_key_env")
            }
            openai_provider = providers.get("openai", {})
            openai_key_env = openai_provider.get("api_key_env") or os.getenv("OPENAI_API_KEY_ENV", "OPENAI_API_KEY")
            runtime = normalized.setdefault("runtime", {})
            runtime["active_backend"] = normalized.get("active_provider")
            runtime["openai_api_key_configured"] = secret_env_configured(openai_key_env)
            runtime["provider_key_configured"] = provider_key_configured
        return normalized

    def scenario_overview(self) -> dict[str, Any]:
        scenarios = []
        for scenario in self._scenario_by_id().values():
            detail = self.scenario_detail(scenario["scenario_id"])
            scenarios.append(
                {
                    "scenario_id": scenario["scenario_id"],
                    "display_name": scenario["display_name"],
                    "status": scenario["status"],
                    "route": detail["route"]["route"],
                    "priority": detail["route"]["priority"],
                    "tool_launch_count": len(detail["tool_launches"]),
                    "prompt_pack_id": detail["prompt_pack"]["prompt_pack_id"],
                    "readiness": detail["readiness"],
                }
            )
        return {
            "schema_version": "1.0",
            "scenario_count": len(scenarios),
            "scenarios": scenarios,
        }

    def scenario_detail(self, scenario_id: str) -> dict[str, Any]:
        scenario = self._scenario_by_id().get(scenario_id)
        if not scenario:
            raise ConfigRegistryError(f"Сценарий не найден: {scenario_id}")
        slot_schema = self._by_id(
            self.active_payload("slot_schemas")["slot_schemas"],
            "slot_schema_id",
        ).get(scenario["slot_schema_id"])
        route = self._by_id(
            self.active_payload("classification_routes")["routes"],
            "route_id",
        ).get(scenario["classification_route_id"])
        policy = self._by_id(
            self.active_payload("orchestrator_policy")["policies"],
            "policy_id",
        ).get(scenario["orchestrator_policy_id"])
        prompt_pack = self._by_id(
            self.active_payload("prompt_packs")["packs"],
            "prompt_pack_id",
        ).get(scenario["prompt_pack_id"])
        escalation_policy = self._by_id(
            self.active_payload("escalation_policies")["policies"],
            "policy_id",
        ).get(scenario["escalation_policy_id"])
        tool_launch_matrix = self._by_id(
            self.active_payload("tool_launch_matrix")["matrices"],
            "matrix_id",
        ).get(scenario["tool_launch_matrix_id"])
        profile_by_id = self._by_id(
            self.active_payload("attribute_resolution_profiles")["profiles"],
            "profile_id",
        )
        resolution_profile_ids = []
        if slot_schema:
            resolution_profile_ids = [
                slot["resolution_profile_id"]
                for slot in slot_schema["slots"]
                if slot_fill_method(slot) == "resolution_profile"
                and slot.get("resolution_profile_id")
            ]
        scenario_profiles = [
            profile_by_id[profile_id]
            for profile_id in dict.fromkeys(resolution_profile_ids)
            if profile_id in profile_by_id
        ]
        launches = tool_launch_matrix["launches"] if tool_launch_matrix else []
        missing = []
        for label, value in (
            ("slot_schema", slot_schema),
            ("route", route),
            ("orchestrator_policy", policy),
            ("tool_launch_matrix", tool_launch_matrix),
            ("prompt_pack", prompt_pack),
            ("escalation_policy", escalation_policy),
        ):
            if value is None:
                missing.append(label)
        if slot_schema:
            for slot in slot_schema["slots"]:
                if slot_fill_method(slot) == "resolution_profile":
                    profile_id = slot.get("resolution_profile_id")
                    profile = profile_by_id.get(profile_id or "")
                    if not profile:
                        missing.append(f"attribute_resolution_profile:{slot['slot_id']}")
        return {
            "schema_version": "1.0",
            "scenario": scenario,
            "slot_schema": slot_schema,
            "attribute_resolution_profiles": scenario_profiles,
            "route": route,
            "orchestrator_policy": policy,
            "tool_launch_matrix": tool_launch_matrix,
            "tool_launches": launches,
            "prompt_pack": prompt_pack,
            "prompt_preview": build_prompt_preview(prompt_pack) if prompt_pack else "",
            "escalation_policy": escalation_policy,
            "readiness": {
                "status": "ready" if not missing else "incomplete",
                "missing": missing,
            },
        }

    def simulate_scenario(
        self,
        scenario_id: str,
        *,
        text: str,
        provided_slots: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        detail = self.scenario_detail(scenario_id)
        slot_schema = detail["slot_schema"] or {"slots": [], "question_order": []}
        profile_by_id = self._by_id(
            detail.get("attribute_resolution_profiles", []),
            "profile_id",
        )
        provided = provided_slots or {}
        slot_values = {}
        missing_slots = []
        resolution_steps = []
        resolution_state = {}
        seen_resolution_profile_ids = set()
        for slot in slot_schema["slots"]:
            slot_id = slot["slot_id"]
            fill_method = slot_fill_method(slot)
            if slot_id in provided:
                slot_values[slot_id] = {
                    "status": "provided",
                    "value": provided[slot_id],
                    "fill_method": "operator_input",
                }
            elif fill_method == "resolution_profile":
                profile = profile_by_id.get(slot.get("resolution_profile_id", ""))
                slot_values[slot_id] = {
                    "status": "resolution_pending",
                    "value": None,
                    "fill_method": fill_method,
                    "resolution_profile_id": slot.get("resolution_profile_id"),
                }
                if profile and profile["profile_id"] not in seen_resolution_profile_ids:
                    seen_resolution_profile_ids.add(profile["profile_id"])
                    current_step = resolution_profile_current_step(profile)
                    current_step_id = current_step["step_id"] if current_step else None
                    completed_steps = []
                    for step in profile["steps"]:
                        if step["step_id"] == current_step_id:
                            break
                        completed_steps.append(
                            {
                                "step_id": step["step_id"],
                                "type": step["type"],
                                "display_name": step["display_name"],
                                "status": "dry_run_simulated",
                            }
                        )
                    question = resolution_profile_question(profile)
                    state_status = "question_required" if question else "resolution_pending"
                    state_summary = {
                        "slot_id": slot_id,
                        "profile_id": profile["profile_id"],
                        "profile_name": profile["display_name"],
                        "status": state_status,
                        "attempt": 1,
                        "max_attempts": profile["max_attempts"],
                        "current_step_id": current_step_id,
                        "current_step_name": current_step["display_name"] if current_step else None,
                        "pending_question": question,
                        "completed_steps": completed_steps,
                        "intermediate_attributes": profile.get("intermediate_attributes", []),
                        "operator_handoff_package": profile.get("operator_handoff_package", []),
                        "ambiguity_policy": profile.get("ambiguity_policy"),
                        "reason": "dry-run не вызывает внешние системы и показывает следующий управляемый шаг разрешения слота.",
                    }
                    if profile.get("ambiguity_policy", {}).get("candidate_count_attribute"):
                        state_summary["candidate_summary"] = {
                            "source_attribute": profile["ambiguity_policy"]["candidate_count_attribute"],
                            "status": "not_executed_in_dry_run",
                        }
                    resolution_state[slot_id] = state_summary
                    resolution_steps.append(
                        {
                            "slot_id": slot_id,
                            "profile_id": profile["profile_id"],
                            "profile_name": profile["display_name"],
                            "status": state_status,
                            "current_step_id": current_step_id,
                            "current_step_name": current_step["display_name"] if current_step else None,
                            "pending_question": question,
                            "attempt": 1,
                            "max_attempts": profile["max_attempts"],
                            "completed_steps": completed_steps,
                            "intermediate_attributes": profile.get("intermediate_attributes", []),
                            "operator_handoff_package": profile.get("operator_handoff_package", []),
                            "ambiguity_policy": profile.get("ambiguity_policy"),
                            "steps": [
                                {
                                    "step_id": step["step_id"],
                                    "type": step["type"],
                                    "display_name": step["display_name"],
                                    "on_success_step": step.get("on_success_step"),
                                    "on_failure_step": step.get("on_failure_step"),
                                    "on_ambiguous_step": step.get("on_ambiguous_step"),
                                }
                                for step in profile["steps"]
                            ],
                            "fallback": profile["fallback"],
                        }
                    )
                if slot["required"]:
                    missing_slots.append(slot_id)
            elif fill_method in {"case", "llm_extraction"}:
                slot_values[slot_id] = {
                    "status": "auto_fill_candidate",
                    "value": None,
                    "fill_method": fill_method,
                }
                if slot["required"]:
                    missing_slots.append(slot_id)
            elif slot["required"]:
                slot_values[slot_id] = {
                    "status": "missing",
                    "value": None,
                    "fill_method": fill_method,
                }
                missing_slots.append(slot_id)
        route = detail["route"]
        keywords = route.get("rules", {}).get("keywords", []) if route else []
        lowered_text = text.lower()
        keyword_hits = [
            keyword
            for keyword in keywords
            if keyword.lower() in lowered_text
        ]
        confidence = 0.92 if keyword_hits else 0.68
        next_question = None
        for slot_id in slot_schema.get("question_order", []):
            if slot_id in missing_slots:
                slot = next(
                    item
                    for item in slot_schema["slots"]
                    if item["slot_id"] == slot_id
                )
                next_question = next_slot_question(slot, profile_by_id)
                break
        ready_launches = []
        blocked_launches = []
        for launch in detail["tool_launches"]:
            missing_for_launch = [
                slot_id
                for slot_id in launch["required_slots"]
                if slot_id in missing_slots
            ]
            launch_summary = {
                "launch_id": launch["launch_id"],
                "tool_name": launch["tool_name"],
                "execution_level": launch["execution_level"],
                "target_execution_level": launch["target_execution_level"],
                "missing_slots": missing_for_launch,
            }
            if missing_for_launch:
                blocked_launches.append(launch_summary)
            else:
                ready_launches.append(launch_summary)
        return {
            "schema_version": "1.0",
            "scenario_id": scenario_id,
            "input_text": text,
            "slot_values": slot_values,
            "missing_slots": missing_slots,
            "next_question": next_question,
            "attribute_resolution": resolution_steps,
            "resolution_state": resolution_state,
            "classification": {
                "route_id": route["route_id"] if route else None,
                "route": route["route"] if route else None,
                "priority": route["priority"] if route else None,
                "confidence": confidence,
                "keyword_hits": keyword_hits,
            },
            "ready_tool_launches": ready_launches,
            "blocked_tool_launches": blocked_launches,
            "final_decision": "continue_slot_filling" if missing_slots else "ready_for_react",
            "dry_run": True,
        }

    def create_draft(
        self,
        *,
        domain: str,
        payload: dict[str, Any],
        created_by: str,
        base_version_id: str | None = None,
    ) -> dict[str, Any]:
        self._require_domain(domain)
        now = utc_now()
        draft = {
            "schema_version": "1.0",
            "draft_id": new_draft_id(),
            "domain": domain,
            "payload": copy.deepcopy(payload),
            "status": "draft",
            "created_by": created_by,
            "created_at": now,
            "updated_at": now,
        }
        if base_version_id:
            draft["base_version_id"] = base_version_id
        self.contracts.require_valid("config_draft", draft)
        with self._connect() as connection:
            connection.execute(
                """
                insert into config_drafts (
                    draft_id,
                    domain,
                    status,
                    draft_json,
                    created_by,
                    created_at,
                    updated_at
                )
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft["draft_id"],
                    draft["domain"],
                    draft["status"],
                    self._to_json(draft),
                    draft["created_by"],
                    draft["created_at"],
                    draft["updated_at"],
                ),
            )
        return draft

    def validate_draft(self, draft_id: str) -> dict[str, Any]:
        draft = self.require_draft(draft_id)
        validation = self.validate_payload(draft["domain"], draft["payload"])
        draft["validation"] = validation
        draft["status"] = "valid" if validation["status"] == "valid" else "invalid"
        draft["updated_at"] = utc_now()
        return self._save_draft(draft)

    def save_regression(self, draft_id: str, regression: dict[str, Any]) -> dict[str, Any]:
        draft = self.require_draft(draft_id)
        draft["regression"] = regression
        if regression["status"] in {"passed", "skipped"} and draft.get("validation", {}).get("status") == "valid":
            draft["status"] = "regression_passed"
        draft["updated_at"] = utc_now()
        return self._save_draft(draft)

    def activate_draft(self, draft_id: str, activated_by: str) -> dict[str, Any]:
        draft = self.require_draft(draft_id)
        validation = draft.get("validation")
        regression = draft.get("regression")
        if validation is None or validation.get("status") != "valid":
            raise ConfigRegistryError("Черновик должен пройти валидацию перед активацией.")
        if regression is None or regression.get("status") not in {"passed", "skipped"}:
            raise ConfigRegistryError("Черновик должен пройти регрессионную проверку перед активацией.")

        previous_version_id = self.active_version_id(draft["domain"])
        activated_at = utc_now()
        version = {
            "schema_version": "1.0",
            "version_id": new_version_id(),
            "domain": draft["domain"],
            "payload": copy.deepcopy(draft["payload"]),
            "source_draft_id": draft["draft_id"],
            "activated_by": activated_by,
            "activated_at": activated_at,
            "validation": validation,
            "regression": regression,
        }
        if previous_version_id:
            version["previous_version_id"] = previous_version_id
        self.contracts.require_valid("config_version", version)

        with self._connect() as connection:
            connection.execute(
                """
                insert into config_versions (
                    version_id,
                    domain,
                    version_json,
                    source_draft_id,
                    activated_by,
                    activated_at
                )
                values (?, ?, ?, ?, ?, ?)
                """,
                (
                    version["version_id"],
                    version["domain"],
                    self._to_json(version),
                    version["source_draft_id"],
                    version["activated_by"],
                    version["activated_at"],
                ),
            )
            connection.execute(
                """
                insert or replace into config_active (
                    domain,
                    version_id,
                    activated_at
                )
                values (?, ?, ?)
                """,
                (version["domain"], version["version_id"], activated_at),
            )

        draft["status"] = "activated"
        draft["updated_at"] = activated_at
        self._save_draft(draft)
        return version

    def rollback(self, *, domain: str, version_id: str, operator_id: str) -> dict[str, Any]:
        self._require_domain(domain)
        version = self.require_version(version_id)
        if version["domain"] != domain:
            raise ConfigRegistryError(
                f"Версия {version_id} относится к домену {version['domain']}, а не {domain}."
            )
        now = utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                insert or replace into config_active (
                    domain,
                    version_id,
                    activated_at
                )
                values (?, ?, ?)
                """,
                (domain, version_id, now),
            )
        return {
            "schema_version": "1.0",
            "domain": domain,
            "active_version_id": version_id,
            "rolled_back_by": operator_id,
            "rolled_back_at": now,
            "version": version,
        }

    def validate_payload(self, domain: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_domain(domain)
        errors: list[str] = []
        contract_name = CONFIG_DOMAINS[domain].contract_name
        errors.extend(self.contracts.validate(contract_name, payload))
        if not errors:
            errors.extend(self._cross_validate(domain, payload))
        return {
            "schema_version": "1.0",
            "domain": domain,
            "contract_name": contract_name,
            "status": "invalid" if errors else "valid",
            "validated_at": utc_now(),
            "errors": errors,
            "gates": [
                {
                    "gate_id": "json_schema",
                    "status": "failed" if errors else "passed",
                    "message": "Валидация по JSON Schema завершена.",
                }
            ],
        }

    def list_drafts(
        self,
        *,
        domain: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        where_sql = ""
        parameters: list[Any] = []
        if domain:
            self._require_domain(domain)
            where_sql = "where domain = ?"
            parameters.append(domain)
        parameters.append(min(max(limit, 0), 1000))
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                select draft_json
                from config_drafts
                {where_sql}
                order by updated_at desc, draft_id desc
                limit ?
                """,
                parameters,
            ).fetchall()
        return [self._draft_from_row(row) for row in rows]

    def get_draft(self, draft_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "select draft_json from config_drafts where draft_id = ?",
                (draft_id,),
            ).fetchone()
        return self._draft_from_row(row) if row else None

    def require_draft(self, draft_id: str) -> dict[str, Any]:
        draft = self.get_draft(draft_id)
        if draft is None:
            raise ConfigDraftNotFound(draft_id)
        return draft

    def list_versions(
        self,
        *,
        domain: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        where_sql = ""
        parameters: list[Any] = []
        if domain:
            self._require_domain(domain)
            where_sql = "where domain = ?"
            parameters.append(domain)
        parameters.append(min(max(limit, 0), 1000))
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                select version_json
                from config_versions
                {where_sql}
                order by activated_at desc, version_id desc
                limit ?
                """,
                parameters,
            ).fetchall()
        return [self._version_from_row(row) for row in rows]

    def get_version(self, version_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "select version_json from config_versions where version_id = ?",
                (version_id,),
            ).fetchone()
        return self._version_from_row(row) if row else None

    def require_version(self, version_id: str) -> dict[str, Any]:
        version = self.get_version(version_id)
        if version is None:
            raise ConfigVersionNotFound(version_id)
        return version

    def active_version_id(self, domain: str) -> str | None:
        self._require_domain(domain)
        with self._connect() as connection:
            row = connection.execute(
                "select version_id from config_active where domain = ?",
                (domain,),
            ).fetchone()
        return str(row["version_id"]) if row else None

    def active_version(self, domain: str) -> dict[str, Any] | None:
        version_id = self.active_version_id(domain)
        return self.get_version(version_id) if version_id else None

    def _save_draft(self, draft: dict[str, Any]) -> dict[str, Any]:
        self.contracts.require_valid("config_draft", draft)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                update config_drafts
                set status = ?,
                    draft_json = ?,
                    updated_at = ?
                where draft_id = ?
                """,
                (
                    draft["status"],
                    self._to_json(draft),
                    draft["updated_at"],
                    draft["draft_id"],
                ),
            )
        if cursor.rowcount != 1:
            raise ConfigDraftNotFound(draft["draft_id"])
        return draft

    def _cross_validate(self, domain: str, payload: dict[str, Any]) -> list[str]:
        if domain == "tools":
            return self._validate_tool_catalog(payload)
        if domain == "integration_endpoints":
            return self._validate_integration_endpoint_catalog(payload)
        if domain == "workflow_states":
            return self._validate_workflow_state_catalog(payload)
        if domain == "workflow_transitions":
            return self._validate_workflow_transition_rules(payload)
        if domain == "prompts":
            return self._validate_prompt_catalog(payload)
        if domain == "n8n_workflows":
            return self._validate_n8n_workflow_catalog(payload)
        if domain == "attribute_resolution_profiles":
            return self._validate_attribute_resolution_profiles(payload)
        if domain == "model_routing":
            return self._validate_model_routing(payload)
        if domain == "service_scenarios":
            return self._validate_service_scenarios(payload)
        if domain == "slot_schemas":
            return self._validate_slot_schemas(payload)
        if domain == "classification_routes":
            return self._validate_classification_routes(payload)
        if domain == "orchestrator_policy":
            return self._validate_orchestrator_policy(payload)
        if domain == "tool_launch_matrix":
            return self._validate_tool_launch_matrix(payload)
        if domain == "prompt_packs":
            return self._validate_prompt_packs(payload)
        if domain == "escalation_policies":
            return self._validate_escalation_policies(payload)
        return []

    def _validate_tool_catalog(self, payload: dict[str, Any]) -> list[str]:
        errors = []
        allowed_tool_names = set(
            self.contracts.entries["proposed_action"].schema["properties"]["tool_name"]["enum"]
        )
        endpoint_catalog = self.active_payload("integration_endpoints")
        endpoint_by_id = {
            endpoint["endpoint_id"]: endpoint
            for endpoint in endpoint_catalog["endpoints"]
        }
        tool_names = [tool["tool_name"] for tool in payload["tools"]]
        for tool_name in self._duplicates(tool_names):
            errors.append(f"Дублируется tool_name: {tool_name}")
        for tool_name in sorted(allowed_tool_names - set(tool_names)):
            errors.append(f"Нет записи tool_catalog для proposed-action tool: {tool_name}")

        for tool in payload["tools"]:
            tool_name = tool["tool_name"]
            if tool_name not in allowed_tool_names:
                errors.append(f"tool_name не разрешен схемой proposed-action: {tool_name}")
            for schema_key in ("parameters_schema", "result_schema"):
                try:
                    Draft202012Validator.check_schema(tool[schema_key])
                except SchemaError as error:
                    errors.append(f"{tool_name} {schema_key} невалидна: {error.message}")
            for binding in tool["endpoint_bindings"]:
                endpoint = endpoint_by_id.get(binding["endpoint_id"])
                if not endpoint:
                    errors.append(
                        f"{tool_name} ссылается на неизвестный endpoint_id: {binding['endpoint_id']}"
                    )
                    continue
                if binding["operation_id"] not in endpoint["operations"]:
                    errors.append(
                        f"{tool_name} ссылается на неизвестный operation_id {binding['operation_id']} "
                        f"для endpoint {binding['endpoint_id']}"
                    )
        return errors

    def _validate_integration_endpoint_catalog(self, payload: dict[str, Any]) -> list[str]:
        endpoint_ids = [endpoint["endpoint_id"] for endpoint in payload["endpoints"]]
        return [f"Дублируется endpoint_id: {endpoint_id}" for endpoint_id in self._duplicates(endpoint_ids)]

    def _validate_workflow_state_catalog(self, payload: dict[str, Any]) -> list[str]:
        state_ids = [state["id"] for state in payload["states"]]
        return [f"Дублируется id состояния workflow: {state_id}" for state_id in self._duplicates(state_ids)]

    def _validate_workflow_transition_rules(self, payload: dict[str, Any]) -> list[str]:
        state_ids = {
            state["id"]
            for state in self.active_payload("workflow_states")["states"]
        }
        return [
            f"Правило перехода workflow ссылается на неизвестный state_id: {rule['state_id']}"
            for rule in payload["rules"]
            if rule["state_id"] not in state_ids
        ]

    def _validate_prompt_catalog(self, payload: dict[str, Any]) -> list[str]:
        prompt_ids = [prompt["prompt_id"] for prompt in payload["prompts"]]
        return [f"Дублируется prompt_id: {prompt_id}" for prompt_id in self._duplicates(prompt_ids)]

    def _validate_model_routing(self, payload: dict[str, Any]) -> list[str]:
        errors = []
        providers = payload.get("providers", {})
        active_provider_id = payload.get("active_provider")
        provider_ids = set(providers)
        if active_provider_id and active_provider_id not in provider_ids:
            errors.append(f"active_provider неизвестен: {active_provider_id}")
        enabled_providers = [
            provider
            for provider in providers.values()
            if provider.get("enabled")
        ]
        if not enabled_providers:
            errors.append("Должно быть включено хотя бы одно подключение модели.")
        aliases = [
            provider.get("model_alias")
            for provider in enabled_providers
            if provider.get("model_alias")
        ]
        for alias in self._duplicates(aliases):
            errors.append(f"Дублируется model_alias: {alias}")
        provider_aliases = {
            provider.get("model_alias")
            for provider in enabled_providers
            if provider.get("model_alias")
        }
        default_alias = payload["default_model_alias"]
        if default_alias not in provider_aliases:
            errors.append("default_model_alias должен совпадать с alias включенного backend.")
        active_provider = providers.get(active_provider_id or "")
        if active_provider and not active_provider.get("enabled"):
            errors.append("active_provider должен ссылаться на включенный backend.")
        for provider_id, provider in providers.items():
            if provider.get("provider_type") not in {"vllm_cpu", "openai", "litellm"}:
                errors.append(f"{provider_id} provider_type должен быть vllm_cpu, openai или litellm.")
            if provider.get("api_key_required") and not (
                provider.get("api_key_env") or provider.get("secret_ref")
            ):
                errors.append(f"{provider_id} требует api_key_env или secret_ref.")
            rate_limits = provider.get("rate_limits", {})
            if rate_limits.get("requests_per_minute") is not None and int(rate_limits["requests_per_minute"]) < 1:
                errors.append(f"{provider_id} requests_per_minute должен быть больше 0.")
            if rate_limits.get("tokens_per_minute") is not None and int(rate_limits["tokens_per_minute"]) < 1:
                errors.append(f"{provider_id} tokens_per_minute должен быть больше 0.")
        for route_name, alias in payload.get("routing", {}).items():
            if alias not in provider_aliases:
                errors.append(f"routing.{route_name} ссылается на неизвестный model alias: {alias}")
        for fallback in payload.get("fallbacks", []):
            if fallback["from"] not in provider_aliases:
                errors.append(f"fallback from ссылается на неизвестный alias: {fallback['from']}")
            if fallback["to"] not in provider_aliases:
                errors.append(f"fallback to ссылается на неизвестный alias: {fallback['to']}")
        temperature = payload.get("settings", {}).get("temperature")
        if temperature is not None and not 0 <= float(temperature) <= 2:
            errors.append("settings.temperature должен быть в диапазоне 0..2.")
        return errors

    def _validate_n8n_workflow_catalog(self, payload: dict[str, Any]) -> list[str]:
        errors = []
        workflow_ids = [workflow["workflow_id"] for workflow in payload["workflows"]]
        for workflow_id in self._duplicates(workflow_ids):
            errors.append(f"Дублируется workflow_id: {workflow_id}")
        endpoint_ids = {
            endpoint["endpoint_id"]
            for endpoint in self.active_payload("integration_endpoints")["endpoints"]
        }
        for workflow in payload["workflows"]:
            if workflow["endpoint_id"] not in endpoint_ids:
                errors.append(
                    f"Workflow n8n {workflow['workflow_id']} ссылается на неизвестный endpoint_id: "
                    f"{workflow['endpoint_id']}"
                )
            callback_endpoint_id = workflow.get("callback_endpoint_id")
            if callback_endpoint_id and callback_endpoint_id not in endpoint_ids:
                errors.append(
                    f"Workflow n8n {workflow['workflow_id']} ссылается на неизвестный callback_endpoint_id: "
                    f"{callback_endpoint_id}"
                )
        return errors

    def _validate_attribute_resolution_profiles(self, payload: dict[str, Any]) -> list[str]:
        errors = []
        profiles = payload["profiles"]
        profile_ids = [profile["profile_id"] for profile in profiles]
        for profile_id in self._duplicates(profile_ids):
            errors.append(f"Дублируется profile_id: {profile_id}")

        tool_by_name = {
            tool["tool_name"]: tool
            for tool in self.active_payload("tools")["tools"]
        }

        for profile in profiles:
            profile_id = profile["profile_id"]
            if profile["target_slot_id"] not in profile["output_slots"]:
                errors.append(f"{profile_id} target_slot_id должен входить в output_slots.")
            confidence_thresholds = profile.get("confidence_thresholds", {})
            auto_fill_threshold = confidence_thresholds.get("auto_fill", profile["confidence_threshold"])
            clarification_threshold = confidence_thresholds.get("clarification", profile["confidence_threshold"])
            operator_threshold = confidence_thresholds.get("operator_handoff", 0)
            if auto_fill_threshold < clarification_threshold:
                errors.append(f"{profile_id} auto_fill threshold не должен быть ниже clarification threshold.")
            if clarification_threshold < operator_threshold:
                errors.append(f"{profile_id} clarification threshold не должен быть ниже operator_handoff threshold.")
            ambiguity_policy = profile.get("ambiguity_policy", {})
            if ambiguity_policy.get("action") == "clarification":
                if not ambiguity_policy.get("question"):
                    errors.append(f"{profile_id} ambiguity_policy clarification должен содержать question.")
                if not ambiguity_policy.get("ask_for_attributes"):
                    errors.append(f"{profile_id} ambiguity_policy clarification должен содержать ask_for_attributes.")

            step_ids = [step["step_id"] for step in profile["steps"]]
            for step_id in self._duplicates(step_ids):
                errors.append(f"{profile_id} содержит дублирующийся step_id: {step_id}")
            known_step_ids = set(step_ids)
            declared_attributes = set(profile["input_slots"])
            declared_attributes.update(profile["output_slots"])
            declared_attributes.update(profile.get("intermediate_attributes", []))
            for package_attr in profile.get("operator_handoff_package", []):
                if package_attr not in declared_attributes:
                    errors.append(f"{profile_id} operator_handoff_package содержит необъявленный атрибут: {package_attr}")
            if ambiguity_policy.get("candidate_count_attribute"):
                candidate_attr = ambiguity_policy["candidate_count_attribute"]
                if candidate_attr not in declared_attributes:
                    errors.append(f"{profile_id} ambiguity_policy ссылается на необъявленный атрибут: {candidate_attr}")
            for attr_id in ambiguity_policy.get("ask_for_attributes", []):
                if attr_id not in declared_attributes:
                    errors.append(f"{profile_id} ambiguity_policy уточняет необъявленный атрибут: {attr_id}")
            for step in profile["steps"]:
                step_label = f"{profile_id}/{step['step_id']}"
                if step["type"] == "tool_call":
                    for required_key in ("tool_name", "endpoint_profile", "operation_id"):
                        if not step.get(required_key):
                            errors.append(f"{step_label} tool_call должен содержать {required_key}.")
                    tool = tool_by_name.get(step.get("tool_name"))
                    if tool:
                        matching_binding = next(
                            (
                                binding
                                for binding in tool["endpoint_bindings"]
                                if binding["profile"] == step.get("endpoint_profile")
                                and binding["operation_id"] == step.get("operation_id")
                            ),
                            None,
                        )
                        if not matching_binding:
                            errors.append(
                                f"{step_label} не имеет tool binding для profile={step.get('endpoint_profile')} "
                                f"operation_id={step.get('operation_id')}."
                            )
                    elif step.get("tool_name"):
                        errors.append(f"{step_label} ссылается на неизвестный tool_name: {step['tool_name']}")
                if step["type"] == "clarification":
                    if not step.get("clarification_question"):
                        errors.append(f"{step_label} clarification должен содержать question.")
                    if not step.get("ask_for_attributes"):
                        errors.append(f"{step_label} clarification должен содержать ask_for_attributes.")
                if step["type"] == "operator_handoff":
                    if not profile.get("operator_handoff_package"):
                        errors.append(f"{step_label} operator_handoff требует operator_handoff_package в профиле.")
                if step["type"] == "fill_slot":
                    if not step.get("fill_slot_id"):
                        errors.append(f"{step_label} fill_slot должен содержать fill_slot_id.")
                    elif step["fill_slot_id"] not in profile["output_slots"]:
                        errors.append(f"{step_label} fill_slot_id должен входить в output_slots профиля.")
                    if not step.get("from_attribute"):
                        errors.append(f"{step_label} fill_slot должен содержать from_attribute.")
                    elif root_attribute(step.get("from_attribute")) not in declared_attributes:
                        errors.append(
                            f"{step_label} from_attribute должен ссылаться на объявленный слот или промежуточный атрибут: "
                            f"{step['from_attribute']}"
                        )
                if step["type"] == "ticket_history_search" and not step.get("history_filter"):
                    errors.append(f"{step_label} ticket_history_search должен содержать history_filter.")
                for attr_id in step.get("inputs", []):
                    if attr_id not in declared_attributes:
                        errors.append(f"{step_label} input не объявлен в профиле или шагах: {attr_id}")
                for attr_id in step.get("outputs", []):
                    if attr_id not in declared_attributes:
                        errors.append(f"{step_label} output не объявлен в output_slots или intermediate_attributes: {attr_id}")
                for attr_id in step.get("ask_for_attributes", []):
                    if attr_id not in declared_attributes:
                        errors.append(f"{step_label} ask_for_attributes содержит необъявленный атрибут: {attr_id}")
                for link_key in ("on_success_step", "on_failure_step", "on_ambiguous_step"):
                    if step.get(link_key) and step[link_key] not in known_step_ids:
                        errors.append(f"{step_label} ссылается на неизвестный {link_key}: {step[link_key]}")

            if profile["fallback"]["action"] == "ask_user" and not profile["fallback"].get("question"):
                errors.append(f"{profile_id} fallback ask_user должен содержать question.")
        return errors

    def _validate_service_scenarios(self, payload: dict[str, Any]) -> list[str]:
        errors = []
        scenarios = payload["scenarios"]
        scenario_ids = [scenario["scenario_id"] for scenario in scenarios]
        for scenario_id in self._duplicates(scenario_ids):
            errors.append(f"Дублируется scenario_id: {scenario_id}")
        slot_schema_ids = set(
            self._by_id(self.active_payload("slot_schemas")["slot_schemas"], "slot_schema_id")
        )
        route_ids = set(
            self._by_id(self.active_payload("classification_routes")["routes"], "route_id")
        )
        policy_ids = set(
            self._by_id(self.active_payload("orchestrator_policy")["policies"], "policy_id")
        )
        matrix_ids = set(
            self._by_id(self.active_payload("tool_launch_matrix")["matrices"], "matrix_id")
        )
        prompt_pack_ids = set(
            self._by_id(self.active_payload("prompt_packs")["packs"], "prompt_pack_id")
        )
        escalation_policy_ids = set(
            self._by_id(self.active_payload("escalation_policies")["policies"], "policy_id")
        )
        for scenario in scenarios:
            scenario_id = scenario["scenario_id"]
            if scenario["slot_schema_id"] not in slot_schema_ids:
                errors.append(f"{scenario_id} ссылается на неизвестную slot_schema_id: {scenario['slot_schema_id']}")
            if scenario["classification_route_id"] not in route_ids:
                errors.append(
                    f"{scenario_id} ссылается на неизвестную classification_route_id: "
                    f"{scenario['classification_route_id']}"
                )
            if scenario["orchestrator_policy_id"] not in policy_ids:
                errors.append(
                    f"{scenario_id} ссылается на неизвестную orchestrator_policy_id: "
                    f"{scenario['orchestrator_policy_id']}"
                )
            if scenario["tool_launch_matrix_id"] not in matrix_ids:
                errors.append(
                    f"{scenario_id} ссылается на неизвестную tool_launch_matrix_id: "
                    f"{scenario['tool_launch_matrix_id']}"
                )
            if scenario["prompt_pack_id"] not in prompt_pack_ids:
                errors.append(f"{scenario_id} ссылается на неизвестный prompt_pack_id: {scenario['prompt_pack_id']}")
            if scenario["escalation_policy_id"] not in escalation_policy_ids:
                errors.append(
                    f"{scenario_id} ссылается на неизвестную escalation_policy_id: "
                    f"{scenario['escalation_policy_id']}"
                )
        return errors

    def _validate_slot_schemas(self, payload: dict[str, Any]) -> list[str]:
        errors = []
        schemas = payload["slot_schemas"]
        schema_ids = [schema["slot_schema_id"] for schema in schemas]
        for schema_id in self._duplicates(schema_ids):
            errors.append(f"Дублируется slot_schema_id: {schema_id}")
        priority_order = {"who": 0, "what": 1, "when": 2, "where": 3, "context": 4}
        for schema in schemas:
            slot_by_id = self._by_id(schema["slots"], "slot_id")
            for slot_id in self._duplicates([slot["slot_id"] for slot in schema["slots"]]):
                errors.append(f"{schema['slot_schema_id']} содержит дублирующийся slot_id: {slot_id}")
            profile_by_id = self._by_id(
                self.active_payload("attribute_resolution_profiles")["profiles"],
                "profile_id",
            )
            for slot in schema["slots"]:
                fill_method = slot_fill_method(slot)
                profile_id = slot.get("resolution_profile_id")
                if fill_method == "resolution_profile":
                    if not profile_id:
                        errors.append(f"{schema['slot_schema_id']} slot {slot['slot_id']} должен иметь resolution_profile_id.")
                    else:
                        profile = profile_by_id.get(profile_id)
                        if not profile:
                            errors.append(f"{schema['slot_schema_id']} slot {slot['slot_id']} ссылается на неизвестный profile_id: {profile_id}")
                        elif slot["slot_id"] not in profile["output_slots"]:
                            errors.append(f"{schema['slot_schema_id']} slot {slot['slot_id']} не входит в output_slots профиля {profile_id}.")
                        else:
                            for profile_slot_id in profile["input_slots"]:
                                if profile_slot_id not in slot_by_id:
                                    errors.append(
                                        f"{schema['slot_schema_id']} профиль {profile_id} требует отсутствующий input slot: "
                                        f"{profile_slot_id}"
                                    )
                elif profile_id:
                    errors.append(f"{schema['slot_schema_id']} slot {slot['slot_id']} не должен иметь profile_id без способа заполнения через профиль.")
            for slot_id in schema["required_slots"]:
                slot = slot_by_id.get(slot_id)
                if not slot:
                    errors.append(f"{schema['slot_schema_id']} содержит неизвестный required slot: {slot_id}")
                    continue
                fill_method = slot_fill_method(slot)
                if fill_method == "user_question" and not slot.get("question"):
                    errors.append(f"{schema['slot_schema_id']} required slot {slot_id} должен иметь question.")
            for slot_id in schema["auto_fill_slots"]:
                slot = slot_by_id.get(slot_id)
                if not slot:
                    errors.append(f"{schema['slot_schema_id']} содержит неизвестный auto-fill slot: {slot_id}")
                elif slot_fill_method(slot) in {"user_question", "operator_manual"}:
                    errors.append(f"{schema['slot_schema_id']} auto-fill slot {slot_id} не может заполняться вопросом или вручную.")
            previous_priority = -1
            for slot_id in schema["question_order"]:
                slot = slot_by_id.get(slot_id)
                if not slot:
                    errors.append(f"{schema['slot_schema_id']} содержит неизвестный slot в question_order: {slot_id}")
                    continue
                current_priority = priority_order[slot["priority_group"]]
                if current_priority < previous_priority:
                    errors.append(
                        f"{schema['slot_schema_id']} нарушает порядок вопросов кто -> что -> когда: {slot_id}"
                    )
                previous_priority = current_priority
            if schema["timeouts"]["draft_after_seconds"] <= schema["timeouts"]["reminder_after_seconds"]:
                errors.append(f"{schema['slot_schema_id']} draft timeout должен быть больше reminder timeout.")
        return errors

    def _validate_classification_routes(self, payload: dict[str, Any]) -> list[str]:
        errors = []
        route_ids = [route["route_id"] for route in payload["routes"]]
        for route_id in self._duplicates(route_ids):
            errors.append(f"Дублируется route_id: {route_id}")
        workflow_state_ids = {
            state["id"]
            for state in self.active_payload("workflow_states")["states"]
        }
        for route in payload["routes"]:
            if route["workflow_state_id"] not in workflow_state_ids:
                errors.append(
                    f"{route['route_id']} ссылается на неизвестный workflow_state_id: {route['workflow_state_id']}"
                )
            confidence = route["confidence"]
            if confidence["human_handoff_below"] > confidence["llm_min"]:
                errors.append(f"{route['route_id']} human_handoff_below не должен быть выше llm_min.")
        return errors

    def _validate_orchestrator_policy(self, payload: dict[str, Any]) -> list[str]:
        errors = []
        policy_ids = [policy["policy_id"] for policy in payload["policies"]]
        for policy_id in self._duplicates(policy_ids):
            errors.append(f"Дублируется policy_id: {policy_id}")
        for policy in payload["policies"]:
            if policy["consecutive_tool_errors_to_escalate"] > policy["max_iterations"]:
                errors.append(f"{policy['policy_id']} лимит ошибок инструментов не может быть выше max_iterations.")
        return errors

    def _validate_tool_launch_matrix(self, payload: dict[str, Any]) -> list[str]:
        errors = []
        matrices = payload["matrices"]
        matrix_ids = [matrix["matrix_id"] for matrix in matrices]
        for matrix_id in self._duplicates(matrix_ids):
            errors.append(f"Дублируется matrix_id: {matrix_id}")
        slot_schema_by_id = self._by_id(
            self.active_payload("slot_schemas")["slot_schemas"],
            "slot_schema_id",
        )
        scenarios_by_matrix = {
            matrix["matrix_id"]: [
                scenario
                for scenario in self._scenario_by_id().values()
                if scenario.get("tool_launch_matrix_id") == matrix["matrix_id"]
            ]
            for matrix in matrices
        }
        tool_by_name = {
            tool["tool_name"]: tool
            for tool in self.active_payload("tools")["tools"]
        }
        for matrix in matrices:
            matrix_id = matrix["matrix_id"]
            launch_ids = [launch["launch_id"] for launch in matrix["launches"]]
            for launch_id in self._duplicates(launch_ids):
                errors.append(f"{matrix_id}: дублируется launch_id: {launch_id}")
            scenarios = scenarios_by_matrix.get(matrix_id, [])
            for launch in matrix["launches"]:
                for scenario in scenarios:
                    slot_schema = slot_schema_by_id.get(scenario["slot_schema_id"])
                    known_slots = {
                        slot["slot_id"]
                        for slot in slot_schema["slots"]
                    } if slot_schema else set()
                    for slot_id in launch["required_slots"]:
                        if slot_id not in known_slots:
                            errors.append(
                                f"{launch['launch_id']} требует неизвестный slot {slot_id} "
                                f"для сценария {scenario['scenario_id']}"
                            )
                    for parameter, binding in launch["parameter_bindings"].items():
                        source, _, value = binding.partition(":")
                        if source == "slot" and value not in known_slots:
                            errors.append(
                                f"{launch['launch_id']} parameter {parameter} ссылается на неизвестный slot "
                                f"{value} для сценария {scenario['scenario_id']}"
                            )
                tool = tool_by_name.get(launch["tool_name"])
                if not tool:
                    errors.append(f"{launch['launch_id']} ссылается на неизвестный tool_name: {launch['tool_name']}")
                    continue
                matching_binding = next(
                    (
                        binding
                        for binding in tool["endpoint_bindings"]
                        if binding["profile"] == launch["endpoint_profile"]
                        and binding["operation_id"] == launch["operation_id"]
                    ),
                    None,
                )
                if not matching_binding:
                    errors.append(
                        f"{launch['launch_id']} не имеет binding для profile={launch['endpoint_profile']} "
                        f"operation_id={launch['operation_id']}"
                    )
                if launch["execution_level"] == "auto" and tool["action_type"] == "action":
                    if tool["policy"].get("approval_required_hint") or not tool["policy"].get("auto_execution_eligible"):
                        errors.append(f"{launch['launch_id']} не может быть auto в текущей policy инструмента.")
                if launch["risk_level"] == "blocked" and launch["execution_level"] != "blocked":
                    errors.append(f"{launch['launch_id']} с risk_level=blocked должен иметь execution_level=blocked.")
        return errors

    def _validate_prompt_packs(self, payload: dict[str, Any]) -> list[str]:
        errors = []
        pack_ids = [pack["prompt_pack_id"] for pack in payload["packs"]]
        for pack_id in self._duplicates(pack_ids):
            errors.append(f"Дублируется prompt_pack_id: {pack_id}")
        scenario_ids = set(self._scenario_by_id())
        required_blocks = {
            "role_context",
            "behavior_principles",
            "slot_schemas",
            "classification_confidence",
            "react_planning",
            "tool_rules",
            "escalation_response",
        }
        for pack in payload["packs"]:
            if pack["scenario_id"] not in scenario_ids:
                errors.append(f"{pack['prompt_pack_id']} ссылается на неизвестный scenario_id: {pack['scenario_id']}")
            empty_blocks = [
                block
                for block in required_blocks
                if not str(pack["blocks"].get(block, "")).strip()
            ]
            if empty_blocks:
                errors.append(f"{pack['prompt_pack_id']} содержит пустые обязательные блоки: {', '.join(sorted(empty_blocks))}")
        return errors

    def _validate_escalation_policies(self, payload: dict[str, Any]) -> list[str]:
        errors = []
        policy_ids = [policy["policy_id"] for policy in payload["policies"]]
        for policy_id in self._duplicates(policy_ids):
            errors.append(f"Дублируется escalation policy_id: {policy_id}")
        required_package = {
            "slots",
            "react_history",
            "tool_results",
            "agent_hypothesis",
            "sla_remaining",
            "user_notification",
        }
        for policy in payload["policies"]:
            package = set(policy["escalation_package"])
            missing = required_package - package
            if missing:
                errors.append(f"{policy['policy_id']} escalation package неполный: {', '.join(sorted(missing))}")
            if policy["major_incident"]["affected_users_threshold"] < 10:
                errors.append(f"{policy['policy_id']} Major Incident threshold должен быть не меньше 10.")
        return errors

    def _draft_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        draft = json.loads(row["draft_json"])
        self.contracts.require_valid("config_draft", draft)
        return draft

    def _version_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        version = json.loads(row["version_json"])
        self.contracts.require_valid("config_version", version)
        return version

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                create table if not exists config_drafts (
                    draft_id text primary key,
                    domain text not null,
                    status text not null,
                    draft_json text not null,
                    created_by text not null,
                    created_at text not null,
                    updated_at text not null
                )
                """
            )
            connection.execute(
                """
                create index if not exists idx_config_drafts_domain
                on config_drafts(domain)
                """
            )
            connection.execute(
                """
                create table if not exists config_versions (
                    version_id text primary key,
                    domain text not null,
                    version_json text not null,
                    source_draft_id text not null,
                    activated_by text not null,
                    activated_at text not null
                )
                """
            )
            connection.execute(
                """
                create index if not exists idx_config_versions_domain
                on config_versions(domain)
                """
            )
            connection.execute(
                """
                create table if not exists config_active (
                    domain text primary key,
                    version_id text not null,
                    activated_at text not null
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _require_domain(self, domain: str) -> None:
        if domain not in CONFIG_DOMAINS:
            raise ConfigRegistryError(f"Неизвестный домен конфигурации: {domain}")

    def _scenario_by_id(self) -> dict[str, dict[str, Any]]:
        return self._by_id(
            self.active_payload("service_scenarios")["scenarios"],
            "scenario_id",
        )

    @staticmethod
    def _by_id(items: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
        return {
            item[key]: item
            for item in items
        }

    @staticmethod
    def _to_json(value: dict[str, Any]) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _duplicates(values: list[str]) -> list[str]:
        return sorted(
            value
            for value in set(values)
            if values.count(value) > 1
        )


DEFAULT_SCENARIOS: tuple[dict[str, str], ...] = (
    {
        "scenario_id": "password_reset",
        "display_name": "Сброс пароля",
        "description": "Пользователь не может войти и требуется сброс пароля или проверка учетной записи.",
    },
    {
        "scenario_id": "software_issue",
        "display_name": "Проблема с приложением",
        "description": "Приложение не запускается, выдает ошибку или работает нестабильно.",
    },
    {
        "scenario_id": "hardware_issue",
        "display_name": "Проблема с устройством",
        "description": "Рабочая станция, ноутбук, периферия или другое устройство требуют диагностики.",
    },
    {
        "scenario_id": "network_issue",
        "display_name": "Проблема с сетью",
        "description": "Пользователь или группа пользователей сообщает о недоступности сети, VPN или сервиса.",
    },
    {
        "scenario_id": "access_request",
        "display_name": "Запрос доступа",
        "description": "Пользователь запрашивает доступ к группе, приложению или ресурсу.",
    },
    {
        "scenario_id": "unknown",
        "display_name": "Неизвестный сценарий",
        "description": "Категория обращения не определена с достаточной уверенностью.",
    },
)


def default_service_scenarios() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "scenarios": [
            {
                "scenario_id": item["scenario_id"],
                "display_name": item["display_name"],
                "status": "active" if item["scenario_id"] != "unknown" else "planned",
                "description": item["description"],
                "slot_schema_id": f"slot.{item['scenario_id']}",
                "classification_route_id": f"route.{item['scenario_id']}",
                "orchestrator_policy_id": f"policy.{item['scenario_id']}",
                "tool_launch_matrix_id": f"matrix.{item['scenario_id']}",
                "prompt_pack_id": f"prompt.{item['scenario_id']}",
                "escalation_policy_id": f"escalation.{item['scenario_id']}",
                "tags": ["mvp"],
            }
            for item in DEFAULT_SCENARIOS
        ],
    }


def _slot(
    slot_id: str,
    display_name: str,
    priority_group: str,
    *,
    required: bool = True,
    fill_method: str = "user_question",
    resolution_profile_id: str | None = None,
    question: str | None = None,
    auto_fill_ref: str | None = None,
) -> dict[str, Any]:
    result = {
        "slot_id": slot_id,
        "display_name": display_name,
        "priority_group": priority_group,
        "required": required,
        "fill_method": fill_method,
    }
    if resolution_profile_id:
        result["resolution_profile_id"] = resolution_profile_id
    if question:
        result["question"] = question
    if auto_fill_ref:
        result["auto_fill_ref"] = auto_fill_ref
    return result


def default_slot_schemas() -> dict[str, Any]:
    common_timeouts = {
        "reminder_after_seconds": 180,
        "draft_after_seconds": 480,
    }
    return {
        "schema_version": "1.0",
        "slot_schemas": [
            {
                "slot_schema_id": "slot.password_reset",
                "display_name": "Слоты сброса пароля",
                "required_slots": ["user_login", "account_type"],
                "auto_fill_slots": ["user_login", "user_id"],
                "question_order": ["user_login", "account_type"],
                "timeouts": common_timeouts,
                "slots": [
                    _slot(
                        "user_login",
                        "Логин пользователя",
                        "who",
                        fill_method="resolution_profile",
                        resolution_profile_id="profile.password_reset.login_from_ad",
                        question="Уточните ФИО, должность или табельный номер пользователя.",
                    ),
                    _slot("account_type", "Тип учетной записи", "what", question="Для какой учетной записи нужен сброс?"),
                    _slot(
                        "user_id",
                        "Идентификатор пользователя",
                        "who",
                        required=False,
                        fill_method="resolution_profile",
                        resolution_profile_id="profile.password_reset.login_from_ad",
                    ),
                ],
            },
            {
                "slot_schema_id": "slot.software_issue",
                "display_name": "Слоты проблемы с приложением",
                "required_slots": ["user_login", "app_name", "error_text"],
                "auto_fill_slots": ["device_name"],
                "question_order": ["user_login", "app_name", "error_text"],
                "timeouts": common_timeouts,
                "slots": [
                    _slot("user_login", "Логин пользователя", "who", question="Уточните логин пользователя."),
                    _slot("app_name", "Приложение", "what", question="С каким приложением проблема?"),
                    _slot("error_text", "Текст ошибки", "what", question="Какой текст ошибки видит пользователь?"),
                    _slot(
                        "device_name",
                        "Имя устройства",
                        "context",
                        required=False,
                        fill_method="resolution_profile",
                        resolution_profile_id="profile.software_issue.device_from_ad",
                    ),
                ],
            },
            {
                "slot_schema_id": "slot.hardware_issue",
                "display_name": "Слоты проблемы с устройством",
                "required_slots": ["user_login", "device_id", "symptom"],
                "auto_fill_slots": ["device_model"],
                "question_order": ["user_login", "device_id", "symptom"],
                "timeouts": common_timeouts,
                "slots": [
                    _slot("user_login", "Логин пользователя", "who", question="Уточните логин пользователя."),
                    _slot("device_id", "ID устройства", "what", question="Уточните имя или инвентарный номер устройства."),
                    _slot("symptom", "Симптом", "what", question="Что именно не работает?"),
                    _slot(
                        "device_model",
                        "Модель устройства",
                        "context",
                        required=False,
                        fill_method="resolution_profile",
                        resolution_profile_id="profile.hardware_issue.device_from_cmdb",
                    ),
                ],
            },
            {
                "slot_schema_id": "slot.network_issue",
                "display_name": "Слоты сетевой проблемы",
                "required_slots": ["user_login", "location", "symptom", "affected_users"],
                "auto_fill_slots": ["subnet"],
                "question_order": ["user_login", "symptom", "affected_users", "location"],
                "timeouts": common_timeouts,
                "slots": [
                    _slot("user_login", "Логин пользователя", "who", question="Уточните логин пользователя."),
                    _slot("symptom", "Симптом", "what", question="Что именно недоступно?"),
                    _slot("affected_users", "Затронутые пользователи", "what", question="Сколько пользователей затронуто?"),
                    _slot("location", "Локация", "where", question="Где наблюдается проблема?"),
                    _slot(
                        "subnet",
                        "Подсеть",
                        "context",
                        required=False,
                        fill_method="resolution_profile",
                        resolution_profile_id="profile.network_issue.subnet_from_cmdb",
                    ),
                ],
            },
            {
                "slot_schema_id": "slot.access_request",
                "display_name": "Слоты запроса доступа",
                "required_slots": ["user_login", "resource_name", "business_reason", "approver_login"],
                "auto_fill_slots": ["user_id"],
                "question_order": ["user_login", "approver_login", "resource_name", "business_reason"],
                "timeouts": common_timeouts,
                "slots": [
                    _slot("user_login", "Логин пользователя", "who", question="Уточните логин пользователя."),
                    _slot("resource_name", "Ресурс", "what", question="К какому ресурсу нужен доступ?"),
                    _slot("business_reason", "Обоснование", "what", question="Уточните бизнес-обоснование доступа."),
                    _slot("approver_login", "Согласующий", "who", question="Кто должен согласовать доступ?"),
                    _slot(
                        "user_id",
                        "Идентификатор пользователя",
                        "who",
                        required=False,
                        fill_method="resolution_profile",
                        resolution_profile_id="profile.access_request.user_from_ad",
                    ),
                ],
            },
            {
                "slot_schema_id": "slot.unknown",
                "display_name": "Слоты неизвестного сценария",
                "required_slots": ["user_login", "symptom"],
                "auto_fill_slots": [],
                "question_order": ["user_login", "symptom"],
                "timeouts": common_timeouts,
                "slots": [
                    _slot("user_login", "Логин пользователя", "who", question="Уточните логин пользователя."),
                    _slot("symptom", "Описание проблемы", "what", question="Опишите проблему одной фразой."),
                ],
            },
        ],
    }


def default_attribute_resolution_profiles() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "profiles": [
            {
                "profile_id": "profile.password_reset.login_from_ad",
                "display_name": "Поиск логина в AD по ФИО",
                "status": "active",
                "description": "Заполняет логин и идентификатор пользователя для сброса пароля: извлекает признаки личности из текста и истории, проверяет AD и задает уточняющий вопрос при однофамильцах.",
                "target_slot_id": "user_login",
                "resolution_mode": "branching",
                "attempt_scope": "profile",
                "input_slots": [],
                "output_slots": ["user_login", "user_id"],
                "intermediate_attributes": [
                    "login_candidate",
                    "last_name",
                    "first_name",
                    "middle_name",
                    "email",
                    "department",
                    "employee_number",
                    "title",
                    "history_identity_hints",
                    "ad_candidates"
                ],
                "steps": [
                    {
                        "step_id": "extract_identity_from_text",
                        "type": "llm_extract",
                        "display_name": "Извлечь логин, ФИО и контакты из текста обращения",
                        "inputs": [],
                        "outputs": ["login_candidate", "last_name", "first_name", "middle_name", "email"],
                        "on_success_step": "search_history_hint",
                        "on_failure_step": "search_history_hint",
                    },
                    {
                        "step_id": "search_history_hint",
                        "type": "rag_search",
                        "display_name": "Проверить похожие заявки и подсказки по личности",
                        "inputs": ["login_candidate", "last_name", "first_name", "middle_name", "email"],
                        "outputs": ["history_identity_hints"],
                        "on_success_step": "validate_login_candidate",
                        "on_failure_step": "validate_login_candidate",
                    },
                    {
                        "step_id": "validate_login_candidate",
                        "type": "tool_call",
                        "display_name": "Проверить найденный логин в Active Directory",
                        "tool_name": "search_ad_users",
                        "endpoint_profile": "mock",
                        "operation_id": "search_ad_users",
                        "parameter_bindings": {
                            "login": "attribute:login_candidate",
                            "email": "attribute:email"
                        },
                        "inputs": ["login_candidate", "email"],
                        "outputs": ["ad_candidates"],
                        "on_success_step": "single_candidate",
                        "on_failure_step": "search_ad_user",
                        "on_ambiguous_step": "ask_identity_hint",
                    },
                    {
                        "step_id": "search_ad_user",
                        "type": "tool_call",
                        "display_name": "Найти пользователя в Active Directory",
                        "tool_name": "search_ad_users",
                        "endpoint_profile": "mock",
                        "operation_id": "search_ad_users",
                        "parameter_bindings": {
                            "last_name": "attribute:last_name",
                            "first_name": "attribute:first_name",
                            "middle_name": "attribute:middle_name",
                            "department": "attribute:department",
                            "employee_number": "attribute:employee_number"
                        },
                        "inputs": ["last_name", "first_name", "middle_name", "department", "employee_number"],
                        "outputs": ["ad_candidates"],
                        "on_success_step": "single_candidate",
                        "on_failure_step": "ask_identity_hint",
                        "on_ambiguous_step": "ask_identity_hint",
                    },
                    {
                        "step_id": "single_candidate",
                        "type": "condition",
                        "display_name": "Проверить единственное совпадение",
                        "condition": "ad_candidates.count == 1",
                        "ambiguity_condition": "ad_candidates.count > 1",
                        "on_success_step": "fill_login",
                        "on_failure_step": "ask_identity_hint",
                        "on_ambiguous_step": "ask_identity_hint",
                    },
                    {
                        "step_id": "ask_identity_hint",
                        "type": "clarification",
                        "display_name": "Уточнить пользователя при неоднозначности",
                        "clarification_question": "Уточните должность, подразделение или табельный номер пользователя.",
                        "ask_for_attributes": ["department", "employee_number", "title"],
                        "on_success_step": "search_ad_user",
                        "on_failure_step": "operator_handoff",
                    },
                    {
                        "step_id": "fill_login",
                        "type": "fill_slot",
                        "display_name": "Заполнить логин пользователя",
                        "fill_slot_id": "user_login",
                        "from_attribute": "ad_candidates.0.login",
                        "on_success_step": "fill_user_id",
                    },
                    {
                        "step_id": "fill_user_id",
                        "type": "fill_slot",
                        "display_name": "Заполнить идентификатор пользователя",
                        "fill_slot_id": "user_id",
                        "from_attribute": "ad_candidates.0.user_id",
                    },
                    {
                        "step_id": "operator_handoff",
                        "type": "operator_handoff",
                        "display_name": "Передать оператору при неоднозначности",
                    },
                ],
                "fallback": {
                    "action": "operator_handoff",
                    "question": "Не удалось однозначно определить пользователя. Проверьте ФИО, должность или табельный номер вручную."
                },
                "confidence_threshold": 0.75,
                "confidence_thresholds": {
                    "auto_fill": 0.85,
                    "clarification": 0.7,
                    "operator_handoff": 0.5
                },
                "ambiguity_policy": {
                    "action": "clarification",
                    "candidate_count_attribute": "ad_candidates",
                    "question": "Уточните должность, подразделение или табельный номер пользователя.",
                    "ask_for_attributes": ["department", "employee_number", "title"]
                },
                "operator_handoff_package": [
                    "login_candidate",
                    "last_name",
                    "first_name",
                    "middle_name",
                    "email",
                    "department",
                    "employee_number",
                    "title",
                    "ad_candidates"
                ],
                "max_attempts": 2,
                "audit_required": True,
                "log_required": True,
            },
            {
                "profile_id": "profile.software_issue.device_from_ad",
                "display_name": "Устройство пользователя из AD",
                "status": "active",
                "description": "Определяет основное устройство пользователя по логину через профиль AD.",
                "target_slot_id": "device_name",
                "input_slots": ["user_login"],
                "output_slots": ["device_name"],
                "steps": [
                    {
                        "step_id": "lookup_user_device",
                        "type": "tool_call",
                        "display_name": "Найти устройство пользователя в AD",
                        "tool_name": "search_ad_users",
                        "endpoint_profile": "mock",
                        "operation_id": "search_ad_users",
                        "parameter_bindings": {
                            "login": "slot:user_login"
                        },
                        "inputs": ["user_login"],
                        "outputs": ["device_name"],
                        "on_failure_step": "ask_device_name",
                    },
                    {
                        "step_id": "ask_device_name",
                        "type": "clarification",
                        "display_name": "Уточнить устройство",
                        "clarification_question": "Уточните имя устройства пользователя.",
                        "ask_for_attributes": ["device_name"],
                    },
                ],
                "fallback": {
                    "action": "ask_user",
                    "question": "Уточните имя устройства пользователя."
                },
                "confidence_threshold": 0.7,
                "max_attempts": 2,
                "audit_required": True,
                "log_required": True,
            },
            {
                "profile_id": "profile.hardware_issue.device_from_cmdb",
                "display_name": "Устройство из CMDB",
                "status": "active",
                "description": "Заполняет модель устройства по имени или инвентарному номеру через CMDB.",
                "target_slot_id": "device_model",
                "input_slots": ["device_id"],
                "output_slots": ["device_model"],
                "steps": [
                    {
                        "step_id": "query_cmdb_device",
                        "type": "tool_call",
                        "display_name": "Найти устройство в CMDB",
                        "tool_name": "query_cmdb_object",
                        "endpoint_profile": "mock",
                        "operation_id": "query_cmdb_object",
                        "parameter_bindings": {
                            "object_ref": "slot:device_id",
                            "object_type": "constant:device"
                        },
                        "inputs": ["device_id"],
                        "outputs": ["device_model"],
                    },
                ],
                "fallback": {
                    "action": "ask_user",
                    "question": "Уточните модель устройства, если она известна."
                },
                "confidence_threshold": 0.7,
                "max_attempts": 1,
                "audit_required": True,
                "log_required": True,
            },
            {
                "profile_id": "profile.network_issue.subnet_from_cmdb",
                "display_name": "Подсеть по локации из CMDB",
                "status": "active",
                "description": "Определяет подсеть по локации для сетевого инцидента.",
                "target_slot_id": "subnet",
                "input_slots": ["location"],
                "output_slots": ["subnet"],
                "steps": [
                    {
                        "step_id": "query_location_subnet",
                        "type": "tool_call",
                        "display_name": "Найти подсеть локации",
                        "tool_name": "query_cmdb_object",
                        "endpoint_profile": "mock",
                        "operation_id": "query_cmdb_object",
                        "parameter_bindings": {
                            "object_ref": "slot:location",
                            "object_type": "constant:location"
                        },
                        "inputs": ["location"],
                        "outputs": ["subnet"],
                    },
                ],
                "fallback": {
                    "action": "operator_handoff",
                    "question": "Не удалось определить подсеть по локации."
                },
                "confidence_threshold": 0.7,
                "max_attempts": 1,
                "audit_required": True,
                "log_required": True,
            },
            {
                "profile_id": "profile.access_request.user_from_ad",
                "display_name": "Пользователь запроса доступа из AD",
                "status": "active",
                "description": "Заполняет идентификатор пользователя для запроса доступа по логину.",
                "target_slot_id": "user_id",
                "input_slots": ["user_login"],
                "output_slots": ["user_id"],
                "steps": [
                    {
                        "step_id": "lookup_requester",
                        "type": "tool_call",
                        "display_name": "Найти пользователя в AD",
                        "tool_name": "search_ad_users",
                        "endpoint_profile": "mock",
                        "operation_id": "search_ad_users",
                        "parameter_bindings": {
                            "login": "slot:user_login"
                        },
                        "inputs": ["user_login"],
                        "outputs": ["user_id"],
                    },
                ],
                "fallback": {
                    "action": "ask_user",
                    "question": "Уточните логин пользователя для запроса доступа."
                },
                "confidence_threshold": 0.7,
                "max_attempts": 1,
                "audit_required": True,
                "log_required": True,
            },
            {
                "profile_id": "profile.history.password_reset.resolved",
                "display_name": "История успешных сбросов пароля",
                "status": "planned",
                "description": "Ищет похожие закрытые заявки сброса пароля только в разрешенном сценарии и только с подтвержденным качеством.",
                "target_slot_id": "account_type",
                "input_slots": ["user_login"],
                "output_slots": ["account_type"],
                "steps": [
                    {
                        "step_id": "search_resolved_tickets",
                        "type": "ticket_history_search",
                        "display_name": "Найти похожие закрытые заявки",
                        "inputs": ["user_login"],
                        "outputs": ["account_type"],
                        "history_filter": {
                            "ticket_statuses": ["resolved", "closed"],
                            "time_window_days": 180,
                            "min_quality": "accepted",
                            "similarity_threshold": 0.78,
                            "allowed_fields": ["account_type"],
                            "excluded_categories": ["security_incident", "vip_case"]
                        }
                    }
                ],
                "fallback": {
                    "action": "ask_user",
                    "question": "Для какой учетной записи нужен сброс?"
                },
                "confidence_threshold": 0.78,
                "max_attempts": 1,
                "audit_required": True,
                "log_required": True,
            },
        ],
    }


def default_classification_routes() -> dict[str, Any]:
    scenario_names = {
        item["scenario_id"]: item["display_name"]
        for item in DEFAULT_SCENARIOS
    }
    route_data = [
        ("password_reset", "P3", "auto_agent", "Сброс пароля через runbook после подтверждения в MVP.", "pending_approval", ["пароль", "войти", "логин"]),
        ("software_issue", "P2", "agent_l1", "Диагностика приложения агентом и подтверждение Л1.", "pending_approval", ["не запускается", "ошибка", "приложение"]),
        ("hardware_issue", "P3", "agent_l1", "Проверка устройства и передача Л1 при необходимости.", "pending_approval", ["ноутбук", "устройство", "принтер"]),
        ("network_issue", "P1", "l2_major_incident", "Немедленная проверка массовости и эскалация при затронутых пользователях.", "escalation_required", ["сеть", "vpn", "недоступно"]),
        ("access_request", "P3", "approver", "Запрос руководителю на согласование доступа.", "pending_approval", ["доступ", "права", "группа"]),
        ("unknown", "P4", "l1_hint", "Передача Л1 с подсказками по вероятным категориям.", "escalation_required", ["помогите", "проблема"]),
    ]
    return {
        "schema_version": "1.0",
        "routes": [
            {
                "route_id": f"route.{scenario_id}",
                "display_name": f"Маршрут: {scenario_names.get(scenario_id, scenario_id)}",
                "priority": priority,
                "route": route,
                "action": action,
                "workflow_state_id": workflow_state_id,
                "confidence": {
                    "rules_min": 0.85,
                    "llm_min": 0.70,
                    "human_handoff_below": 0.50,
                },
                "rules": {
                    "keywords": keywords,
                    "negative_keywords": [],
                },
                "top_categories_on_low_confidence": 3,
            }
            for scenario_id, priority, route, action, workflow_state_id, keywords in route_data
        ],
    }


def default_orchestrator_policy() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "policies": [
            {
                "policy_id": f"policy.{item['scenario_id']}",
                "display_name": f"ReAct-политика: {item['display_name']}",
                "max_iterations": 6,
                "consecutive_tool_errors_to_escalate": 2,
                "stop_conditions": [
                    "user_confirmed_success",
                    "waiting_for_user",
                    "tool_errors_limit",
                    "iteration_limit",
                    "low_confidence",
                    "major_incident",
                ],
                "allowed_tool_classes": ["read_only", "action"],
            }
            for item in DEFAULT_SCENARIOS
        ],
    }


def default_tool_launch_matrix() -> dict[str, Any]:
    scenario_names = {
        item["scenario_id"]: item["display_name"]
        for item in DEFAULT_SCENARIOS
    }
    launches_by_scenario = {
        "password_reset": [
            _launch(
                "launch.password_reset.runbook",
                "start_systemcenter_runbook",
                ["user_login", "account_type"],
                {
                    "runbook_name": "constant:password_reset",
                    "user_login": "slot:user_login",
                    "account_type": "slot:account_type",
                    "environment": "constant:prod",
                },
                "operator_approval",
                "auto",
                "n8n",
                "start_systemcenter_runbook",
                "medium",
                "support_l1",
            ),
        ],
        "software_issue": [
            _launch(
                "launch.software_issue.diagnostic",
                "start_systemcenter_runbook",
                ["user_login", "app_name", "error_text", "device_name"],
                {
                    "runbook_name": "constant:software_diagnostic",
                    "user_login": "slot:user_login",
                    "app_name": "slot:app_name",
                    "device_name": "slot:device_name",
                    "environment": "constant:prod",
                },
                "operator_approval",
                "auto",
                "n8n",
                "start_systemcenter_runbook",
                "medium",
                "support_l1",
            ),
        ],
        "hardware_issue": [
            _launch(
                "launch.hardware_issue.cmdb",
                "query_cmdb_object",
                ["device_id"],
                {
                    "object_id": "slot:device_id",
                    "object_type": "constant:device",
                },
                "auto",
                "auto",
                "mock",
                "query_cmdb_object",
                "low",
                None,
            ),
        ],
        "network_issue": [
            _launch(
                "launch.network_issue.status",
                "check_zabbix_status",
                ["location", "symptom"],
                {
                    "service": "slot:symptom",
                    "location": "slot:location",
                    "environment": "constant:prod",
                },
                "auto",
                "auto",
                "n8n",
                "check_zabbix_status",
                "low",
                None,
            ),
        ],
        "access_request": [
            _launch(
                "launch.access_request.owner",
                "get_service_owner",
                ["resource_name"],
                {
                    "service": "slot:resource_name",
                },
                "auto",
                "auto",
                "mock",
                "get_service_owner",
                "low",
                None,
            ),
        ],
        "unknown": [
            _launch(
                "launch.unknown.known_incidents",
                "search_known_incidents",
                ["symptom"],
                {
                    "query": "slot:symptom",
                },
                "auto",
                "auto",
                "mock",
                "search_known_incidents",
                "low",
                None,
            ),
        ],
    }
    return {
        "schema_version": "1.0",
        "matrices": [
            {
                "matrix_id": f"matrix.{scenario_id}",
                "display_name": f"Матрица инструментов: {scenario_names.get(scenario_id, scenario_id)}",
                "launches": launches,
            }
            for scenario_id, launches in launches_by_scenario.items()
        ],
    }


def _launch(
    launch_id: str,
    tool_name: str,
    required_slots: list[str],
    parameter_bindings: dict[str, str],
    execution_level: str,
    target_execution_level: str,
    endpoint_profile: str,
    operation_id: str,
    risk_level: str,
    approval_role: str | None,
) -> dict[str, Any]:
    result = {
        "launch_id": launch_id,
        "tool_name": tool_name,
        "required_slots": required_slots,
        "parameter_bindings": parameter_bindings,
        "execution_level": execution_level,
        "target_execution_level": target_execution_level,
        "endpoint_profile": endpoint_profile,
        "operation_id": operation_id,
        "risk_level": risk_level,
        "audit_required": True,
        "log_required": True,
        "stop_on_error": True,
    }
    if approval_role:
        result["approval_role"] = approval_role
    return result


def default_prompt_packs() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "packs": [
            {
                "prompt_pack_id": f"prompt.{item['scenario_id']}",
                "scenario_id": item["scenario_id"],
                "display_name": f"Prompt pack: {item['display_name']}",
                "status": "active" if item["scenario_id"] != "unknown" else "planned",
                "active_version": "dev-structured-v1",
                "blocks": _prompt_blocks(item["display_name"]),
            }
            for item in DEFAULT_SCENARIOS
        ],
    }


def _prompt_blocks(display_name: str) -> dict[str, str]:
    return {
        "role_context": f"Ты AI ServiceDesk агент. Текущий сценарий: {display_name}. Работай только в границах утвержденной конфигурации сценария.",
        "behavior_principles": "Задавай один вопрос за раз. Не раскрывай внутренние инструменты пользователю. Пиши без жаргона и фиксируй недостающие данные.",
        "slot_schemas": "Собирай слоты в порядке кто -> что -> когда. Используй auto-fill источники до вопроса пользователю. При таймауте 3 минуты напомни, при 8 минутах сохрани черновик.",
        "classification_confidence": "Сначала используй правила и ключевые слова. Если confidence ниже 0.85, используй LLM few-shot. Если ниже 0.70, передай Л1 с топ-3 категориями. Если ниже 0.50, не принимай финальное решение автоматически.",
        "react_planning": "Используй цикл Думай -> Действуй -> Наблюдай. Максимум 6 итераций. При двух ошибках инструментов подряд эскалируй на Л2.",
        "tool_rules": "Проверяй required slots и parameter bindings перед каждым инструментом. Action tools в MVP запускаются только после подтверждения оператора, даже если target_execution_level равен auto.",
        "escalation_response": "Передавай на Л2 полный пакет: слоты, историю ReAct, результаты инструментов, гипотезу причины, остаток SLA и текст уведомления пользователя.",
    }


def build_prompt_preview(prompt_pack: dict[str, Any]) -> str:
    block_titles = {
        "role_context": "1. Роль и контекст",
        "behavior_principles": "2. Принципы поведения",
        "slot_schemas": "3. Схемы слотов",
        "classification_confidence": "4. Классификация и confidence",
        "react_planning": "5. ReAct и планирование",
        "tool_rules": "6. Правила инструментов",
        "escalation_response": "7. Эскалация и формат ответа",
    }
    blocks = prompt_pack.get("blocks", {})
    return "\n\n".join(
        f"{title}\n{blocks.get(key, '')}"
        for key, title in block_titles.items()
    )


def default_escalation_policies() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "policies": [
            {
                "policy_id": f"escalation.{item['scenario_id']}",
                "display_name": f"Решение и эскалация: {item['display_name']}",
                "auto_close": {
                    "requires_tool_success": True,
                    "requires_user_confirmation": True,
                },
                "waiting": {
                    "pause_sla": True,
                    "auto_close_after_hours": 24,
                },
                "l2_conditions": [
                    "two_tool_errors",
                    "iteration_limit",
                    "confidence_below_050",
                    "affected_users_threshold",
                    "policy_blocked",
                ],
                "major_incident": {
                    "affected_users_threshold": 10,
                    "notify_on_call": item["scenario_id"] == "network_issue",
                },
                "escalation_package": [
                    "slots",
                    "react_history",
                    "tool_results",
                    "agent_hypothesis",
                    "sla_remaining",
                    "user_notification",
                ],
                "user_notification_template": "Передаю обращение специалисту со всеми собранными данными. Мы сохранили контекст и вернемся с обновлением.",
            }
            for item in DEFAULT_SCENARIOS
        ],
    }


def default_prompt_catalog() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "status": "config_ready",
        "storage": "config_registry",
        "activation_mode": "draft_validate_activate",
        "prompts": [
            {
                "prompt_id": "system.default",
                "prompt_type": "system",
                "display_name": "Системный prompt по умолчанию",
                "active_version": "dev-static",
                "status": "planned",
                "description": "Целевой prompt для базового поведения AI.",
            },
            {
                "prompt_id": "classification.default",
                "prompt_type": "classification",
                "display_name": "Классификация обращения",
                "active_version": "dev-static",
                "status": "planned",
                "description": "Целевой prompt для выбора answer, clarification, escalation или action.",
            },
            {
                "prompt_id": "escalation.default",
                "prompt_type": "escalation",
                "display_name": "Эскалация",
                "active_version": "dev-static",
                "status": "planned",
                "description": "Целевой prompt для формулировки причины эскалации.",
            },
            {
                "prompt_id": "summarization.default",
                "prompt_type": "summarization",
                "display_name": "Суммаризация",
                "active_version": "dev-static",
                "status": "planned",
                "description": "Целевой prompt для краткого резюме кейса.",
            },
            {
                "prompt_id": "tool_selection.default",
                "prompt_type": "tool_selection",
                "display_name": "Выбор инструмента",
                "active_version": "dev-static",
                "status": "planned",
                "description": "Целевой prompt для выбора proposed action без права исполнения.",
            },
        ],
    }


def default_model_routing() -> dict[str, Any]:
    vllm_alias = os.getenv("LITELLM_MODEL_ALIAS", "local-opt-125m")
    openai_alias = os.getenv("OPENAI_MODEL_ALIAS", "openai-primary")
    openai_model = os.getenv("OPENAI_MODEL", "openai/gpt-4.1-mini")
    openai_key_env = os.getenv("OPENAI_API_KEY_ENV", "OPENAI_API_KEY")
    active_provider = os.getenv("MODEL_ACTIVE_PROVIDER", "vllm_cpu")
    if active_provider not in {"vllm_cpu", "openai"}:
        active_provider = "vllm_cpu"
    default_alias = openai_alias if active_provider == "openai" else vllm_alias
    vllm_context_length = int(os.getenv("VLLM_MAX_MODEL_LEN", "2048"))
    openai_context_length = int(os.getenv("OPENAI_CONTEXT_LENGTH", "128000"))
    return {
        "schema_version": "1.0",
        "active_provider": active_provider,
        "providers": {
            "vllm_cpu": {
                "enabled": True,
                "provider_type": "vllm_cpu",
                "display_name": "vLLM CPU локально",
                "base_url": os.getenv("LITELLM_BASE_URL", "http://127.0.0.1:4000/v1"),
                "model_alias": vllm_alias,
                "model": os.getenv("VLLM_MODEL", "facebook/opt-125m"),
                "api_key_env": os.getenv("LITELLM_API_KEY_ENV", "LITELLM_MASTER_KEY"),
                "api_key_required": False,
                "context_length": vllm_context_length,
                "temperature": float(os.getenv("VLLM_TEMPERATURE", "0")),
                "max_tokens": int(os.getenv("VLLM_MAX_TOKENS", "512")),
                "timeout_seconds": int(os.getenv("VLLM_TIMEOUT_SECONDS", "60")),
                "rate_limits": {
                    "requests_per_minute": int(os.getenv("VLLM_REQUESTS_PER_MINUTE", "30")),
                    "tokens_per_minute": int(os.getenv("VLLM_TOKENS_PER_MINUTE", "30000")),
                },
                "runtime": {
                    "dtype": os.getenv("VLLM_DTYPE", "float32"),
                    "max_num_seqs": os.getenv("VLLM_MAX_NUM_SEQS", "1"),
                    "cpu_kvcache_space": os.getenv("VLLM_CPU_KVCACHE_SPACE", "4"),
                },
            },
            "openai": {
                "enabled": True,
                "provider_type": "openai",
                "display_name": "OpenAI API",
                "base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
                "model_alias": openai_alias,
                "model": openai_model,
                "api_key_env": openai_key_env,
                "api_key_required": True,
                "context_length": openai_context_length,
                "temperature": float(os.getenv("OPENAI_TEMPERATURE", "0")),
                "max_tokens": int(os.getenv("OPENAI_MAX_TOKENS", "4096")),
                "timeout_seconds": int(os.getenv("OPENAI_TIMEOUT_SECONDS", "60")),
                "rate_limits": {
                    "requests_per_minute": int(os.getenv("OPENAI_REQUESTS_PER_MINUTE", "60")),
                    "tokens_per_minute": int(os.getenv("OPENAI_TOKENS_PER_MINUTE", "120000")),
                },
            },
        },
        "gateway": {
            "type": "litellm",
            "base_url": os.getenv("LITELLM_BASE_URL", "http://127.0.0.1:4000/v1"),
        },
        "default_model_alias": default_alias,
        "upstream_model": os.getenv("LITELLM_UPSTREAM_MODEL", "hosted_vllm/facebook/opt-125m")
        if active_provider == "vllm_cpu"
        else openai_model,
        "routing": {
            "default": default_alias,
            "classification": default_alias,
            "summarization": default_alias,
            "tool_selection": default_alias,
            "slot_resolution": default_alias,
        },
        "fallbacks": [
            {
                "from": openai_alias,
                "to": vllm_alias,
            }
        ] if active_provider == "openai" else [],
        "settings": {
            "temperature": 0,
            "context_length": openai_context_length if active_provider == "openai" else vllm_context_length,
            "rate_limits": {
                "requests_per_minute": 60,
            },
        },
        "runtime": {
            "active_backend": active_provider,
            "openai_api_key_configured": secret_env_configured(openai_key_env),
        },
    }
