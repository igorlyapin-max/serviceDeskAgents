from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, SchemaError
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012


REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACTS_ROOT = REPO_ROOT / "contracts"


class ContractValidationError(ValueError):
    def __init__(self, contract_name: str, errors: list[str]):
        self.contract_name = contract_name
        self.errors = errors
        super().__init__(f"{contract_name} validation failed: {'; '.join(errors)}")


@dataclass(frozen=True)
class SchemaEntry:
    name: str
    path: Path
    schema: dict[str, Any]


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


class ContractRegistry:
    """Loads JSON Schema contracts and validates runtime payloads."""

    def __init__(self, contracts_root: Path = CONTRACTS_ROOT):
        self.contracts_root = contracts_root
        self.entries = self._load_entries()
        self.schema_registry = self._build_schema_registry()
        self.validators = {
            entry.name: self._build_validator(entry)
            for entry in self.entries.values()
        }
        self.workflow_state_catalog = load_json(
            self.contracts_root / "workflow" / "workflow-state-catalog.json"
        )
        self.workflow_transition_rules = load_json(
            self.contracts_root / "workflow" / "workflow-transition-rules.json"
        )
        self.tool_catalog = load_json(
            self.contracts_root / "tools" / "tool-catalog.json"
        )
        self.integration_endpoint_catalog = load_json(
            self.contracts_root / "integrations" / "integration-endpoint-catalog.json"
        )
        self.knowledge_source_catalog = load_json(
            self.contracts_root / "knowledge" / "knowledge-source-catalog.json"
        )
        self.security_catalog = load_json(
            self.contracts_root / "security" / "security-catalog.json"
        )
        self.n8n_workflow_catalog = load_json(
            self.contracts_root / "config" / "n8n-workflow-catalog.json"
        )
        self._validate_static_contract_data()

    def _load_entries(self) -> dict[str, SchemaEntry]:
        paths = {
            "ai_decision": self.contracts_root / "decisions" / "ai-decision.schema.json",
            "proposed_action": self.contracts_root / "tools" / "proposed-action.schema.json",
            "tool_definition": self.contracts_root / "tools" / "tool-definition.schema.json",
            "tool_catalog": self.contracts_root / "tools" / "tool-catalog.schema.json",
            "tool_invocation": self.contracts_root / "tools" / "tool-invocation.schema.json",
            "tool_result": self.contracts_root / "tools" / "tool-result.schema.json",
            "integration_endpoint": self.contracts_root
            / "integrations"
            / "integration-endpoint.schema.json",
            "integration_endpoint_catalog": self.contracts_root
            / "integrations"
            / "integration-endpoint-catalog.schema.json",
            "integration_callback": self.contracts_root
            / "integrations"
            / "integration-callback.schema.json",
            "external_event": self.contracts_root
            / "integrations"
            / "external-event.schema.json",
            "execution_policy_result": self.contracts_root
            / "execution"
            / "execution-policy-result.schema.json",
            "execution_policy_rules": self.contracts_root
            / "execution"
            / "execution-policy-rules.schema.json",
            "action_gate_record": self.contracts_root
            / "execution"
            / "action-gate-record.schema.json",
            "action_gate_decision": self.contracts_root
            / "execution"
            / "action-gate-decision.schema.json",
            "action_gate_result": self.contracts_root
            / "execution"
            / "action-gate-result.schema.json",
            "model_output_invalid": self.contracts_root
            / "execution"
            / "model-output-invalid.schema.json",
            "knowledge_source": self.contracts_root
            / "knowledge"
            / "knowledge-source.schema.json",
            "knowledge_source_catalog": self.contracts_root
            / "knowledge"
            / "knowledge-source-catalog.schema.json",
            "knowledge_document": self.contracts_root
            / "knowledge"
            / "knowledge-document.schema.json",
            "knowledge_chunk": self.contracts_root
            / "knowledge"
            / "knowledge-chunk.schema.json",
            "knowledge_index_manifest": self.contracts_root
            / "knowledge"
            / "knowledge-index-manifest.schema.json",
            "retrieval_query": self.contracts_root
            / "knowledge"
            / "retrieval-query.schema.json",
            "retrieval_result": self.contracts_root
            / "knowledge"
            / "retrieval-result.schema.json",
            "knowledge_rebuild_result": self.contracts_root
            / "knowledge"
            / "knowledge-rebuild-result.schema.json",
            "feedback_request": self.contracts_root
            / "feedback"
            / "feedback-request.schema.json",
            "feedback_record": self.contracts_root
            / "feedback"
            / "feedback-record.schema.json",
            "evaluation_case": self.contracts_root
            / "feedback"
            / "evaluation-case.schema.json",
            "evaluation_run": self.contracts_root
            / "feedback"
            / "evaluation-run.schema.json",
            "evaluation_result": self.contracts_root
            / "feedback"
            / "evaluation-result.schema.json",
            "case_record": self.contracts_root / "cases" / "case-record.schema.json",
            "case_event": self.contracts_root / "cases" / "case-event.schema.json",
            "case_timeline": self.contracts_root / "cases" / "case-timeline.schema.json",
            "workflow_state": self.contracts_root / "workflow" / "workflow-state.schema.json",
            "workflow_state_catalog": self.contracts_root
            / "workflow"
            / "workflow-state-catalog.schema.json",
            "workflow_transition_rules": self.contracts_root
            / "workflow"
            / "workflow-transition-rules.schema.json",
            "security_catalog": self.contracts_root
            / "security"
            / "security-catalog.schema.json",
            "audit_event": self.contracts_root / "security" / "audit-event.schema.json",
            "prompt_catalog": self.contracts_root / "config" / "prompt-catalog.schema.json",
            "model_routing": self.contracts_root / "config" / "model-routing.schema.json",
            "n8n_workflow_catalog": self.contracts_root
            / "config"
            / "n8n-workflow-catalog.schema.json",
            "interaction_channels": self.contracts_root
            / "config"
            / "interaction-channels.schema.json",
            "attribute_resolution_profiles": self.contracts_root
            / "config"
            / "attribute-resolution-profiles.schema.json",
            "service_scenarios": self.contracts_root
            / "config"
            / "service-scenarios.schema.json",
            "slot_schemas": self.contracts_root / "config" / "slot-schemas.schema.json",
            "classification_routes": self.contracts_root
            / "config"
            / "classification-routes.schema.json",
            "orchestrator_policy": self.contracts_root
            / "config"
            / "orchestrator-policy.schema.json",
            "tool_launch_matrix": self.contracts_root
            / "config"
            / "tool-launch-matrix.schema.json",
            "prompt_packs": self.contracts_root / "config" / "prompt-packs.schema.json",
            "escalation_policies": self.contracts_root
            / "config"
            / "escalation-policies.schema.json",
            "config_draft": self.contracts_root / "config" / "config-draft.schema.json",
            "config_version": self.contracts_root / "config" / "config-version.schema.json",
        }
        return {
            name: SchemaEntry(name=name, path=path, schema=load_json(path))
            for name, path in paths.items()
        }

    def _build_schema_registry(self) -> Registry:
        resources: list[tuple[str, Resource[dict[str, Any]]]] = []
        for entry in self.entries.values():
            resource = Resource(contents=entry.schema, specification=DRAFT202012)
            schema_id = entry.schema.get("$id")
            if schema_id:
                resources.append((schema_id, resource))
            resources.append((entry.path.as_uri(), resource))
        return Registry().with_resources(resources)

    def _build_validator(self, entry: SchemaEntry) -> Draft202012Validator:
        Draft202012Validator.check_schema(entry.schema)
        return Draft202012Validator(entry.schema, registry=self.schema_registry)

    def _validate_static_contract_data(self) -> None:
        self.require_valid("workflow_state_catalog", self.workflow_state_catalog)
        self.require_valid("workflow_transition_rules", self.workflow_transition_rules)
        self.require_valid("tool_catalog", self.tool_catalog)
        self.require_valid("integration_endpoint_catalog", self.integration_endpoint_catalog)
        self.require_valid("knowledge_source_catalog", self.knowledge_source_catalog)
        self.require_valid("security_catalog", self.security_catalog)
        self.require_valid("n8n_workflow_catalog", self.n8n_workflow_catalog)
        state_ids = {
            state["id"]
            for state in self.workflow_state_catalog["states"]
        }
        unknown_state_ids = [
            rule["state_id"]
            for rule in self.workflow_transition_rules["rules"]
            if rule["state_id"] not in state_ids
        ]
        if unknown_state_ids:
            raise ContractValidationError(
                "workflow_transition_rules",
                [f"unknown state_id: {state_id}" for state_id in unknown_state_ids],
            )
        self._validate_tool_catalog_references()
        self._validate_knowledge_source_catalog()
        self._validate_security_catalog()
        self._validate_n8n_workflow_catalog()

    def _validate_tool_catalog_references(self) -> None:
        endpoint_by_id = {
            endpoint["endpoint_id"]: endpoint
            for endpoint in self.integration_endpoint_catalog["endpoints"]
        }

        errors = []
        endpoint_ids = [
            endpoint["endpoint_id"]
            for endpoint in self.integration_endpoint_catalog["endpoints"]
        ]
        duplicate_endpoint_ids = sorted(
            endpoint_id
            for endpoint_id in set(endpoint_ids)
            if endpoint_ids.count(endpoint_id) > 1
        )
        for endpoint_id in duplicate_endpoint_ids:
            errors.append(f"Дублируется endpoint_id: {endpoint_id}")

        for endpoint in self.integration_endpoint_catalog["endpoints"]:
            for operation_id, operation in endpoint["operations"].items():
                try:
                    Draft202012Validator.check_schema(operation["request_schema"])
                except SchemaError as error:
                    errors.append(
                        f"{endpoint['endpoint_id']}/{operation_id} request_schema невалидна: {error.message}"
                    )
                try:
                    Draft202012Validator.check_schema(operation["response_schema"])
                except SchemaError as error:
                    errors.append(
                        f"{endpoint['endpoint_id']}/{operation_id} response_schema невалидна: {error.message}"
                    )
                for event_type, async_contract in (operation.get("async_event_contracts") or {}).items():
                    for schema_key in ("result_schema", "progress_schema", "error_schema"):
                        schema = async_contract.get(schema_key)
                        if not schema:
                            continue
                        try:
                            Draft202012Validator.check_schema(schema)
                        except SchemaError as error:
                            errors.append(
                                f"{endpoint['endpoint_id']}/{operation_id}/{event_type} "
                                f"{schema_key} невалидна: {error.message}"
                            )
                if operation.get("mock_output") is not None:
                    validator = Draft202012Validator(operation["response_schema"])
                    for error in validator.iter_errors(operation["mock_output"]):
                        errors.append(
                            f"{endpoint['endpoint_id']}/{operation_id} mock_output не соответствует response_schema: {error.message}"
                        )

        seen_tool_names: set[str] = set()
        for tool in self.tool_catalog["tools"]:
            tool_name = tool["tool_name"]
            if tool_name in seen_tool_names:
                errors.append(f"Дублируется tool_name: {tool_name}")
            seen_tool_names.add(tool_name)

            try:
                Draft202012Validator.check_schema(tool["parameters_schema"])
            except SchemaError as error:
                errors.append(f"{tool_name} parameters_schema невалидна: {error.message}")
            try:
                Draft202012Validator.check_schema(tool["result_schema"])
            except SchemaError as error:
                errors.append(f"{tool_name} result_schema невалидна: {error.message}")

            for binding in tool["endpoint_bindings"]:
                endpoint = endpoint_by_id.get(binding["endpoint_id"])
                if not endpoint:
                    errors.append(
                        f"{tool_name} ссылается на неизвестный endpoint_id: {binding['endpoint_id']}"
                    )
                    continue
                if binding["operation_id"] not in endpoint["operations"]:
                    errors.append(
                        f"{tool_name} ссылается на неизвестный operation_id "
                        f"{binding['operation_id']} для endpoint {binding['endpoint_id']}"
                    )
                    continue
                operation = endpoint["operations"][binding["operation_id"]]
                mapping = binding.get("parameter_mapping", {})
                for required_parameter in operation["request_schema"].get("required", []):
                    if required_parameter not in mapping:
                        errors.append(
                            f"{tool_name} не заполняет обязательный параметр операции "
                            f"{binding['endpoint_id']}/{binding['operation_id']}: {required_parameter}"
                        )
                result_mapping = binding.get("result_mapping", {})
                for required_field in tool["result_schema"].get("required", []):
                    if required_field not in result_mapping:
                        errors.append(
                            f"{tool_name} не маппит обязательное поле результата "
                            f"{binding['endpoint_id']}/{binding['operation_id']}: {required_field}"
                        )

        if errors:
            raise ContractValidationError("tool_catalog", errors)

    def _validate_knowledge_source_catalog(self) -> None:
        errors = []
        source_ids = [
            source["source_id"]
            for source in self.knowledge_source_catalog["sources"]
        ]
        duplicate_source_ids = sorted(
            source_id
            for source_id in set(source_ids)
            if source_ids.count(source_id) > 1
        )
        for source_id in duplicate_source_ids:
            errors.append(f"Дублируется source_id: {source_id}")

        for source in self.knowledge_source_catalog["sources"]:
            if source["enabled"] is False and not source.get("disabled_reason"):
                errors.append(f"{source['source_id']} отключенный источник должен указывать disabled_reason")
            if source["connector_type"] == "local_files" and not source.get("path"):
                errors.append(f"{source['source_id']} источник local_files должен указывать path")

        if errors:
            raise ContractValidationError("knowledge_source_catalog", errors)

    def _validate_security_catalog(self) -> None:
        errors = []
        permission_ids = [
            permission["permission_id"]
            for permission in self.security_catalog["permissions"]
        ]
        role_ids = [
            role["role_id"]
            for role in self.security_catalog["roles"]
        ]
        user_ids = [
            user["user_id"]
            for user in self.security_catalog["users"]
        ]
        secret_ids = [
            secret["secret_id"]
            for secret in self.security_catalog["secret_references"]
        ]

        for permission_id in self._duplicates(permission_ids):
            errors.append(f"Дублируется permission_id: {permission_id}")
        for role_id in self._duplicates(role_ids):
            errors.append(f"Дублируется role_id: {role_id}")
        for user_id in self._duplicates(user_ids):
            errors.append(f"Дублируется user_id: {user_id}")
        for secret_id in self._duplicates(secret_ids):
            errors.append(f"Дублируется secret_id: {secret_id}")

        known_permissions = set(permission_ids)
        for role in self.security_catalog["roles"]:
            for permission_id in role["permissions"]:
                if permission_id not in known_permissions:
                    errors.append(
                        f"Роль {role['role_id']} ссылается на неизвестный permission_id: {permission_id}"
                    )

        known_roles = set(role_ids)
        for user in self.security_catalog["users"]:
            for role_id in user["roles"]:
                if role_id not in known_roles:
                    errors.append(
                        f"Пользователь {user['user_id']} ссылается на неизвестный role_id: {role_id}"
                    )

        if errors:
            raise ContractValidationError("security_catalog", errors)

    def _validate_n8n_workflow_catalog(self) -> None:
        errors = []
        workflow_ids = [
            workflow["workflow_id"]
            for workflow in self.n8n_workflow_catalog["workflows"]
        ]
        for workflow_id in self._duplicates(workflow_ids):
            errors.append(f"Дублируется workflow_id: {workflow_id}")

        endpoint_by_id = {
            endpoint["endpoint_id"]: endpoint
            for endpoint in self.integration_endpoint_catalog["endpoints"]
        }
        for workflow in self.n8n_workflow_catalog["workflows"]:
            endpoint = endpoint_by_id.get(workflow["endpoint_id"])
            if not endpoint:
                errors.append(
                    f"Workflow n8n {workflow['workflow_id']} ссылается на неизвестный endpoint_id: "
                    f"{workflow['endpoint_id']}"
                )
            else:
                for operation_id in workflow.get("operations", []):
                    if operation_id not in endpoint["operations"]:
                        errors.append(
                            f"Workflow n8n {workflow['workflow_id']} ссылается на неизвестную operation "
                            f"{operation_id} для endpoint {workflow['endpoint_id']}"
                        )
            callback_endpoint_id = workflow.get("callback_endpoint_id")
            if callback_endpoint_id and callback_endpoint_id not in endpoint_by_id:
                errors.append(
                    f"Workflow n8n {workflow['workflow_id']} ссылается на неизвестный "
                    f"callback_endpoint_id: {callback_endpoint_id}"
                )

        if errors:
            raise ContractValidationError("n8n_workflow_catalog", errors)

    def validate(self, contract_name: str, payload: Any) -> list[str]:
        validator = self.validators[contract_name]
        errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.path))
        return [
            self._format_error(error)
            for error in errors
        ]

    def require_valid(self, contract_name: str, payload: Any) -> None:
        errors = self.validate(contract_name, payload)
        if errors:
            raise ContractValidationError(contract_name, errors)

    @staticmethod
    def _format_error(error: Any) -> str:
        path = ".".join(str(part) for part in error.path)
        prefix = path if path else "$"
        return f"{prefix}: {error.message}"

    @staticmethod
    def _duplicates(values: list[str]) -> list[str]:
        return sorted(
            value
            for value in set(values)
            if values.count(value) > 1
        )
