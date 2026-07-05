from __future__ import annotations

import copy
import contextvars
import json
import os
import re
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request

from jsonschema import Draft202012Validator, SchemaError

from .action_gates import DEFAULT_STATE_DB_PATH, utc_now
from .contracts import CONTRACTS_ROOT, ContractRegistry, ContractValidationError, load_json
from .execution_context import (
    build_execution_reference_context,
    build_simulation_variable_context,
    template_refs,
    validate_template_refs,
)
from .http_client import urlopen_with_retry
from .privacy import redact_for_llm


_ACTIVE_PAYLOAD_OVERRIDES: contextvars.ContextVar[dict[str, dict[str, Any]] | None] = contextvars.ContextVar(
    "servicedesk_config_active_payload_overrides",
    default=None,
)


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

SLOT_CONTEXT_FIELDS = {
    "user_question",
    "case_source_ref",
    "extraction_instruction",
    "fallback_question",
    "operator_hint",
    "resolution_profile_id",
    "examples",
}

SLOT_METHOD_ALLOWED_FIELDS = {
    "user_question": {"user_question"},
    "case": {"case_source_ref"},
    "llm_extraction": {"extraction_instruction", "examples"},
    "resolution_profile": {"resolution_profile_id", "fallback_question"},
    "operator_manual": {"operator_hint"},
}

EXTERNAL_EVENT_TYPE_RE = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$")

CANONICAL_CAPABILITY_INPUT_CONTRACTS: dict[str, dict[str, tuple[str, ...]]] = {
    "provider_channel_repair_monitor": {
        "required": ("problem_url", "service_request", "from", "reply_to"),
        "non_empty_strings": ("problem_url", "service_request", "from", "reply_to"),
    },
}

SLOT_METHOD_REQUIRED_FIELD = {
    "user_question": "user_question",
    "case": "case_source_ref",
    "llm_extraction": "extraction_instruction",
    "resolution_profile": "resolution_profile_id",
    "operator_manual": "operator_hint",
}

DEFAULT_CONFIDENCE_THRESHOLDS = {
    "auto_accept_confidence": 0.85,
    "clarification_confidence": 0.70,
    "operator_handoff_confidence": 0.50,
    "min_extraction_confidence": 0.70,
}

DEFAULT_EDITOR_REFERENCE_HIDDEN_FIELDS = [
    {
        "field": "accepted_at",
        "contexts": ["capability_output", "step_output", "wait"],
        "display_name": "Accepted at",
        "description": "Техническое время принятия async-команды или ожидания.",
        "show_in_hints": False,
    },
    {
        "field": "action_id",
        "contexts": ["capability_output", "step_output"],
        "display_name": "Action ID",
        "description": "Технический идентификатор команды исполнения.",
        "show_in_hints": False,
    },
    {
        "field": "async_delivery",
        "contexts": ["capability_output", "step_output"],
        "display_name": "Async delivery",
        "description": "Служебная metadata доставки async-результата.",
        "show_in_hints": False,
    },
    {
        "field": "correlation_id",
        "contexts": ["capability_output", "step_output", "wait", "channel"],
        "display_name": "Correlation ID",
        "description": "Технический идентификатор корреляции сообщений и callback.",
        "show_in_hints": False,
    },
    {
        "field": "has_callback_url",
        "contexts": ["capability_output", "step_output"],
        "display_name": "Has callback URL",
        "description": "Служебный признак наличия callback URL.",
        "show_in_hints": False,
    },
    {
        "field": "invocation_id",
        "contexts": ["capability_output", "step_output"],
        "display_name": "Invocation ID",
        "description": "Технический идентификатор вызова endpoint.",
        "show_in_hints": False,
    },
    {
        "field": "message",
        "contexts": ["capability_output", "step_output"],
        "display_name": "Message",
        "description": "Служебное сообщение транспорта; бизнес-текст лучше брать из явных полей контракта.",
        "show_in_hints": False,
    },
    {
        "field": "result_topic",
        "contexts": ["capability_output", "step_output", "wait", "channel"],
        "display_name": "Result topic",
        "description": "Технический Kafka topic доставки результата.",
        "show_in_hints": False,
    },
    {
        "field": "result_transport",
        "contexts": ["capability_output", "step_output", "wait"],
        "display_name": "Result transport",
        "description": "Технический способ доставки результата async-вызова.",
        "show_in_hints": False,
    },
    {
        "field": "runbook_status",
        "contexts": ["capability_output", "step_output"],
        "display_name": "Runbook status",
        "description": "Транспортный статус запуска runbook, не итоговое бизнес-решение сценария.",
        "show_in_hints": False,
    },
    {
        "field": "wait_id",
        "contexts": ["capability_output", "step_output", "wait"],
        "display_name": "Wait ID",
        "description": "Технический идентификатор состояния ожидания.",
        "show_in_hints": False,
    },
    {
        "field": "idempotency_key",
        "contexts": ["capability_output", "step_output", "wait", "channel"],
        "display_name": "Idempotency key",
        "description": "Технический ключ идемпотентности доставки команды.",
        "show_in_hints": False,
    },
    {
        "field": "callback_url",
        "contexts": ["capability_output", "step_output", "wait", "channel"],
        "display_name": "Callback URL",
        "description": "Технический URL callback для async-результата.",
        "show_in_hints": False,
    },
    {
        "field": "event_type",
        "contexts": ["capability_output", "step_output", "wait"],
        "display_name": "Event type",
        "description": "Технический тип события во внешнем callback.",
        "show_in_hints": False,
    },
    {
        "field": "source",
        "contexts": ["capability_output", "step_output", "wait", "channel"],
        "display_name": "Source",
        "description": "Служебный источник события или параметра.",
        "show_in_hints": False,
    },
]

STEP_SOURCE_REF_RE = re.compile(
    r"^(step[1-9][0-9]*)\.capability\.([a-z][a-z0-9_.-]*)\.(input|output)\.([A-Za-z0-9_][A-Za-z0-9_.-]*)$"
)
PARAM_CAPABILITY_OUTPUT_REF_RE = re.compile(
    r"^\$\{paramCapability\.(?P<capability_id>[A-Za-z][A-Za-z0-9_.-]*)\.output\."
    r"(?P<field>[A-Za-z0-9_][A-Za-z0-9_.-]*)\}$"
)
STEP_CAPABILITY_OUTPUT_REF_RE = re.compile(
    r"^\$\{step\.(?P<step_id>step[1-9][0-9]*)\.capability\."
    r"(?P<capability_id>[A-Za-z][A-Za-z0-9_.-]*)\.output\."
    r"(?P<field>[A-Za-z0-9_][A-Za-z0-9_.-]*)\}$"
)

DEFAULT_CLIENT_WAITING_POLICY = {
    "auto_close_requires_client_confirmation": True,
    "pause_sla_on_client_wait": True,
    "client_wait_auto_close_after_hours": 24,
}

DEFAULT_EXTERNAL_EVENT_RESULT_TOPIC = "external.events"
DEFAULT_SERVICEDESK_TASK_TOPIC_TEMPLATE = "public.ittask.serviceDesk{agent_type}.task"
DEFAULT_SERVICEDESK_AGENT_TYPE = "Default"

DRAFT_VALIDATION_RELATED_DOMAINS = {
    "slot_schemas": {"attribute_resolution_profiles"},
    "attribute_resolution_profiles": {"slot_schemas"},
}

SCENARIO_LINKED_VALIDATION_DOMAINS = (
    "service_scenarios",
    "slot_schemas",
    "attribute_resolution_profiles",
    "capabilities",
    "capability_bindings",
    "mcp_environments",
    "classification_routes",
    "prompt_packs",
    "orchestrator_policy",
    "escalation_policies",
    "interaction_channels",
)

DEFAULT_CHANNEL_CAPABILITIES = {
    "supports_client_questions": True,
    "supports_operator_questions": True,
    "supports_work_order_creation": True,
    "supports_async_result": False,
}

DEFAULT_SERVICEDESK_CHANNEL_CAPABILITIES = {
    "supports_client_questions": False,
    "supports_operator_questions": False,
    "supports_work_order_creation": True,
    "supports_async_result": True,
}

DEFAULT_DEBUG_CHANNEL_CAPABILITIES = {
    "supports_client_questions": False,
    "supports_operator_questions": False,
    "supports_work_order_creation": False,
    "supports_async_result": False,
}

AGENT_OUTCOME_LABELS = {
    "success": "Завершено автоматически",
    "needs_review": "Требуется эскалация",
    "waiting": "Вопрос клиенту",
    "waiting_external_event": "Ожидает внешний результат",
    "escalated": "Требуется эскалация",
    "error": "Ошибка",
}

AGENT_OUTCOME_NEXT_STEPS = {
    "success": "Автообработка завершена; проверьте трассу и итоговые данные при необходимости.",
    "needs_review": "Передайте обращение оператору вместе с контекстом и трассой обработки.",
    "waiting": "Передайте клиенту уточняющий вопрос и продолжите обработку после ответа.",
    "waiting_external_event": "Дождитесь terminal ExternalEvent от внешнего исполнителя; после callback сценарий продолжит обработку.",
    "escalated": "Проверьте пакет передачи и передайте обращение в настроенный канал эскалации.",
    "error": "Исправьте конфигурацию, mock или контракт и повторите тестовый прогон.",
}

TRANSPORT_SECURITY_SELECTOR_KEYS = {"selected_transport", "result_transport"}

SIMULATION_RUN_MODES = {
    "config_check": {
        "display_name": "Проверка конфигурации",
        "allow_llm": False,
        "allow_readonly_integrations": False,
        "allow_mock_integrations": False,
        "allow_action_with_approval": False,
        "bypass_policy_gates": False,
        "async_diagnostics_level": "off",
    },
    "llm": {
        "display_name": "С моделью",
        "allow_llm": True,
        "allow_readonly_integrations": False,
        "allow_mock_integrations": False,
        "allow_action_with_approval": False,
        "bypass_policy_gates": False,
        "async_diagnostics_level": "off",
    },
    "llm_readonly": {
        "display_name": "С моделью и безопасными интеграциями",
        "allow_llm": True,
        "allow_readonly_integrations": True,
        "allow_mock_integrations": True,
        "allow_action_with_approval": False,
        "bypass_policy_gates": False,
        "async_diagnostics_level": "basic",
    },
    "approval_debug": {
        "display_name": "Отладочный запуск с подтверждениями",
        "allow_llm": True,
        "allow_readonly_integrations": True,
        "allow_mock_integrations": True,
        "allow_action_with_approval": True,
        "bypass_policy_gates": False,
        "async_diagnostics_level": "basic",
    },
    "operator_full_debug": {
        "display_name": "Полный операторский отладочный прогон",
        "allow_llm": True,
        "allow_readonly_integrations": True,
        "allow_mock_integrations": True,
        "allow_action_with_approval": True,
        "bypass_policy_gates": True,
        "async_diagnostics_level": "verbose",
    },
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

LEGACY_ENDPOINT_ID_MAP = {
    "mock.diagnostics": "mock",
    "mock.identity": "mock",
    "mock.cmdb": "mock",
    "mock.ownership": "mock",
    "mock.known_incidents": "mock",
    "mock.runbooks": "mock",
}

ENDPOINT_DISPLAY_NAME_OVERRIDES = {
    "mock": "Тестовое подключение интеграций",
}


def normalize_endpoint_id(value: str | None) -> str | None:
    if not value:
        return value
    return LEGACY_ENDPOINT_ID_MAP.get(value, value)


def normalize_endpoint_reference(item: dict[str, Any]) -> None:
    legacy_value = item.pop("endpoint_profile", None)
    endpoint_id = item.get("endpoint_id") or legacy_value
    if endpoint_id:
        item["endpoint_id"] = normalize_endpoint_id(str(endpoint_id))


def normalize_endpoint_binding(binding: dict[str, Any]) -> None:
    binding.pop("profile", None)
    normalize_endpoint_reference(binding)


def schema_composition_branches(schema: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(schema, dict):
        return []
    branches: list[dict[str, Any]] = []
    for key in ("allOf", "anyOf", "oneOf"):
        value = schema.get(key)
        if isinstance(value, list):
            branches.extend(item for item in value if isinstance(item, dict))
    return branches


def schema_properties(schema: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return {}
    properties = schema.get("properties", {})
    result = dict(properties) if isinstance(properties, dict) else {}
    for branch in schema_composition_branches(schema):
        for name, property_schema in schema_properties(branch).items():
            result.setdefault(name, property_schema)
    return result


def schema_required(schema: dict[str, Any] | None) -> list[str]:
    if not isinstance(schema, dict):
        return []
    required = schema.get("required", [])
    return required if isinstance(required, list) else []


def schema_type(schema: dict[str, Any] | None) -> str | None:
    if not isinstance(schema, dict):
        return None
    value = schema.get("type")
    if isinstance(value, list):
        return next((str(item) for item in value if item != "null"), None)
    return str(value) if value else None


def _schema_value_is_present(value: Any) -> bool:
    return value not in (None, "")


def coerce_schema_value(schema: dict[str, Any] | None, value: Any) -> Any:
    if not isinstance(schema, dict) or not isinstance(value, str):
        return value
    expected_type = schema_type(schema)
    text = value.strip()
    if expected_type == "integer" and re.fullmatch(r"-?\d+", text):
        try:
            return int(text)
        except ValueError:
            return value
    if expected_type == "number" and re.fullmatch(r"-?(?:\d+|\d+\.\d+)", text):
        try:
            return float(text) if "." in text else int(text)
        except ValueError:
            return value
    if expected_type == "boolean":
        lowered = text.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
    return value


def coerce_schema_parameter_values(
    schema: dict[str, Any] | None,
    parameters: dict[str, Any] | None,
) -> dict[str, Any]:
    result = copy.deepcopy(parameters or {})
    properties = schema_properties(schema)
    for parameter, value in list(result.items()):
        result[parameter] = coerce_schema_value(properties.get(parameter), value)
    return result


def schema_at_path(schema: dict[str, Any] | None, path: str | None) -> dict[str, Any] | None:
    if not isinstance(schema, dict) or not path:
        return None
    current: dict[str, Any] | None = schema
    for raw_part in str(path).replace("[]", "").split("."):
        if not raw_part:
            continue
        current_type = schema_type(current)
        if current_type == "array":
            item_schema = current.get("items", {}) if isinstance(current, dict) else {}
            current = item_schema if isinstance(item_schema, dict) else None
            if raw_part.isdigit():
                continue
        if not current:
            return None
        properties = schema_properties(current)
        current = properties.get(raw_part)
        if current is None:
            return None
    return current


def schema_declares_path(
    schema: dict[str, Any] | None,
    path: str | None,
    *,
    allow_nested_additional: bool = False,
) -> bool:
    if not isinstance(schema, dict) or not path:
        return False
    current: dict[str, Any] | None = schema
    traversed_explicit = schema_type(current) == "array"
    for raw_part in str(path).replace("[]", "").split("."):
        if not raw_part:
            continue
        current_type = schema_type(current)
        if current_type == "array":
            item_schema = current.get("items", {}) if isinstance(current, dict) else {}
            current = item_schema if isinstance(item_schema, dict) else None
            traversed_explicit = True
            if raw_part.isdigit():
                continue
        if not current:
            return False
        properties = schema_properties(current)
        if raw_part in properties:
            current = properties[raw_part]
            traversed_explicit = True
            continue
        additional = current.get("additionalProperties") if isinstance(current, dict) else None
        if allow_nested_additional and traversed_explicit and additional is True:
            return True
        if allow_nested_additional and traversed_explicit and isinstance(additional, dict):
            current = additional
            continue
        return False
    return True


def schema_allows_mapping_path(schema: dict[str, Any] | None, path: str | None) -> bool:
    if schema_declares_path(schema, path, allow_nested_additional=True):
        return True
    if not isinstance(schema, dict) or not path:
        return False
    first_part = str(path).replace("[]", "").split(".", 1)[0]
    if not first_part:
        return False
    additional = schema.get("additionalProperties")
    return additional is True or isinstance(additional, dict)


def schemas_are_type_compatible(source_schema: dict[str, Any] | None, target_schema: dict[str, Any] | None) -> bool:
    source_type = schema_type(source_schema)
    target_type = schema_type(target_schema)
    if not source_type or not target_type:
        return True
    if source_type == target_type:
        return True
    return source_type == "integer" and target_type == "number"


def default_request_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": True,
    }


def default_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": True,
    }


def infer_schema_from_value(value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int) and not isinstance(value, bool):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "number"}
    if isinstance(value, str):
        return {"type": "string"}
    if isinstance(value, list):
        item_schema = infer_schema_from_value(value[0]) if value else {}
        result = {"type": "array"}
        if item_schema:
            result["items"] = item_schema
        return result
    if isinstance(value, dict):
        return infer_object_schema_from_sample(value)
    return {}


def infer_object_schema_from_sample(value: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, dict) or not value:
        return default_response_schema()
    return {
        "type": "object",
        "required": sorted(value.keys()),
        "properties": {
            key: infer_schema_from_value(item)
            for key, item in value.items()
        },
        "additionalProperties": True,
    }


def compact_agent_dict(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item
        for key, item in value.items()
        if item not in (None, "", [], {})
    }


def build_agent_outcome_from_simulation(simulation: dict[str, Any]) -> dict[str, Any]:
    slot_values = simulation.get("slot_values") or {}
    missing_slots = list(simulation.get("missing_slots") or [])
    filled_slots = [
        slot_id
        for slot_id, value in slot_values.items()
        if (value or {}).get("value") not in (None, "")
    ]
    ready_calls = list(simulation.get("ready_tool_launches") or [])
    blocked_calls = list(simulation.get("blocked_tool_launches") or [])
    trace = list(simulation.get("execution_trace") or [])
    error_events = [
        item
        for item in trace
        if str(item.get("status") or "").lower() in {"error", "failed"}
    ]
    low_confidence_slots = [
        slot_id
        for slot_id, value in slot_values.items()
        if (value or {}).get("status") in {"candidate_below_threshold", "model_unavailable"}
        or (value or {}).get("threshold_decision") == "accepted_for_test_below_auto_accept"
    ]
    ambiguous_resolution = [
        item
        for item in simulation.get("attribute_resolution") or []
        if item.get("status") in {
            "ambiguous",
            "no_result",
            "question_required",
            "llm_resolution_pending",
            "resolution_pending",
            "blocked_by_configuration",
        }
    ]
    pending_live_resolution = [
        item
        for item in simulation.get("attribute_resolution") or []
        if item.get("status") == "pending_live_execution"
        or item.get("decision") == "execute_capability"
    ]
    missing_slot_set = set(missing_slots)
    configuration_blocks = []
    for item in blocked_calls:
        unknown_required_slots = item.get("unknown_required_slots") or []
        unresolved_parameters = [
            slot_id
            for slot_id in item.get("missing_parameter_slots") or []
            if slot_id not in missing_slot_set
        ]
        if unknown_required_slots or unresolved_parameters:
            configuration_blocks.append(item)
    final_decision = simulation.get("final_decision")
    operator_escalation = simulation.get("operator_escalation") or {}

    if error_events or configuration_blocks or final_decision == "blocked_by_configuration":
        status = "error"
        summary = "Агент не смог продолжить из-за ошибки конфигурации, контракта или выполнения."
    elif operator_escalation.get("required"):
        status = "escalated"
        summary = operator_escalation.get("reason") or "Агент завершил автообработку и подготовил передачу оператору."
    elif pending_live_resolution:
        status = "waiting_external_event"
        summary = "Агент ожидает внешний результат capability."
    elif simulation.get("awaiting_client_response") or simulation.get("next_question"):
        status = "waiting"
        summary = "Агенту не хватает данных: сформирован вопрос клиенту."
    elif missing_slots:
        status = "waiting"
        summary = "Агенту не хватает обязательных данных: нужно задать вопрос клиенту."
    elif (
        low_confidence_slots
        or ambiguous_resolution
        or final_decision in {"pending_auto_fill", "waiting_operator_approval"}
    ):
        status = "escalated"
        summary = "Агент не может надежно продолжить автоматически: требуется передача оператору."
    else:
        status = "success"
        summary = "Агент собрал обязательные данные и завершил тестовый прогон автоматически."

    return {
        "schema_version": "1.0",
        "status": status,
        "label": AGENT_OUTCOME_LABELS[status],
        "summary": summary,
        "next_step": AGENT_OUTCOME_NEXT_STEPS[status],
        "filled_slots": filled_slots,
        "missing_slots": missing_slots,
        "low_confidence_slots": low_confidence_slots,
        "ambiguous_resolution_count": len(ambiguous_resolution),
        "ready_capabilities": [
            compact_agent_dict(
                {
                    "capability_id": item.get("capability_id"),
                    "mcp_environment_id": item.get("mcp_environment_id"),
                    "mcp_tool_name": item.get("mcp_tool_name"),
                    "execution_mode": item.get("execution_mode"),
                    "status": item.get("status", "ready"),
                    "parameters": item.get("parameters"),
                }
            )
            for item in ready_calls
            if item.get("capability_id")
        ],
        "blocked_capabilities": [
            compact_agent_dict(
                {
                    "capability_id": item.get("capability_id"),
                    "mcp_environment_id": item.get("mcp_environment_id"),
                    "mcp_tool_name": item.get("mcp_tool_name"),
                    "block_reasons": item.get("block_reasons"),
                    "missing_slots": item.get("missing_slots"),
                    "missing_parameter_slots": item.get("missing_parameter_slots"),
                    "unknown_required_slots": item.get("unknown_required_slots"),
                }
            )
            for item in blocked_calls
            if item.get("capability_id")
        ],
        "error_count": len(error_events),
        "final_decision": final_decision,
    }


def string_property(title: str | None = None) -> dict[str, Any]:
    result = {"type": "string", "minLength": 1}
    if title:
        result["title"] = title
    return result


def object_schema(required: list[str], properties: dict[str, dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "type": "object",
        "properties": copy.deepcopy(properties),
        "additionalProperties": True,
    }
    if required:
        result["required"] = required
    return result


SYSTEM_OPERATION_PARAMETERS = {"invocation"}


def schema_parameter_default(
    schema: dict[str, Any] | None,
    parameter_name: str,
) -> tuple[bool, Any]:
    parameter_schema = schema_properties(schema).get(parameter_name)
    if not isinstance(parameter_schema, dict):
        return False, None
    for key in ("default", "x-servicedesk-default"):
        if key in parameter_schema:
            return True, copy.deepcopy(parameter_schema[key])
    return False, None


def _append_required_group(
    groups: list[list[str]],
    seen: set[tuple[str, ...]],
    alternatives: list[str],
) -> None:
    clean = [
        item
        for item in dict.fromkeys(str(value) for value in alternatives if value)
        if item not in SYSTEM_OPERATION_PARAMETERS
    ]
    if not clean:
        return
    key = tuple(sorted(clean))
    if key in seen:
        return
    seen.add(key)
    groups.append(clean)


def schema_required_parameter_groups(schema: dict[str, Any] | None) -> list[list[str]]:
    groups: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()

    def visit(item: dict[str, Any] | None) -> None:
        if not isinstance(item, dict):
            return
        for required_name in schema_required(item):
            _append_required_group(groups, seen, [required_name])
        for branch in item.get("allOf") or []:
            if isinstance(branch, dict):
                visit(branch)
        for composition_key in ("anyOf", "oneOf"):
            alternatives: list[str] = []
            for branch in item.get(composition_key) or []:
                if not isinstance(branch, dict):
                    continue
                branch_required = [
                    str(required_name)
                    for required_name in schema_required(branch)
                    if required_name not in SYSTEM_OPERATION_PARAMETERS
                ]
                if len(branch_required) == 1:
                    alternatives.append(branch_required[0])
                else:
                    for required_name in branch_required:
                        _append_required_group(groups, seen, [required_name])
            if alternatives:
                _append_required_group(groups, seen, alternatives)

    visit(schema)
    return groups


def missing_required_parameter_groups(
    schema: dict[str, Any] | None,
    parameters: dict[str, Any] | None,
) -> list[list[str]]:
    values = parameters or {}
    missing = []
    for group in schema_required_parameter_groups(schema):
        if any(_schema_value_is_present(values.get(parameter)) for parameter in group):
            continue
        if any(schema_parameter_default(schema, parameter)[0] for parameter in group):
            continue
        missing.append(group)
    return missing


def format_required_parameter_group(group: list[str]) -> str:
    return " или ".join(group)


def apply_schema_parameter_defaults(
    schema: dict[str, Any] | None,
    parameters: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    result = coerce_schema_parameter_values(schema, parameters)
    applied: dict[str, Any] = {}
    for group in schema_required_parameter_groups(schema):
        if any(_schema_value_is_present(result.get(parameter)) for parameter in group):
            continue
        for parameter in group:
            has_default, default_value = schema_parameter_default(schema, parameter)
            if not has_default:
                continue
            properties = schema_properties(schema)
            value = coerce_schema_value(properties.get(parameter), copy.deepcopy(default_value))
            result[parameter] = value
            applied[parameter] = value
            break
    return coerce_schema_parameter_values(schema, result), applied


def normalize_capability_contracts(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(payload)
    for capability in normalized.get("capabilities") or []:
        if not isinstance(capability, dict):
            continue
        canonical = CANONICAL_CAPABILITY_INPUT_CONTRACTS.get(str(capability.get("capability_id") or ""))
        if not canonical:
            continue
        schema = capability.get("input_schema")
        if not isinstance(schema, dict):
            schema = {"type": "object", "properties": {}}
            capability["input_schema"] = schema
        schema.setdefault("type", "object")
        properties = schema.get("properties")
        if not isinstance(properties, dict):
            properties = {}
            schema["properties"] = properties
        required = [
            str(item)
            for item in schema.get("required", [])
            if item not in (None, "")
        ]
        for parameter in canonical.get("required", ()):
            if parameter not in required:
                required.append(parameter)
        schema["required"] = required
        for parameter in canonical.get("non_empty_strings", ()):
            property_schema = properties.get(parameter)
            if not isinstance(property_schema, dict):
                property_schema = {}
            property_schema.setdefault("type", "string")
            if property_schema.get("type") == "string":
                try:
                    current_min_length = int(property_schema.get("minLength") or 0)
                except (TypeError, ValueError):
                    current_min_length = 0
                property_schema["minLength"] = max(current_min_length, 1)
            properties[parameter] = property_schema
    return normalized


def constant_source_ref(value: Any) -> str:
    if isinstance(value, bool):
        return f"constant:{str(value).lower()}"
    if isinstance(value, (int, float)):
        return f"constant:{value}"
    if isinstance(value, (dict, list)):
        return f"constant:{json.dumps(value, ensure_ascii=False, sort_keys=True)}"
    return f"constant:{value}"


def parameter_mapping_with_schema_defaults(
    schema: dict[str, Any] | None,
    mapping: dict[str, Any] | None,
) -> dict[str, str]:
    result = {str(key): str(value) for key, value in (mapping or {}).items()}
    for group in schema_required_parameter_groups(schema):
        if any(parameter in result for parameter in group):
            continue
        for parameter in group:
            has_default, default_value = schema_parameter_default(schema, parameter)
            if not has_default:
                continue
            result[parameter] = constant_source_ref(default_value)
            break
    return result


def snake_case_name(value: str) -> str:
    return re.sub(r"(?<!^)([A-Z])", r"_\1", str(value or "")).lower()


def schema_marks_alias(schema: dict[str, Any] | None) -> bool:
    if not isinstance(schema, dict):
        return False
    description = str(schema.get("description") or "").strip().lower()
    return (
        description.startswith("alias")
        or "alias accepted" in description
        or "alias, принимаемый" in description
    )


def is_endpoint_parameter_alias(
    name: str,
    names: set[str],
    schema: dict[str, Any] | None = None,
) -> bool:
    value = str(name or "")
    if schema_marks_alias(schema) and "_" not in value:
        return True
    if not any(character.isupper() for character in value):
        return False
    canonical_name = snake_case_name(value)
    return canonical_name != value and canonical_name in names


def visible_endpoint_parameter_schema(schema: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return default_request_schema()
    normalized = copy.deepcopy(schema)
    properties = schema_properties(normalized)
    if not properties:
        return normalized
    property_names = set(properties)
    hidden_names = {
        name
        for name in property_names
        if (
            name in SYSTEM_OPERATION_PARAMETERS
            or is_endpoint_parameter_alias(name, property_names, properties.get(name))
        )
    }
    if not hidden_names:
        return normalized
    for hidden_name in hidden_names:
        hidden_schema = properties.get(hidden_name)
        canonical_name = snake_case_name(hidden_name)
        canonical_schema = properties.get(canonical_name)
        if not isinstance(hidden_schema, dict) or not isinstance(canonical_schema, dict):
            continue
        for default_key in ("default", "x-servicedesk-default"):
            if default_key in hidden_schema and default_key not in canonical_schema:
                canonical_schema[default_key] = copy.deepcopy(hidden_schema[default_key])
    normalized["properties"] = {
        name: property_schema
        for name, property_schema in properties.items()
        if name not in hidden_names
    }
    normalized["required"] = [
        name
        for name in schema_required(normalized)
        if name not in hidden_names
    ]
    return normalized


CANONICAL_CAPABILITY_PARAMETER_SCHEMAS = {
    "check_zabbix_status": object_schema(["target_ref"], {"target_ref": string_property()}),
    "query_cmdb_object": object_schema(["object_ref"], {"object_ref": string_property()}),
    "get_service_owner": object_schema(["target_ref"], {"target_ref": string_property()}),
    "search_known_incidents": object_schema(["query"], {"query": string_property()}),
    "wait_for_email_by_ticket": object_schema(
        ["ticket_number", "poll_interval_minutes", "timeout_minutes"],
        {
            "ticket_number": string_property("Номер заявки"),
            "poll_interval_minutes": {"type": "integer", "title": "Интервал опроса, минут", "default": 1},
            "timeout_minutes": {"type": "integer", "title": "Таймаут ожидания, минут", "default": 15},
        },
    ),
    "start_systemcenter_runbook": object_schema(
        ["runbook_code"],
        {
            "runbook_code": string_property("Код ранбука"),
            "user_login": string_property("Логин пользователя"),
            "account_type": string_property("Тип учетной записи"),
            "device_name": string_property("Имя устройства"),
            "app_name": string_property("Приложение"),
            "error_text": string_property("Текст ошибки"),
        },
    ),
}

CANONICAL_OPERATION_REQUEST_SCHEMAS = {
    "check_zabbix_status": object_schema(["target_ref"], {"target_ref": string_property()}),
    "query_cmdb_object": object_schema(["object_ref"], {"object_ref": string_property()}),
    "get_service_owner": object_schema(["target_ref"], {"target_ref": string_property()}),
    "search_known_incidents": object_schema(["query"], {"query": string_property()}),
    "start_systemcenter_runbook": object_schema(
        ["runbook_code"],
        {
            "runbook_code": string_property("Код ранбука"),
            "login": string_property("Логин пользователя"),
            "account_type": string_property("Тип учетной записи"),
            "device_name": string_property("Имя устройства"),
            "app_name": string_property("Приложение"),
            "error_text": string_property("Текст ошибки"),
        },
    ),
}


CANONICAL_OPERATION_RESPONSE_SCHEMAS = {
    "check_zabbix_status": object_schema(
        ["service_status", "message"],
        {
            "service_status": string_property(),
            "message": string_property(),
        },
    ),
    "query_cmdb_object": object_schema(
        ["object_found", "message"],
        {
            "object_found": {"type": "boolean"},
            "device_model": string_property("Модель устройства"),
            "subnet": string_property("Подсеть"),
            "message": string_property(),
        },
    ),
    "get_service_owner": object_schema(
        ["owner_team", "message"],
        {
            "owner_team": string_property(),
            "message": string_property(),
        },
    ),
    "search_known_incidents": object_schema(
        ["matches", "message"],
        {
            "matches": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "message": string_property(),
        },
    ),
    "search_ad_users": object_schema(
        ["candidate_count", "users", "message"],
        {
            "candidate_count": {"type": "integer", "minimum": 0},
            "users": {
                "type": "array",
                "items": object_schema(
                    [],
                    {
                        "login": string_property("Логин пользователя"),
                        "user_id": string_property("ID пользователя"),
                        "display_name": string_property("Отображаемое имя"),
                        "department": string_property("Подразделение"),
                        "device_name": string_property("Основное устройство"),
                        "email": string_property("Email"),
                        "title": string_property("Должность"),
                        "employee_number": string_property("Табельный номер"),
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                ),
            },
            "message": string_property(),
        },
    ),
    "start_systemcenter_runbook": object_schema(
        ["runbook_status", "message"],
        {
            "runbook_status": string_property(),
            "message": string_property(),
        },
    ),
}


def normalize_tool_launch_parameter_bindings(launch: dict[str, Any]) -> None:
    original_bindings = dict(launch.get("parameter_bindings") or {})
    bindings = dict(original_bindings)
    tool_name = str(launch.get("tool_name") or "")
    launch_id = str(launch.get("launch_id") or "")

    if tool_name == "start_systemcenter_runbook":
        if "password_reset" in launch_id:
            bindings = {
                "runbook_code": "constant:password_reset",
                "user_login": "slot:user_login",
            }
        elif "software_issue" in launch_id:
            bindings = {
                "runbook_code": "constant:software_diagnostic",
                "user_login": "slot:user_login",
                "device_name": "slot:device_name",
                "app_name": "slot:app_name",
                "error_text": "slot:error_text",
            }
        else:
            bindings = {
                "runbook_code": bindings.get("runbook_code")
                or "constant:manual_runbook"
            }
    elif tool_name == "check_zabbix_status":
        bindings = {
            "target_ref": bindings.get("target_ref")
            or original_bindings.get("location")
            or original_bindings.get("service")
            or "context:target_ref"
        }
    elif tool_name == "get_service_owner":
        bindings = {
            "target_ref": bindings.get("target_ref")
            or original_bindings.get("service")
            or original_bindings.get("resource_name")
            or "context:target_ref"
        }
    elif tool_name == "query_cmdb_object":
        bindings = {
            "object_ref": bindings.get("object_ref")
            or original_bindings.get("object_id")
            or "context:object_ref"
        }

    canonical_schema = canonical_capability_parameter_schema(tool_name)
    if canonical_schema:
        allowed_parameters = set(schema_required(canonical_schema))
        allowed_parameters.update(schema_properties(canonical_schema))
        bindings = {
            parameter_name: source_ref
            for parameter_name, source_ref in bindings.items()
            if parameter_name in allowed_parameters
        }
    launch["parameter_bindings"] = bindings
    required_slots = []
    for source_ref in bindings.values():
        source, _, value = str(source_ref).partition(":")
        if source == "slot" and value and value not in required_slots:
            required_slots.append(value)
    launch["required_slots"] = required_slots
    normalize_tool_launch_completion_policy(launch)


def normalize_tool_launch_completion_policy(launch: dict[str, Any]) -> None:
    policy = copy.deepcopy(launch.get("completion_policy") or {})
    mode = str(policy.get("mode") or "sync")
    if mode not in {"sync", "external_event", "timer_wait"}:
        mode = "sync"
    if mode == "sync":
        launch["completion_policy"] = {
            "mode": "sync",
            "max_wait_seconds": 0,
            "timeout_action": "resume_agent",
        }
        return
    max_wait_seconds = int(policy.get("max_wait_seconds") or 86400)
    result = {
        "mode": mode,
        "max_wait_seconds": max_wait_seconds,
        "timeout_action": str(policy.get("timeout_action") or "escalate_operator"),
    }
    check_interval_seconds = int(policy.get("check_interval_seconds") or 0)
    if check_interval_seconds:
        result["check_interval_seconds"] = check_interval_seconds
    expected_event_type = str(policy.get("expected_event_type") or "").strip()
    if expected_event_type:
        result["expected_event_type"] = expected_event_type
    elif mode == "external_event":
        result["expected_event_type"] = f"{launch.get('operation_id') or launch.get('tool_name') or 'operation'}_completed"
    if mode == "external_event":
        result_transport = str(policy.get("result_transport") or "http_callback")
        result["result_transport"] = result_transport
        result_topic = str(policy.get("result_topic") or "").strip()
        if result_topic:
            result["result_topic"] = result_topic
    launch["completion_policy"] = result


def async_event_types_for_operation(operation: dict[str, Any] | None) -> list[str]:
    if not isinstance(operation, dict):
        return []
    async_contracts = operation.get("async_event_contracts") or {}
    if not isinstance(async_contracts, dict):
        return []
    return [
        event_type
        for event_type, contract in sorted(async_contracts.items())
        if isinstance(contract, dict) and contract.get("contract_status") != "broken"
    ]


def operation_response_looks_like_async_ack(operation: dict[str, Any] | None) -> bool:
    if not isinstance(operation, dict):
        return False
    response_schema = operation.get("response_schema")
    properties = schema_properties(response_schema)
    required = set(schema_required(response_schema))
    return (
        "async_delivery" in properties
        and "runbook_status" in properties
        and (
            "async_delivery" in required
            or properties.get("async_delivery", {}).get("const") is True
        )
    )


def operation_terminal_result_schema(operation: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(operation, dict):
        return None
    async_contracts = operation.get("async_event_contracts") or {}
    if len(async_contracts) == 1:
        contract = next(iter(async_contracts.values()))
        if isinstance(contract, dict) and isinstance(contract.get("result_schema"), dict):
            return contract["result_schema"]
    return operation.get("response_schema")


def default_async_completion_policy_for_operation(
    operation: dict[str, Any] | None,
    *,
    operation_id: str | None = None,
    delivery_defaults: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    event_types = async_event_types_for_operation(operation)
    if len(event_types) != 1:
        return None
    defaults = copy.deepcopy(delivery_defaults or {})
    result_delivery = (
        operation.get("extensions", {}).get("result_delivery")
        if isinstance(operation, dict) and isinstance(operation.get("extensions"), dict)
        else None
    )
    if isinstance(result_delivery, dict):
        if not defaults.get("result_transport") and result_delivery.get("default_transport"):
            defaults["result_transport"] = result_delivery["default_transport"]
        if not defaults.get("result_topic") and result_delivery.get("default_result_topic"):
            defaults["result_topic"] = result_delivery["default_result_topic"]
    policy = {
        "mode": "external_event",
        "max_wait_seconds": int(defaults.get("max_wait_seconds") or 86400),
        "timeout_action": str(defaults.get("timeout_action") or "escalate_operator"),
        "expected_event_type": event_types[0],
        "result_transport": str(defaults.get("result_transport") or "http_callback"),
        "result_topic": str(defaults.get("result_topic") or DEFAULT_EXTERNAL_EVENT_RESULT_TOPIC),
    }
    launch = {
        "operation_id": operation_id,
        "completion_policy": policy,
    }
    normalize_tool_launch_completion_policy(launch)
    return launch["completion_policy"]


def select_tool_binding(
    tool: dict[str, Any] | None,
    *,
    endpoint_id: str | None = None,
    operation_id: str | None = None,
) -> dict[str, Any] | None:
    bindings = list((tool or {}).get("endpoint_bindings") or [])
    if not bindings:
        return None
    if endpoint_id or operation_id:
        for binding in bindings:
            if endpoint_id and binding.get("endpoint_id") != endpoint_id:
                continue
            if operation_id and binding.get("operation_id") != operation_id:
                continue
            return binding
        return None
    return bindings[0]


def source_ref_slot_ids(mapping: dict[str, Any] | None) -> list[str]:
    slot_ids: list[str] = []
    for source_ref in (mapping or {}).values():
        source, separator, value = str(source_ref).partition(":")
        if separator == ":" and source == "slot" and value and value not in slot_ids:
            slot_ids.append(value)
    return slot_ids


def required_source_ref_slot_ids(
    schema: dict[str, Any] | None,
    mapping: dict[str, Any] | None,
) -> list[str]:
    required_inputs = {
        name
        for group in schema_required_parameter_groups(schema)
        for name in group
    }
    required_mapping = {
        str(name): source_ref
        for name, source_ref in (mapping or {}).items()
        if str(name) in required_inputs
    }
    return source_ref_slot_ids(required_mapping)


def contains_transport_delivery_selector(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            key in TRANSPORT_SECURITY_SELECTOR_KEYS or contains_transport_delivery_selector(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(contains_transport_delivery_selector(item) for item in value)
    return False


def endpoint_transport_security(endpoint: dict[str, Any] | None) -> dict[str, Any]:
    extensions = (endpoint or {}).get("extensions") or {}
    transport_security = extensions.get("transport_security") or {}
    return transport_security if isinstance(transport_security, dict) else {}


def endpoint_has_transport_security(endpoint: dict[str, Any] | None, transport: str) -> bool:
    security = endpoint_transport_security(endpoint)
    section = security.get(transport)
    return isinstance(section, dict) and bool(section)


def canonical_capability_parameter_schema(tool_name: str | None) -> dict[str, Any] | None:
    schema = CANONICAL_CAPABILITY_PARAMETER_SCHEMAS.get(str(tool_name or ""))
    return copy.deepcopy(schema) if schema else None


def canonical_operation_request_schema(operation_id: str | None) -> dict[str, Any] | None:
    schema = CANONICAL_OPERATION_REQUEST_SCHEMAS.get(str(operation_id or ""))
    return copy.deepcopy(schema) if schema else None


def canonical_operation_response_schema(operation_id: str | None) -> dict[str, Any] | None:
    schema = CANONICAL_OPERATION_RESPONSE_SCHEMAS.get(str(operation_id or ""))
    return copy.deepcopy(schema) if schema else None


def normalize_operation_definition(operation_id: str | None, operation: dict[str, Any]) -> None:
    operation.setdefault("request_schema", default_request_schema())
    canonical_schema = canonical_operation_request_schema(operation_id)
    if canonical_schema:
        operation["request_schema"] = canonical_schema
    canonical_response_schema = canonical_operation_response_schema(operation_id)
    if canonical_response_schema and "response_schema" not in operation:
        operation["response_schema"] = canonical_response_schema
    elif operation.get("mock_output") and "response_schema" not in operation:
        operation["response_schema"] = infer_object_schema_from_sample(operation.get("mock_output"))
    else:
        operation.setdefault("response_schema", default_response_schema())
    operation.setdefault("contract_version", "1.0")
    operation.setdefault("contract_status", "valid")
    operation.setdefault("async_event_contracts", {})
    for event_type, contract in list(operation.get("async_event_contracts", {}).items()):
        contract.setdefault("display_name", humanize_config_id(event_type))
        contract.setdefault("statuses", ["progress", "success", "error", "timeout", "cancelled"])
        contract.setdefault("contract_version", operation.get("contract_version", "1.0"))
        contract.setdefault("contract_status", operation.get("contract_status", "valid"))


def merge_legacy_integration_endpoints(payload: dict[str, Any]) -> dict[str, Any]:
    endpoints_by_id: dict[str, dict[str, Any]] = {}
    for source_endpoint in payload.get("endpoints", []):
        endpoint = copy.deepcopy(source_endpoint)
        endpoint["endpoint_id"] = normalize_endpoint_id(endpoint.get("endpoint_id")) or endpoint.get("endpoint_id")
        endpoint_id = endpoint["endpoint_id"]
        if endpoint_id in ENDPOINT_DISPLAY_NAME_OVERRIDES:
            endpoint["display_name"] = ENDPOINT_DISPLAY_NAME_OVERRIDES[endpoint_id]
        if endpoint_id not in endpoints_by_id:
            endpoints_by_id[endpoint_id] = endpoint
            continue

        target = endpoints_by_id[endpoint_id]
        target.setdefault("operations", {}).update(endpoint.get("operations", {}))
        for key in ("base_url", "base_url_env", "auth", "disabled_reason", "contract_source", "extensions"):
            if not target.get(key) and endpoint.get(key):
                target[key] = endpoint[key]
        target["enabled"] = bool(target.get("enabled", False) or endpoint.get("enabled", False))

    payload["endpoints"] = list(endpoints_by_id.values())
    return payload


def slot_fill_method(slot: dict[str, Any]) -> str:
    if slot.get("fill_method"):
        return slot["fill_method"]
    return LEGACY_SLOT_SOURCE_METHODS.get(slot.get("source"), "resolution_profile")


def normalize_slot_definition(
    slot: dict[str, Any],
) -> None:
    fill_method = slot_fill_method(slot)
    legacy_question = slot.pop("question", None)
    legacy_auto_fill_ref = slot.pop("auto_fill_ref", None)
    if legacy_question:
        if fill_method == "user_question":
            slot.setdefault("user_question", legacy_question)
        elif fill_method == "llm_extraction":
            slot.setdefault("extraction_instruction", legacy_question)
        elif fill_method == "operator_manual":
            slot.setdefault("operator_hint", legacy_question)
        elif fill_method == "resolution_profile":
            slot.setdefault("fallback_question", legacy_question)
    if legacy_auto_fill_ref and fill_method == "case":
        slot.setdefault("case_source_ref", legacy_auto_fill_ref)

    allowed_context_fields = SLOT_METHOD_ALLOWED_FIELDS.get(fill_method, set())
    for field in SLOT_CONTEXT_FIELDS - allowed_context_fields:
        slot.pop(field, None)


def slot_question_text(slot: dict[str, Any]) -> str | None:
    fill_method = slot_fill_method(slot)
    if fill_method == "user_question":
        return slot.get("user_question")
    if fill_method == "operator_manual":
        return slot.get("operator_hint")
    if fill_method == "resolution_profile":
        return slot.get("fallback_question")
    return None


def slot_source_summary(slot: dict[str, Any]) -> dict[str, Any]:
    fill_method = slot_fill_method(slot)
    if fill_method == "case":
        return {"case_source_ref": slot.get("case_source_ref")}
    if fill_method == "llm_extraction":
        return {
            "extraction_instruction": slot.get("extraction_instruction"),
            "examples": slot.get("examples", []),
        }
    if fill_method == "operator_manual":
        return {"operator_hint": slot.get("operator_hint")}
    if fill_method == "user_question":
        return {"user_question": slot.get("user_question")}
    if fill_method == "resolution_profile":
        return {
            "resolution_profile_id": slot.get("resolution_profile_id"),
            "fallback_question": slot.get("fallback_question"),
        }
    return {}


def slot_schema_stages(slot_schema: dict[str, Any] | None) -> list[dict[str, Any]]:
    return list((slot_schema or {}).get("stages") or [])


def flatten_slot_schema_slots(slot_schema: dict[str, Any] | None) -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    for stage in sorted(slot_schema_stages(slot_schema), key=lambda item: int(item.get("order", 999))):
        slots.extend(stage.get("slots") or [])
    return slots


def slot_schema_resolution_profile_ids(slot_schema: dict[str, Any] | None) -> list[str]:
    profile_ids: list[str] = []
    for stage in slot_schema_stages(slot_schema):
        profile_id = stage.get("resolution_profile_id")
        if profile_id:
            profile_ids.append(profile_id)
        for slot in stage.get("slots") or []:
            if slot_fill_method(slot) == "resolution_profile" and slot.get("resolution_profile_id"):
                profile_ids.append(slot["resolution_profile_id"])
    return list(dict.fromkeys(profile_ids))


def active_config_status(value: dict[str, Any] | None) -> str:
    return str((value or {}).get("status") or "active")


def config_item_is_active(value: dict[str, Any] | None) -> bool:
    return active_config_status(value) not in {"disabled", "archived", "deleted"}


def operator_manual_slot_hint(slot: dict[str, Any]) -> str:
    return (
        slot.get("operator_hint")
        or slot.get("fallback_question")
        or slot.get("user_question")
        or f"Заполните \"{slot.get('display_name') or slot.get('slot_id') or 'слот'}\" вручную: профиль разрешения отсутствует."
    )


def convert_slot_to_operator_manual(slot: dict[str, Any]) -> None:
    slot["fill_method"] = "operator_manual"
    slot["operator_hint"] = operator_manual_slot_hint(slot)
    for field in SLOT_CONTEXT_FIELDS - {"operator_hint"}:
        slot.pop(field, None)


def normalize_slot_schema_stages(slot_schema: dict[str, Any]) -> None:
    stages = slot_schema.get("stages")
    if not isinstance(stages, list) or not stages:
        legacy_slots = slot_schema.get("slots")
        if isinstance(legacy_slots, list) and legacy_slots:
            stages = [
                {
                    "stage_id": "stage.default",
                    "display_name": "Основной этап",
                    "order": 1,
                    "slots": copy.deepcopy(legacy_slots),
                }
            ]
        else:
            raise ConfigRegistryError(
                f"{slot_schema.get('slot_schema_id', 'slot_schema')} должен содержать stages "
                "или legacy flat slots для автоматической миграции."
            )
    normalized_stages = []
    for index, stage in enumerate(stages, start=1):
        stage = copy.deepcopy(stage)
        stage.setdefault("stage_id", f"stage{index}")
        stage.setdefault("display_name", f"Этап {index}")
        stage["order"] = int(stage.get("order") or index)
        stage.setdefault("slots", [])
        for slot in stage["slots"]:
            normalize_slot_definition(slot)
            if slot.get("confidence_overrides") is not None:
                slot["confidence_overrides"] = normalize_confidence_thresholds(
                    slot.get("confidence_overrides"),
                )
        normalized_stages.append(stage)
    normalized_stages.sort(key=lambda item: int(item.get("order", 999)))
    slot_schema["stages"] = normalized_stages
    slots = flatten_slot_schema_slots(slot_schema)
    slot_schema["slots"] = slots
    slot_schema["required_slots"] = [slot["slot_id"] for slot in slots if slot.get("required")]
    slot_schema["auto_fill_slots"] = [
        slot["slot_id"]
        for slot in slots
        if slot_fill_method(slot) not in {"user_question", "operator_manual"}
    ]
    priority_order = {"who": 0, "what": 1, "when": 2, "where": 3, "context": 4}
    question_candidates = [
        (index, slot)
        for index, slot in enumerate(slots)
        if slot.get("required") and slot_fill_method(slot) in {"user_question", "resolution_profile", "operator_manual"}
    ]
    slot_schema["question_order"] = [
        slot["slot_id"]
        for index, slot in sorted(
            question_candidates,
            key=lambda item: (priority_order.get(item[1].get("priority_group"), 99), item[0]),
        )
    ]


def normalize_confidence_thresholds(
    thresholds: dict[str, Any] | None,
    *,
    require_all: bool = False,
) -> dict[str, float]:
    if not isinstance(thresholds, dict):
        return copy.deepcopy(DEFAULT_CONFIDENCE_THRESHOLDS) if require_all else {}
    source = DEFAULT_CONFIDENCE_THRESHOLDS if require_all else {}
    result: dict[str, float] = copy.deepcopy(source)
    for key in DEFAULT_CONFIDENCE_THRESHOLDS:
        value = thresholds.get(key)
        if value is None or value == "":
            continue
        result[key] = float(value)
    return result


def normalize_editor_reference_hints(hints: dict[str, Any] | None) -> dict[str, Any]:
    defaults = copy.deepcopy(DEFAULT_EDITOR_REFERENCE_HIDDEN_FIELDS)
    by_key: dict[tuple[str, tuple[str, ...]], dict[str, Any]] = {
        (
            str(item.get("field") or ""),
            tuple(sorted(str(context) for context in item.get("contexts") or [])),
        ): item
        for item in defaults
    }
    configured_items = (hints or {}).get("hidden_fields", []) if isinstance(hints, dict) else []
    for item in configured_items:
        field = str(item.get("field") or "").strip()
        contexts = [str(context).strip() for context in item.get("contexts") or [] if str(context).strip()]
        if not field or not contexts:
            continue
        key = (field, tuple(sorted(contexts)))
        current = by_key.get(key, {})
        by_key[key] = {
            "field": field,
            "contexts": contexts,
            "display_name": str(item.get("display_name") or current.get("display_name") or field),
            "description": str(item.get("description") or current.get("description") or field),
            "show_in_hints": bool(item.get("show_in_hints")),
        }
    return {"hidden_fields": list(by_key.values())}


def validate_confidence_thresholds(thresholds: dict[str, Any] | None, label: str, *, require_all: bool = False) -> list[str]:
    errors: list[str] = []
    if not thresholds:
        return [f"{label} должен содержать пороги confidence."] if require_all else []
    normalized = normalize_confidence_thresholds(thresholds, require_all=require_all)
    if require_all:
        missing = [key for key in DEFAULT_CONFIDENCE_THRESHOLDS if key not in thresholds]
        for key in missing:
            errors.append(f"{label} должен содержать {key}.")
    if not normalized:
        return errors
    for key, value in normalized.items():
        if value < 0 or value > 1:
            errors.append(f"{label}.{key} должен быть в диапазоне 0..1.")
    auto_accept = normalized.get("auto_accept_confidence")
    clarification = normalized.get("clarification_confidence")
    operator_handoff = normalized.get("operator_handoff_confidence")
    min_extraction = normalized.get("min_extraction_confidence")
    if None not in (auto_accept, clarification, operator_handoff) and not (operator_handoff <= clarification <= auto_accept):
        errors.append(
            f"{label}: должен соблюдаться порядок "
            "operator_handoff_confidence <= clarification_confidence <= auto_accept_confidence."
        )
    if None not in (auto_accept, operator_handoff, min_extraction) and not (operator_handoff <= min_extraction <= auto_accept):
        errors.append(
            f"{label}: min_extraction_confidence должен быть между "
            "operator_handoff_confidence и auto_accept_confidence."
        )
    return errors


def validate_confidence_overrides(
    base_thresholds: dict[str, Any],
    overrides: dict[str, Any] | None,
    label: str,
) -> list[str]:
    errors = validate_confidence_thresholds(overrides, label)
    if not overrides:
        return errors
    effective = normalize_confidence_thresholds(base_thresholds, require_all=True)
    effective.update(normalize_confidence_thresholds(overrides))
    errors.extend(
        validate_confidence_thresholds(
            effective,
            f"{label}.effective",
            require_all=True,
        )
    )
    return errors


def client_waiting_defaults_from_legacy_escalation(payload: dict[str, Any] | None) -> dict[str, Any]:
    defaults = copy.deepcopy(DEFAULT_CLIENT_WAITING_POLICY)
    for policy in (payload or {}).get("policies", []):
        auto_close = policy.get("auto_close") or {}
        waiting = policy.get("waiting") or {}
        if "requires_user_confirmation" in auto_close:
            defaults["auto_close_requires_client_confirmation"] = bool(auto_close["requires_user_confirmation"])
        if "pause_sla" in waiting:
            defaults["pause_sla_on_client_wait"] = bool(waiting["pause_sla"])
        if "auto_close_after_hours" in waiting:
            try:
                defaults["client_wait_auto_close_after_hours"] = int(waiting["auto_close_after_hours"])
            except (TypeError, ValueError):
                defaults["client_wait_auto_close_after_hours"] = DEFAULT_CLIENT_WAITING_POLICY[
                    "client_wait_auto_close_after_hours"
                ]
        if auto_close or waiting:
            break
    return defaults


def normalize_channel_waiting_policy(
    waiting_policy: dict[str, Any] | None,
    legacy_defaults: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = copy.deepcopy(waiting_policy or {})
    defaults = copy.deepcopy(DEFAULT_CLIENT_WAITING_POLICY)
    defaults.update(legacy_defaults or {})
    for key, value in defaults.items():
        if key not in result or result[key] is None:
            result[key] = value
    try:
        result["client_wait_auto_close_after_hours"] = int(result["client_wait_auto_close_after_hours"])
    except (TypeError, ValueError):
        result["client_wait_auto_close_after_hours"] = DEFAULT_CLIENT_WAITING_POLICY[
            "client_wait_auto_close_after_hours"
        ]
    result["auto_close_requires_client_confirmation"] = bool(result["auto_close_requires_client_confirmation"])
    result["pause_sla_on_client_wait"] = bool(result["pause_sla_on_client_wait"])
    return result


def channel_capability_defaults(channel_id: str | None, mode: str | None) -> dict[str, bool]:
    if channel_id == "service_desk":
        return copy.deepcopy(DEFAULT_SERVICEDESK_CHANNEL_CAPABILITIES)
    if mode == "debug":
        return copy.deepcopy(DEFAULT_DEBUG_CHANNEL_CAPABILITIES)
    result = copy.deepcopy(DEFAULT_CHANNEL_CAPABILITIES)
    result["supports_client_questions"] = mode == "online_interactive"
    result["supports_operator_questions"] = mode == "offline_interactive"
    result["supports_work_order_creation"] = mode == "offline_interactive"
    result["supports_async_result"] = False
    return result


def normalize_channel_capabilities(
    capabilities: dict[str, Any] | None,
    *,
    channel_id: str | None = None,
    mode: str | None = None,
) -> dict[str, bool]:
    result = channel_capability_defaults(channel_id, mode)
    for key in result:
        if capabilities and key in capabilities:
            result[key] = bool(capabilities[key])
    return result


def render_channel_task_topic(template: str | None, agent_type: str | None) -> str:
    topic_template = template or DEFAULT_SERVICEDESK_TASK_TOPIC_TEMPLATE
    return topic_template.replace("{agent_type}", agent_type or DEFAULT_SERVICEDESK_AGENT_TYPE)


def normalize_channel_technical_profile(
    profile: dict[str, Any] | None,
    *,
    channel_id: str | None = None,
) -> dict[str, Any]:
    result = copy.deepcopy(profile or {})
    if channel_id == "service_desk":
        result.setdefault("transport", "kafka")
        result.setdefault("endpoint_id", "operu_it_servicedesk")
        result.setdefault("agent_type", DEFAULT_SERVICEDESK_AGENT_TYPE)
        result.setdefault("task_topic_template", DEFAULT_SERVICEDESK_TASK_TOPIC_TEMPLATE)
        result.setdefault("result_topic", "public.ittask.result")
        result.setdefault("invalid_topic", "public.ittask.invalid")
        result.setdefault("temp_password_topic", "public.ittask.temp_password")
        result.setdefault("message_key_parameter", "task_key")
        result.setdefault("hmac_required", True)
    else:
        result.setdefault("transport", "none")
    if result.get("transport") == "kafka":
        result["task_topic"] = render_channel_task_topic(
            result.get("task_topic_template"),
            result.get("agent_type"),
        )
    else:
        result.pop("task_topic", None)
    return result


def default_channel_parameters(channel_id: str | None) -> list[dict[str, Any]]:
    if channel_id != "service_desk":
        return []
    return [
        {
            "parameter_id": "agent_type",
            "display_name": "Тип агента",
            "direction": "input",
            "source": "technical_profile.agent_type",
            "description": "Тип агента ServiceDesk, который подставляется в шаблон topic.",
        },
        {
            "parameter_id": "task_topic",
            "display_name": "Topic задачи",
            "direction": "input",
            "source": "technical_profile.task_topic",
            "description": "Вычисленное имя Kafka topic для постановки задачи ServiceDesk.",
        },
        {
            "parameter_id": "task_key",
            "display_name": "Kafka key задачи",
            "direction": "input",
            "source": "kafka.message_key",
            "description": "Ключ Kafka-сообщения; по контракту содержит номер задачи в ОперуИТ.",
        },
        {
            "parameter_id": "task_number",
            "display_name": "Номер задачи ОперуИТ",
            "direction": "bidirectional",
            "source": "kafka.message_key",
            "description": "Номер задачи ОперуИТ, используемый для task/result/invalid correlation.",
        },
        {
            "parameter_id": "result_code",
            "display_name": "Код результата",
            "direction": "output",
            "source": "TaskResultCode",
            "description": "Результат выполнения операции: Выполнено или Не выполнено.",
        },
        {
            "parameter_id": "result_message",
            "display_name": "Сообщение результата",
            "direction": "output",
            "source": "TaskResultMessage",
            "description": "Сообщение о выполнении операции из ServiceDesk result topic.",
        },
        {
            "parameter_id": "result_topic",
            "display_name": "Topic результата",
            "direction": "input",
            "source": "technical_profile.result_topic",
            "description": "Kafka topic входящих результатов выполнения задач.",
        },
        {
            "parameter_id": "invalid_payload",
            "display_name": "Некорректное исполнение",
            "direction": "output",
            "source": "public.ittask.invalid",
            "description": "Payload из topic некорректных исполнений задач.",
        },
        {
            "parameter_id": "temp_password_personal_id",
            "display_name": "Табельный номер временного пароля",
            "direction": "output",
            "source": "TaskTemp_PasswordMsg.personalID",
            "description": "Идентификатор сотрудника из события временного пароля.",
        },
    ]


def normalize_channel_parameters(
    parameters: list[dict[str, Any]] | None,
    *,
    channel_id: str | None = None,
) -> list[dict[str, Any]]:
    configured = copy.deepcopy(parameters or [])
    defaults = {
        parameter["parameter_id"]: parameter
        for parameter in default_channel_parameters(channel_id)
    }
    result_by_id = copy.deepcopy(defaults)
    for parameter in configured:
        parameter_id = parameter.get("parameter_id")
        if not parameter_id:
            continue
        result_by_id[parameter_id] = {
            **result_by_id.get(parameter_id, {}),
            **parameter,
        }
    return list(result_by_id.values())


def default_channel_handoff_action(channel: dict[str, Any] | None) -> dict[str, Any]:
    channel = channel or {}
    mode = channel.get("mode")
    channel_id = channel.get("channel_id")
    if channel_id == "service_desk" or mode == "offline_interactive":
        return {
            "action_type": "create_work_order",
            "message_template": "Создать наряд ответственному специалисту с пакетом эскалации.",
        }
    if channel_id == "messenger_bot" or mode == "online_interactive":
        return {
            "action_type": "call_specialist",
            "message_template": "Позвать специалиста в диалог с полным контекстом сценария.",
        }
    return {
        "action_type": "debug_stop",
        "message_template": "Остановить сценарий и показать причину эскалации оператору.",
    }


def normalize_simulation_options(
    *,
    run_mode: str | None = None,
    allow_llm: bool | None = None,
    allow_readonly_integrations: bool | None = None,
    allow_mock_integrations: bool | None = None,
    allow_action_with_approval: bool | None = None,
    bypass_policy_gates: bool | None = None,
    async_diagnostics_level: str | None = None,
) -> dict[str, Any]:
    mode = run_mode or "config_check"
    if mode not in SIMULATION_RUN_MODES:
        mode = "config_check"
    options = copy.deepcopy(SIMULATION_RUN_MODES[mode])
    options["run_mode"] = mode
    for key, value in (
        ("allow_llm", allow_llm),
        ("allow_readonly_integrations", allow_readonly_integrations),
        ("allow_mock_integrations", allow_mock_integrations),
        ("allow_action_with_approval", allow_action_with_approval),
        ("bypass_policy_gates", bypass_policy_gates),
    ):
        if value is not None:
            options[key] = bool(value)
    if async_diagnostics_level is not None:
        level = str(async_diagnostics_level or "").strip().lower()
        options["async_diagnostics_level"] = level if level in {"off", "basic", "verbose"} else "off"
    return options


def append_trace(
    trace: list[dict[str, Any]],
    *,
    step: str,
    status: str,
    title: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    item = {
        "step": step,
        "status": status,
        "title": title,
        "message": message,
    }
    if details:
        item["details"] = details
    trace.append(item)


def compact_trace_value(value: Any, limit: int = 120) -> str:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    else:
        text = str(value)
    return text if len(text) <= limit else f"{text[:limit - 3]}..."


def slot_value_is_filled(slot_values: dict[str, Any], provided: dict[str, Any], slot_id: str) -> bool:
    if provided.get(slot_id) not in (None, ""):
        return True
    value = slot_values.get(slot_id)
    if not isinstance(value, dict):
        return value not in (None, "")
    if value.get("status") in {
        "candidate_below_threshold",
        "model_unavailable",
        "waiting_for_dependencies",
        "blocked_by_dependency_cycle",
        "extraction_pending",
        "resolution_pending",
    }:
        return False
    return value.get("value") not in (None, "")


def filled_slot_values_for_context(slot_values: dict[str, Any], provided: dict[str, Any]) -> dict[str, Any]:
    context: dict[str, Any] = {
        slot_id: value
        for slot_id, value in provided.items()
        if value not in (None, "")
    }
    for slot_id, slot_value in slot_values.items():
        if not slot_value_is_filled(slot_values, provided, slot_id):
            continue
        if isinstance(slot_value, dict):
            context[slot_id] = slot_value.get("value")
        else:
            context[slot_id] = slot_value
    return context


def slot_template_dependencies(*values: Any) -> list[str]:
    dependencies: list[str] = []
    for value in values:
        if isinstance(value, dict):
            nested = value.values()
        elif isinstance(value, list):
            nested = value
        else:
            nested = [value]
        for item in nested:
            if isinstance(item, (dict, list)):
                for dependency in slot_template_dependencies(item):
                    if dependency not in dependencies:
                        dependencies.append(dependency)
                continue
            for ref in template_refs(str(item or "")):
                if not ref.startswith("slot."):
                    continue
                slot_id = ref.split(".", 1)[1].split(".", 1)[0].strip()
                if slot_id and slot_id not in dependencies:
                    dependencies.append(slot_id)
    return dependencies


def slot_mapping_dependencies(mapping: dict[str, Any] | None) -> list[str]:
    dependencies = source_ref_slot_ids(mapping)
    for dependency in slot_template_dependencies(mapping or {}):
        if dependency not in dependencies:
            dependencies.append(dependency)
    return dependencies


def llm_slot_dependencies(slot: dict[str, Any]) -> list[str]:
    dependencies = slot_template_dependencies(
        slot.get("extraction_instruction"),
        slot.get("examples", []),
    )
    return [slot_id for slot_id in dependencies if slot_id != slot.get("slot_id")]


def resolution_profile_input_dependencies(profile: dict[str, Any]) -> list[str]:
    dependencies: list[str] = []
    for step in profile.get("enrichment_steps", []) or []:
        for dependency in slot_mapping_dependencies(step.get("parameter_mapping") or {}):
            if dependency not in dependencies:
                dependencies.append(dependency)
        for dependency in slot_template_dependencies(
            step.get("configuration_instruction"),
            step.get("step_name"),
        ):
            if dependency not in dependencies:
                dependencies.append(dependency)
    return dependencies


def missing_slot_dependencies(
    dependencies: list[str],
    *,
    slot_values: dict[str, Any],
    provided: dict[str, Any],
) -> list[str]:
    return [
        slot_id
        for slot_id in dependencies
        if not slot_value_is_filled(slot_values, provided, slot_id)
    ]


def resolved_dry_run_parameters(
    mapping: dict[str, Any],
    *,
    provided: dict[str, Any],
    slot_values: dict[str, Any] | None = None,
    enrichment_step_results: dict[str, Any] | None = None,
    output_values: dict[str, Any] | None = None,
) -> dict[str, Any]:
    parameters: dict[str, Any] = {}
    slots = slot_values or {}
    step_results = enrichment_step_results or {}
    outputs = output_values or {}
    for parameter, source_ref in (mapping or {}).items():
        source, separator, source_value = str(source_ref).partition(":")
        if separator != ":":
            continue
        value: Any = None
        if source == "slot":
            if source_value in provided:
                value = provided.get(source_value)
            elif source_value in slots:
                slot_value = slots[source_value]
                value = slot_value.get("value") if isinstance(slot_value, dict) else slot_value
        elif source == "output":
            value = outputs.get(source_value)
        elif source == "case":
            value = value_at_path(provided, source_value)
            if value is None:
                value = value_at_path(provided.get("case"), source_value) if isinstance(provided.get("case"), dict) else None
        elif source == "step":
            match = STEP_SOURCE_REF_RE.match(source_value)
            if match:
                step_id, capability_id, kind, field_path = match.groups()
                step_record = step_results.get(step_id)
                if step_record and step_record.get("capability_id") != capability_id:
                    step_record = None
                if step_record and kind == "input":
                    value = step_record.get("parameters", {}).get(field_path)
                elif step_record:
                    value = value_at_path(step_record.get("result"), field_path)
        elif source == "constant":
            value = source_value
        elif source == "secret":
            value = "секрет скрыт"
        if source == "step" and value in (None, ""):
            parameters[parameter] = None
        else:
            parameters[parameter] = value if value not in (None, "") else source_ref
    return parameters


def capability_input_resolution_rows(
    *,
    schema: dict[str, Any] | None,
    mapping: dict[str, Any] | None,
    parameters: dict[str, Any] | None,
    applied_defaults: dict[str, Any] | None = None,
    provided: dict[str, Any] | None = None,
    slot_values: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    bindings = mapping or {}
    values = parameters or {}
    defaults = applied_defaults or {}
    provided_values = provided or {}
    slots = slot_values or {}
    input_names: list[str] = []
    for name in [*schema_properties(schema), *bindings]:
        if name and name not in input_names:
            input_names.append(str(name))
    for group in schema_required_parameter_groups(schema):
        for name in group:
            if name and name not in input_names:
                input_names.append(str(name))
    rows: list[dict[str, Any]] = []
    required_inputs = {
        name
        for group in schema_required_parameter_groups(schema)
        for name in group
    }
    for input_name in input_names:
        source_ref = str(bindings.get(input_name) or "")
        value = copy.deepcopy(values.get(input_name))
        source, separator, source_value = source_ref.partition(":")
        missing = not _schema_value_is_present(value)
        if input_name in defaults:
            status = "defaulted"
            value = copy.deepcopy(defaults[input_name])
        elif source == "slot" and separator == ":":
            missing = not slot_value_is_filled(slots, provided_values, source_value)
            status = "missing" if missing else "resolved"
            if missing:
                value = None
        elif source_ref and value == source_ref and source not in {"constant", "secret"}:
            status = "missing"
            missing = True
            value = None
        else:
            status = "missing" if missing else "resolved"
        row = {
            "input": input_name,
            "source_ref": source_ref,
            "value": value,
            "status": status,
            "required": input_name in required_inputs,
        }
        if source == "slot" and separator == ":":
            row["slot_id"] = source_value
        if status == "defaulted":
            row["defaulted"] = True
        rows.append(row)
    return rows


def missing_capability_input_resolution(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if row.get("status") == "missing"
        and row.get("required")
    ]


def drop_missing_optional_capability_inputs(
    parameters: dict[str, Any],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    result = copy.deepcopy(parameters)
    for row in rows:
        if row.get("status") != "missing" or row.get("required"):
            continue
        input_name = row.get("input")
        if input_name:
            result.pop(str(input_name), None)
    return result


def profile_confidence_thresholds(profile: dict[str, Any] | None) -> dict[str, float]:
    if not profile:
        return {}
    thresholds = profile.get("confidence_thresholds") or {}
    base = profile.get("confidence_threshold")
    result: dict[str, float] = {}
    if thresholds.get("auto_fill") is not None:
        result["auto_accept_confidence"] = float(thresholds["auto_fill"])
    elif base is not None:
        result["auto_accept_confidence"] = float(base)
    if thresholds.get("clarification") is not None:
        result["clarification_confidence"] = float(thresholds["clarification"])
    elif base is not None:
        result["clarification_confidence"] = float(base)
    if thresholds.get("operator_handoff") is not None:
        result["operator_handoff_confidence"] = float(thresholds["operator_handoff"])
    if not result:
        return {}
    result["min_extraction_confidence"] = result.get(
        "clarification_confidence",
        result.get("auto_accept_confidence", DEFAULT_CONFIDENCE_THRESHOLDS["min_extraction_confidence"]),
    )
    return result


def next_slot_question(
    slot: dict[str, Any],
    profile_by_id: dict[str, dict[str, Any]],
) -> str | None:
    if slot_fill_method(slot) == "resolution_profile":
        profile = profile_by_id.get(slot.get("resolution_profile_id", ""))
        if profile:
            if resolution_profile_human_action(profile) != "ask_client":
                return None
            return resolution_profile_question(profile) or slot_question_text(slot)
    return slot_question_text(slot)


def select_model_provider(model_config: dict[str, Any], alias: str | None) -> dict[str, Any] | None:
    providers = model_config.get("providers", {})
    for provider in providers.values():
        if provider.get("model_alias") == alias:
            return provider
    active_provider = model_config.get("active_provider")
    if active_provider in providers:
        return providers[active_provider]
    return next((provider for provider in providers.values() if provider.get("enabled")), None)


def runtime_model_routing(model_config: dict[str, Any]) -> dict[str, Any]:
    payload = copy.deepcopy(model_config)
    gateway = payload.get("gateway")
    if not isinstance(gateway, dict):
        gateway = {}
        payload["gateway"] = gateway

    runtime = payload.get("runtime")
    if not isinstance(runtime, dict):
        runtime = {}
        payload["runtime"] = runtime

    public_url = os.getenv("LITELLM_PUBLIC_BASE_URL", "").strip()
    if not public_url:
        public_url = f"http://127.0.0.1:{os.getenv('LITELLM_PORT', '4000')}/v1"
    runtime["litellm_public_base_url"] = public_url

    runtime_url = os.getenv("LITELLM_BASE_URL", "").strip()
    runtime["litellm_runtime_override_applied"] = False
    if runtime_url and gateway.get("type") == "litellm":
        previous_url = str(gateway.get("base_url") or "").strip()
        gateway["base_url"] = runtime_url
        runtime["litellm_runtime_base_url"] = runtime_url
        runtime["litellm_runtime_override_applied"] = previous_url != runtime_url
        providers = payload.get("providers")
        if isinstance(providers, dict):
            for provider in providers.values():
                if isinstance(provider, dict) and provider.get("provider_type") in {"vllm_cpu", "litellm"}:
                    provider["base_url"] = runtime_url
    return payload


def parse_json_object(raw_text: str) -> dict[str, Any]:
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            parsed = json.loads(text[start : end + 1])
            return parsed if isinstance(parsed, dict) else {}
        raise


def build_slot_extraction_prompt(
    *,
    scenario: dict[str, Any],
    slots: list[dict[str, Any]],
    text: str,
    slot_values: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    slot_specs = [
        {
            "slot_id": slot["slot_id"],
            "display_name": slot.get("display_name", slot["slot_id"]),
            "required": slot.get("required", False),
            "instruction": slot.get("extraction_instruction", ""),
            "examples": slot.get("examples", []),
        }
        for slot in slots
    ]
    return [
        {
            "role": "system",
            "content": (
                "Ты извлекаешь значения слотов для AI ServiceDesk. "
                "Верни только JSON без markdown. Не выдумывай значения. "
                "Если данных нет, используй null и confidence 0."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "scenario": scenario.get("display_name", scenario.get("scenario_id")),
                    "ticket_text": text,
                    "known_slot_values": slot_values or {},
                    "slots": slot_specs,
                    "response_schema": {
                        "slots": {
                            "<slot_id>": {
                                "value": "string|null",
                                "confidence": "number 0..1",
                                "reason": "short russian explanation",
                            }
                        }
                    },
                },
                ensure_ascii=False,
            ),
        },
    ]


def invoke_slot_extraction_model(
    *,
    model_config: dict[str, Any],
    scenario: dict[str, Any],
    slots: list[dict[str, Any]],
    text: str,
    slot_values: dict[str, Any] | None = None,
) -> dict[str, Any]:
    alias = model_config.get("routing", {}).get("slot_resolution") or model_config.get("default_model_alias")
    provider = select_model_provider(model_config, alias)
    if not provider:
        return {
            "status": "error",
            "error": {
                "code": "model_provider_not_configured",
                "message": "Не найдено включенное подключение модели для slot_resolution.",
            },
        }

    gateway = model_config.get("gateway", {})
    base_url = gateway.get("base_url") or provider.get("base_url")
    if not base_url:
        return {
            "status": "error",
            "error": {
                "code": "model_base_url_missing",
                "message": "Не задан base_url для модели.",
            },
        }

    model_name = alias if gateway.get("type") == "litellm" and alias else provider.get("model")
    runtime = model_config.get("runtime", {}) if isinstance(model_config.get("runtime"), dict) else {}
    model_runtime_details = {
        "gateway_base_url": base_url,
        "runtime_override_applied": bool(runtime.get("litellm_runtime_override_applied")),
    }
    api_key = os.getenv("LITELLM_MASTER_KEY", "").strip() if gateway.get("type") == "litellm" else ""
    if not api_key:
        api_key = os.getenv(provider.get("api_key_env", ""), "").strip()
    if provider.get("api_key_required") and not api_key:
        return {
            "status": "error",
            "provider": provider.get("display_name"),
            "model": model_name,
            "error": {
                "code": "model_api_key_missing",
                "message": f"Не задан ключ модели в {provider.get('api_key_env')}.",
            },
        }

    redaction = redact_for_llm(text)
    payload = {
        "model": model_name,
        "messages": build_slot_extraction_prompt(
            scenario=scenario,
            slots=slots,
            text=redaction.text,
            slot_values=slot_values,
        ),
        "temperature": provider.get("temperature", 0),
        "max_tokens": min(int(provider.get("max_tokens", 1024)), 2048),
        "response_format": {"type": "json_object"},
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    started = time.perf_counter()
    try:
        raw_body = urlopen_with_retry(
            request,
            timeout=int(provider.get("timeout_seconds", 60)),
            operation_name=f"model/{provider.get('provider_id') or provider.get('display_name') or 'unknown'}",
        ).decode("utf-8")
        body = json.loads(raw_body)
    except HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        return {
            "status": "error",
            "provider": provider.get("display_name"),
            "model": model_name,
            **model_runtime_details,
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "redaction": redaction.as_dict(),
            "error": {
                "code": f"model_http_{error.code}",
                "message": error_body[:1000] or error.reason or "Модель вернула HTTP-ошибку.",
            },
        }
    except (URLError, TimeoutError) as error:
        return {
            "status": "error",
            "provider": provider.get("display_name"),
            "model": model_name,
            **model_runtime_details,
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "redaction": redaction.as_dict(),
            "error": {
                "code": "model_unreachable",
                "message": str(error),
            },
        }
    except json.JSONDecodeError as error:
        return {
            "status": "error",
            "provider": provider.get("display_name"),
            "model": model_name,
            **model_runtime_details,
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "redaction": redaction.as_dict(),
            "error": {
                "code": "model_response_not_json",
                "message": str(error),
            },
        }

    content = (
        body.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )
    try:
        parsed = parse_json_object(content)
    except (json.JSONDecodeError, TypeError) as error:
        return {
            "status": "error",
            "provider": provider.get("display_name"),
            "model": model_name,
            **model_runtime_details,
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "raw_content": content[:1000],
            "redaction": redaction.as_dict(),
            "error": {
                "code": "slot_extraction_json_invalid",
                "message": str(error),
            },
        }

    return {
        "status": "success",
        "provider": provider.get("display_name"),
        "model": model_name,
        **model_runtime_details,
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "usage": body.get("usage", {}),
        "redaction": redaction.as_dict(),
        "slots": parsed.get("slots", parsed),
    }


def normalized_llm_slot_result(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"value": None, "confidence": 0.0, "reason": "Модель не вернула объект результата."}
    raw_confidence = value.get("confidence", 0)
    try:
        confidence = float(raw_confidence)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    result_value = value.get("value")
    if result_value == "":
        result_value = None
    return {
        "value": result_value,
        "confidence": confidence,
        "reason": str(value.get("reason") or "Модель не пояснила результат."),
    }


DEFAULT_RESOLUTION_DECISION_POLICY = {
    "empty_result": "ask_clarification",
    "single_result": "auto_fill_if_confident",
    "multiple_results": "ask_disambiguation",
    "source_error": "operator_handoff",
    "attempt_limit": "operator_handoff",
}


def resolution_attribute(
    attribute_id: str,
    *,
    display_name: str | None = None,
    source: str = "llm",
    source_ref: str | None = None,
    required: bool = False,
    extraction_instruction: str | None = None,
) -> dict[str, Any]:
    result = {
        "attribute_id": attribute_id,
        "display_name": display_name or humanize_config_id(attribute_id),
        "source": source,
        "required": required,
    }
    if source_ref:
        result["source_ref"] = source_ref
    if extraction_instruction:
        result["extraction_instruction"] = extraction_instruction
    return result


def default_result_policy(tool_name: str | None, target_slot_id: str | None = None) -> dict[str, Any]:
    if tool_name == "search_ad_users":
        return {
            "result_type": "list",
            "list_path": "users",
            "target_value_path": "login",
            "confidence_path": "confidence",
            "display_value_path": "display_name",
            "output_mapping": {
                "user_id": "user_id",
            },
        }
    if tool_name == "query_cmdb_object":
        return {
            "result_type": "object",
            "object_path": "object",
            "success_path": "object_found",
            "target_value_path": target_slot_id or "value",
            "display_value_path": "message",
            "output_mapping": {},
        }
    return {
        "result_type": "list",
        "list_path": "candidates",
        "target_value_path": "value",
        "confidence_path": "confidence",
        "display_value_path": "display_name",
        "output_mapping": {},
    }


def result_policy_from_candidate_mapping(mapping: dict[str, Any] | None, tool_name: str | None, target_slot_id: str | None) -> dict[str, Any]:
    if not mapping:
        return default_result_policy(tool_name, target_slot_id)
    candidate_path = mapping.get("candidates_path") or "candidates"
    count_path = mapping.get("candidate_count_path")
    looks_like_object = count_path in {"object_found", "found", "success"} or candidate_path == "object"
    result_policy = {
        "result_type": "object" if looks_like_object else "list",
        "target_value_path": mapping.get("value_path") or target_slot_id or "value",
        "output_mapping": copy.deepcopy(mapping.get("output_mapping") or {}),
    }
    if looks_like_object:
        result_policy["object_path"] = candidate_path
        if count_path:
            result_policy["success_path"] = count_path
    else:
        result_policy["list_path"] = candidate_path
    if mapping.get("confidence_path"):
        result_policy["confidence_path"] = mapping["confidence_path"]
    if mapping.get("label_path"):
        result_policy["display_value_path"] = mapping["label_path"]
    return result_policy


def normalize_resolution_decision_policy(policy: dict[str, Any] | None) -> dict[str, Any]:
    result = copy.deepcopy(DEFAULT_RESOLUTION_DECISION_POLICY)
    policy = policy or {}
    legacy_keys = {
        "zero_candidates": "empty_result",
        "single_candidate": "single_result",
        "multiple_candidates": "multiple_results",
    }
    for key, value in policy.items():
        normalized_key = legacy_keys.get(key, key)
        if normalized_key in result:
            result[normalized_key] = value
    return result


def step_source_ref(step: dict[str, Any], field_path: str, *, kind: str = "output") -> str:
    step_id = step.get("step_id") or "step1"
    capability_id = step.get("capability_id") or "capability_id"
    return f"step:{step_id}.capability.{capability_id}.{kind}.{field_path}"


def step_template_ref(step: dict[str, Any], field_path: str, *, kind: str = "output") -> str:
    step_id = step.get("step_id") or "step1"
    capability_id = step.get("capability_id") or "capability_id"
    return f"${{step.{step_id}.capability.{capability_id}.{kind}.{field_path}}}"


def migrate_entity_source_ref(source_ref: Any, entity_step_by_name: dict[str, dict[str, Any]]) -> Any:
    if not isinstance(source_ref, str) or not source_ref.startswith("entity:"):
        return source_ref
    entity_path = source_ref[len("entity:") :]
    for entity_name in sorted(entity_step_by_name, key=len, reverse=True):
        prefix = f"{entity_name}."
        if not entity_path.startswith(prefix):
            continue
        field_path = entity_path[len(prefix) :]
        if not field_path:
            return source_ref
        return step_source_ref(entity_step_by_name[entity_name], f"{entity_name}.{field_path}")
    return source_ref


def migrate_entity_parameter_mapping(
    mapping: dict[str, Any] | None,
    entity_step_by_name: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        parameter: migrate_entity_source_ref(source_ref, entity_step_by_name)
        for parameter, source_ref in (mapping or {}).items()
    }


def migrate_entity_template_refs(text: str | None, entity_step_by_name: dict[str, dict[str, Any]]) -> str:
    if not text or not entity_step_by_name:
        return text or ""
    names_pattern = "|".join(re.escape(name) for name in sorted(entity_step_by_name, key=len, reverse=True))

    def replace_template(match: re.Match[str]) -> str:
        entity_name = match.group("entity")
        field_path = match.group("field")
        step = entity_step_by_name.get(entity_name)
        if not step:
            return match.group(0)
        return step_template_ref(step, f"{entity_name}.{field_path}")

    def replace_inline(match: re.Match[str]) -> str:
        entity_name = match.group("entity")
        field_path = match.group("field")
        step = entity_step_by_name.get(entity_name)
        if not step:
            return match.group(0)
        return step_source_ref(step, f"{entity_name}.{field_path}")

    result = re.sub(
        rf"\$\{{entity\.(?P<entity>{names_pattern})\.(?P<field>[A-Za-z0-9_][A-Za-z0-9_.-]*)\}}",
        replace_template,
        text,
    )
    result = re.sub(
        rf"\$\{{entity\.(?P<entity>{names_pattern})\}}",
        lambda match: step_template_ref(
            entity_step_by_name[match.group("entity")],
            f"{match.group('entity')}.<field>",
        ),
        result,
    )
    result = re.sub(
        rf"\bentity:(?P<entity>{names_pattern})\.(?P<field>[A-Za-z0-9_][A-Za-z0-9_.-]*)\b",
        replace_inline,
        result,
    )
    return re.sub(
        rf"\bentity:(?P<entity>{names_pattern})\b",
        lambda match: step_source_ref(
            entity_step_by_name[match.group("entity")],
            f"{match.group('entity')}.<field>",
        ),
        result,
    )


def normalize_attribute_resolution_profile(profile: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(profile)
    result["status"] = result.get("status") or "active"
    result["use_llm_after_steps"] = bool(result.get("use_llm_after_steps", True))
    normalized_enrichment_steps = []
    for index, enrichment_step in enumerate(result.get("enrichment_steps", []), start=1):
        enrichment_step = copy.deepcopy(enrichment_step)
        legacy_parameter_mapping = enrichment_step.pop("parameter_mapping", None)
        for legacy_key in ("react_call", "endpoint_id", "operation_id", "result_fields"):
            enrichment_step.pop(legacy_key, None)
        if "input_mapping" not in enrichment_step and isinstance(legacy_parameter_mapping, dict):
            migrated_input_mapping = {
                parameter: source_ref
                for parameter, source_ref in legacy_parameter_mapping.items()
                if re.match(r"^(slot|output|step|case|constant|secret):.+$", str(source_ref or ""))
            }
            if migrated_input_mapping:
                enrichment_step["input_mapping"] = migrated_input_mapping
        step_id = str(enrichment_step.get("step_id") or "")
        if not re.match(r"^step[1-9][0-9]*$", step_id):
            enrichment_step["step_id"] = f"step{index}"
        normalized_enrichment_steps.append(enrichment_step)
    result["enrichment_steps"] = normalized_enrichment_steps
    last_step = normalized_enrichment_steps[-1] if normalized_enrichment_steps else None
    if last_step:
        output_hint_by_slot = {
            hint["target"]: hint["field"]
            for hint in output_mapping_hints_from_instruction(last_step.get("configuration_instruction"))
        }
        if output_hint_by_slot:
            for item in result.get("output_slots_order", []):
                slot_id = item.get("slot_id")
                if slot_id in output_hint_by_slot:
                    item["source_hint"] = output_hint_by_slot[slot_id]
    result["output_slots_order"] = normalize_output_slot_order(
        result.get("output_slots_order", []),
        result.get("target_slot_id"),
        last_step=last_step,
    )
    selected_output_slot_ids = {
        str(item.get("slot_id"))
        for item in result.get("output_slots_order", []) or []
        if item.get("slot_id")
    }
    for enrichment_step in result.get("enrichment_steps", []) or []:
        output_mapping = enrichment_step.get("output_mapping")
        if not isinstance(output_mapping, dict):
            enrichment_step["output_mapping"] = {}
            continue
        enrichment_step["output_mapping"] = {
            str(slot_id): field_path
            for slot_id, field_path in output_mapping.items()
            if str(slot_id) in selected_output_slot_ids
        }

    fallback = result.setdefault(
        "fallback",
        {
            "action": "operator_handoff",
            "question": "Не удалось однозначно заполнить атрибут.",
        },
    )
    human_policy = result.get("human_resolution_policy") or {}
    action = human_policy.get("action")
    result["human_resolution_policy"] = {
        "action": action if action in {"ask_client", "escalate_operator"} else "ask_client",
        "message_template": (
            human_policy.get("message_template")
            or human_policy.get("clarification_question")
            or fallback.get("question")
            or "Уточните данные для заполнения слота."
        ),
    }
    if "llm_resolution_script" not in result:
        result["llm_resolution_script"] = {
            "script_text": default_resolution_script_text(result),
            "response_contract": default_resolution_response_contract(),
        }
    result.setdefault("max_attempts", 1)
    return result


def completion_policy_is_empty(policy: Any) -> bool:
    return isinstance(policy, dict) and not policy


def compact_config_dict(value: dict[str, Any], keep_empty: set[str] | None = None) -> dict[str, Any]:
    keep_empty = keep_empty or set()
    return {
        key: item
        for key, item in value.items()
        if key in keep_empty or item not in (None, "", [], {})
    }


def slot_parameter_mapping_from_legacy(
    mapping: dict[str, Any],
    input_attributes: list[dict[str, Any]],
) -> dict[str, str]:
    attribute_by_id = {
        attribute.get("attribute_id"): attribute
        for attribute in input_attributes or []
    }
    result = {}
    for parameter, source_ref in (mapping or {}).items():
        source, separator, source_value = str(source_ref).partition(":")
        if separator != ":" or not source_value:
            continue
        if source == "slot":
            result[parameter] = f"slot:{source_value}"
        elif source == "attribute":
            attribute = attribute_by_id.get(source_value, {})
            if attribute.get("source") == "slot":
                result[parameter] = f"slot:{attribute.get('source_ref') or source_value}"
    return result


def operation_result_entity_from_policy(
    resolver_operation: dict[str, Any],
    result_policy: dict[str, Any],
) -> dict[str, Any]:
    operation_id = resolver_operation.get("operation_id") or resolver_operation.get("source_type") or "result"
    entity_name = (
        str(result_policy.get("list_path") or result_policy.get("object_path") or operation_id)
        .replace(".", "_")
        .replace("-", "_")
    )
    fields = []
    for field_id in [
        result_policy.get("target_value_path"),
        result_policy.get("confidence_path"),
        result_policy.get("display_value_path"),
        *list((result_policy.get("output_mapping") or {}).values()),
    ]:
        if not field_id:
            continue
        normalized = str(field_id).split(".")[-1]
        if normalized and normalized not in [item["field_id"] for item in fields]:
            fields.append({
                "field_id": normalized,
                "display_name": humanize_config_id(normalized),
                "field_type": "unknown",
            })
    return {
        "entity_name": entity_name or "result",
        "entity_description": f"Результат операции {humanize_config_id(operation_id)}.",
        "available_fields": fields,
    }


def enrichment_steps_from_legacy(
    resolver_operation: dict[str, Any],
    result_entity: dict[str, Any],
) -> list[dict[str, Any]]:
    _ = (resolver_operation, result_entity)
    return []


def output_slots_order_from_policy(
    target_slot_id: str | None,
    output_slots: list[str],
    result_policy: dict[str, Any],
) -> list[dict[str, Any]]:
    result = []
    seen = set()
    for index, slot_id in enumerate(output_slots or [target_slot_id], start=1):
        if not slot_id or slot_id in seen:
            continue
        seen.add(slot_id)
        source_hint = result_policy.get("target_value_path") if slot_id == target_slot_id else None
        source_hint = source_hint or (result_policy.get("output_mapping") or {}).get(slot_id) or slot_id
        result.append({
            "slot_id": slot_id,
            "order": index,
            "required_for_success": slot_id == target_slot_id,
            "source_hint": str(source_hint),
            "fallback": "ask_clarification" if slot_id == target_slot_id else "leave_empty",
        })
    return result


def normalize_output_source_hint(
    source_hint: Any,
    *,
    last_step: dict[str, Any] | None = None,
) -> str:
    hint = str(source_hint or "").strip()
    if not hint:
        return ""
    if re.match(r"^(paramCapability|step)\.", hint):
        return f"${{{hint}}}"
    capability_step_match = STEP_CAPABILITY_OUTPUT_REF_RE.match(hint)
    if capability_step_match and last_step:
        if (
            capability_step_match.group("step_id") == last_step.get("step_id")
            and capability_step_match.group("capability_id") == last_step.get("capability_id")
        ):
            return capability_step_match.group("field")
    return hint


def enrichment_step_id(step: dict[str, Any], index: int) -> str:
    value = str(step.get("step_id") or "").strip()
    return value if re.match(r"^step[1-9][0-9]*$", value) else f"step{index}"


def output_source_hint_reference(
    source_hint: Any,
    enrichment_steps: list[dict[str, Any]],
) -> dict[str, Any]:
    hint = str(source_hint or "").strip()
    if re.match(r"^(paramCapability|step)\.", hint):
        hint = f"${{{hint}}}"
    if not enrichment_steps:
        return {
            "source_hint": hint,
            "field": hint,
            "error": "output_slots_order не может ссылаться на результат: шаги обогащения не настроены.",
        }
    steps = [
        {**step, "step_id": enrichment_step_id(step, index)}
        for index, step in enumerate(enrichment_steps, start=1)
    ]
    capability_step_match = STEP_CAPABILITY_OUTPUT_REF_RE.match(hint)
    if capability_step_match:
        step_id = capability_step_match.group("step_id")
        capability_id = capability_step_match.group("capability_id")
        step = next((item for item in steps if item.get("step_id") == step_id), None)
        if not step:
            return {
                "source_hint": hint,
                "step_id": step_id,
                "capability_id": capability_id,
                "field": capability_step_match.group("field"),
                "error": f"source_hint ссылается на неизвестный шаг: {step_id}.",
            }
        if step.get("capability_id") != capability_id:
            return {
                "source_hint": hint,
                "step_id": step_id,
                "capability_id": capability_id,
                "field": capability_step_match.group("field"),
                "error": (
                    f"source_hint ожидает capability {capability_id} в {step_id}, "
                    f"но там настроена {step.get('capability_id')}."
                ),
            }
        return {
            "source_hint": hint,
            "step": step,
            "step_id": step_id,
            "capability_id": capability_id,
            "field": capability_step_match.group("field"),
        }

    capability_param_match = PARAM_CAPABILITY_OUTPUT_REF_RE.match(hint)
    if capability_param_match:
        capability_id = capability_param_match.group("capability_id")
        matches = [step for step in steps if step.get("capability_id") == capability_id]
        if not matches:
            return {
                "source_hint": hint,
                "capability_id": capability_id,
                "field": capability_param_match.group("field"),
                "error": f"source_hint ссылается на capability, которой нет в шагах профиля: {capability_id}.",
            }
        if len(matches) > 1:
            step_ids = ", ".join(step.get("step_id", "") for step in matches)
            return {
                "source_hint": hint,
                "capability_id": capability_id,
                "field": capability_param_match.group("field"),
                "error": (
                    f"source_hint неоднозначен: capability {capability_id} используется в шагах {step_ids}. "
                    "Используйте формат ${step.<step_id>.capability.<capability_id>.output.<field>}."
                ),
            }
        step = matches[0]
        return {
            "source_hint": hint,
            "step": step,
            "step_id": step.get("step_id"),
            "capability_id": capability_id,
            "field": capability_param_match.group("field"),
        }

    step = steps[-1]
    return {
        "source_hint": hint,
        "step": step,
        "step_id": step.get("step_id"),
        "capability_id": step.get("capability_id"),
        "field": hint,
    }


def output_mapping_hints_from_instruction(
    instruction: str | None,
) -> list[dict[str, str]]:
    output_pattern = (
        r"\$\{paramCapability\."
        r"(?P<capability_id>[A-Za-z][A-Za-z0-9_.-]*)\.output\."
        r"(?P<field>[A-Za-z0-9_][A-Za-z0-9_.-]*)\}"
    )
    slot_target_pattern = (
        r"(?:\$\{slot\.(?P<slot>[A-Za-z][A-Za-z0-9_.-]*)\}"
        r"|(?P<plain_slot>[A-Za-z][A-Za-z0-9_.-]*))"
    )
    hints: list[dict[str, str]] = []
    for pattern in (
        rf"{slot_target_pattern}\s*(?:<-|=|из|from)\s*{output_pattern}",
        rf"{output_pattern}\s*(?:->|=>|в|to)\s*{slot_target_pattern}",
    ):
        for match in re.finditer(pattern, instruction or "", flags=re.IGNORECASE):
            target = match.group("slot") or match.group("plain_slot")
            if target:
                hints.append({"target": target, "field": match.group("field")})
    return hints


def normalize_output_slot_order(
    items: list[dict[str, Any]],
    target_slot_id: str | None,
    *,
    last_step: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    normalized = []
    seen = set()
    for item in sorted(items or [], key=lambda value: int(value.get("order", 999))):
        slot_id = item.get("slot_id")
        if not slot_id or slot_id in seen:
            continue
        seen.add(slot_id)
        normalized.append({
            "slot_id": slot_id,
            "order": len(normalized) + 1,
            "required_for_success": bool(item.get("required_for_success", slot_id == target_slot_id)),
            "source_hint": normalize_output_source_hint(item.get("source_hint") or slot_id, last_step=last_step),
            "fallback": item.get("fallback") or ("ask_clarification" if slot_id == target_slot_id else "leave_empty"),
        })
    return normalized


def default_resolution_response_contract() -> dict[str, Any]:
    return {
        "decision": "fill | ask_clarification | handoff | leave_empty",
        "filled_slots": {"<slot_id>": "string|null"},
        "confidence": "number 0..1",
        "next_question": "string",
        "reason": "short russian explanation",
    }


def default_resolution_script_text(profile: dict[str, Any]) -> str:
    output_slots = ", ".join(item["slot_id"] for item in profile.get("output_slots_order", []))
    step_refs = ", ".join(
        f"{step.get('step_id', f'step{index}')}.capability.{step.get('capability_id', 'capability_id')}.output.<field>"
        for index, step in enumerate(profile.get("enrichment_steps", []), start=1)
    ) or "нет результатов capability"
    return (
        "Проанализируй входные слоты и результаты шагов обогащения. "
        f"Доступные ссылки на результаты: {step_refs}. "
        f"Заполняй только разрешенные выходные слоты: {output_slots or profile.get('target_slot_id')}. "
        "Если результат однозначный, верни decision=fill и filled_slots. "
        "Если данных недостаточно или кандидатов несколько, верни decision=ask_clarification и один уточняющий вопрос. "
        "Если уверенно решить нельзя после попыток, верни decision=handoff."
    )


DEFAULT_SLOT_RESOLUTION_PROMPT_TEMPLATE = (
    "Проанализируй входные слоты и результаты шагов обогащения. "
    "Доступные ссылки на результаты: {{step_refs}}. "
    "Заполняй только разрешенные выходные слоты: {{output_slots}}. "
    "Если результат однозначный, верни decision=fill и filled_slots. "
    "Если данных недостаточно или кандидатов несколько, верни decision=ask_clarification и один уточняющий вопрос. "
    "Если уверенно решить нельзя после попыток, верни decision=handoff."
)

DEFAULT_CAPABILITY_STEP_ASSIST_PROMPT_TEMPLATE = (
    "Ты помощник настройки capability step для AI ServiceDesk. "
    "Верни только JSON без markdown. Не исполняй capability и не используй MCP/n8n/tool детали. "
    "Выбери одну capability из списка и заполни mapping только из доступных slot/case/step refs или constants. "
    "Явные refs и selected_capability_id из запроса являются constraints и имеют приоритет над догадками. "
    "Если constraints.requires_output_mapping=true, заполняй output_mapping только в selected_output_slots. "
    "Если constraints.requires_output_mapping=false, верни output_mapping={} и не подбирай выходы. "
    "Используй descriptions слотов и полей capability как основной источник смысла. "
    "Возвращай итоговый input_mapping явно; администратор будет проверять deterministic source-ref и resolved values. "
    "Если descriptions/examples недостаточны или два слота похожи по смыслу, не угадывай: выбери самый явно описанный source-ref и отрази предположение в reason. "
    "Не выдумывай слоты, capability, input/output поля."
)


def result_container_paths_from_schema(schema: dict[str, Any] | None) -> list[dict[str, str]]:
    if not isinstance(schema, dict):
        return []
    root_type = schema_type(schema)
    if root_type in {"array", "object"} and root_type == "array":
        return [{"path": "", "kind": "array"}]
    containers = []
    for name, property_schema in schema_properties(schema).items():
        property_type = schema_type(property_schema)
        if property_type in {"array", "object"}:
            containers.append({"path": name, "kind": property_type})
    return containers


def operation_result_selector_path(
    response_schema: dict[str, Any] | None,
    output_slots_order: list[dict[str, Any]],
    operation_result: Any = None,
) -> tuple[str | None, str | None]:
    containers = result_container_paths_from_schema(response_schema)
    if isinstance(operation_result, dict) and operation_result:
        containers = [
            container
            for container in containers
            if not container["path"] or container["path"] in operation_result
        ]
    if not containers:
        return "", None

    source_roots = {
        root
        for root in (root_attribute(rule.get("source_hint")) for rule in output_slots_order or [])
        if root
    }
    response_properties = schema_properties(response_schema)
    if source_roots and any(root in response_properties for root in source_roots):
        container_roots = {container["path"] for container in containers}
        if not any(root in container_roots for root in source_roots):
            return "", None
    explicit_matches = [container for container in containers if container["path"] in source_roots]
    if len(explicit_matches) == 1:
        return explicit_matches[0]["path"], None
    if len(explicit_matches) > 1:
        paths = ", ".join(container["path"] or "<root>" for container in explicit_matches)
        return None, f"source_hint указывает на несколько контейнеров результата: {paths}."

    list_containers = [container for container in containers if container["kind"] == "array"]
    if len(list_containers) == 1:
        return list_containers[0]["path"], None
    object_containers = [container for container in containers if container["kind"] == "object"]
    if not list_containers and len(object_containers) == 1:
        return object_containers[0]["path"], None
    paths = ", ".join(container["path"] or "<root>" for container in containers)
    return None, (
        "Контракт результата содержит несколько возможных контейнеров. "
        f"Укажите поле контейнера в source_hint выходного слота: {paths}."
    )


def operation_result_local_hint(source_hint: str, result_summary: dict[str, Any] | None = None) -> str:
    hint = str(source_hint or "").replace("[]", "").strip(".")
    result_path = str((result_summary or {}).get("result_path") or "").strip(".")
    if result_path:
        if hint == result_path:
            return ""
        if hint.startswith(f"{result_path}."):
            hint = hint[len(result_path) + 1 :]
    parts = [part for part in hint.split(".") if part]
    if parts and parts[0].isdigit():
        parts = parts[1:]
    return ".".join(parts)


def selected_operation_result_schema(
    response_schema: dict[str, Any] | None,
    result_path: str | None,
) -> dict[str, Any] | None:
    selected_schema = schema_at_path(response_schema, result_path) if result_path else response_schema
    if schema_type(selected_schema) == "array":
        items = selected_schema.get("items", {}) if isinstance(selected_schema, dict) else {}
        return items if isinstance(items, dict) else None
    return selected_schema


def display_label(display_name: Any, technical_id: Any) -> str:
    display = str(display_name or "").strip()
    technical = str(technical_id or "").strip()
    if display and technical and display != technical:
        return f'"{display}" ({technical})'
    if display:
        return f'"{display}"'
    return technical


def output_slot_error_context(
    *,
    profile: dict[str, Any],
    rule: dict[str, Any],
    source_ref: dict[str, Any],
    tool: dict[str, Any],
    selected_schema: dict[str, Any] | None,
    source_hint: str,
    local_hint: str,
    slot_schema: dict[str, Any] | None,
) -> str:
    slot_id = str(rule.get("slot_id") or "")
    slot_by_id = {
        slot.get("slot_id"): slot
        for slot in (slot_schema or {}).get("slots", [])
        if slot.get("slot_id")
    }
    slot = slot_by_id.get(slot_id, {})
    steps = [
        {**step, "step_id": enrichment_step_id(step, index)}
        for index, step in enumerate(profile.get("enrichment_steps", []), start=1)
    ]
    step = next((item for item in steps if item.get("step_id") == source_ref.get("step_id")), {})
    step_index = next(
        (index for index, item in enumerate(steps, start=1) if item.get("step_id") == source_ref.get("step_id")),
        None,
    )
    step_prefix = f"шаг {step_index}" if step_index else f"шаг {source_ref.get('step_id') or 'н/д'}"
    step_label = display_label(
        step.get("step_name") or step.get("display_name"),
        step.get("step_id") or source_ref.get("step_id"),
    )
    tool_label = display_label(tool.get("display_name"), tool.get("tool_name"))
    available_fields = sorted(schema_properties(selected_schema).keys()) if selected_schema else []
    available_text = ", ".join(available_fields) if available_fields else "контракт не содержит именованных полей"
    return (
        f"Профиль {display_label(profile.get('display_name'), profile.get('profile_id'))} -> "
        f"Выходные слоты и порядок заполнения -> строка {rule.get('order') or '?'} "
        f"{display_label(slot.get('display_name'), slot_id)} -> Источник значения \"{source_hint}\": "
        f"поле \"{local_hint}\" отсутствует в результате {step_prefix} {step_label} / "
        f"capability {tool_label}. Доступные поля результата: {available_text}."
    )


def operation_response_items(
    operation_result: dict[str, Any],
    response_schema: dict[str, Any] | None = None,
    output_slots_order: list[dict[str, Any]] | None = None,
) -> tuple[int, dict[str, Any] | None, dict[str, Any]]:
    result_path, selector_error = operation_result_selector_path(
        response_schema,
        output_slots_order or [],
        operation_result,
    )
    if selector_error:
        return -1, None, {
            "result_type": "ambiguous",
            "source_status": "configuration_error",
            "reason": selector_error,
        }
    selected_result: Any = value_at_path(operation_result, result_path) if result_path else operation_result
    if selected_result is None:
        return 0, None, {
            "result_type": "missing",
            "result_path": result_path,
            "source_status": "mock_output",
        }
    operation_result = selected_result
    if isinstance(operation_result, list):
        return len(operation_result), (operation_result[0] if operation_result else None), {
            "result_type": "list",
            "result_path": result_path,
            "item_count": len(operation_result),
            "source_status": "mock_output",
        }
    if not isinstance(operation_result, dict):
        return 1, {"value": operation_result}, {
            "result_type": "scalar",
            "result_path": result_path,
            "object_found": True,
            "source_status": "mock_output",
        }
    object_found = operation_result.get("object_found")
    if object_found is False:
        return 0, None, {
            "result_type": "object",
            "result_path": result_path,
            "object_found": False,
            "source_status": "mock_output",
        }
    if result_path is not None:
        return 1, operation_result, {
            "result_type": "object",
            "result_path": result_path,
            "object_found": True,
            "source_status": "mock_output",
        }
    for key, value in operation_result.items():
        if isinstance(value, list):
            return len(value), (value[0] if value else None), {
                "result_type": "list",
                "result_path": key,
                "item_count": len(value),
                "source_status": "mock_output",
            }
        if isinstance(value, dict):
            return 1, value, {
                "result_type": "object",
                "result_path": key,
                "object_found": True,
                "source_status": "mock_output",
            }
    return 1, operation_result, {
        "result_type": "object",
        "result_path": result_path,
        "object_found": True,
        "source_status": "mock_output",
    }


def operation_result_value(
    result_item: dict[str, Any] | None,
    source_hint: str,
    result_summary: dict[str, Any] | None = None,
) -> Any:
    if not result_item or not source_hint:
        return None
    hint = operation_result_local_hint(source_hint, result_summary)
    return value_at_path(result_item, hint)


def resolved_output_rule_values(
    *,
    profile: dict[str, Any],
    enrichment_step_results: dict[str, Any],
    capability_by_id: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    output_values: dict[str, Any] = {}
    selected_items: dict[str, dict[str, Any]] = {}
    summaries: dict[str, dict[str, Any]] = {}
    counts: dict[str, int] = {}
    errors: list[str] = []
    enrichment_steps = profile.get("enrichment_steps", [])
    source_refs_by_rule: list[tuple[dict[str, Any], dict[str, Any]]] = []

    for rule in profile.get("output_slots_order", []):
        source_ref = output_source_hint_reference(rule.get("source_hint"), enrichment_steps)
        if source_ref.get("error"):
            errors.append(f"{rule.get('slot_id')}: {source_ref['error']}")
            continue
        source_refs_by_rule.append((rule, source_ref))

    for rule, source_ref in source_refs_by_rule:
        step_id = source_ref.get("step_id")
        step_result = enrichment_step_results.get(step_id or "")
        raw_result = (step_result or {}).get("result")
        capability = capability_by_id.get(source_ref.get("capability_id") or "")
        if raw_result is None or not capability:
            errors.append(f"{rule.get('slot_id')}: результат шага {step_id} недоступен.")
            continue
        if step_id not in selected_items:
            count, result_item, result_summary = operation_response_items(
                raw_result,
                capability.get("output_schema"),
                [
                    {**item_rule, "source_hint": item_ref.get("field", "")}
                    for item_rule, item_ref in source_refs_by_rule
                    if item_ref.get("step_id") == step_id
                ],
            )
            counts[step_id] = count
            summaries[step_id] = result_summary
            selected_items[step_id] = result_item or {}
            if result_summary.get("source_status") == "configuration_error":
                errors.append(result_summary.get("reason") or f"Контракт результата шага {step_id} неоднозначен.")
        result_item = selected_items.get(step_id) or {}
        result_summary = summaries.get(step_id) or {}
        value = operation_result_value(result_item, source_ref.get("field", ""), result_summary)
        if value is not None:
            output_values[rule["slot_id"]] = value

    return output_values, {
        "counts": counts,
        "summaries": summaries,
        "errors": errors,
        "source_status": "configuration_error" if errors else "mock_output",
    }


def resolution_profile_human_action(profile: dict[str, Any]) -> str:
    action = profile.get("human_resolution_policy", {}).get("action")
    if action == "escalate_operator":
        return "escalate_operator"
    return "ask_client"


def resolution_profile_message_template(profile: dict[str, Any]) -> str:
    policy = profile.get("human_resolution_policy", {})
    return (
        policy.get("message_template")
        or policy.get("clarification_question")
        or profile.get("fallback", {}).get("question")
        or "Уточните данные для заполнения слота."
    )


def unresolved_resolution_decision(
    *,
    profile: dict[str, Any],
    output_values: dict[str, Any],
    confidence: float,
    reason: str,
) -> dict[str, Any]:
    message = resolution_profile_message_template(profile)
    if resolution_profile_human_action(profile) == "escalate_operator":
        return {
            "decision": "handoff",
            "status": "operator_handoff",
            "filled_slots": output_values,
            "confidence": confidence,
            "next_question": "",
            "handoff_message": message,
            "message": message,
            "reason": reason,
        }
    return {
        "decision": "ask_clarification",
        "status": "question_required",
        "filled_slots": output_values,
        "confidence": confidence,
        "next_question": message,
        "handoff_message": "",
        "message": message,
        "reason": reason,
    }


def simulated_llm_resolution_decision(
    *,
    profile: dict[str, Any],
    result_item: dict[str, Any] | None,
    result_summary: dict[str, Any] | None = None,
    count: int,
    confidence: float,
    effective_thresholds: dict[str, float],
    precomputed_output_values: dict[str, Any] | None = None,
) -> dict[str, Any]:
    output_values = dict(precomputed_output_values or {})
    if count == 1 and result_item and not precomputed_output_values:
        for rule in profile["output_slots_order"]:
            value = operation_result_value(result_item, rule.get("source_hint", ""), result_summary)
            if value is not None:
                output_values[rule["slot_id"]] = value
    required_slots = [
        rule["slot_id"]
        for rule in profile["output_slots_order"]
        if rule.get("required_for_success")
    ]
    missing_required = [
        slot_id
        for slot_id in required_slots
        if output_values.get(slot_id) in (None, "")
    ]
    if count == 1 and not missing_required and confidence >= effective_thresholds["auto_accept_confidence"]:
        return {
            "decision": "fill",
            "status": "filled",
            "filled_slots": output_values,
            "confidence": confidence,
            "next_question": "",
            "reason": "LLM-правило dry-run приняло единственный результат операции.",
        }
    if count == 0:
        reason = "Операция не вернула результатов."
    elif count > 1:
        reason = "Операция вернула несколько результатов."
    elif missing_required:
        reason = f"Не заполнены обязательные выходные слоты: {', '.join(missing_required)}."
    else:
        reason = "Confidence результата ниже порога автозаполнения."
    return unresolved_resolution_decision(
        profile=profile,
        output_values={},
        confidence=confidence,
        reason=reason,
    )


def direct_mapping_resolution_decision(
    *,
    profile: dict[str, Any],
    result_item: dict[str, Any] | None,
    result_summary: dict[str, Any] | None = None,
    count: int,
    confidence: float,
    precomputed_output_values: dict[str, Any] | None = None,
) -> dict[str, Any]:
    output_values = dict(precomputed_output_values or {})
    if count == 1 and result_item and not precomputed_output_values:
        for rule in profile["output_slots_order"]:
            value = operation_result_value(result_item, rule.get("source_hint", ""), result_summary)
            if value is not None:
                output_values[rule["slot_id"]] = value
    required_rules = [
        rule
        for rule in profile["output_slots_order"]
        if rule.get("required_for_success")
    ]
    missing_required = [
        rule
        for rule in required_rules
        if output_values.get(rule["slot_id"]) in (None, "")
    ]
    if count == 1 and not missing_required:
        return {
            "decision": "fill",
            "status": "filled",
            "filled_slots": output_values,
            "confidence": confidence,
            "next_question": "",
            "reason": "Выходные слоты заполнены прямым маппингом результата capability.",
        }
    if count == 0:
        reason = "Операция не вернула результатов."
    elif count > 1:
        reason = "Операция вернула несколько результатов; без LLM-правила выбрать результат нельзя."
    elif missing_required:
        reason = "Не заполнены обязательные выходные слоты: " + ", ".join(rule["slot_id"] for rule in missing_required) + "."
    else:
        reason = "Не удалось заполнить слоты прямым маппингом."
    if missing_required and all(rule.get("fallback") == "leave_empty" for rule in missing_required):
        return {
            "decision": "leave_empty",
            "status": "skipped",
            "filled_slots": output_values,
            "confidence": confidence,
            "next_question": "",
            "reason": f"{reason} Профиль настроен продолжить сценарий без заполнения этих слотов.",
        }
    return unresolved_resolution_decision(
        profile=profile,
        output_values=output_values,
        confidence=confidence,
        reason=reason,
    )


def resolution_profile_question(profile: dict[str, Any]) -> str | None:
    if resolution_profile_human_action(profile) != "ask_client":
        return None
    return resolution_profile_message_template(profile)


def resolution_profile_current_step(profile: dict[str, Any]) -> dict[str, Any] | None:
    for step in profile.get("steps", []):
        if step["type"] in {"clarification", "operator_handoff", "escalate"}:
            return step
    return profile.get("steps", [None])[-1]


def endpoint_operation_async_usage_refs(
    endpoint_id: str,
    operation_id: str,
    event_type: str,
    attribute_resolution_profiles: dict[str, Any] | None = None,
) -> list[str]:
    refs: list[str] = []
    for profile in (attribute_resolution_profiles or {}).get("profiles", []):
        for step in profile.get("enrichment_steps", []):
            completion_policy = step.get("completion_policy") or {}
            if completion_policy.get("mode") != "external_event":
                continue
            if completion_policy.get("expected_event_type") != event_type:
                continue
            if step.get("endpoint_id") != endpoint_id or step.get("operation_id") != operation_id:
                continue
            refs.append(f"{profile.get('profile_id')}.{step.get('step_id')}")
    return refs


def root_attribute(attribute_ref: str | None) -> str | None:
    if not attribute_ref:
        return None
    return attribute_ref.split(".", 1)[0]


def value_at_path(value: Any, path: str | None) -> Any:
    if not path:
        return None
    current = value
    for part in path.split("."):
        if current is None:
            return None
        if isinstance(current, list):
            if part.isdigit():
                index = int(part)
                current = current[index] if index < len(current) else None
            else:
                return None
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def result_items_from_operation_response(operation_result: dict[str, Any], result_policy: dict[str, Any]) -> tuple[int, dict[str, Any] | None, dict[str, Any]]:
    result_type = result_policy.get("result_type")
    if result_type == "object":
        raw_success = value_at_path(operation_result, result_policy.get("success_path"))
        object_path = result_policy.get("object_path")
        object_value = value_at_path(operation_result, object_path) if object_path else operation_result
        selected_object = object_value if isinstance(object_value, dict) else None
        if isinstance(raw_success, bool):
            count = 1 if raw_success else 0
        elif selected_object:
            count = 1
        else:
            count = 0
        if count == 1 and selected_object is None and isinstance(operation_result, dict):
            selected_object = operation_result
        return count, selected_object, {
            "result_type": "object",
            "object_found": count == 1,
            "source_status": "mock_output",
        }

    raw_items = value_at_path(operation_result, result_policy.get("list_path"))
    items = raw_items if isinstance(raw_items, list) else []
    first_item = items[0] if items and isinstance(items[0], dict) else None
    return len(items), first_item, {
        "result_type": "list",
        "item_count": len(items),
        "source_status": "mock_output",
    }


def result_value(result_item: dict[str, Any] | None, result_policy: dict[str, Any], slot_id: str) -> Any:
    if not result_item:
        return None
    value = value_at_path(result_item, result_policy.get("target_value_path"))
    if value is None:
        value = value_at_path(result_item, result_policy.get("output_mapping", {}).get(slot_id))
    return value


def result_confidence(result_item: dict[str, Any] | None, result_policy: dict[str, Any]) -> float:
    if not result_item:
        return 0.0
    raw_confidence = value_at_path(result_item, result_policy.get("confidence_path"))
    try:
        return max(0.0, min(1.0, float(raw_confidence)))
    except (TypeError, ValueError):
        return 0.9


def normalized_match_text(value: str) -> str:
    return " ".join(str(value or "").lower().split())


def classification_rule(
    text: str,
    *,
    match_type: str = "contains",
    polarity: str = "positive",
    weight: float = 0.5,
    required: bool = False,
    blocking: bool = False,
    explanation: str | None = None,
) -> dict[str, Any]:
    return {
        "text": text,
        "match_type": match_type,
        "polarity": polarity,
        "weight": weight,
        "required": required,
        "blocking": blocking,
        "explanation": explanation or f"Признак классификации: {text}",
    }


def classification_rule_matches(text: str, rule: dict[str, Any]) -> bool:
    normalized_text = normalized_match_text(text)
    normalized_rule = normalized_match_text(rule.get("text", ""))
    if not normalized_rule:
        return False
    match_type = rule.get("match_type", "contains")
    if match_type == "word":
        return re.search(rf"(?<!\w){re.escape(normalized_rule)}(?!\w)", normalized_text, re.UNICODE) is not None
    if match_type == "phrase":
        return normalized_rule in normalized_text
    return normalized_rule in normalized_text


def score_classification_route(route: dict[str, Any], text: str) -> dict[str, Any]:
    rule_items = route.get("rules", {}).get("rule_items", [])
    positive_total = 0.0
    positive_score = 0.0
    negative_score = 0.0
    positive_hits: list[dict[str, Any]] = []
    negative_hits: list[dict[str, Any]] = []
    required_missing: list[dict[str, Any]] = []
    blocked_by_rules: list[dict[str, Any]] = []
    for rule in rule_items:
        weight = float(rule.get("weight") or 0)
        matched = classification_rule_matches(text, rule)
        rule_summary = {
            "text": rule.get("text"),
            "match_type": rule.get("match_type"),
            "polarity": rule.get("polarity"),
            "weight": weight,
            "explanation": rule.get("explanation"),
        }
        if rule.get("polarity") == "negative":
            if matched:
                negative_score += weight
                negative_hits.append(rule_summary)
                if rule.get("blocking"):
                    blocked_by_rules.append(rule_summary)
            continue
        positive_total += weight
        if matched:
            positive_score += weight
            positive_hits.append(rule_summary)
        elif rule.get("required"):
            required_missing.append(rule_summary)

    if blocked_by_rules or required_missing or positive_total <= 0:
        confidence = 0.0
    else:
        confidence = max(0.0, min(1.0, positive_score - negative_score))

    return {
        "route_id": route["route_id"],
        "display_name": route.get("display_name", route["route_id"]),
        "route": route["route"],
        "priority": route["priority"],
        "workflow_state_id": route["workflow_state_id"],
        "confidence": round(confidence, 3),
        "positive_score": round(positive_score, 3),
        "negative_score": round(negative_score, 3),
        "positive_hits": positive_hits,
        "negative_hits": negative_hits,
        "required_missing": required_missing,
        "blocked_by_rules": blocked_by_rules,
    }


def classification_decision_level(confidence: float, route: dict[str, Any] | None) -> str:
    thresholds = (route or {}).get("confidence", {})
    rules_min = float(thresholds.get("rules_min", 0.85))
    llm_min = float(thresholds.get("llm_min", 0.70))
    human_handoff_below = float(thresholds.get("human_handoff_below", 0.50))
    if confidence >= rules_min:
        return "accepted_by_rules"
    if confidence >= llm_min:
        return "llm_required"
    if confidence >= human_handoff_below:
        return "human_review_required"
    return "human_required"


def humanize_config_id(value: str) -> str:
    return value.replace("_", " ").replace("-", " ")


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
    "interaction_channels": ConfigDomain(
        domain="interaction_channels",
        title="Каналы взаимодействия",
        contract_name="interaction_channels",
        read_permission="workflow.read",
        manage_permission="workflow.manage",
    ),
    "attribute_resolution_profiles": ConfigDomain(
        domain="attribute_resolution_profiles",
        title="Профили разрешения атрибутов",
        contract_name="attribute_resolution_profiles",
        read_permission="workflow.read",
        manage_permission="workflow.manage",
    ),
    "capabilities": ConfigDomain(
        domain="capabilities",
        title="Каталог capabilities",
        contract_name="capability_catalog",
        read_permission="workflow.read",
        manage_permission="workflow.manage",
    ),
    "mcp_environments": ConfigDomain(
        domain="mcp_environments",
        title="Каталог внешних MCP-окружений",
        contract_name="mcp_environment_catalog",
        read_permission="tools.read",
        manage_permission="tools.manage",
    ),
    "capability_bindings": ConfigDomain(
        domain="capability_bindings",
        title="Привязки capabilities к MCP-окружениям",
        contract_name="capability_binding_catalog",
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
        if domain == "workflow_states":
            return copy.deepcopy(self.contracts.workflow_state_catalog)
        if domain == "workflow_transitions":
            return copy.deepcopy(self.contracts.workflow_transition_rules)
        if domain == "prompts":
            return default_prompt_catalog()
        if domain == "model_routing":
            return default_model_routing()
        if domain == "interaction_channels":
            return default_interaction_channels()
        if domain == "attribute_resolution_profiles":
            return default_attribute_resolution_profiles()
        if domain == "capabilities":
            return default_capabilities()
        if domain == "mcp_environments":
            return default_mcp_environments()
        if domain == "capability_bindings":
            return default_capability_bindings()
        if domain == "service_scenarios":
            return default_service_scenarios()
        if domain == "slot_schemas":
            return default_slot_schemas()
        if domain == "classification_routes":
            return default_classification_routes()
        if domain == "orchestrator_policy":
            return default_orchestrator_policy()
        if domain == "prompt_packs":
            return default_prompt_packs()
        if domain == "escalation_policies":
            return default_escalation_policies()
        raise ConfigRegistryError(f"Неизвестный домен конфигурации: {domain}")

    def active_config(self, domain: str) -> dict[str, Any]:
        self._require_domain(domain)
        active_version = self.active_version(domain)
        if active_version:
            normalized_payload = self._normalize_payload(domain, active_version["payload"])
            version = copy.deepcopy(active_version)
            version["payload"] = normalized_payload
            return {
                "schema_version": "1.0",
                "domain": domain,
                "source": "active_version",
                "active_version_id": active_version["version_id"],
                "payload": normalized_payload,
                "version": version,
            }
        return {
            "schema_version": "1.0",
            "domain": domain,
            "source": "default",
            "active_version_id": None,
            "payload": self._normalize_payload(domain, self.default_config(domain)),
        }

    def active_payload(self, domain: str) -> dict[str, Any]:
        overrides = _ACTIVE_PAYLOAD_OVERRIDES.get()
        if overrides and domain in overrides:
            return self._normalize_payload(domain, overrides[domain])
        return self.active_config(domain)["payload"]

    @contextmanager
    def active_payload_overrides(self, overrides: dict[str, dict[str, Any]] | None):
        normalized = self._validation_overrides(overrides)
        token = _ACTIVE_PAYLOAD_OVERRIDES.set(normalized) if normalized else None
        try:
            yield
        finally:
            if token is not None:
                _ACTIVE_PAYLOAD_OVERRIDES.reset(token)

    def _validation_overrides(
        self,
        overrides: dict[str, dict[str, Any]] | None,
    ) -> dict[str, dict[str, Any]] | None:
        if not overrides:
            return None
        return {domain: copy.deepcopy(payload) for domain, payload in overrides.items()}

    def _legacy_client_waiting_defaults(self) -> dict[str, Any]:
        active_version = self.active_version("escalation_policies")
        payload = active_version["payload"] if active_version else self.default_config("escalation_policies")
        return client_waiting_defaults_from_legacy_escalation(payload)

    def validate_external_event_result_contract(self, wait: dict[str, Any], event: dict[str, Any]) -> None:
        origin = wait.get("origin") or {}
        if origin.get("kind") != "capability":
            return
        snapshot = self._wait_contract_snapshot(wait)
        if snapshot:
            endpoint_id = snapshot.get("endpoint_id")
            operation_id = snapshot.get("operation_id")
            capability_id = snapshot.get("capability_id")
            async_contracts = {
                snapshot.get("event_type"): copy.deepcopy(snapshot.get("async_event_contract") or {})
            }
        else:
            capability_id = origin.get("capability_id")
            endpoint_id = None
            operation_id = None
            if not capability_id:
                return
            capability = self._by_id(
                self.active_payload("capabilities").get("capabilities", []),
                "capability_id",
            ).get(capability_id)
            if not capability:
                raise ContractValidationError(
                    "external_event_result",
                    [f"Не найдена capability для ожидания: {capability_id}."],
                )
            async_contracts = capability.get("async_event_contracts") or {}
        if not async_contracts:
            return
        event_type = event.get("event_type")
        async_contract = async_contracts.get(event_type)
        contract_owner = capability_id or f"{endpoint_id}/{operation_id}"
        if not async_contract:
            raise ContractValidationError(
                "external_event_result",
                [f"{contract_owner} не содержит async_event_contracts.{event_type}."],
            )
        errors = []
        if async_contract.get("contract_status") == "broken":
            errors.append(f"{contract_owner}/{event_type} имеет contract_status=broken.")
        status = event.get("status")
        allowed_statuses = set(async_contract.get("statuses") or [])
        if allowed_statuses and status not in allowed_statuses:
            errors.append(
                f"{contract_owner}/{event_type} не допускает status={status}; "
                f"разрешено: {', '.join(sorted(allowed_statuses))}."
            )
        schema_key = {
            "success": "result_schema",
            "progress": "progress_schema",
            "error": "error_schema",
        }.get(status)
        payload_key = "error" if status == "error" else "result"
        schema = async_contract.get(schema_key or "") if schema_key else None
        if schema:
            if payload_key not in event:
                errors.append(f"{event_type} status={status} должен содержать {payload_key}.")
            else:
                validator = Draft202012Validator(schema)
                for error in validator.iter_errors(event[payload_key]):
                    path = ".".join(str(item) for item in error.path) or "$"
                    errors.append(f"{event_type}.{payload_key}.{path}: {error.message}")
        if errors:
            raise ContractValidationError("external_event_result", errors)

    def capability_event_contract_snapshot(
        self,
        *,
        capability_id: str,
        event_type: str,
    ) -> dict[str, Any]:
        capability = self._by_id(
            self.active_payload("capabilities").get("capabilities", []),
            "capability_id",
        ).get(capability_id)
        async_contract = (capability or {}).get("async_event_contracts", {}).get(event_type)
        if not capability or not async_contract:
            raise ContractValidationError(
                "external_event_result",
                [f"Не найден async_event_contracts.{event_type} для capability {capability_id}."],
            )
        return {
            "schema_version": "1.0",
            "capability_id": capability_id,
            "capability_contract_version": capability.get("contract_version"),
            "event_type": event_type,
            "async_event_contract": copy.deepcopy(async_contract),
        }

    @staticmethod
    def _wait_contract_snapshot(wait: dict[str, Any]) -> dict[str, Any] | None:
        payload = wait.get("payload") or {}
        origin = wait.get("origin") or {}
        snapshot = payload.get("contract_snapshot") or origin.get("contract_snapshot")
        return snapshot if isinstance(snapshot, dict) else None

    def _normalize_payload(self, domain: str, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = copy.deepcopy(payload)
        scenario_names = {
            item["scenario_id"]: item["display_name"]
            for item in DEFAULT_SCENARIOS
        }
        if domain == "capabilities":
            normalized = normalize_capability_contracts(normalized)
        elif domain == "service_scenarios":
            for scenario in normalized.get("scenarios", []):
                scenario.pop("tool_launch_matrix_id", None)
                scenario.setdefault("default_channel_id", "debug")
                scenario.setdefault("allowed_channel_ids", ["messenger_bot", "service_desk", "debug"])
                scenario.setdefault("audit_required", True)
                scenario.setdefault("log_required", True)
        elif domain == "attribute_resolution_profiles":
            normalized["profiles"] = [
                normalize_attribute_resolution_profile(profile)
                for profile in normalized.get("profiles", [])
            ]
            self._normalize_attribute_resolution_completion_policies(normalized["profiles"])
            self._assign_attribute_resolution_slot_schema_ids(normalized["profiles"])
        elif domain == "slot_schemas":
            for slot_schema in normalized.get("slot_schemas", []):
                slot_schema.pop("scenario_id", None)
                slot_schema.pop("timeouts", None)
                normalize_slot_schema_stages(slot_schema)
        elif domain == "classification_routes":
            route_mapping = {
                "agent_l1": "agent_with_confirmation",
                "l1_hint": "human_review",
            }
            for route in normalized.get("routes", []):
                scenario_id = route.pop("scenario_id", None)
                route.setdefault("display_name", f"Маршрут: {scenario_names.get(scenario_id or '', route['route_id'])}")
                if route.get("route") in route_mapping:
                    route["route"] = route_mapping[route["route"]]
        elif domain == "orchestrator_policy":
            normalized["confidence_defaults"] = normalize_confidence_thresholds(
                normalized.get("confidence_defaults"),
                require_all=True,
            )
            normalized["editor_reference_hints"] = normalize_editor_reference_hints(
                normalized.get("editor_reference_hints"),
            )
            for policy in normalized.get("policies", []):
                scenario_id = policy.pop("scenario_id", None)
                policy.setdefault("display_name", f"Политика оркестрации: {scenario_names.get(scenario_id or '', policy['policy_id'])}")
        elif domain == "escalation_policies":
            for policy in normalized.get("policies", []):
                scenario_id = policy.pop("scenario_id", None)
                policy.setdefault("display_name", f"Решение и эскалация: {scenario_names.get(scenario_id or '', policy['policy_id'])}")
                policy.setdefault("auto_close", {})
                policy["auto_close"].setdefault("requires_capability_success", True)
                policy["auto_close"].pop("requires_user_confirmation", None)
                policy.pop("waiting", None)
                policy.pop("channel_profile_mapping", None)
        elif domain == "interaction_channels":
            legacy_waiting_defaults = self._legacy_client_waiting_defaults()
            for channel in normalized.get("channels", []):
                channel["capabilities"] = normalize_channel_capabilities(
                    channel.get("capabilities"),
                    channel_id=channel.get("channel_id"),
                    mode=channel.get("mode"),
                )
                channel["technical_profile"] = normalize_channel_technical_profile(
                    channel.get("technical_profile"),
                    channel_id=channel.get("channel_id"),
                )
                channel["channel_parameters"] = normalize_channel_parameters(
                    channel.get("channel_parameters"),
                    channel_id=channel.get("channel_id"),
                )
                channel.pop("audit_required", None)
                channel["waiting_policy"] = normalize_channel_waiting_policy(
                    channel.get("waiting_policy"),
                    legacy_waiting_defaults,
                )
                for legacy_action_key in (
                    "question_delivery",
                    "incomplete_discussion_action",
                    "escalation_action",
                    "action_profiles",
                ):
                    channel.pop(legacy_action_key, None)
        elif domain == "prompt_packs":
            replacements = {
                "передай Л1": "передай человеку",
                "передачей Л1": "эскалацией оператору",
                "Передавай на Л2": "Передавай в канал эскалации",
                "эскалируй на Л2": "эскалируй через канал взаимодействия",
                "Л1": "человеку",
                "Л2": "канал эскалации",
            }
            for pack in normalized.get("packs", []):
                pack.pop("scenario_id", None)
                blocks = pack.get("blocks", {})
                for block_key, block_text in list(blocks.items()):
                    if isinstance(block_text, str):
                        for source, target in replacements.items():
                            block_text = block_text.replace(source, target)
                        blocks[block_key] = block_text
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

    def _assign_attribute_resolution_slot_schema_ids(self, profiles: list[dict[str, Any]]) -> None:
        try:
            slot_schemas = self.active_payload("slot_schemas")["slot_schemas"]
        except Exception:
            slot_schemas = self.default_config("slot_schemas")["slot_schemas"]
        refs_by_profile: dict[str, list[str]] = {}
        slots_by_schema = {
            schema["slot_schema_id"]: {slot["slot_id"] for slot in schema.get("slots", [])}
            for schema in slot_schemas
        }
        for schema in slot_schemas:
            schema_id = schema["slot_schema_id"]
            for profile_id in [
                stage.get("resolution_profile_id")
                for stage in slot_schema_stages(schema)
                if stage.get("resolution_profile_id")
            ]:
                refs_by_profile.setdefault(profile_id, []).append(schema_id)
            for slot in schema.get("slots", []):
                profile_id = slot.get("resolution_profile_id")
                if profile_id:
                    refs_by_profile.setdefault(profile_id, []).append(schema_id)
        for profile in profiles:
            if profile.get("slot_schema_id"):
                continue
            profile_id = profile.get("profile_id", "")
            referenced_schema_ids = refs_by_profile.get(profile_id, [])
            if referenced_schema_ids:
                profile["slot_schema_id"] = referenced_schema_ids[0]
                continue
            related_slots = {
                profile.get("target_slot_id"),
                *[item.get("slot_id") for item in profile.get("output_slots_order", [])],
            }
            related_slots = {slot_id for slot_id in related_slots if slot_id}
            best_schema_id = ""
            best_score = 0
            for schema_id, slot_ids in slots_by_schema.items():
                score = len(related_slots & slot_ids)
                if score > best_score:
                    best_schema_id = schema_id
                    best_score = score
            if best_schema_id:
                profile["slot_schema_id"] = best_schema_id

    def _active_capability_binding_for_step(self, step: dict[str, Any]) -> dict[str, Any] | None:
        capability_id = step.get("capability_id")
        environment_id = step.get("mcp_environment_id")
        candidates = [
            binding
            for binding in self.active_payload("capability_bindings").get("bindings", [])
            if binding.get("capability_id") == capability_id
            and binding.get("status") == "active"
            and (not environment_id or binding.get("environment_id") == environment_id)
        ]
        return candidates[0] if len(candidates) == 1 else None

    def _completion_policy_for_capability_step(
        self,
        step: dict[str, Any],
        capability_by_id: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        capability = capability_by_id.get(str(step.get("capability_id") or ""))
        default_policy = copy.deepcopy((capability or {}).get("default_completion_policy") or {})
        if default_policy:
            return default_policy
        binding = self._active_capability_binding_for_step(step)
        if (binding or {}).get("execution_mode") == "sync":
            return {"mode": "sync", "max_wait_seconds": 0, "timeout_action": "resume_agent"}
        return {}

    def _normalize_attribute_resolution_completion_policies(self, profiles: list[dict[str, Any]]) -> None:
        capability_by_id = self._by_id(
            self.active_payload("capabilities").get("capabilities", []),
            "capability_id",
        )
        for profile in profiles:
            for step in profile.get("enrichment_steps", []) or []:
                if not step.get("capability_id"):
                    continue
                policy = step.get("completion_policy")
                if isinstance(policy, dict) and policy:
                    continue
                if policy is not None and not completion_policy_is_empty(policy):
                    continue
                normalized_policy = self._completion_policy_for_capability_step(step, capability_by_id)
                if normalized_policy:
                    step["completion_policy"] = normalized_policy
                else:
                    step.pop("completion_policy", None)

    def _profile_capability_launch(
        self,
        *,
        profile: dict[str, Any],
        step: dict[str, Any],
        capability_by_id: dict[str, dict[str, Any]],
        environment_by_id: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        capability_id = step.get("capability_id")
        capability = capability_by_id.get(capability_id or "")
        binding = self._active_capability_binding_for_step(step)
        environment = environment_by_id.get((binding or {}).get("environment_id") or step.get("mcp_environment_id") or "")
        policy = copy.deepcopy(step.get("completion_policy") or (capability or {}).get("default_completion_policy") or {})
        if (binding or {}).get("execution_mode") == "sync" and not policy:
            policy = {"mode": "sync", "max_wait_seconds": 0, "timeout_action": "mark_failed"}
        input_mapping = parameter_mapping_with_schema_defaults(
            (capability or {}).get("input_schema", {}),
            copy.deepcopy(step.get("input_mapping") or {}),
        )
        return {
            "launch_id": f"{profile.get('profile_id')}.{step.get('step_id')}",
            "launch_type": "capability",
            "profile_id": profile.get("profile_id"),
            "profile_name": profile.get("display_name"),
            "slot_schema_id": profile.get("slot_schema_id"),
            "target_slot_id": profile.get("target_slot_id"),
            "output_slots_order": copy.deepcopy(profile.get("output_slots_order", [])),
            "step_id": step.get("step_id"),
            "step_name": step.get("step_name"),
            "tool_name": capability_id,
            "capability_id": capability_id,
            "mcp_environment_id": (environment or {}).get("environment_id") or step.get("mcp_environment_id"),
            "mcp_tool_name": (binding or {}).get("mcp_tool_name"),
            "execution_mode": (binding or {}).get("execution_mode"),
            "action_type": "read_only",
            "parameter_bindings": input_mapping,
            "required_slots": required_source_ref_slot_ids(
                (capability or {}).get("input_schema") or {},
                input_mapping,
            ),
            "input_schema": copy.deepcopy((capability or {}).get("input_schema") or {}),
            "completion_policy": policy,
            "capability_exists": bool(capability),
            "binding_exists": bool(binding),
            "environment_exists": bool(environment),
        }

    def _profile_tool_launches(self, profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        capability_by_id = self._by_id(
            self.active_payload("capabilities").get("capabilities", []),
            "capability_id",
        )
        environment_by_id = self._by_id(
            self.active_payload("mcp_environments").get("environments", []),
            "environment_id",
        )
        launches: list[dict[str, Any]] = []
        for profile in profiles:
            for step in profile.get("enrichment_steps", []):
                if step.get("capability_id"):
                    launches.append(
                        self._profile_capability_launch(
                            profile=profile,
                            step=step,
                            capability_by_id=capability_by_id,
                            environment_by_id=environment_by_id,
                        )
                    )
        return launches

    @staticmethod
    def _planned_wait_for_launch(launch: dict[str, Any]) -> dict[str, Any] | None:
        policy = launch.get("completion_policy") or {}
        if policy.get("mode") != "external_event":
            return None
        planned_wait = {
            "wait_type": "external_event_wait",
            "expected_event_type": policy.get("expected_event_type"),
            "result_transport": policy.get("result_transport"),
            "result_topic": policy.get("result_topic") or DEFAULT_EXTERNAL_EVENT_RESULT_TOPIC,
            "max_wait_seconds": policy.get("max_wait_seconds"),
            "timeout_action": policy.get("timeout_action"),
        }
        if launch.get("launch_type") == "capability":
            planned_wait.update(
                {
                    "capability_id": launch.get("capability_id"),
                    "mcp_environment_id": launch.get("mcp_environment_id"),
                    "mcp_tool_name": launch.get("mcp_tool_name"),
                    "execution_mode": launch.get("execution_mode"),
                }
            )
        return planned_wait

    def _simulate_profile_launches(
        self,
        launches: list[dict[str, Any]],
        *,
        slot_values: dict[str, Any],
        provided: dict[str, Any] | None = None,
        missing_slots: list[str],
        simulation_options: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        ready_launches: list[dict[str, Any]] = []
        blocked_launches: list[dict[str, Any]] = []
        next_allowed_actions: list[dict[str, Any]] = []
        missing_slot_set = set(missing_slots)
        blocked_profile_steps: dict[str, dict[str, Any]] = {}
        for launch in launches:
            missing_parameter_slots = [
                slot_id
                for slot_id in launch.get("required_slots", [])
                if slot_id in missing_slot_set
                or (slot_values.get(slot_id) or {}).get("value") in (None, "")
            ]
            item = {
                **copy.deepcopy(launch),
                "missing_parameter_slots": missing_parameter_slots,
                "unknown_required_slots": [],
                "planned_wait": self._planned_wait_for_launch(launch),
            }
            parameters = resolved_dry_run_parameters(
                launch.get("parameter_bindings") or {},
                provided=provided or {},
                slot_values=slot_values,
            )
            parameters, applied_parameter_defaults = apply_schema_parameter_defaults(
                launch.get("input_schema") or {},
                parameters,
            )
            if applied_parameter_defaults:
                item["applied_parameter_defaults"] = applied_parameter_defaults
            input_resolution = capability_input_resolution_rows(
                schema=launch.get("input_schema") or {},
                mapping=launch.get("parameter_bindings") or {},
                parameters=parameters,
                applied_defaults=applied_parameter_defaults,
                provided=provided or {},
                slot_values=slot_values,
            )
            parameters = drop_missing_optional_capability_inputs(parameters, input_resolution)
            item["parameters"] = copy.deepcopy(parameters)
            missing_input_resolution = missing_capability_input_resolution(input_resolution)
            item["input_resolution"] = input_resolution
            if missing_input_resolution:
                item["missing_inputs"] = missing_input_resolution
            profile_key = str(launch.get("profile_id") or launch.get("launch_id") or "")
            previous_blocker = blocked_profile_steps.get(profile_key)
            if previous_blocker:
                item["status"] = "blocked_by_previous_step"
                item["previous_launch_id"] = previous_blocker.get("launch_id")
                item["block_reasons"] = [
                    (
                        f"Ожидается предыдущий шаг профиля: "
                        f"{previous_blocker.get('launch_id') or previous_blocker.get('step_id') or 'н/д'}."
                    )
                ]
                blocked_launches.append(item)
                continue
            if launch.get("launch_type") == "capability":
                config_missing = [
                    label
                    for label, exists in (
                        ("capability", launch.get("capability_exists")),
                        ("capability_binding", launch.get("binding_exists")),
                        ("mcp_environment", launch.get("environment_exists")),
                    )
                    if not exists
                ]
                if config_missing:
                    item["status"] = "blocked_by_configuration"
                    item["block_reasons"] = config_missing
                    blocked_launches.append(item)
                    if profile_key:
                        blocked_profile_steps[profile_key] = item
                    continue
            if missing_parameter_slots:
                item["status"] = "blocked_by_missing_slots"
                item["block_reasons"] = [
                    (
                        f"{row.get('input')} <- {row.get('source_ref')}: значение не заполнено"
                        if row.get("source_ref")
                        else f"{row.get('input')}: значение не заполнено"
                    )
                    for row in missing_input_resolution
                    if row.get("slot_id") in missing_parameter_slots
                ] or [
                    f"Не заполнены слоты параметров: {', '.join(missing_parameter_slots)}."
                ]
                blocked_launches.append(item)
                if profile_key:
                    blocked_profile_steps[profile_key] = item
                continue
            missing_required_input_groups = missing_required_parameter_groups(
                launch.get("input_schema") or {},
                parameters,
            )
            if missing_required_input_groups:
                missing_required_inputs = [
                    format_required_parameter_group(group)
                    for group in missing_required_input_groups
                ]
                item["status"] = "blocked_by_missing_required_inputs"
                item["missing_required_inputs"] = missing_required_inputs
                item["block_reasons"] = [
                    "Не заполнены обязательные параметры capability: "
                    f"{', '.join(missing_required_inputs)}."
                ]
                blocked_launches.append(item)
                if profile_key:
                    blocked_profile_steps[profile_key] = item
                continue
            if simulation_options.get("bypass_policy_gates"):
                item["status"] = "ready"
            elif launch.get("action_type") == "action" and not simulation_options.get("allow_action_with_approval"):
                item["status"] = "approval_required"
            else:
                item["status"] = "ready"
            ready_launches.append(item)
            action_extensions = {
                "capability_id": launch.get("capability_id"),
                "mcp_environment_id": launch.get("mcp_environment_id"),
                "mcp_tool_name": launch.get("mcp_tool_name"),
                "execution_mode": launch.get("execution_mode"),
                "completion_policy": launch.get("completion_policy"),
                "source_profile_id": launch.get("profile_id"),
                "source_step_id": launch.get("step_id"),
                "source_slot_schema_id": launch.get("slot_schema_id"),
                "source_target_slot_id": launch.get("target_slot_id"),
                "source_output_slots_order": launch.get("output_slots_order"),
            }
            async_diagnostics_level = str(simulation_options.get("async_diagnostics_level") or "off").lower()
            if launch.get("completion_policy", {}).get("mode") == "external_event" and async_diagnostics_level != "off":
                item["async_diagnostics"] = {
                    "level": async_diagnostics_level,
                    "source": "scenario_simulation",
                    "run_mode": simulation_options.get("run_mode"),
                }
                action_extensions["async_diagnostics"] = {
                    "level": async_diagnostics_level,
                    "source": "scenario_simulation",
                    "run_mode": simulation_options.get("run_mode"),
                }
            action_extensions = {
                key: value
                for key, value in action_extensions.items()
                if value not in (None, "", {}, [])
            }
            next_allowed_actions.append(
                {
                    "tool_name": launch.get("tool_name") or launch.get("capability_id") or launch.get("mcp_tool_name"),
                    "capability_id": launch.get("capability_id"),
                    "action_id": f"{launch.get('launch_id')}.action",
                    "action_type": "mcp_capability" if launch.get("launch_type") == "capability" else launch.get("action_type"),
                    "parameters": copy.deepcopy(parameters),
                    "reason": (
                        "Автоматический запуск шага профиля разрешения "
                        f"{launch.get('profile_name') or launch.get('profile_id')}."
                    ),
                    "risk_level": "medium" if launch.get("action_type") == "action" else "low",
                    "expected_effect": (
                        "Внешняя MCP capability будет вызвана с параметрами, рассчитанными "
                        "из заполненных слотов сценария."
                    ),
                    "requires_state_change": launch.get("action_type") == "action",
                    "extensions": action_extensions,
                    "status": item["status"],
                }
            )
        return ready_launches, blocked_launches, next_allowed_actions

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
                    "channel_id": detail["interaction_channel"]["channel_id"] if detail["interaction_channel"] else None,
                    "channel_name": detail["interaction_channel"]["display_name"] if detail["interaction_channel"] else None,
                    "stage_count": len(slot_schema_stages(detail["slot_schema"])),
                    "prompt_pack_id": detail["prompt_pack"]["prompt_pack_id"],
                    "readiness": detail["readiness"],
                }
            )
        return {
            "schema_version": "1.0",
            "scenario_count": len(scenarios),
            "scenarios": scenarios,
        }

    def _profile_validation_for_usage(self, profile: dict[str, Any]) -> dict[str, Any]:
        try:
            validation = self.validate_payload(
                "attribute_resolution_profiles",
                {"schema_version": "1.0", "profiles": [copy.deepcopy(profile)]},
            )
        except Exception as error:  # noqa: BLE001 - usage must remain diagnostic, not break admin UI.
            return {
                "status": "invalid",
                "errors": [str(error)],
            }
        return {
            "status": validation.get("status", "invalid"),
            "errors": copy.deepcopy(validation.get("errors") or []),
        }

    def resolution_profile_usage(self) -> dict[str, Any]:
        profiles = self.active_payload("attribute_resolution_profiles").get("profiles", [])
        slot_schemas = self.active_payload("slot_schemas").get("slot_schemas", [])
        scenarios = [
            scenario
            for scenario in self.active_payload("service_scenarios").get("scenarios", [])
            if config_item_is_active(scenario)
        ]
        scenarios_by_schema: dict[str, list[dict[str, Any]]] = {}
        for scenario in scenarios:
            scenarios_by_schema.setdefault(str(scenario.get("slot_schema_id") or ""), []).append(scenario)

        used_by: dict[str, list[dict[str, Any]]] = {
            profile.get("profile_id", ""): []
            for profile in profiles
            if profile.get("profile_id")
        }
        config_refs: dict[str, list[dict[str, Any]]] = {
            profile.get("profile_id", ""): []
            for profile in profiles
            if profile.get("profile_id")
        }
        seen_usage: set[tuple[Any, ...]] = set()
        seen_refs: set[tuple[Any, ...]] = set()

        def add_ref(
            profile_id: str | None,
            *,
            slot_schema: dict[str, Any],
            ref_type: str,
            stage: dict[str, Any] | None = None,
            slot: dict[str, Any] | None = None,
        ) -> None:
            if not profile_id:
                return
            schema_id = slot_schema.get("slot_schema_id")
            stage_id = (stage or {}).get("stage_id")
            slot_id = (slot or {}).get("slot_id")
            ref_key = (profile_id, schema_id, ref_type, stage_id, slot_id)
            ref = {
                "slot_schema_id": schema_id,
                "slot_schema_name": slot_schema.get("display_name") or schema_id,
                "ref_type": ref_type,
                "stage_id": stage_id,
                "stage_name": (stage or {}).get("display_name") or stage_id,
                "slot_id": slot_id,
                "slot_name": (slot or {}).get("display_name") or slot_id,
            }
            ref = {key: value for key, value in ref.items() if value not in (None, "", [], {})}
            if ref_key not in seen_refs:
                seen_refs.add(ref_key)
                config_refs.setdefault(profile_id, []).append(ref)
            for scenario in scenarios_by_schema.get(str(schema_id or ""), []):
                usage_key = (profile_id, scenario.get("scenario_id"), schema_id, ref_type, stage_id, slot_id)
                if usage_key in seen_usage:
                    continue
                seen_usage.add(usage_key)
                used_by.setdefault(profile_id, []).append(
                    {
                        **copy.deepcopy(ref),
                        "scenario_id": scenario.get("scenario_id"),
                        "scenario_name": scenario.get("display_name") or scenario.get("scenario_id"),
                    }
                )

        for slot_schema in slot_schemas:
            for stage in slot_schema_stages(slot_schema):
                add_ref(
                    stage.get("resolution_profile_id"),
                    slot_schema=slot_schema,
                    ref_type="stage",
                    stage=stage,
                )
                for slot in stage.get("slots") or []:
                    if slot_fill_method(slot) == "resolution_profile":
                        add_ref(
                            slot.get("resolution_profile_id"),
                            slot_schema=slot_schema,
                            ref_type="slot",
                            stage=stage,
                            slot=slot,
                        )
            staged_slot_ids = {
                slot.get("slot_id")
                for stage in slot_schema_stages(slot_schema)
                for slot in stage.get("slots") or []
            }
            for slot in slot_schema.get("slots") or []:
                if slot.get("slot_id") in staged_slot_ids:
                    continue
                if slot_fill_method(slot) == "resolution_profile":
                    add_ref(
                        slot.get("resolution_profile_id"),
                        slot_schema=slot_schema,
                        ref_type="slot",
                        slot=slot,
                    )

        result_profiles: list[dict[str, Any]] = []
        for profile in profiles:
            profile_id = profile.get("profile_id", "")
            validation = self._profile_validation_for_usage(profile)
            profile_used_by = copy.deepcopy(used_by.get(profile_id, []))
            profile_refs = copy.deepcopy(config_refs.get(profile_id, []))
            delete_blockers = [
                (
                    f"{ref.get('slot_schema_name') or ref.get('slot_schema_id')} / "
                    f"{'этап' if ref.get('ref_type') == 'stage' else 'слот'} "
                    f"\"{ref.get('stage_name') or ref.get('slot_name') or ref.get('stage_id') or ref.get('slot_id')}\""
                )
                for ref in profile_refs
            ]
            result_profiles.append(
                {
                    "profile_id": profile_id,
                    "display_name": profile.get("display_name") or profile_id,
                    "status": active_config_status(profile),
                    "validation_status": validation["status"],
                    "validation_errors": validation["errors"],
                    "participates": (
                        bool(profile_used_by)
                        and config_item_is_active(profile)
                        and validation["status"] == "valid"
                    ),
                    "used_by": profile_used_by,
                    "config_refs": profile_refs,
                    "unused": not profile_used_by and not profile_refs,
                    "delete_allowed": not profile_refs,
                    "delete_blockers": list(dict.fromkeys(delete_blockers)),
                }
            )

        return {
            "schema_version": "1.0",
            "profile_count": len(result_profiles),
            "used_count": sum(1 for profile in result_profiles if profile["used_by"]),
            "unused_count": sum(1 for profile in result_profiles if profile["unused"]),
            "profiles": result_profiles,
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
        channel_by_id = self._by_id(
            self.active_payload("interaction_channels")["channels"],
            "channel_id",
        )
        interaction_channel = channel_by_id.get(scenario.get("default_channel_id", "debug"))
        allowed_interaction_channels = [
            channel_by_id[channel_id]
            for channel_id in (scenario.get("allowed_channel_ids") or [scenario.get("default_channel_id", "debug")])
            if channel_id in channel_by_id
        ]
        profile_by_id = self._by_id(
            self.active_payload("attribute_resolution_profiles")["profiles"],
            "profile_id",
        )
        resolution_profile_ids = []
        if slot_schema:
            resolution_profile_ids = slot_schema_resolution_profile_ids(slot_schema)
        scenario_profiles = [
            profile_by_id[profile_id]
            for profile_id in dict.fromkeys(resolution_profile_ids)
            if profile_id in profile_by_id and config_item_is_active(profile_by_id[profile_id])
        ]
        tool_launches = self._profile_tool_launches(scenario_profiles)
        missing = []
        for label, value in (
            ("slot_schema", slot_schema),
            ("route", route),
            ("orchestrator_policy", policy),
            ("prompt_pack", prompt_pack),
            ("escalation_policy", escalation_policy),
            ("interaction_channel", interaction_channel),
        ):
            if value is None:
                missing.append(label)
        if slot_schema:
            slot_ids = {slot["slot_id"] for slot in slot_schema["slots"]}
            for slot in slot_schema["slots"]:
                if slot_fill_method(slot) == "resolution_profile":
                    profile_id = slot.get("resolution_profile_id")
                    profile = profile_by_id.get(profile_id or "")
                    if not profile:
                        missing.append(f"attribute_resolution_profile:{slot['slot_id']}")
                    elif not config_item_is_active(profile):
                        missing.append(f"attribute_resolution_profile:{slot['slot_id']}:inactive")
            for stage in slot_schema_stages(slot_schema):
                profile_id = stage.get("resolution_profile_id")
                if profile_id and profile_id not in profile_by_id:
                    missing.append(f"attribute_resolution_profile:{stage['stage_id']}")
                elif profile_id and not config_item_is_active(profile_by_id.get(profile_id)):
                    missing.append(f"attribute_resolution_profile:{stage['stage_id']}:inactive")
        system_confidence_defaults = self.system_confidence_defaults()
        slot_confidence_thresholds = {}
        if slot_schema:
            slot_confidence_thresholds = {
                slot["slot_id"]: self.effective_confidence_thresholds(
                    scenario=scenario,
                    slot=slot,
                    profile=profile_by_id.get(slot.get("resolution_profile_id", "")),
                    include_profile=False,
                )
                for slot in slot_schema["slots"]
            }
        return {
            "schema_version": "1.0",
            "scenario": scenario,
            "slot_schema": slot_schema,
            "attribute_resolution_profiles": scenario_profiles,
            "resolution_profile_usage": [
                item
                for item in self.resolution_profile_usage()["profiles"]
                if item["profile_id"] in {profile.get("profile_id") for profile in scenario_profiles}
            ],
            "route": route,
            "orchestrator_policy": policy,
            "tool_launches": tool_launches,
            "interaction_channel": interaction_channel,
            "allowed_interaction_channels": allowed_interaction_channels,
            "prompt_pack": prompt_pack,
            "prompt_preview": build_prompt_preview(prompt_pack) if prompt_pack else "",
            "escalation_policy": escalation_policy,
            "system_confidence_defaults": system_confidence_defaults,
            "slot_confidence_thresholds": slot_confidence_thresholds,
            "readiness": {
                "status": "ready" if not missing else "incomplete",
                "missing": missing,
            },
        }

    def operator_scenario_detail(self, scenario_id: str) -> dict[str, Any]:
        detail = copy.deepcopy(self.scenario_detail(scenario_id))
        scenario = detail.get("scenario")
        if isinstance(scenario, dict):
            scenario.pop("escalation_policy_id", None)
        detail.pop("escalation_policy", None)
        return detail

    def orchestration_graph(
        self,
        *,
        scenario_id: str | None = None,
        view: str = "scenario",
    ) -> dict[str, Any]:
        graph_view = view if view in {"base", "scenario"} else "scenario"
        scenarios = list(self._scenario_by_id().values())
        detail = None
        if graph_view == "scenario":
            selected_scenario_id = scenario_id or (scenarios[0]["scenario_id"] if scenarios else None)
            if selected_scenario_id:
                detail = self.scenario_detail(selected_scenario_id)
                scenario_id = selected_scenario_id
            else:
                graph_view = "base"

        nodes = self._orchestration_graph_nodes(detail=detail)
        edges = self._orchestration_graph_edges()
        warnings = []
        if detail and detail["readiness"]["status"] != "ready":
            warnings.extend(
                f"Не заполнена связь сценария: {item}"
                for item in detail["readiness"].get("missing", [])
            )
        return {
            "schema_version": "1.0",
            "graph_id": f"scenario.{scenario_id}" if detail else "base.orchestrator",
            "view": graph_view,
            "scenario_id": scenario_id if detail else None,
            "title": (
                f"Граф сценария: {detail['scenario']['display_name']}"
                if detail
                else "Базовый граф оркестрации"
            ),
            "readonly": True,
            "layout": {
                "width": 1760,
                "height": 520,
                "node_width": 180,
                "node_height": 82,
            },
            "nodes": nodes,
            "edges": edges,
            "warnings": warnings,
        }

    def _orchestration_graph_nodes(self, *, detail: dict[str, Any] | None) -> list[dict[str, Any]]:
        capability_by_id = self._by_id(
            self.active_payload("capabilities").get("capabilities", []),
            "capability_id",
        )
        environment_by_id = self._by_id(
            self.active_payload("mcp_environments").get("environments", []),
            "environment_id",
        )

        def item_status(item: dict[str, Any] | None) -> str:
            return "valid" if item else "missing"

        def config_ref(
            *,
            domain: str,
            title: str,
            item: dict[str, Any] | None,
            id_key: str,
            view_name: str,
        ) -> dict[str, Any] | None:
            if not item:
                return None
            return {
                "domain": domain,
                "title": title,
                "id": item.get(id_key),
                "display_name": item.get("display_name") or item.get(id_key),
                "view": view_name,
            }

        def compact_refs(refs: list[dict[str, Any] | None]) -> list[dict[str, Any]]:
            return [ref for ref in refs if ref]

        def node(
            node_id: str,
            title: str,
            *,
            x: int,
            y: int,
            step_number: int | None = None,
            node_type: str = "orchestrator_step",
            status: str = "valid",
            description: str = "",
            config_refs: list[dict[str, Any] | None] | None = None,
            metrics: list[dict[str, Any]] | None = None,
        ) -> dict[str, Any]:
            return {
                "id": node_id,
                "title": title,
                "step_number": step_number,
                "type": node_type,
                "status": status,
                "description": description,
                "config_refs": compact_refs(config_refs or []),
                "metrics": metrics or [],
                "readonly": True,
                "layout": {
                    "x": x,
                    "y": y,
                },
            }

        scenario = detail.get("scenario") if detail else None
        slot_schema = detail.get("slot_schema") if detail else None
        profiles = detail.get("attribute_resolution_profiles", []) if detail else []
        route = detail.get("route") if detail else None
        policy = detail.get("orchestrator_policy") if detail else None
        prompt_pack = detail.get("prompt_pack") if detail else None
        escalation_policy = detail.get("escalation_policy") if detail else None
        channel = detail.get("interaction_channel") if detail else None
        stage_count = len(slot_schema_stages(slot_schema)) if slot_schema else 0
        profile_capability_ids = sorted({
            step.get("capability_id")
            for profile in profiles
            for step in profile.get("enrichment_steps", [])
            if step.get("capability_id")
        })
        profile_capabilities = [
            capability_by_id[capability_id]
            for capability_id in profile_capability_ids
            if capability_id in capability_by_id
        ]
        environment_ids = sorted({
            step.get("mcp_environment_id")
            for profile in profiles
            for step in profile.get("enrichment_steps", [])
            if step.get("mcp_environment_id")
        })
        profile_environments = [
            environment_by_id[environment_id]
            for environment_id in environment_ids
            if environment_id in environment_by_id
        ]

        return [
            node(
                "intake",
                "Приём обращения",
                x=40,
                y=210,
                node_type="entry",
                description="Точка входа из канала: чат, бот, email, портал или отладочный операторский режим.",
                config_refs=[
                    config_ref(
                        domain="service_scenarios",
                        title="Сценарий",
                        item=scenario,
                        id_key="scenario_id",
                        view_name="scenarios",
                    ),
                ],
            ),
            node(
                "prompt_pack",
                "6. Промпты",
                x=40,
                y=70,
                step_number=6,
                node_type="configuration",
                status=item_status(prompt_pack) if detail else "valid",
                description="Обязательные блоки системного промпта, которые направляют поведение оркестратора.",
                config_refs=[
                    config_ref(
                        domain="prompt_packs",
                        title="Пакет промптов",
                        item=prompt_pack,
                        id_key="prompt_pack_id",
                        view_name="scenarioPrompts",
                    ),
                ],
                metrics=[
                    {
                        "label": "Блоков",
                        "value": len(prompt_pack.get("blocks", {})) if prompt_pack else 0,
                    },
                ] if detail else [],
            ),
            node(
                "slot_filling",
                "Этапы сценария",
                x=250,
                y=210,
                step_number=0,
                status=item_status(slot_schema) if detail else "valid",
                description="План этапов сценария: профиль разрешения этапа и слоты, которые заполняются моделью, оператором или клиентом.",
                config_refs=[
                    config_ref(
                        domain="slot_schemas",
                        title="План этапов",
                        item=slot_schema,
                        id_key="slot_schema_id",
                        view_name="scenarioSlots",
                    ),
                ],
                metrics=[
                    {
                        "label": "Этапов",
                        "value": stage_count,
                    },
                    {
                        "label": "Слотов",
                        "value": len(slot_schema.get("slots", [])) if slot_schema else 0,
                    },
                    {
                        "label": "Обязательных",
                        "value": len(slot_schema.get("required_slots", [])) if slot_schema else 0,
                    },
                ] if detail else [],
            ),
            node(
                "attribute_resolution",
                "Профили разрешения",
                x=460,
                y=210,
                step_number=1,
                status="valid" if not detail or profiles else "partial",
                description="Заполнение атрибутов через входные слоты, capabilities, LLM-правило, уточнение у клиента и эскалацию оператору.",
                config_refs=[
                    {
                        "domain": "attribute_resolution_profiles",
                        "title": "Профиль разрешения",
                        "id": profile["profile_id"],
                        "display_name": profile.get("display_name") or profile["profile_id"],
                        "view": "resolution",
                    }
                    for profile in profiles
                ],
                metrics=[
                    {
                        "label": "Профилей",
                        "value": len(profiles),
                    },
                ] if detail else [],
            ),
            node(
                "classification",
                "2. Классификация и маршрут",
                x=670,
                y=210,
                step_number=2,
                status=item_status(route) if detail else "valid",
                description="Выбор категории, приоритета и маршрута через правила, LLM и передачу оператору при низкой уверенности.",
                config_refs=[
                    config_ref(
                        domain="classification_routes",
                        title="Маршрут",
                        item=route,
                        id_key="route_id",
                        view_name="scenarioClassification",
                    ),
                ],
                metrics=[
                    {
                        "label": "Маршрут",
                        "value": route.get("route") if route else "н/д",
                    },
                    {
                        "label": "Приоритет",
                        "value": route.get("priority") if route else "н/д",
                    },
                ] if detail else [],
            ),
            node(
                "orchestration",
                "3. Оркестрация",
                x=880,
                y=210,
                step_number=3,
                status=item_status(policy) if detail else "valid",
                description="Цикл оркестрации со стоп-условиями и лимитом итераций.",
                config_refs=[
                    config_ref(
                        domain="orchestrator_policy",
                        title="Политика оркестрации",
                        item=policy,
                        id_key="policy_id",
                        view_name="scenarioOrchestration",
                    ),
                ],
                metrics=[
                    {
                        "label": "Итераций",
                        "value": policy.get("max_iterations") if policy else "н/д",
                    },
                    {
                        "label": "Ошибок до стопа",
                        "value": policy.get("consecutive_capability_errors_to_escalate") if policy else "н/д",
                    },
                ] if detail else [],
            ),
            node(
                "capability_contracts",
                "Capabilities / MCP",
                x=1090,
                y=370,
                node_type="configuration",
                description="Capability contracts и внешние MCP-окружения, используемые enrichment шагами профилей разрешения.",
                config_refs=[
                    *[
                        {
                            "domain": "capabilities",
                            "title": "Capability",
                            "id": capability["capability_id"],
                            "display_name": capability.get("display_name") or capability["capability_id"],
                            "view": "capabilities",
                        }
                        for capability in profile_capabilities
                    ],
                    *[
                        {
                            "domain": "mcp_environments",
                            "title": "MCP environment",
                            "id": environment["environment_id"],
                            "display_name": environment.get("display_name") or environment["environment_id"],
                            "view": "mcpEnvironments",
                        }
                        for environment in profile_environments
                    ],
                ],
                metrics=[
                    {
                        "label": "MCP окружений",
                        "value": len(profile_environments),
                    },
                    {
                        "label": "Capabilities",
                        "value": len(profile_capability_ids),
                    },
                ] if detail else [],
            ),
            node(
                "decision",
                "5. Решение и эскалация",
                x=1300,
                y=210,
                step_number=5,
                status=item_status(escalation_policy) if detail else "valid",
                description="Системные правила финального решения, ожидания клиента и handoff оператору.",
            ),
            node(
                "interaction_channel",
                "Канал взаимодействия",
                x=250,
                y=370,
                node_type="configuration",
                status=item_status(channel) if detail else "valid",
                description="Профиль ожидания, доставки вопросов и действия при незавершенном обсуждении.",
                config_refs=[
                    config_ref(
                        domain="interaction_channels",
                        title="Канал",
                        item=channel,
                        id_key="channel_id",
                        view_name="interactionChannels",
                    ),
                ],
            ),
            node(
                "waiting",
                "Ожидание ответа клиента",
                x=1510,
                y=70,
                node_type="terminal",
                description="AI задал уточняющий вопрос клиенту и после ответа продолжит сценарий.",
            ),
            node(
                "closed",
                "Закрытие",
                x=1510,
                y=210,
                node_type="terminal",
                description="Условие успеха выполнено, подтверждение получено, кейс можно закрыть.",
            ),
            node(
                "escalation",
                "Эскалация оператору",
                x=1510,
                y=350,
                node_type="terminal",
                description="AI завершает самостоятельную обработку и передает оператору пакет контекста.",
            ),
        ]

    @staticmethod
    def _orchestration_graph_edges() -> list[dict[str, Any]]:
        def edge(
            source: str,
            target: str,
            label: str,
            *,
            condition: str | None = None,
            edge_type: str = "flow",
        ) -> dict[str, Any]:
            return {
                "from": source,
                "to": target,
                "label": label,
                "condition": condition,
                "type": edge_type,
            }

        return [
            edge("intake", "slot_filling", "текст обращения"),
            edge("prompt_pack", "slot_filling", "инструкции", edge_type="support"),
            edge("prompt_pack", "classification", "пороги и правила", edge_type="support"),
            edge("prompt_pack", "orchestration", "правила оркестрации", edge_type="support"),
            edge("interaction_channel", "slot_filling", "доставка вопросов", edge_type="support"),
            edge("slot_filling", "attribute_resolution", "нужны атрибуты"),
            edge("attribute_resolution", "waiting", "вопрос клиенту", condition="не хватает данных", edge_type="support"),
            edge("waiting", "slot_filling", "ответ клиента", condition="возобновить сценарий", edge_type="loop"),
            edge("attribute_resolution", "classification", "слоты готовы"),
            edge("classification", "orchestration", "маршрут выбран"),
            edge("classification", "escalation", "эскалация оператору", condition="human review или низкая уверенность"),
            edge("capability_contracts", "attribute_resolution", "capability contracts", edge_type="support"),
            edge("orchestration", "decision", "стоп-условие"),
            edge("decision", "waiting", "ожидать клиента", condition="нет ответа клиента"),
            edge("decision", "closed", "закрыть", condition="success + подтверждение"),
            edge("decision", "escalation", "эскалировать оператору", condition="ошибки, лимит, confidence"),
            edge("interaction_channel", "decision", "правила ожидания", edge_type="support"),
        ]

    def system_confidence_defaults(self) -> dict[str, float]:
        policy_payload = self.active_payload("orchestrator_policy")
        return normalize_confidence_thresholds(
            policy_payload.get("confidence_defaults"),
            require_all=True,
        )

    def effective_confidence_thresholds(
        self,
        *,
        scenario: dict[str, Any] | None,
        slot: dict[str, Any] | None,
        profile: dict[str, Any] | None = None,
        include_profile: bool = False,
    ) -> dict[str, float]:
        thresholds = self.system_confidence_defaults()
        thresholds.update(normalize_confidence_thresholds((slot or {}).get("confidence_overrides")))
        if include_profile:
            thresholds.update(profile_confidence_thresholds(profile))
        return thresholds

    def classify_text(self, text: str, configured_route: dict[str, Any] | None) -> dict[str, Any]:
        routes = self.active_payload("classification_routes")["routes"]
        candidates = [
            score_classification_route(route, text)
            for route in routes
        ]
        candidates.sort(
            key=lambda item: (
                item["confidence"],
                item["positive_score"],
                -item["negative_score"],
                item["display_name"],
            ),
            reverse=True,
        )
        selected = candidates[0] if candidates else None
        route_by_id = {route["route_id"]: route for route in routes}
        selected_route = route_by_id.get(selected["route_id"]) if selected else configured_route
        top_limit = int((configured_route or {}).get("top_categories_on_low_confidence") or 3)
        top_limit = max(1, min(top_limit, len(candidates) or 1))
        configured_score = next(
            (item for item in candidates if item["route_id"] == (configured_route or {}).get("route_id")),
            None,
        )
        confidence = float((selected or {}).get("confidence") or 0.0)
        decision_level = classification_decision_level(confidence, selected_route)
        return {
            "route_id": (selected or configured_route or {}).get("route_id"),
            "display_name": (selected or configured_route or {}).get("display_name"),
            "route": (selected or configured_route or {}).get("route"),
            "priority": (selected or configured_route or {}).get("priority"),
            "workflow_state_id": (selected or configured_route or {}).get("workflow_state_id"),
            "confidence": confidence,
            "decision_level": decision_level,
            "configured_route_id": (configured_route or {}).get("route_id"),
            "configured_route_confidence": (configured_score or {}).get("confidence"),
            "matches_configured_route": bool(
                selected
                and configured_route
                and selected["route_id"] == configured_route.get("route_id")
            ),
            "positive_hits": (selected or {}).get("positive_hits", []),
            "negative_hits": (selected or {}).get("negative_hits", []),
            "required_missing": (selected or {}).get("required_missing", []),
            "blocked_by_rules": (selected or {}).get("blocked_by_rules", []),
            "top_routes": candidates[:top_limit],
        }

    def simulate_attribute_resolution_profile(
        self,
        *,
        profile: dict[str, Any],
        slot_schema: dict[str, Any],
        provided: dict[str, Any],
        simulation_options: dict[str, Any],
        effective_thresholds: dict[str, float],
        execution_trace: list[dict[str, Any]],
        slot_values: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        enrichment_steps = profile.get("enrichment_steps", [])
        human_policy = profile["human_resolution_policy"]
        question = resolution_profile_question(profile)
        default_result = {
            "profile_id": profile["profile_id"],
            "profile_name": profile["display_name"],
            "use_llm_after_steps": bool(profile.get("use_llm_after_steps", True)),
            "resolution_mode": "llm_rule" if profile.get("use_llm_after_steps", True) else "direct_mapping",
            "status": "question_required" if question else "resolution_pending",
            "decision": "ask_clarification" if question else "operator_handoff",
            "attempt": 1,
            "max_attempts": profile["max_attempts"],
            "pending_question": question,
            "enrichment_steps": enrichment_steps,
            "enrichment_step_results": {},
            "output_slots_order": profile.get("output_slots_order", []),
            "llm_resolution_script": profile.get("llm_resolution_script", {}),
            "human_resolution_policy": human_policy,
            "candidate_count": None,
            "result_summary": None,
            "llm_decision": None,
            "output_values": {},
            "effective_confidence_thresholds": effective_thresholds,
        }
        if not enrichment_steps:
            append_trace(
                execution_trace,
                step="1",
                status="skipped",
                title=f"Разрешение атрибута: {profile['display_name']}",
                message="Для профиля не настроено обогащение контекста через capability.",
                details={"enrichment_steps": 0},
            )
            return {
                **default_result,
            "reason": "Обогащение контекста не настроено для выбранного профиля.",
            }

        capability_by_id = self._by_id(
            self.active_payload("capabilities").get("capabilities", []),
            "capability_id",
        )
        environment_by_id = self._by_id(
            self.active_payload("mcp_environments").get("environments", []),
            "environment_id",
        )
        enrichment_step_results: dict[str, Any] = {}
        last_step: dict[str, Any] | None = None
        last_mock_output: dict[str, Any] | None = None
        last_capability: dict[str, Any] | None = None
        last_environment_id = ""
        last_mcp_tool_name = ""

        for step_index, enrichment_step in enumerate(enrichment_steps, start=1):
            if enrichment_step.get("capability_id"):
                capability_id = enrichment_step.get("capability_id")
                capability = capability_by_id.get(capability_id or "")
                binding = self._active_capability_binding_for_step(enrichment_step)
                environment = environment_by_id.get((binding or {}).get("environment_id") or enrichment_step.get("mcp_environment_id") or "")
                launch = self._profile_capability_launch(
                    profile=profile,
                    step=enrichment_step,
                    capability_by_id=capability_by_id,
                    environment_by_id=environment_by_id,
                )
                if not capability or not binding or not environment:
                    append_trace(
                        execution_trace,
                        step="1",
                        status="blocked",
                        title=f"Обогащение контекста: {enrichment_step.get('step_name') or profile['display_name']}",
                        message="Capability, MCP binding или MCP-окружение не найдены.",
                        details={
                            "capability_id": capability_id,
                            "mcp_environment_id": enrichment_step.get("mcp_environment_id"),
                            "binding_exists": bool(binding),
                            "environment_exists": bool(environment),
                        },
                    )
                    return {
                        **default_result,
                        "enrichment_step_results": enrichment_step_results,
                        "status": "blocked_by_configuration",
                        "decision": "handoff",
                        "reason": "Capability, MCP binding или MCP-окружение шага обогащения не найдены.",
                    }
                parameter_sources = enrichment_step.get("input_mapping", {})
                parameters = resolved_dry_run_parameters(
                    parameter_sources,
                    provided=provided,
                    slot_values=slot_values,
                    enrichment_step_results=enrichment_step_results,
                )
                unresolved_step_parameters = [
                    parameter
                    for parameter, source_ref in parameter_sources.items()
                    if str(source_ref).startswith("step:") and parameters.get(parameter) is None
                ]
                if unresolved_step_parameters:
                    append_trace(
                        execution_trace,
                        step="1",
                        status="blocked",
                        title=f"Обогащение контекста: {enrichment_step.get('step_name') or profile['display_name']}",
                        message="Не удалось разрешить ссылку на результат предыдущего шага.",
                        details={
                            "capability_id": capability_id,
                            "parameter_sources": parameter_sources,
                            "unresolved_parameters": unresolved_step_parameters,
                        },
                    )
                    return {
                        **default_result,
                        "enrichment_step_results": enrichment_step_results,
                        "status": "blocked_by_configuration",
                        "decision": "handoff",
                        "reason": (
                            "Не удалось разрешить параметры capability из предыдущих шагов: "
                            f"{', '.join(unresolved_step_parameters)}."
                        ),
                    }
                parameters, applied_parameter_defaults = apply_schema_parameter_defaults(
                    capability.get("input_schema", {}),
                    parameters,
                )
                input_resolution = capability_input_resolution_rows(
                    schema=capability.get("input_schema", {}),
                    mapping=parameter_sources,
                    parameters=parameters,
                    applied_defaults=applied_parameter_defaults,
                    provided=provided,
                    slot_values=slot_values,
                )
                parameters = drop_missing_optional_capability_inputs(parameters, input_resolution)
                missing_required_input_groups = missing_required_parameter_groups(
                    capability.get("input_schema", {}),
                    parameters,
                )
                if missing_required_input_groups:
                    missing_required_inputs = [
                        format_required_parameter_group(group)
                        for group in missing_required_input_groups
                    ]
                    append_trace(
                        execution_trace,
                        step="1",
                        status="blocked",
                        title=f"Обогащение контекста: {enrichment_step.get('step_name') or profile['display_name']}",
                        message="Не заполнены обязательные параметры capability.",
                        details={
                            "capability_id": capability_id,
                            "parameter_sources": parameter_sources,
                            "parameters": parameters,
                            "applied_parameter_defaults": applied_parameter_defaults,
                            "input_resolution": input_resolution,
                            "missing_required_inputs": missing_required_inputs,
                        },
                    )
                    return {
                        **default_result,
                        "enrichment_step_results": enrichment_step_results,
                        "status": "blocked_by_missing_required_inputs",
                        "decision": "handoff",
                        "reason": (
                            "Не заполнены обязательные параметры capability: "
                            f"{', '.join(missing_required_inputs)}."
                        ),
                    }
                mock_output = copy.deepcopy(
                    ((binding.get("extensions") or {}).get("mock_output"))
                    or ((capability.get("extensions") or {}).get("mock_output"))
                    or {}
                )
                step_id = enrichment_step.get("step_id") or f"step{step_index}"
                if not mock_output:
                    if simulation_options.get("run_mode") == "operator_full_debug":
                        enrichment_step_results[step_id] = {
                            "step_id": step_id,
                            "step_name": enrichment_step.get("step_name"),
                            "capability_id": capability_id,
                            "mcp_environment_id": environment.get("environment_id"),
                            "mcp_tool_name": binding.get("mcp_tool_name"),
                            "execution_mode": binding.get("execution_mode"),
                            "parameters": parameters,
                            "applied_parameter_defaults": applied_parameter_defaults,
                            "input_resolution": input_resolution,
                            "result": {
                                "status": "ready_for_execution",
                                "reason": "Capability будет выполнена внешним MCP при анализе заявки.",
                            },
                            "completion_policy": launch.get("completion_policy"),
                        }
                        append_trace(
                            execution_trace,
                            step="1",
                            status="ready",
                            title=f"Обогащение контекста: {enrichment_step.get('step_name') or profile['display_name']}",
                            message="Тестовый ответ capability не задан; в полном отладочном прогоне будет вызвано внешнее MCP-окружение.",
                            details={
                                "step_index": step_index,
                                "step_id": step_id,
                                "capability_id": capability_id,
                                "mcp_environment_id": environment.get("environment_id"),
                                "mcp_tool_name": binding.get("mcp_tool_name"),
                                "execution_mode": binding.get("execution_mode"),
                                "completion_policy": launch.get("completion_policy"),
                                "parameter_sources": parameter_sources,
                                "parameters": parameters,
                                "applied_parameter_defaults": applied_parameter_defaults,
                                "input_resolution": input_resolution,
                                "result": enrichment_step_results[step_id]["result"],
                            },
                        )
                        return {
                            **default_result,
                            "enrichment_step_results": enrichment_step_results,
                            "status": "pending_live_execution",
                            "decision": "execute_capability",
                            "reason": "Capability будет выполнена внешним MCP при анализе заявки.",
                        }
                    append_trace(
                        execution_trace,
                        step="1",
                        status="blocked",
                        title=f"Обогащение контекста: {enrichment_step.get('step_name') or profile['display_name']}",
                        message="В режиме проверки без выполнения нужен тестовый ответ capability.",
                        details={
                            "capability_id": capability_id,
                            "mcp_environment_id": environment.get("environment_id"),
                            "parameter_sources": parameter_sources,
                            "parameters": parameters,
                            "applied_parameter_defaults": applied_parameter_defaults,
                            "input_resolution": input_resolution,
                            "result": {
                                "status": "not_executed",
                                "reason": "В режиме проверки без выполнения нужен тестовый ответ capability.",
                            },
                        },
                    )
                    return {
                        **default_result,
                        "enrichment_step_results": enrichment_step_results,
                        "status": "blocked_by_configuration",
                        "decision": "handoff",
                        "reason": "В режиме проверки без выполнения нужен тестовый ответ capability.",
                    }

                enrichment_step_results[step_id] = {
                    "step_id": step_id,
                    "step_name": enrichment_step.get("step_name"),
                    "capability_id": capability_id,
                    "mcp_environment_id": environment.get("environment_id"),
                    "mcp_tool_name": binding.get("mcp_tool_name"),
                    "execution_mode": binding.get("execution_mode"),
                    "parameters": parameters,
                    "applied_parameter_defaults": applied_parameter_defaults,
                    "input_resolution": input_resolution,
                    "result": mock_output,
                    "completion_policy": launch.get("completion_policy"),
                }
                append_trace(
                    execution_trace,
                    step="1",
                    status="completed",
                    title=f"Обогащение контекста: {enrichment_step.get('step_name') or step_id}",
                    message=f"Capability {capability_id} выполнила шаг {step_id}.",
                    details={
                        "step_index": step_index,
                        "step_id": step_id,
                        "capability_id": capability_id,
                        "mcp_environment_id": environment.get("environment_id"),
                        "mcp_tool_name": binding.get("mcp_tool_name"),
                        "execution_mode": binding.get("execution_mode"),
                        "completion_policy": launch.get("completion_policy"),
                        "parameter_sources": parameter_sources,
                        "parameters": parameters,
                        "applied_parameter_defaults": applied_parameter_defaults,
                        "input_resolution": input_resolution,
                        "result": mock_output,
                    },
                )
                last_step = enrichment_step
                last_mock_output = mock_output
                last_capability = capability
                last_environment_id = environment.get("environment_id") or ""
                last_mcp_tool_name = binding.get("mcp_tool_name") or ""
                continue

            append_trace(
                execution_trace,
                step="1",
                status="blocked",
                title=f"Обогащение контекста: {enrichment_step.get('step_name') or profile['display_name']}",
                message="Старый operation binding удален; настройте шаг через capability.",
                details={"step_id": enrichment_step.get("step_id")},
            )
            return {
                **default_result,
                "enrichment_step_results": enrichment_step_results,
                "status": "blocked_by_configuration",
                "decision": "handoff",
                "reason": "Старый operation binding удален; используйте capability_id/input_mapping/output_mapping.",
            }

        if not last_step or last_mock_output is None:
            append_trace(
                execution_trace,
                step="1",
                status="blocked",
                title=f"Разрешение атрибута: {profile['display_name']}",
                message="Обогащение контекста не вернуло результата.",
                details={"enrichment_steps": len(enrichment_steps)},
            )
            return {
                **default_result,
                "enrichment_step_results": enrichment_step_results,
                "status": "blocked_by_configuration",
                "decision": "handoff",
                "reason": "Обогащение контекста не вернуло результата.",
            }

        count = 1
        result_item = last_mock_output
        result_summary = {
            "result_type": "object",
            "result_path": None,
            "object_found": True,
            "source_status": "mock_output",
            "source_kind": "capability",
        }
        if result_summary.get("source_status") == "configuration_error":
            append_trace(
                execution_trace,
                step="1",
                status="blocked",
                title=f"Разрешение атрибута: {profile['display_name']}",
                message=result_summary.get("reason") or "Контракт результата операции неоднозначен.",
                details={
                    "enrichment_steps": len(enrichment_steps),
                    "last_step_id": last_step.get("step_id"),
                    "result_summary": result_summary,
                },
            )
            return {
                **default_result,
                "enrichment_step_results": enrichment_step_results,
                "status": "blocked_by_configuration",
                "decision": "handoff",
                "result_summary": result_summary,
                "reason": result_summary.get("reason") or "Контракт результата операции неоднозначен.",
            }
        precomputed_output_values = {
            slot_id: value_at_path(last_mock_output, field_path)
            for slot_id, field_path in (last_step.get("output_mapping") or {}).items()
        }
        output_resolution_summary = {
            "source_status": "mock_output",
            "source_kind": "capability",
            "output_mapping": copy.deepcopy(last_step.get("output_mapping") or {}),
        }
        if output_resolution_summary.get("source_status") == "configuration_error":
            reason = "; ".join(output_resolution_summary.get("errors") or []) or "Не удалось разрешить источники выходных слотов."
            append_trace(
                execution_trace,
                step="1",
                status="blocked",
                title=f"Разрешение атрибута: {profile['display_name']}",
                message=reason,
                details={
                    "enrichment_steps": len(enrichment_steps),
                    "output_slots_order": profile.get("output_slots_order", []),
                    "result_summary": output_resolution_summary,
                },
            )
            return {
                **default_result,
                "enrichment_step_results": enrichment_step_results,
                "status": "blocked_by_configuration",
                "decision": "handoff",
                "result_summary": output_resolution_summary,
                "reason": reason,
            }
        confidence = result_confidence(result_item, {"confidence_path": "confidence"})
        if not profile.get("use_llm_after_steps", True):
            llm_decision = None
            resolution_decision = direct_mapping_resolution_decision(
                profile=profile,
                result_item=result_item,
                result_summary=result_summary,
                count=count,
                confidence=confidence,
                precomputed_output_values=precomputed_output_values,
            )
        elif not simulation_options["allow_llm"]:
            llm_decision = {
                "decision": "await_llm_rule",
                "status": "llm_resolution_pending",
                "filled_slots": {},
                "confidence": confidence,
                "next_question": question or (
                    resolution_profile_message_template(profile)
                    if resolution_profile_human_action(profile) == "ask_client"
                    else ""
                ),
                "handoff_message": (
                    resolution_profile_message_template(profile)
                    if resolution_profile_human_action(profile) == "escalate_operator"
                    else ""
                ),
                "reason": "Режим тестового прогона не разрешает выполнение LLM-правила разрешения атрибута.",
            }
            resolution_decision = llm_decision
        else:
            llm_decision = simulated_llm_resolution_decision(
                profile=profile,
                result_item=result_item,
                result_summary=result_summary,
                count=count,
                confidence=confidence,
                effective_thresholds=effective_thresholds,
                precomputed_output_values=precomputed_output_values,
            )
            resolution_decision = llm_decision
        output_values = resolution_decision.get("filled_slots", {})
        status = resolution_decision.get("status", "question_required")
        decision = resolution_decision.get("decision", "ask_clarification")
        reason = resolution_decision.get("reason", "")
        resolution_mode = "LLM-правила" if profile.get("use_llm_after_steps", True) else "прямого маппинга"

        append_trace(
            execution_trace,
            step="1",
            status="completed" if status == "filled" else "blocked",
            title=f"Разрешение атрибута: {profile['display_name']}",
            message=f"Результатов обогащения: {count}; решение {resolution_mode}: {decision}.",
            details={
                "enrichment_steps": len(enrichment_steps),
                "last_step_id": last_step.get("step_id"),
                "resolution_mode": default_result["resolution_mode"],
                "confidence": confidence,
                "result": resolution_decision,
                "output_slots": sorted(output_values),
            },
        )
        return {
            **default_result,
            "status": status,
            "decision": decision,
            "candidate_count": count,
            "candidate_confidence": confidence,
            "enrichment_step_results": enrichment_step_results,
            "output_values": output_values,
            "resolution_decision": resolution_decision,
            "llm_decision": llm_decision,
            "pending_question": resolution_decision.get("next_question") or question,
            "result_summary": {
                **result_summary,
                "count": count,
                "source": f"{last_capability.get('capability_id')}/{last_environment_id}/{last_mcp_tool_name}"
                if last_capability
                else "",
            },
            "reason": reason,
        }

    def resolve_simulation_channel(self, scenario: dict[str, Any], channel_id: str) -> dict[str, Any]:
        requested_channel_id = str(channel_id or "").strip()
        if not requested_channel_id:
            raise ConfigRegistryError("Укажите channel_id для отладочного прогона канала.")
        allowed_channel_ids = scenario.get("allowed_channel_ids") or [scenario.get("default_channel_id", "debug")]
        if requested_channel_id not in allowed_channel_ids:
            raise ConfigRegistryError(
                f"Канал {requested_channel_id} не входит в allowed_channel_ids сценария {scenario.get('scenario_id')}."
            )
        channel_by_id = self._by_id(self.active_payload("interaction_channels")["channels"], "channel_id")
        channel = channel_by_id.get(requested_channel_id)
        if not channel:
            raise ConfigRegistryError(f"Канал не найден: {requested_channel_id}")
        return copy.deepcopy(channel)

    def _record_llm_slot_result(
        self,
        *,
        slot: dict[str, Any],
        slot_values: dict[str, Any],
        missing_slots: list[str],
        extracted: dict[str, Any],
        effective_thresholds: dict[str, float],
        execution_trace: list[dict[str, Any]],
        iteration: int,
        dependencies: list[str],
    ) -> bool:
        slot_id = slot["slot_id"]
        confidence = extracted["confidence"]
        value = extracted["value"]
        accepted = value is not None and confidence >= effective_thresholds["min_extraction_confidence"]
        status = "filled_by_model" if accepted else "candidate_below_threshold"
        decision = "accepted" if accepted else "rejected"
        if accepted and confidence < effective_thresholds["auto_accept_confidence"]:
            decision = "accepted_for_test_below_auto_accept"
        slot_values[slot_id] = {
            "status": status,
            "value": value,
            "candidate_value": value,
            "fill_method": "llm_extraction",
            "source": "llm",
            "confidence": confidence,
            "threshold_decision": decision,
            "reason": extracted["reason"],
            "dependencies": dependencies,
            "effective_confidence_thresholds": effective_thresholds,
            **slot_source_summary(slot),
        }
        append_trace(
            execution_trace,
            step="1",
            status="completed" if accepted else "blocked",
            title=f"LLM extraction: {slot_id}",
            message=(
                f"Значение принято: {value}"
                if accepted
                else "Кандидат ниже минимального порога извлечения."
            ),
            details={
                "iteration": iteration,
                "dependencies": dependencies,
                "candidate_value": value,
                "confidence": confidence,
                "min_extraction_confidence": effective_thresholds["min_extraction_confidence"],
                "auto_accept_confidence": effective_thresholds["auto_accept_confidence"],
                "decision": decision,
                "reason": extracted["reason"],
            },
        )
        if slot.get("required") and not accepted and slot_id not in missing_slots:
            missing_slots.append(slot_id)
        if accepted and slot_id in missing_slots:
            missing_slots.remove(slot_id)
        return accepted

    def _simulate_slot_filling(
        self,
        *,
        detail: dict[str, Any],
        slot_schema: dict[str, Any],
        stages: list[dict[str, Any]],
        known_slot_ids: set[str],
        provided: dict[str, Any],
        text: str,
        simulation_options: dict[str, Any],
        execution_trace: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], list[str], list[dict[str, Any]], dict[str, Any]]:
        profile_by_id = self._by_id(
            detail.get("attribute_resolution_profiles", []),
            "profile_id",
        )
        slot_values: dict[str, Any] = {}
        missing_slots: list[str] = []
        resolution_steps: list[dict[str, Any]] = []
        resolution_state: dict[str, Any] = {}
        seen_resolution_profile_ids: set[str] = set()
        profile_results: dict[str, dict[str, Any]] = {}
        attempted_llm_slots: set[str] = set()
        waiting_dependencies: dict[str, list[str]] = {}
        max_iterations = int((detail.get("orchestrator_policy") or {}).get("max_iterations") or 6)
        max_iterations = max(1, min(max_iterations, 50))

        for stage in stages:
            append_trace(
                execution_trace,
                step="0",
                status="started",
                title=f"Этап планирования: {stage.get('display_name') or stage.get('stage_id')}",
                message=(
                    "Этап содержит профиль разрешения."
                    if stage.get("resolution_profile_id")
                    else f"Этап содержит слотов: {len(stage.get('slots') or [])}."
                ),
                details={
                    "stage_id": stage.get("stage_id"),
                    "order": stage.get("order"),
                    "slot_ids": [slot.get("slot_id") for slot in stage.get("slots") or []],
                    "resolution_profile_id": stage.get("resolution_profile_id"),
                },
            )

        for slot in slot_schema["slots"]:
            slot_id = slot["slot_id"]
            if slot_id not in provided:
                continue
            effective_thresholds = self.effective_confidence_thresholds(
                scenario=detail["scenario"],
                slot=slot,
                profile=profile_by_id.get(slot.get("resolution_profile_id", "")),
                include_profile=slot_fill_method(slot) == "resolution_profile",
            )
            slot_values[slot_id] = {
                "status": "provided",
                "value": provided[slot_id],
                "fill_method": "operator_input",
                "source": "operator_input",
                "reason": "Значение введено оператором в тестовом прогоне.",
                "effective_confidence_thresholds": effective_thresholds,
            }
            append_trace(
                execution_trace,
                step="1",
                status="completed",
                title=f"Слот {slot_id}",
                message="Значение предоставлено оператором.",
            )

        for iteration in range(1, max_iterations + 1):
            progress = False
            waiting_dependencies.clear()

            for slot in slot_schema["slots"]:
                slot_id = slot["slot_id"]
                if slot_value_is_filled(slot_values, provided, slot_id):
                    continue
                if slot_fill_method(slot) != "resolution_profile":
                    continue
                profile = profile_by_id.get(slot.get("resolution_profile_id", ""))
                profile_id = profile["profile_id"] if profile else slot.get("resolution_profile_id")
                dependencies = resolution_profile_input_dependencies(profile or {})
                missing_dependencies = missing_slot_dependencies(
                    dependencies,
                    slot_values=slot_values,
                    provided=provided,
                )
                if missing_dependencies:
                    waiting_dependencies[slot_id] = missing_dependencies
                    continue
                profile_result = None
                if profile:
                    if profile["profile_id"] not in profile_results:
                        profile_results[profile["profile_id"]] = self.simulate_attribute_resolution_profile(
                            profile=profile,
                            slot_schema=slot_schema,
                            provided=provided,
                            simulation_options=simulation_options,
                            effective_thresholds=self.effective_confidence_thresholds(
                                scenario=detail["scenario"],
                                slot=slot,
                                profile=profile,
                                include_profile=True,
                            ),
                            execution_trace=execution_trace,
                            slot_values=slot_values,
                        )
                    profile_result = profile_results[profile["profile_id"]]

                output_value = (profile_result or {}).get("output_values", {}).get(slot_id)
                effective_thresholds = self.effective_confidence_thresholds(
                    scenario=detail["scenario"],
                    slot=slot,
                    profile=profile,
                    include_profile=True,
                )
                if output_value is not None:
                    slot_values[slot_id] = {
                        "status": "filled_by_profile",
                        "value": output_value,
                        "fill_method": "resolution_profile",
                        "source": "resolution_profile",
                        "resolution_profile_id": profile_id,
                        "confidence": (profile_result or {}).get("candidate_confidence"),
                        "reason": (profile_result or {}).get("reason"),
                        "dependencies": dependencies,
                        "effective_confidence_thresholds": effective_thresholds,
                        **slot_source_summary(slot),
                    }
                    if slot_id in missing_slots:
                        missing_slots.remove(slot_id)
                    progress = True
                else:
                    slot_values[slot_id] = {
                        "status": (profile_result or {}).get("status", "resolution_pending"),
                        "value": None,
                        "fill_method": "resolution_profile",
                        "source": "resolution_profile",
                        "resolution_profile_id": profile_id,
                        "dependencies": dependencies,
                        "effective_confidence_thresholds": effective_thresholds,
                        "reason": (profile_result or {}).get(
                            "reason",
                            "Профиль разрешения атрибута ожидает результат операции или уточнение.",
                        ),
                        **slot_source_summary(slot),
                    }
                    if slot.get("required") and slot_id not in missing_slots:
                        missing_slots.append(slot_id)

                if profile and profile["profile_id"] not in seen_resolution_profile_ids:
                    seen_resolution_profile_ids.add(profile["profile_id"])
                    state_summary = {
                        "slot_id": slot_id,
                        "iteration": iteration,
                        **(profile_result or {}),
                    }
                    resolution_state[slot_id] = state_summary
                    resolution_steps.append(state_summary)

            for stage in stages:
                profile_id = stage.get("resolution_profile_id")
                if not profile_id or profile_id in profile_results:
                    continue
                profile = profile_by_id.get(profile_id)
                if not profile:
                    continue
                dependencies = resolution_profile_input_dependencies(profile)
                missing_dependencies = missing_slot_dependencies(
                    dependencies,
                    slot_values=slot_values,
                    provided=provided,
                )
                if missing_dependencies:
                    waiting_dependencies[stage.get("stage_id") or profile_id] = missing_dependencies
                    continue
                profile_results[profile_id] = self.simulate_attribute_resolution_profile(
                    profile=profile,
                    slot_schema=slot_schema,
                    provided=provided,
                    simulation_options=simulation_options,
                    effective_thresholds=self.system_confidence_defaults(),
                    execution_trace=execution_trace,
                    slot_values=slot_values,
                )
                profile_result = profile_results[profile_id]
                for output_slot_id, output_value in profile_result.get("output_values", {}).items():
                    if output_slot_id in known_slot_ids and output_value not in (None, ""):
                        slot_values[output_slot_id] = {
                            "status": "filled_by_stage_profile",
                            "value": output_value,
                            "fill_method": "resolution_profile",
                            "source": "stage_resolution_profile",
                            "resolution_profile_id": profile_id,
                            "confidence": profile_result.get("candidate_confidence"),
                            "reason": profile_result.get("reason"),
                            "dependencies": dependencies,
                            "effective_confidence_thresholds": self.system_confidence_defaults(),
                        }
                        if output_slot_id in missing_slots:
                            missing_slots.remove(output_slot_id)
                        progress = True
                if profile_id not in seen_resolution_profile_ids:
                    seen_resolution_profile_ids.add(profile_id)
                    state_summary = {
                        "stage_id": stage.get("stage_id"),
                        "profile_id": profile_id,
                        "iteration": iteration,
                        **profile_result,
                    }
                    resolution_state[stage.get("stage_id") or profile_id] = state_summary
                    resolution_steps.append(state_summary)

            ready_llm_slots: list[dict[str, Any]] = []
            ready_llm_dependencies: dict[str, list[str]] = {}
            for slot in slot_schema["slots"]:
                slot_id = slot["slot_id"]
                if slot_fill_method(slot) != "llm_extraction":
                    continue
                if slot_id in attempted_llm_slots or slot_value_is_filled(slot_values, provided, slot_id):
                    continue
                dependencies = llm_slot_dependencies(slot)
                missing_dependencies = missing_slot_dependencies(
                    dependencies,
                    slot_values=slot_values,
                    provided=provided,
                )
                if missing_dependencies:
                    waiting_dependencies[slot_id] = missing_dependencies
                    continue
                ready_llm_slots.append(slot)
                ready_llm_dependencies[slot_id] = dependencies

            if ready_llm_slots and simulation_options["allow_llm"]:
                attempted_llm_slots.update(slot["slot_id"] for slot in ready_llm_slots)
                model_result = invoke_slot_extraction_model(
                    model_config=runtime_model_routing(self.active_payload("model_routing")),
                    scenario=detail["scenario"],
                    slots=ready_llm_slots,
                    text=text,
                    slot_values=filled_slot_values_for_context(slot_values, provided),
                )
                if model_result.get("status") == "success":
                    llm_result_by_slot = {
                        slot_id: normalized_llm_slot_result(slot_result)
                        for slot_id, slot_result in (model_result.get("slots") or {}).items()
                    }
                    append_trace(
                        execution_trace,
                        step="1",
                        status="completed",
                        title="Извлечение слотов моделью",
                        message=f"Модель вернула результаты для {len(llm_result_by_slot)} слотов.",
                        details={
                            "iteration": iteration,
                            "provider": model_result.get("provider"),
                            "model": model_result.get("model"),
                            "gateway_base_url": model_result.get("gateway_base_url"),
                            "runtime_override_applied": model_result.get("runtime_override_applied"),
                            "duration_ms": model_result.get("duration_ms"),
                            "usage": model_result.get("usage", {}),
                            "redaction": model_result.get("redaction", {}),
                            "known_slot_ids": sorted(filled_slot_values_for_context(slot_values, provided)),
                            "parameters": {"slot_ids": [slot["slot_id"] for slot in ready_llm_slots]},
                            "result": llm_result_by_slot,
                        },
                    )
                    for slot in ready_llm_slots:
                        slot_id = slot["slot_id"]
                        extracted = llm_result_by_slot.get(slot_id)
                        if not extracted:
                            continue
                        accepted = self._record_llm_slot_result(
                            slot=slot,
                            slot_values=slot_values,
                            missing_slots=missing_slots,
                            extracted=extracted,
                            effective_thresholds=self.effective_confidence_thresholds(
                                scenario=detail["scenario"],
                                slot=slot,
                                profile=None,
                                include_profile=False,
                            ),
                            execution_trace=execution_trace,
                            iteration=iteration,
                            dependencies=ready_llm_dependencies.get(slot_id, []),
                        )
                        progress = progress or accepted
                else:
                    llm_error = model_result.get("error", {})
                    append_trace(
                        execution_trace,
                        step="1",
                        status="error",
                        title="Извлечение слотов моделью",
                        message=llm_error.get("message", "Модель недоступна."),
                        details={
                            "iteration": iteration,
                            "provider": model_result.get("provider"),
                            "model": model_result.get("model"),
                            "gateway_base_url": model_result.get("gateway_base_url"),
                            "runtime_override_applied": model_result.get("runtime_override_applied"),
                            "code": llm_error.get("code"),
                            "redaction": model_result.get("redaction", {}),
                        },
                    )
                    for slot in ready_llm_slots:
                        slot_id = slot["slot_id"]
                        slot_values[slot_id] = {
                            "status": "model_unavailable",
                            "value": None,
                            "fill_method": "llm_extraction",
                            "source": "llm",
                            "error": llm_error,
                            "reason": "Модель не вернула результат для слота.",
                            "dependencies": ready_llm_dependencies.get(slot_id, []),
                            "effective_confidence_thresholds": self.effective_confidence_thresholds(
                                scenario=detail["scenario"],
                                slot=slot,
                                profile=None,
                                include_profile=False,
                            ),
                            **slot_source_summary(slot),
                        }
                        if slot.get("required") and slot_id not in missing_slots:
                            missing_slots.append(slot_id)
            elif ready_llm_slots:
                attempted_llm_slots.update(slot["slot_id"] for slot in ready_llm_slots)
                append_trace(
                    execution_trace,
                    step="1",
                    status="skipped",
                    title="Извлечение слотов моделью",
                    message="Режим тестового прогона не разрешает вызов LLM.",
                    details={
                        "iteration": iteration,
                        "slot_ids": [slot["slot_id"] for slot in ready_llm_slots],
                    },
                )
                for slot in ready_llm_slots:
                    slot_id = slot["slot_id"]
                    slot_values[slot_id] = {
                        "status": "extraction_pending",
                        "value": None,
                        "fill_method": "llm_extraction",
                        "source": "llm",
                        "reason": "Вызов модели не выполнялся в выбранном режиме тестового прогона.",
                        "dependencies": ready_llm_dependencies.get(slot_id, []),
                        "effective_confidence_thresholds": self.effective_confidence_thresholds(
                            scenario=detail["scenario"],
                            slot=slot,
                            profile=None,
                            include_profile=False,
                        ),
                        **slot_source_summary(slot),
                    }
                    if slot.get("required") and slot_id not in missing_slots:
                        missing_slots.append(slot_id)

            if not progress:
                break

        unresolved_dependency_slots = {
            slot_id: deps
            for slot_id, deps in waiting_dependencies.items()
            if deps
        }
        unresolved_ids = set(unresolved_dependency_slots)
        cycle_like = bool(unresolved_ids) and all(
            any(dependency in unresolved_ids for dependency in deps)
            for deps in unresolved_dependency_slots.values()
        )
        for slot in slot_schema["slots"]:
            slot_id = slot["slot_id"]
            fill_method = slot_fill_method(slot)
            if slot_value_is_filled(slot_values, provided, slot_id):
                if slot_id in missing_slots:
                    missing_slots.remove(slot_id)
                continue
            if slot_id in slot_values and (slot_values[slot_id] or {}).get("status") == "candidate_below_threshold":
                if slot.get("required") and slot_id not in missing_slots:
                    missing_slots.append(slot_id)
                continue
            effective_thresholds = self.effective_confidence_thresholds(
                scenario=detail["scenario"],
                slot=slot,
                profile=profile_by_id.get(slot.get("resolution_profile_id", "")),
                include_profile=fill_method == "resolution_profile",
            )
            dependencies = (
                llm_slot_dependencies(slot)
                if fill_method == "llm_extraction"
                else resolution_profile_input_dependencies(profile_by_id.get(slot.get("resolution_profile_id", ""), {}))
                if fill_method == "resolution_profile"
                else []
            )
            missing_dependencies = missing_slot_dependencies(
                dependencies,
                slot_values=slot_values,
                provided=provided,
            )
            if missing_dependencies:
                status = "blocked_by_dependency_cycle" if cycle_like and slot_id in unresolved_ids else "waiting_for_dependencies"
                slot_values[slot_id] = {
                    "status": status,
                    "value": None,
                    "fill_method": fill_method,
                    "reason": "Ожидаются зависимые слоты: " + ", ".join(missing_dependencies) + ".",
                    "dependencies": dependencies,
                    "missing_dependencies": missing_dependencies,
                    "effective_confidence_thresholds": effective_thresholds,
                    **slot_source_summary(slot),
                }
                append_trace(
                    execution_trace,
                    step="1",
                    status="blocked" if status == "blocked_by_dependency_cycle" else "waiting",
                    title=f"Зависимости слота: {slot_id}",
                    message=slot_values[slot_id]["reason"],
                    details={
                        "slot_id": slot_id,
                        "dependencies": dependencies,
                        "missing_dependencies": missing_dependencies,
                        "status": status,
                    },
                )
            elif slot_id not in slot_values:
                slot_values[slot_id] = {
                    "status": "missing" if slot.get("required") else "optional",
                    "value": None,
                    "fill_method": fill_method,
                    "reason": "Для обязательного слота нет заполненного значения." if slot.get("required") else "Необязательный слот не заполнен.",
                    "effective_confidence_thresholds": effective_thresholds,
                    **slot_source_summary(slot),
                }
            if slot.get("required") and not slot_value_is_filled(slot_values, provided, slot_id) and slot_id not in missing_slots:
                missing_slots.append(slot_id)

        return slot_values, missing_slots, resolution_steps, resolution_state

    def simulate_scenario(
        self,
        scenario_id: str,
        *,
        text: str,
        provided_slots: dict[str, Any] | None = None,
        channel_id: str | None = None,
        channel_parameter_values: dict[str, Any] | None = None,
        run_mode: str | None = None,
        allow_llm: bool | None = None,
        allow_readonly_integrations: bool | None = None,
        allow_mock_integrations: bool | None = None,
        allow_action_with_approval: bool | None = None,
        bypass_policy_gates: bool | None = None,
        async_diagnostics_level: str | None = None,
    ) -> dict[str, Any]:
        detail = self.scenario_detail(scenario_id)
        if channel_id:
            interaction_channel = self.resolve_simulation_channel(detail["scenario"], channel_id)
            detail["interaction_channel"] = interaction_channel
        slot_schema = detail["slot_schema"] or {"slots": [], "question_order": []}
        stages = slot_schema_stages(slot_schema)
        known_slot_ids = {slot["slot_id"] for slot in slot_schema["slots"]}
        simulation_options = normalize_simulation_options(
            run_mode=run_mode,
            allow_llm=allow_llm,
            allow_readonly_integrations=allow_readonly_integrations,
            allow_mock_integrations=allow_mock_integrations,
            allow_action_with_approval=allow_action_with_approval,
            bypass_policy_gates=bypass_policy_gates,
            async_diagnostics_level=async_diagnostics_level,
        )
        execution_trace: list[dict[str, Any]] = []
        append_trace(
            execution_trace,
            step="0",
            status="started",
            title="Режим отладочного прогона",
            message=simulation_options["display_name"],
            details={
                key: simulation_options[key]
                for key in (
                    "run_mode",
                    "allow_llm",
                    "allow_readonly_integrations",
                    "allow_mock_integrations",
                    "allow_action_with_approval",
                    "bypass_policy_gates",
                    "async_diagnostics_level",
                )
            },
        )
        profile_by_id = self._by_id(
            detail.get("attribute_resolution_profiles", []),
            "profile_id",
        )
        provided = provided_slots or {}
        thresholds_by_slot = {}
        for slot in slot_schema["slots"]:
            fill_method = slot_fill_method(slot)
            profile = profile_by_id.get(slot.get("resolution_profile_id", ""))
            thresholds_by_slot[slot["slot_id"]] = self.effective_confidence_thresholds(
                scenario=detail["scenario"],
                slot=slot,
                profile=profile,
                include_profile=fill_method == "resolution_profile",
            )
        slot_values, missing_slots, resolution_steps, resolution_state = self._simulate_slot_filling(
            detail=detail,
            slot_schema=slot_schema,
            stages=stages,
            known_slot_ids=known_slot_ids,
            provided=provided,
            text=text,
            simulation_options=simulation_options,
            execution_trace=execution_trace,
        )
        route = detail["route"]
        classification = self.classify_text(text, route)
        confidence = classification["confidence"]
        positive_hit_texts = [item["text"] for item in classification.get("positive_hits", [])]
        negative_hit_texts = [item["text"] for item in classification.get("negative_hits", [])]
        append_trace(
            execution_trace,
            step="2",
            status="completed",
            title="Классификация правилами",
            message=(
                f"Маршрут {classification.get('display_name') or classification.get('route_id')}; "
                f"confidence {confidence}; уровень: {classification['decision_level']}; "
                f"позитивные совпадения: {', '.join(positive_hit_texts) if positive_hit_texts else 'нет'}; "
                f"негативные совпадения: {', '.join(negative_hit_texts) if negative_hit_texts else 'нет'}."
            ),
            details={
                "route_id": classification.get("route_id"),
                "configured_route_id": classification.get("configured_route_id"),
                "matches_configured_route": classification.get("matches_configured_route"),
                "positive_hits": positive_hit_texts,
                "negative_hits": negative_hit_texts,
            },
        )
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
        if next_question:
            append_trace(
                execution_trace,
                step="1",
                status="question_required",
                title="Уточнение у клиента",
                message=next_question,
            )
        profile_launches = self._profile_tool_launches(detail.get("attribute_resolution_profiles", []))
        ready_launches, blocked_launches, next_allowed_actions = self._simulate_profile_launches(
            profile_launches,
            slot_values=slot_values,
            provided=provided,
            missing_slots=missing_slots,
            simulation_options=simulation_options,
        )
        interaction_channel = detail.get("interaction_channel") or {}
        missing_slot_set = set(missing_slots)
        resolution_operator_handoffs = [
            item
            for item in resolution_steps
            if item.get("status") == "operator_handoff" or item.get("decision") == "handoff"
        ]
        resolution_pending_live = [
            item
            for item in resolution_steps
            if item.get("status") == "pending_live_execution"
            or item.get("decision") == "execute_capability"
        ]
        blocking_configuration = any(
            item.get("unknown_required_slots")
            or any(
                slot_id not in missing_slot_set
                for slot_id in item.get("missing_parameter_slots") or []
            )
            for item in blocked_launches
        )
        if next_question:
            final_decision = "continue_slot_filling"
        elif resolution_operator_handoffs:
            final_decision = "operator_handoff"
        elif resolution_pending_live:
            final_decision = "waiting_external_event"
        elif missing_slots:
            final_decision = "pending_auto_fill"
        elif blocking_configuration:
            final_decision = "blocked_by_configuration"
        elif any(item.get("status") == "approval_required" for item in ready_launches):
            final_decision = "waiting_operator_approval"
        else:
            final_decision = "ready_for_capability"
        client_question = {
            "required": bool(next_question),
            "question": next_question,
            "delivery": {
                "channel_id": interaction_channel.get("channel_id"),
                "mode": interaction_channel.get("mode"),
                "capabilities": interaction_channel.get("capabilities", {}),
            },
            "waiting_policy": interaction_channel.get("waiting_policy"),
            "resume_after_answer": bool(next_question),
            "semantic": "client_clarification",
        }
        operator_escalation_required = (
            final_decision == "blocked_by_configuration"
            or final_decision == "operator_handoff"
            or classification.get("decision_level") == "human_required"
            or classification.get("route") == "human_review"
        )
        operator_escalation_reason = None
        if operator_escalation_required:
            if final_decision == "blocked_by_configuration":
                operator_escalation_reason = "Конфигурация или параметры capability не позволяют продолжить автообработку."
            elif final_decision == "operator_handoff":
                operator_escalation_reason = "Профиль разрешения слота настроен на эскалацию оператору."
            elif classification.get("decision_level") == "human_required":
                operator_escalation_reason = "Уверенность классификации ниже порога самостоятельного решения."
            else:
                operator_escalation_reason = "Маршрут требует участия оператора."
        escalation_action = default_channel_handoff_action(interaction_channel)
        escalation_policy = detail.get("escalation_policy") or {}
        escalation_package = {
            "policy_id": escalation_policy.get("policy_id"),
            "package_items": escalation_policy.get("handoff_package", []),
            "slots": {
                slot_id: slot_value.get("value")
                for slot_id, slot_value in slot_values.items()
            },
            "missing_slots": missing_slots,
            "classification": {
                "route_id": classification.get("route_id"),
                "route": classification.get("route"),
                "priority": classification.get("priority"),
                "confidence": classification.get("confidence"),
                "decision_level": classification.get("decision_level"),
            },
            "blocked_tool_launches": blocked_launches,
            "ready_tool_launches": ready_launches,
            "attribute_resolution_handoffs": resolution_operator_handoffs,
            "user_notification": escalation_policy.get("user_notification_template"),
        }
        operator_escalation = {
            "required": operator_escalation_required,
            "reason": operator_escalation_reason,
            "event_type": "standard_handoff",
            "channel_id": interaction_channel.get("channel_id"),
            "channel_name": interaction_channel.get("display_name"),
            "action": escalation_action,
            "package": escalation_package if operator_escalation_required else None,
            "semantic": "operator_escalation",
        }
        planned_waits = [
            item["planned_wait"]
            for item in [*ready_launches, *blocked_launches]
            if item.get("planned_wait")
        ]
        simulation_result = {
            "schema_version": "1.0",
            "scenario_id": scenario_id,
            "input_text": text,
            "run_mode": simulation_options["run_mode"],
            "simulation_options": simulation_options,
            "interaction_channel": interaction_channel,
            "waiting_policy": interaction_channel.get("waiting_policy"),
            "escalation_action": escalation_action,
            "slot_values": slot_values,
            "missing_slots": missing_slots,
            "next_question": next_question,
            "next_client_question": next_question,
            "client_question": client_question,
            "awaiting_client_response": bool(next_question),
            "operator_escalation": operator_escalation,
            "escalation_package": escalation_package if operator_escalation_required else None,
            "attribute_resolution": resolution_steps,
            "resolution_state": resolution_state,
            "classification": classification,
            "ready_tool_launches": ready_launches,
            "blocked_tool_launches": blocked_launches,
            "planned_waits": planned_waits,
            "next_allowed_actions": next_allowed_actions,
            "execution_trace": execution_trace,
            "final_decision": final_decision,
            "dry_run": True,
        }
        simulation_result["agent_outcome"] = build_agent_outcome_from_simulation(simulation_result)
        simulation_result["variable_context_snapshot"] = build_simulation_variable_context(
            scenario_id=scenario_id,
            input_text=text,
            slot_values=slot_values,
            resolution_state=resolution_state,
            classification=classification,
            ready_tool_launches=ready_launches,
            blocked_tool_launches=blocked_launches,
            planned_waits=simulation_result["planned_waits"],
            final_decision=final_decision,
            agent_outcome=simulation_result["agent_outcome"],
            interaction_channel=interaction_channel,
            channel_parameter_values=channel_parameter_values,
        )
        simulation_result["channel_variables"] = copy.deepcopy(
            simulation_result["variable_context_snapshot"].get("channel") or {}
        )
        simulation_result["channel_parameter_state"] = channel_debug_parameter_state(
            interaction_channel,
            simulation_result["channel_variables"],
        )
        return simulation_result

    def create_draft(
        self,
        *,
        domain: str,
        payload: dict[str, Any],
        created_by: str,
        base_version_id: str | None = None,
        scope: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._require_domain(domain)
        now = utc_now()
        draft_payload = copy.deepcopy(payload)
        if domain == "attribute_resolution_profiles":
            draft_payload = self._normalize_payload(domain, draft_payload)
        draft = {
            "schema_version": "1.0",
            "draft_id": new_draft_id(),
            "domain": domain,
            "payload": draft_payload,
            "status": "draft",
            "created_by": created_by,
            "created_at": now,
            "updated_at": now,
        }
        if base_version_id:
            draft["base_version_id"] = base_version_id
        if scope:
            draft["scope"] = copy.deepcopy(scope)
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
        if draft.get("domain") == "attribute_resolution_profiles":
            draft["payload"] = self._normalize_payload("attribute_resolution_profiles", draft["payload"])
        if self.is_scoped_attribute_resolution_profile_draft(draft):
            validation = self._validate_scoped_attribute_resolution_profile_draft(draft)
        else:
            active_overrides, override_errors = self._draft_validation_overrides(draft)
            validation = self.validate_payload(
                draft["domain"],
                draft["payload"],
                active_overrides=active_overrides,
            )
            if override_errors:
                validation["errors"] = [*override_errors, *validation.get("errors", [])]
                validation["status"] = "invalid"
                for gate in validation.get("gates", []):
                    gate["status"] = "failed"
        draft["validation"] = validation
        draft["status"] = "valid" if validation["status"] == "valid" else "invalid"
        draft["updated_at"] = utc_now()
        return self._save_draft(draft)

    @staticmethod
    def _draft_scope_key(scope: dict[str, Any] | None) -> tuple[str, str, str, str] | None:
        if not isinstance(scope, dict):
            return None
        if scope.get("type") != "collection_item":
            return None
        collection = str(scope.get("collection") or "")
        id_key = str(scope.get("id_key") or "")
        item_id = str(scope.get("id") or "")
        if not collection or not id_key or not item_id:
            return None
        return ("collection_item", collection, id_key, item_id)

    @staticmethod
    def _draft_scope_action(scope: dict[str, Any] | None) -> str:
        action = str((scope or {}).get("action") or "upsert")
        return action if action in {"upsert", "delete"} else "upsert"

    def is_scoped_attribute_resolution_profile_draft(self, draft: dict[str, Any]) -> bool:
        return (
            draft.get("domain") == "attribute_resolution_profiles"
            and self._draft_scope_key(draft.get("scope")) is not None
            and draft.get("scope", {}).get("collection") == "profiles"
            and draft.get("scope", {}).get("id_key") == "profile_id"
        )

    def _scoped_profile_id(self, draft: dict[str, Any]) -> str:
        return str((draft.get("scope") or {}).get("id") or "")

    @staticmethod
    def _profile_from_payload(payload: dict[str, Any], profile_id: str) -> dict[str, Any] | None:
        return next(
            (profile for profile in payload.get("profiles", []) if profile.get("profile_id") == profile_id),
            None,
        )

    @staticmethod
    def _slot_schema_slot_ids(slot_schema: dict[str, Any] | None) -> set[str]:
        if not slot_schema:
            return set()
        slot_ids = {
            slot.get("slot_id")
            for slot in slot_schema.get("slots", [])
            if slot.get("slot_id")
        }
        for stage in slot_schema.get("stages", []) or []:
            slot_ids.update(
                slot.get("slot_id")
                for slot in stage.get("slots", []) or []
                if slot.get("slot_id")
            )
        return {str(slot_id) for slot_id in slot_ids if slot_id}

    def _scoped_profile_slot_errors(self, profile: dict[str, Any]) -> list[str]:
        slot_schema_id = profile.get("slot_schema_id") or ""
        slot_schema = next(
            (
                item
                for item in self.active_payload("slot_schemas").get("slot_schemas", [])
                if item.get("slot_schema_id") == slot_schema_id
            ),
            None,
        )
        if not slot_schema:
            return []
        active_slot_ids = self._slot_schema_slot_ids(slot_schema)
        declared_slot_ids = {
            rule.get("slot_id")
            for rule in profile.get("output_slots_order", []) or []
            if rule.get("slot_id")
        }
        if profile.get("target_slot_id"):
            declared_slot_ids.add(profile["target_slot_id"])
        missing_slot_ids = sorted(slot_id for slot_id in declared_slot_ids if slot_id not in active_slot_ids)
        if not missing_slot_ids:
            return []
        return [
            "Профиль нельзя активировать отдельно: выходные слоты отсутствуют в активной схеме "
            f"{slot_schema.get('display_name') or slot_schema_id}: {', '.join(missing_slot_ids)}. "
            "Используйте «Активировать пакет», чтобы применить профиль вместе со схемой слотов."
        ]

    def _scoped_profile_delete_errors(self, profile_id: str) -> list[str]:
        refs: list[str] = []
        for slot_schema in self.active_payload("slot_schemas").get("slot_schemas", []):
            schema_name = slot_schema.get("display_name") or slot_schema.get("slot_schema_id")
            for stage in slot_schema.get("stages", []) or []:
                stage_name = stage.get("display_name") or stage.get("stage_id")
                if stage.get("resolution_profile_id") == profile_id:
                    refs.append(f'{schema_name} / этап "{stage_name}"')
                for slot in stage.get("slots", []) or []:
                    if slot.get("resolution_profile_id") == profile_id:
                        refs.append(f'{schema_name} / слот "{slot.get("display_name") or slot.get("slot_id")}"')
            for slot in slot_schema.get("slots", []) or []:
                if slot.get("resolution_profile_id") == profile_id:
                    refs.append(f'{schema_name} / слот "{slot.get("display_name") or slot.get("slot_id")}"')
        if not refs:
            return []
        return [
            "Профиль нельзя удалить отдельно: он используется в схеме слотов. "
            f"Связи: {', '.join(dict.fromkeys(refs))}. "
            "Сначала уберите связи или используйте инструмент обслуживания конфигурации."
        ]

    def _validate_scoped_attribute_resolution_profile_draft(self, draft: dict[str, Any]) -> dict[str, Any]:
        profile_id = self._scoped_profile_id(draft)
        action = self._draft_scope_action(draft.get("scope"))
        contract_name = CONFIG_DOMAINS["attribute_resolution_profiles"].contract_name
        errors: list[str] = []
        if not profile_id:
            errors.append("Scoped draft профиля должен содержать scope.id.")
        if action == "delete":
            if not self._profile_from_payload(self.active_payload("attribute_resolution_profiles"), profile_id):
                errors.append(f"Профиль для удаления не найден в активной конфигурации: {profile_id}.")
            errors.extend(self._scoped_profile_delete_errors(profile_id))
        else:
            profile = self._profile_from_payload(draft.get("payload") or {}, profile_id)
            if not profile:
                errors.append(f"Scoped draft не содержит профиль {profile_id}.")
            else:
                scoped_payload = {
                    "schema_version": "1.0",
                    "profiles": [copy.deepcopy(profile)],
                }
                validation = self.validate_payload("attribute_resolution_profiles", scoped_payload)
                errors.extend(validation.get("errors") or [])
                errors.extend(self._scoped_profile_slot_errors(profile))
        return {
            "schema_version": "1.0",
            "domain": "attribute_resolution_profiles",
            "contract_name": contract_name,
            "status": "invalid" if errors else "valid",
            "validated_at": utc_now(),
            "errors": errors,
            "scope": copy.deepcopy(draft.get("scope")),
            "gates": [
                {
                    "gate_id": "scoped_profile",
                    "status": "failed" if errors else "passed",
                    "message": "Валидация одного профиля разрешения завершена.",
                }
            ],
        }

    def _draft_validation_overrides(
        self,
        draft: dict[str, Any],
    ) -> tuple[dict[str, dict[str, Any]] | None, list[str]]:
        domain = draft["domain"]
        related_domains = DRAFT_VALIDATION_RELATED_DOMAINS.get(domain, set())
        if not related_domains:
            return None, []

        raw_payloads: dict[str, dict[str, Any]] = {
            related_domain: self._latest_working_draft_payload(
                domain=related_domain,
                created_by=draft.get("created_by", ""),
                base_version_id=self.active_version_id(related_domain),
            )
            or self.active_payload(related_domain)
            for related_domain in related_domains
        }
        raw_payloads[domain] = copy.deepcopy(draft["payload"])
        return self._normalize_draft_validation_overrides(raw_payloads, current_domain=domain)

    def _latest_working_draft_payload(
        self,
        *,
        domain: str,
        created_by: str,
        base_version_id: str | None = None,
    ) -> dict[str, Any] | None:
        working_statuses = {"draft", "valid", "regression_passed"}
        current_base_version_id = base_version_id or self.active_version_id(domain)
        for candidate in self.list_drafts(domain=domain, limit=100):
            if candidate.get("status") not in working_statuses:
                continue
            if candidate.get("created_by") != created_by:
                continue
            candidate_base_version_id = candidate.get("base_version_id")
            if current_base_version_id and candidate_base_version_id != current_base_version_id:
                continue
            if not current_base_version_id and candidate_base_version_id:
                continue
            payload = candidate.get("payload")
            if isinstance(payload, dict):
                return copy.deepcopy(payload)
        return None

    def _delete_working_drafts_for_domain_operator(
        self,
        connection: sqlite3.Connection,
        *,
        domain: str,
        operator_id: str,
        preserve_draft_ids: set[str],
    ) -> list[str]:
        if not operator_id:
            return []
        rows = connection.execute(
            """
            select draft_id
            from config_drafts
            where domain = ?
              and created_by = ?
              and status in ('draft', 'valid', 'regression_passed')
            order by updated_at desc, draft_id desc
            """,
            (domain, operator_id),
        ).fetchall()
        draft_ids = [
            str(row["draft_id"])
            for row in rows
            if str(row["draft_id"]) not in preserve_draft_ids
        ]
        if draft_ids:
            connection.executemany(
                "delete from config_drafts where draft_id = ?",
                [(draft_id,) for draft_id in draft_ids],
            )
        return draft_ids

    def _delete_drafts_for_same_scope_operator(
        self,
        connection: sqlite3.Connection,
        *,
        domain: str,
        operator_id: str,
        scope: dict[str, Any] | None,
        preserve_draft_ids: set[str],
    ) -> list[str]:
        scope_key = self._draft_scope_key(scope)
        if not operator_id or not scope_key:
            return []
        rows = connection.execute(
            """
            select draft_id, draft_json
            from config_drafts
            where domain = ?
              and created_by = ?
              and status in ('draft', 'valid', 'invalid', 'regression_passed')
            order by updated_at desc, draft_id desc
            """,
            (domain, operator_id),
        ).fetchall()
        draft_ids: list[str] = []
        for row in rows:
            draft_id = str(row["draft_id"])
            if draft_id in preserve_draft_ids:
                continue
            try:
                candidate = json.loads(row["draft_json"])
            except json.JSONDecodeError:
                continue
            if self._draft_scope_key(candidate.get("scope")) == scope_key:
                draft_ids.append(draft_id)
        if draft_ids:
            connection.executemany(
                "delete from config_drafts where draft_id = ?",
                [(draft_id,) for draft_id in draft_ids],
            )
        return draft_ids

    def _normalize_draft_validation_overrides(
        self,
        raw_payloads: dict[str, dict[str, Any]],
        *,
        current_domain: str,
    ) -> tuple[dict[str, dict[str, Any]], list[str]]:
        normalized: dict[str, dict[str, Any]] = {}
        errors: list[str] = []
        if "slot_schemas" in raw_payloads:
            slot_payload = self._normalize_payload("slot_schemas", raw_payloads["slot_schemas"])
            slot_errors = self.contracts.validate(CONFIG_DOMAINS["slot_schemas"].contract_name, slot_payload)
            if slot_errors and current_domain != "slot_schemas":
                errors.extend(
                    f"Связанный черновик slot_schemas невалиден: {error}"
                    for error in slot_errors
                )
            else:
                normalized["slot_schemas"] = slot_payload

        if "attribute_resolution_profiles" in raw_payloads:
            token = _ACTIVE_PAYLOAD_OVERRIDES.set(normalized) if normalized else None
            try:
                profile_payload = self._normalize_payload(
                    "attribute_resolution_profiles",
                    raw_payloads["attribute_resolution_profiles"],
                )
            finally:
                if token is not None:
                    _ACTIVE_PAYLOAD_OVERRIDES.reset(token)
            profile_errors = self.contracts.validate(
                CONFIG_DOMAINS["attribute_resolution_profiles"].contract_name,
                profile_payload,
            )
            if profile_errors and current_domain != "attribute_resolution_profiles":
                errors.extend(
                    f"Связанный черновик attribute_resolution_profiles невалиден: {error}"
                    for error in profile_errors
                )
            else:
                normalized["attribute_resolution_profiles"] = profile_payload

        return normalized, errors

    def save_regression(self, draft_id: str, regression: dict[str, Any]) -> dict[str, Any]:
        draft = self.require_draft(draft_id)
        draft["regression"] = regression
        if regression["status"] in {"passed", "skipped"} and draft.get("validation", {}).get("status") == "valid":
            draft["status"] = "regression_passed"
        draft["updated_at"] = utc_now()
        return self._save_draft(draft)

    def validate_draft_bundle(self, draft_ids: list[str]) -> dict[str, Any]:
        drafts = self._require_draft_bundle(draft_ids)
        overrides = self._normalize_bundle_payloads(drafts)
        validations: dict[str, dict[str, Any]] = {}
        saved_drafts = []
        for draft in drafts:
            domain = draft["domain"]
            validation = self.validate_payload(
                domain,
                overrides.get(domain, draft["payload"]),
                active_overrides=overrides,
            )
            draft["validation"] = validation
            draft["status"] = "valid" if validation["status"] == "valid" else "invalid"
            draft["updated_at"] = utc_now()
            saved_drafts.append(self._save_draft(draft))
            validations[domain] = validation
        status = "invalid" if any(item.get("status") != "valid" for item in validations.values()) else "valid"
        return {
            "schema_version": "1.0",
            "status": status,
            "draft_ids": [draft["draft_id"] for draft in saved_drafts],
            "domains": [draft["domain"] for draft in saved_drafts],
            "drafts": saved_drafts,
            "validations": validations,
        }

    def normalized_draft_bundle_payloads(self, draft_ids: list[str]) -> dict[str, dict[str, Any]]:
        return self._normalize_bundle_payloads(self._require_draft_bundle(draft_ids))

    def normalized_draft_payloads_for_regression(self, draft_id: str) -> dict[str, dict[str, Any]]:
        draft = self.require_draft(draft_id)
        overrides, override_errors = self._draft_validation_overrides(draft)
        if override_errors:
            raise ConfigRegistryError("; ".join(override_errors))
        if overrides and draft["domain"] in overrides:
            return overrides
        payload = self._normalize_payload(draft["domain"], draft["payload"])
        result = overrides or {}
        result[draft["domain"]] = payload
        return result

    def activate_draft_bundle(self, draft_ids: list[str], activated_by: str) -> dict[str, Any]:
        drafts = self._require_draft_bundle(draft_ids)
        for draft in drafts:
            validation = draft.get("validation")
            regression = draft.get("regression")
            if validation is None or validation.get("status") != "valid":
                raise ConfigRegistryError("Все черновики пакета должны пройти валидацию перед активацией.")
            if regression is None or regression.get("status") not in {"passed", "skipped"}:
                raise ConfigRegistryError("Все черновики пакета должны пройти регрессионную проверку перед активацией.")

        normalized_payloads = self._normalize_bundle_payloads(drafts)
        activation_errors = self._bundle_activation_errors(normalized_payloads)
        if activation_errors:
            raise ConfigRegistryError(
                "Итоговая конфигурация после пакетной активации невалидна: "
                + "; ".join(activation_errors)
            )

        activated_at = utc_now()
        versions = []
        for draft in drafts:
            domain = draft["domain"]
            version = {
                "schema_version": "1.0",
                "version_id": new_version_id(),
                "domain": domain,
                "payload": normalized_payloads[domain],
                "source_draft_id": draft["draft_id"],
                "activated_by": activated_by,
                "activated_at": activated_at,
                "validation": draft["validation"],
                "regression": draft["regression"],
            }
            previous_version_id = self.active_version_id(domain)
            if previous_version_id:
                version["previous_version_id"] = previous_version_id
            self.contracts.require_valid("config_version", version)
            versions.append(version)

        with self._connect() as connection:
            for version in versions:
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
            for draft in drafts:
                draft["status"] = "activated"
                draft["updated_at"] = activated_at
                connection.execute(
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
            preserve_by_domain: dict[str, set[str]] = {}
            for draft in drafts:
                preserve_by_domain.setdefault(draft["domain"], set()).add(draft["draft_id"])
            for domain, preserve_draft_ids in preserve_by_domain.items():
                self._delete_working_drafts_for_domain_operator(
                    connection,
                    domain=domain,
                    operator_id=activated_by,
                    preserve_draft_ids=preserve_draft_ids,
                )

        return {
            "schema_version": "1.0",
            "status": "activated",
            "activated_by": activated_by,
            "activated_at": activated_at,
            "draft_ids": [draft["draft_id"] for draft in drafts],
            "versions": versions,
        }

    def _require_draft_bundle(self, draft_ids: list[str]) -> list[dict[str, Any]]:
        unique_ids = [draft_id for draft_id in dict.fromkeys(draft_ids) if draft_id]
        if len(unique_ids) < 2:
            raise ConfigRegistryError("Пакетная операция требует минимум два черновика.")
        drafts = [self.require_draft(draft_id) for draft_id in unique_ids]
        domains = [draft["domain"] for draft in drafts]
        duplicate_domains = self._duplicates(domains)
        if duplicate_domains:
            raise ConfigRegistryError(
                "Пакетная операция не поддерживает несколько черновиков одного домена: "
                + ", ".join(duplicate_domains)
            )
        return drafts

    def _normalize_bundle_payloads(self, drafts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        raw_payloads = {draft["domain"]: copy.deepcopy(draft["payload"]) for draft in drafts}
        normalized: dict[str, dict[str, Any]] = {}
        if "slot_schemas" in raw_payloads:
            normalized["slot_schemas"] = self._normalize_payload("slot_schemas", raw_payloads["slot_schemas"])
        for domain, payload in raw_payloads.items():
            if domain in {"slot_schemas", "attribute_resolution_profiles"}:
                continue
            normalized[domain] = self._normalize_payload(domain, payload)
        if "attribute_resolution_profiles" in raw_payloads:
            token = _ACTIVE_PAYLOAD_OVERRIDES.set(normalized) if normalized else None
            try:
                normalized["attribute_resolution_profiles"] = self._normalize_payload(
                    "attribute_resolution_profiles",
                    raw_payloads["attribute_resolution_profiles"],
                )
            finally:
                if token is not None:
                    _ACTIVE_PAYLOAD_OVERRIDES.reset(token)
        return normalized

    def _latest_operator_payload_or_active(self, domain: str, operator_id: str) -> dict[str, Any]:
        draft_payload = self._latest_working_draft_payload(
            domain=domain,
            created_by=operator_id,
            base_version_id=self.active_version_id(domain),
        )
        return draft_payload or self.active_payload(domain)

    def _linked_scenario_raw_payloads(
        self,
        *,
        scenario: dict[str, Any],
        operator_id: str,
    ) -> dict[str, dict[str, Any]]:
        scenario_id = str(scenario.get("scenario_id") or "").strip()
        raw_payloads = {
            domain: self._latest_operator_payload_or_active(domain, operator_id)
            for domain in SCENARIO_LINKED_VALIDATION_DOMAINS
        }
        scenarios_payload = copy.deepcopy(raw_payloads["service_scenarios"])
        scenarios = list(scenarios_payload.get("scenarios") or [])
        if scenario_id:
            scenario_index = next(
                (index for index, item in enumerate(scenarios) if item.get("scenario_id") == scenario_id),
                -1,
            )
            if scenario_index >= 0:
                scenarios[scenario_index] = copy.deepcopy(scenario)
            else:
                scenarios.append(copy.deepcopy(scenario))
        scenarios_payload["scenarios"] = scenarios
        raw_payloads["service_scenarios"] = scenarios_payload
        return raw_payloads

    def _normalize_linked_scenario_payloads(
        self,
        raw_payloads: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        normalized: dict[str, dict[str, Any]] = {}
        profile_domain = "attribute_resolution_profiles"
        for domain in SCENARIO_LINKED_VALIDATION_DOMAINS:
            if domain == profile_domain:
                continue
            normalized[domain] = self._normalize_payload(domain, raw_payloads[domain])
        token = _ACTIVE_PAYLOAD_OVERRIDES.set(normalized) if normalized else None
        try:
            normalized[profile_domain] = self._normalize_payload(profile_domain, raw_payloads[profile_domain])
        finally:
            if token is not None:
                _ACTIVE_PAYLOAD_OVERRIDES.reset(token)
        return normalized

    def _scenario_scoped_validation_payloads(
        self,
        payloads: dict[str, dict[str, Any]],
        scenario_id: str,
    ) -> dict[str, dict[str, Any]]:
        scoped = copy.deepcopy(payloads)

        def pick_collection(
            domain: str,
            collection_key: str,
            id_key: str,
            ids: set[str],
        ) -> list[dict[str, Any]]:
            by_id = self._by_id(payloads[domain].get(collection_key) or [], id_key)
            return [
                copy.deepcopy(by_id[item_id])
                for item_id in sorted(ids)
                if item_id in by_id
            ]

        scenario = self._by_id(payloads["service_scenarios"].get("scenarios") or [], "scenario_id").get(scenario_id)
        scoped["service_scenarios"] = {
            "schema_version": "1.0",
            "scenarios": [copy.deepcopy(scenario)] if scenario else [],
        }
        slot_schema = None
        if scenario:
            slot_schema = self._by_id(
                payloads["slot_schemas"].get("slot_schemas") or [],
                "slot_schema_id",
            ).get(scenario.get("slot_schema_id") or "")
        scoped["slot_schemas"] = {
            "schema_version": "1.0",
            "slot_schemas": [copy.deepcopy(slot_schema)] if slot_schema else [],
        }
        profile_ids = set(slot_schema_resolution_profile_ids(slot_schema))
        profile_by_id = self._by_id(
            payloads["attribute_resolution_profiles"].get("profiles") or [],
            "profile_id",
        )
        profiles = [
            copy.deepcopy(profile_by_id[profile_id])
            for profile_id in sorted(profile_ids)
            if profile_id in profile_by_id
        ]
        scoped["attribute_resolution_profiles"] = {
            "schema_version": "1.0",
            "profiles": profiles,
        }
        capability_ids = {
            str(step.get("capability_id") or "").strip()
            for profile in profiles
            for step in profile.get("enrichment_steps") or []
            if str(step.get("capability_id") or "").strip()
        }
        step_environment_ids = {
            str(step.get("mcp_environment_id") or "").strip()
            for profile in profiles
            for step in profile.get("enrichment_steps") or []
            if str(step.get("mcp_environment_id") or "").strip()
        }
        scoped["capabilities"] = {
            "schema_version": "1.0",
            "capabilities": pick_collection("capabilities", "capabilities", "capability_id", capability_ids),
        }
        linked_bindings = [
            copy.deepcopy(binding)
            for binding in payloads["capability_bindings"].get("bindings") or []
            if str(binding.get("capability_id") or "").strip() in capability_ids
        ]
        scoped["capability_bindings"] = {
            "schema_version": "1.0",
            "bindings": linked_bindings,
        }
        binding_environment_ids = {
            str(binding.get("environment_id") or "").strip()
            for binding in linked_bindings
            if str(binding.get("environment_id") or "").strip()
        }
        scoped["mcp_environments"] = {
            "schema_version": "1.0",
            "environments": pick_collection(
                "mcp_environments",
                "environments",
                "environment_id",
                step_environment_ids | binding_environment_ids,
            ),
        }
        scoped["classification_routes"] = {
            "schema_version": "1.0",
            "routes": [],
        }
        scoped["prompt_packs"] = {
            "schema_version": "1.0",
            "packs": [],
        }
        scoped["orchestrator_policy"] = {
            "schema_version": "1.0",
            "policies": [],
        }
        scoped["escalation_policies"] = {
            "schema_version": "1.0",
            "policies": [],
        }
        scoped["interaction_channels"] = {
            "schema_version": "1.0",
            "channels": [],
        }
        if scenario:
            scoped["classification_routes"] = {
                "schema_version": "1.0",
                "routes": pick_collection(
                    "classification_routes",
                    "routes",
                    "route_id",
                    {str(scenario.get("classification_route_id") or "").strip()},
                ),
            }
            scoped["prompt_packs"] = {
                "schema_version": "1.0",
                "packs": pick_collection(
                    "prompt_packs",
                    "packs",
                    "prompt_pack_id",
                    {str(scenario.get("prompt_pack_id") or "").strip()},
                ),
            }
            scoped["orchestrator_policy"] = {
                "schema_version": "1.0",
                "policies": pick_collection(
                    "orchestrator_policy",
                    "policies",
                    "policy_id",
                    {str(scenario.get("orchestrator_policy_id") or "").strip()},
                ),
            }
            scoped["escalation_policies"] = {
                "schema_version": "1.0",
                "policies": pick_collection(
                    "escalation_policies",
                    "policies",
                    "policy_id",
                    {str(scenario.get("escalation_policy_id") or "").strip()},
                ),
            }
            channel_ids = {
                str(scenario.get("default_channel_id") or "").strip(),
                *[
                    str(channel_id or "").strip()
                    for channel_id in scenario.get("allowed_channel_ids") or []
                ],
            }
            scoped["interaction_channels"] = {
                "schema_version": "1.0",
                "channels": pick_collection("interaction_channels", "channels", "channel_id", channel_ids),
            }
        return scoped

    def validate_scenario_linked_structure(
        self,
        *,
        scenario: dict[str, Any],
        operator_id: str,
    ) -> dict[str, Any]:
        scenario_id = str(scenario.get("scenario_id") or "").strip()
        raw_payloads = self._linked_scenario_raw_payloads(
            scenario=scenario,
            operator_id=operator_id,
        )
        payloads = self._normalize_linked_scenario_payloads(raw_payloads)
        validation_payloads = self._scenario_scoped_validation_payloads(payloads, scenario_id)
        validations = {
            domain: self.validate_payload(domain, validation_payloads[domain], active_overrides=payloads)
            for domain in SCENARIO_LINKED_VALIDATION_DOMAINS
        }
        domain_errors = [
            f"{CONFIG_DOMAINS[domain].title}: {error}"
            for domain, validation in validations.items()
            for error in validation.get("errors") or []
        ]
        hierarchy_errors = self._validate_linked_scenario_hierarchy(payloads, scenario_id)
        errors = list(dict.fromkeys([*domain_errors, *hierarchy_errors]))
        return {
            "schema_version": "1.0",
            "status": "invalid" if errors else "valid",
            "scenario_id": scenario_id,
            "checked_domains": list(SCENARIO_LINKED_VALIDATION_DOMAINS),
            "errors": errors,
            "warnings": [],
            "validations": validations,
        }

    @staticmethod
    def _linked_object_label(item: dict[str, Any] | None, id_key: str) -> str:
        if not item:
            return "н/д"
        item_id = str(item.get(id_key) or "")
        display_name = str(item.get("display_name") or item.get("name") or item_id)
        return f'"{display_name}" ({item_id})' if item_id and display_name != item_id else item_id or display_name

    def _validate_linked_scenario_hierarchy(
        self,
        payloads: dict[str, dict[str, Any]],
        scenario_id: str,
    ) -> list[str]:
        errors: list[str] = []
        if not scenario_id:
            return ["Сценарий: scenario_id не заполнен."]

        scenario_by_id = self._by_id(payloads["service_scenarios"].get("scenarios") or [], "scenario_id")
        scenario = scenario_by_id.get(scenario_id)
        if not scenario:
            return [f"Сценарий {scenario_id}: не найден в effective service_scenarios."]
        scenario_path = f"Сценарий {self._linked_object_label(scenario, 'scenario_id')}"

        linked_catalogs = [
            (
                "classification_routes",
                "routes",
                "route_id",
                "classification_route_id",
                "маршрут классификации",
            ),
            ("prompt_packs", "packs", "prompt_pack_id", "prompt_pack_id", "prompt pack"),
            (
                "orchestrator_policy",
                "policies",
                "policy_id",
                "orchestrator_policy_id",
                "политика оркестрации",
            ),
            (
                "escalation_policies",
                "policies",
                "policy_id",
                "escalation_policy_id",
                "политика эскалации",
            ),
        ]
        for domain, collection_key, id_key, field_name, label in linked_catalogs:
            ref_id = str(scenario.get(field_name) or "").strip()
            if not ref_id:
                errors.append(f"{scenario_path}: {label} не указана: {field_name}.")
                continue
            item = self._by_id(payloads[domain].get(collection_key) or [], id_key).get(ref_id)
            if not item:
                errors.append(f"{scenario_path}: {label} не найдена: {ref_id}.")
            elif not config_item_is_active(item):
                errors.append(f"{scenario_path}: {label} не активна: {ref_id}.")

        channel_by_id = self._by_id(payloads["interaction_channels"].get("channels") or [], "channel_id")
        channel_refs = [
            ("канал по умолчанию", str(scenario.get("default_channel_id") or "").strip()),
            *[
                ("разрешенный канал", str(channel_id or "").strip())
                for channel_id in scenario.get("allowed_channel_ids") or []
            ],
        ]
        for label, channel_id in channel_refs:
            if not channel_id:
                errors.append(f"{scenario_path}: {label} не указан.")
                continue
            channel = channel_by_id.get(channel_id)
            if not channel:
                errors.append(f"{scenario_path}: {label} не найден: {channel_id}.")
            elif not config_item_is_active(channel):
                errors.append(f"{scenario_path}: {label} не активен: {channel_id}.")

        slot_schema_by_id = self._by_id(payloads["slot_schemas"].get("slot_schemas") or [], "slot_schema_id")
        profile_by_id = self._by_id(payloads["attribute_resolution_profiles"].get("profiles") or [], "profile_id")
        capability_by_id = self._by_id(payloads["capabilities"].get("capabilities") or [], "capability_id")
        environment_by_id = self._by_id(payloads["mcp_environments"].get("environments") or [], "environment_id")
        bindings = payloads["capability_bindings"].get("bindings") or []

        slot_schema_id = scenario.get("slot_schema_id")
        slot_schema = slot_schema_by_id.get(slot_schema_id or "")
        if not slot_schema:
            errors.append(f"{scenario_path}: схема слотов не найдена: {slot_schema_id}.")
            return errors
        if not config_item_is_active(slot_schema):
            errors.append(f"{scenario_path}: схема слотов не активна: {slot_schema_id}.")
        slot_schema_path = f"{scenario_path} -> Схема слотов {self._linked_object_label(slot_schema, 'slot_schema_id')}"
        slot_ids = {
            slot.get("slot_id")
            for slot in [*(slot_schema.get("slots") or []), *flatten_slot_schema_slots(slot_schema)]
            if slot.get("slot_id")
        }

        profile_refs: list[tuple[str, str]] = []
        for stage in slot_schema_stages(slot_schema):
            stage_label = self._linked_object_label(stage, "stage_id")
            stage_profile_id = stage.get("resolution_profile_id")
            if stage_profile_id:
                profile_refs.append((f"{slot_schema_path} -> Этап {stage_label}", stage_profile_id))
            for slot in stage.get("slots") or []:
                if slot_fill_method(slot) == "resolution_profile" and slot.get("resolution_profile_id"):
                    slot_label = self._linked_object_label(slot, "slot_id")
                    profile_refs.append((f"{slot_schema_path} -> Слот {slot_label}", slot["resolution_profile_id"]))
        for slot in slot_schema.get("slots") or []:
            if slot_fill_method(slot) == "resolution_profile" and slot.get("resolution_profile_id"):
                slot_label = self._linked_object_label(slot, "slot_id")
                profile_refs.append((f"{slot_schema_path} -> Слот {slot_label}", slot["resolution_profile_id"]))

        checked_profile_ids: set[str] = set()
        for ref_path, profile_id in profile_refs:
            profile = profile_by_id.get(profile_id or "")
            if not profile:
                errors.append(f"{ref_path}: профиль разрешения не найден: {profile_id}.")
                continue
            if not config_item_is_active(profile):
                errors.append(f"{ref_path}: профиль разрешения не активен: {profile_id}.")
            if profile.get("slot_schema_id") != slot_schema.get("slot_schema_id"):
                errors.append(
                    f"{ref_path}: профиль {profile_id} привязан к другой схеме слотов: "
                    f"{profile.get('slot_schema_id') or 'не указана'}."
                )
            if profile_id in checked_profile_ids:
                continue
            checked_profile_ids.add(profile_id)
            profile_path = f"{slot_schema_path} -> Профиль {self._linked_object_label(profile, 'profile_id')}"
            for output in profile.get("output_slots_order") or []:
                output_slot_id = output.get("slot_id")
                if output_slot_id and output_slot_id not in slot_ids:
                    errors.append(
                        f"{profile_path}: выходной слот {output_slot_id} отсутствует в схеме слотов."
                    )
            errors.extend(
                self._validate_linked_profile_capabilities(
                    profile=profile,
                    profile_path=profile_path,
                    capability_by_id=capability_by_id,
                    environment_by_id=environment_by_id,
                    bindings=bindings,
                )
            )
        return errors

    def _validate_linked_profile_capabilities(
        self,
        *,
        profile: dict[str, Any],
        profile_path: str,
        capability_by_id: dict[str, dict[str, Any]],
        environment_by_id: dict[str, dict[str, Any]],
        bindings: list[dict[str, Any]],
    ) -> list[str]:
        errors: list[str] = []
        for index, step in enumerate(profile.get("enrichment_steps") or [], start=1):
            capability_id = step.get("capability_id")
            if not capability_id:
                continue
            step_path = (
                f"{profile_path} -> Шаг {index} "
                f'"{step.get("step_name") or step.get("step_id") or f"step{index}"}"'
            )
            capability = capability_by_id.get(capability_id or "")
            if not capability:
                errors.append(f"{step_path}: capability не найдена: {capability_id}.")
                continue
            if not config_item_is_active(capability):
                errors.append(f"{step_path}: capability не активна: {capability_id}.")
            completion_policy = step.get("completion_policy") or capability.get("default_completion_policy") or {}
            expected_mode = ""
            if completion_policy.get("mode") == "external_event":
                expected_mode = "async"
            elif completion_policy.get("mode") == "sync":
                expected_mode = "sync"
            environment_id = step.get("mcp_environment_id")
            candidates = [
                binding
                for binding in bindings
                if binding.get("capability_id") == capability_id
                and binding.get("status") == "active"
                and (not expected_mode or binding.get("execution_mode") == expected_mode)
                and (not environment_id or binding.get("environment_id") == environment_id)
            ]
            if not candidates:
                mode_text = f"/{expected_mode}" if expected_mode else ""
                env_text = f" в MCP окружении {environment_id}" if environment_id else ""
                errors.append(
                    f"{step_path}: нет active capability binding для {capability_id}{mode_text}{env_text}."
                )
                continue
            if len(candidates) > 1:
                errors.append(
                    f"{step_path}: найдено больше одной active capability binding для {capability_id}: "
                    f"{', '.join(binding.get('binding_id') or 'н/д' for binding in candidates)}."
                )
            binding = candidates[0]
            environment = environment_by_id.get(binding.get("environment_id") or "")
            if not environment:
                errors.append(
                    f"{step_path}: MCP окружение binding {binding.get('binding_id')} не найдено: "
                    f"{binding.get('environment_id')}."
                )
                continue
            if not config_item_is_active(environment):
                errors.append(
                    f"{step_path}: MCP окружение {binding.get('environment_id')} не активно."
                )
            allowed_capabilities = set(environment.get("allowed_capabilities") or [])
            if allowed_capabilities and capability_id not in allowed_capabilities:
                errors.append(
                    f"{step_path}: capability {capability_id} не разрешена в MCP окружении "
                    f"{binding.get('environment_id')}."
                )
        return errors

    def _bundle_activation_errors(self, payloads: dict[str, dict[str, Any]]) -> list[str]:
        errors: list[str] = []
        for domain, payload in payloads.items():
            validation = self.validate_payload(domain, payload, active_overrides=payloads)
            if validation.get("status") != "valid":
                errors.extend(f"{domain}: {error}" for error in validation.get("errors") or [])
        return errors

    def activate_draft(self, draft_id: str, activated_by: str) -> dict[str, Any]:
        draft = self.require_draft(draft_id)
        validation = draft.get("validation")
        regression = draft.get("regression")
        if validation is None or validation.get("status") != "valid":
            raise ConfigRegistryError("Черновик должен пройти валидацию перед активацией.")
        if regression is None or regression.get("status") not in {"passed", "skipped"}:
            raise ConfigRegistryError("Черновик должен пройти регрессионную проверку перед активацией.")
        if self.is_scoped_attribute_resolution_profile_draft(draft):
            return self._activate_scoped_attribute_resolution_profile_draft(draft, activated_by)

        previous_version_id = self.active_version_id(draft["domain"])
        activated_at = utc_now()
        normalized_payload = self._normalize_payload(draft["domain"], draft["payload"])
        activation_errors = self._activation_cross_domain_errors(draft["domain"], normalized_payload)
        if activation_errors:
            raise ConfigRegistryError(
                "Итоговая конфигурация после активации невалидна: "
                + "; ".join(activation_errors)
            )
        version = {
            "schema_version": "1.0",
            "version_id": new_version_id(),
            "domain": draft["domain"],
            "payload": normalized_payload,
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
            connection.execute(
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
            self._delete_working_drafts_for_domain_operator(
                connection,
                domain=draft["domain"],
                operator_id=activated_by,
                preserve_draft_ids={draft["draft_id"]},
            )
        return version

    def _activate_scoped_attribute_resolution_profile_draft(
        self,
        draft: dict[str, Any],
        activated_by: str,
    ) -> dict[str, Any]:
        validation = self._validate_scoped_attribute_resolution_profile_draft(draft)
        if validation.get("status") != "valid":
            raise ConfigRegistryError(
                "Итоговая конфигурация после активации профиля невалидна: "
                + "; ".join(validation.get("errors") or [])
            )
        domain = "attribute_resolution_profiles"
        profile_id = self._scoped_profile_id(draft)
        action = self._draft_scope_action(draft.get("scope"))
        previous_version_id = self.active_version_id(domain)
        activated_at = utc_now()
        next_payload = copy.deepcopy(self.active_payload(domain))
        profiles = list(next_payload.get("profiles", []))
        index = next((idx for idx, profile in enumerate(profiles) if profile.get("profile_id") == profile_id), -1)
        if action == "delete":
            if index >= 0:
                profiles.pop(index)
        else:
            scoped_profile = self._profile_from_payload(draft.get("payload") or {}, profile_id)
            if not scoped_profile:
                raise ConfigRegistryError(f"Scoped draft не содержит профиль {profile_id}.")
            if index >= 0:
                profiles[index] = copy.deepcopy(scoped_profile)
            else:
                profiles.append(copy.deepcopy(scoped_profile))
        next_payload["profiles"] = profiles
        normalized_payload = self._normalize_payload(domain, next_payload)
        version = {
            "schema_version": "1.0",
            "version_id": new_version_id(),
            "domain": domain,
            "payload": normalized_payload,
            "source_draft_id": draft["draft_id"],
            "activated_by": activated_by,
            "activated_at": activated_at,
            "validation": draft["validation"],
            "regression": draft["regression"],
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
            connection.execute(
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
            self._delete_drafts_for_same_scope_operator(
                connection,
                domain=domain,
                operator_id=activated_by,
                scope=draft.get("scope"),
                preserve_draft_ids={draft["draft_id"]},
            )
        return version

    def _activation_cross_domain_errors(self, domain: str, payload: dict[str, Any]) -> list[str]:
        if domain == "slot_schemas":
            overrides = {
                "slot_schemas": payload,
                "attribute_resolution_profiles": self.active_payload("attribute_resolution_profiles"),
            }
            validation = self.validate_payload("slot_schemas", payload, active_overrides=overrides)
            return [f"slot_schemas: {error}" for error in validation.get("errors") or []]
        if domain == "attribute_resolution_profiles":
            slot_payload = self.active_payload("slot_schemas")
            overrides = {
                "slot_schemas": slot_payload,
                "attribute_resolution_profiles": payload,
            }
            profile_validation = self.validate_payload(
                "attribute_resolution_profiles",
                payload,
                active_overrides=overrides,
            )
            slot_validation = self.validate_payload(
                "slot_schemas",
                slot_payload,
                active_overrides=overrides,
            )
            return [
                *[f"attribute_resolution_profiles: {error}" for error in profile_validation.get("errors") or []],
                *[f"slot_schemas: {error}" for error in slot_validation.get("errors") or []],
            ]
        return []

    def cleanup_legacy_slot_resolution(
        self,
        *,
        slot_schema_id: str,
        slot_ids: list[str] | None = None,
        profile_ids: list[str] | None = None,
        operator_id: str,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        plan = self._build_legacy_slot_resolution_cleanup_plan(
            slot_schema_id=slot_schema_id,
            slot_ids=slot_ids,
            profile_ids=profile_ids,
        )
        if dry_run:
            return plan
        if plan["status"] == "blocked":
            raise ConfigRegistryError("Очистка legacy-связок заблокирована: " + "; ".join(plan["blocked_reasons"]))

        versions: list[dict[str, Any]] = []
        activated_at = utc_now()
        source_draft_id = f"legacy-cleanup-{uuid.uuid4().hex[:12]}"
        regression = {
            "schema_version": "1.0",
            "status": "skipped",
            "summary": "Специализированная очистка legacy-связок слотов и профилей.",
        }
        for domain in ("slot_schemas", "attribute_resolution_profiles"):
            validation = plan["validations"][domain]
            if validation.get("status") != "valid":
                raise ConfigRegistryError(
                    f"Итоговая конфигурация {domain} невалидна: "
                    + "; ".join(validation.get("errors") or [])
                )
            previous_version_id = self.active_version_id(domain)
            version = {
                "schema_version": "1.0",
                "version_id": new_version_id(),
                "domain": domain,
                "payload": copy.deepcopy(plan["payloads"][domain]),
                "source_draft_id": source_draft_id,
                "activated_by": operator_id,
                "activated_at": activated_at,
                "validation": validation,
                "regression": regression,
            }
            if previous_version_id:
                version["previous_version_id"] = previous_version_id
            self.contracts.require_valid("config_version", version)
            versions.append(version)

        with self._connect() as connection:
            for version in versions:
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

        result = copy.deepcopy(plan)
        result["schema_version"] = "1.0"
        result["status"] = "applied"
        result["dry_run"] = False
        result["versions"] = versions
        return result

    def repair_orphaned_resolution_profiles(
        self,
        *,
        slot_schema_id: str,
        operator_id: str,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        plan = self._build_orphaned_resolution_profile_repair_plan(slot_schema_id=slot_schema_id)
        if dry_run:
            return plan
        if plan["status"] == "blocked":
            raise ConfigRegistryError(
                "Исправление висячих ссылок заблокировано: " + "; ".join(plan["blocked_reasons"])
            )
        if plan["status"] == "ready" and not plan["summary"]["orphan_slots_repaired"] and not plan["summary"]["orphan_stage_links_cleared"]:
            result = copy.deepcopy(plan)
            result["status"] = "noop"
            result["dry_run"] = False
            result["versions"] = []
            return result

        activated_at = utc_now()
        source_draft_id = f"orphan-profile-repair-{uuid.uuid4().hex[:12]}"
        validation = plan["validations"]["slot_schemas"]
        previous_version_id = self.active_version_id("slot_schemas")
        version = {
            "schema_version": "1.0",
            "version_id": new_version_id(),
            "domain": "slot_schemas",
            "payload": copy.deepcopy(plan["payloads"]["slot_schemas"]),
            "source_draft_id": source_draft_id,
            "activated_by": operator_id,
            "activated_at": activated_at,
            "validation": validation,
            "regression": {
                "schema_version": "1.0",
                "status": "skipped",
                "summary": "Исправление висячих ссылок на отсутствующие профили разрешения.",
            },
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
                ("slot_schemas", version["version_id"], activated_at),
            )
        result = copy.deepcopy(plan)
        result["status"] = "applied"
        result["dry_run"] = False
        result["versions"] = [version]
        return result

    def _build_orphaned_resolution_profile_repair_plan(self, *, slot_schema_id: str) -> dict[str, Any]:
        slot_payload = self.active_payload("slot_schemas")
        profile_payload = self.active_payload("attribute_resolution_profiles")
        scenarios_payload = self.active_payload("service_scenarios")
        profile_ids = {
            profile["profile_id"]
            for profile in profile_payload.get("profiles", [])
            if profile.get("profile_id")
        }
        next_slot_payload = copy.deepcopy(slot_payload)
        schemas = next_slot_payload.get("slot_schemas", [])
        schema = next((item for item in schemas if item.get("slot_schema_id") == slot_schema_id), None)
        blocked_reasons: list[str] = []
        if not schema:
            blocked_reasons.append(f"Схема слотов не найдена: {slot_schema_id}")

        orphan_slots: list[dict[str, str]] = []
        orphan_stage_links: list[dict[str, str]] = []
        affected_scenarios = [
            {
                "scenario_id": scenario["scenario_id"],
                "display_name": scenario.get("display_name", scenario["scenario_id"]),
            }
            for scenario in scenarios_payload.get("scenarios", [])
            if scenario.get("slot_schema_id") == slot_schema_id
        ]

        if schema:
            for stage in list(slot_schema_stages(schema)):
                stage_id = stage.get("stage_id", "")
                stage_profile_id = stage.get("resolution_profile_id")
                if stage_profile_id and stage_profile_id not in profile_ids:
                    orphan_stage_links.append({
                        "slot_schema_id": slot_schema_id,
                        "stage_id": stage_id,
                        "missing_profile_id": stage_profile_id,
                    })
                    stage.pop("resolution_profile_id", None)
                for slot in stage.get("slots") or []:
                    profile_id = slot.get("resolution_profile_id")
                    if slot_fill_method(slot) == "resolution_profile" and profile_id and profile_id not in profile_ids:
                        orphan_slots.append({
                            "slot_schema_id": slot_schema_id,
                            "stage_id": stage_id,
                            "slot_id": slot.get("slot_id", ""),
                            "display_name": slot.get("display_name", slot.get("slot_id", "")),
                            "missing_profile_id": profile_id,
                            "new_fill_method": "operator_manual",
                        })
                        convert_slot_to_operator_manual(slot)
                if not (stage.get("slots") or []) and not stage.get("resolution_profile_id"):
                    schema["stages"].remove(stage)
            if not slot_schema_stages(schema):
                blocked_reasons.append(f"Схема {slot_schema_id} останется без этапов.")

        validations: dict[str, dict[str, Any]]
        normalized_slot_payload = copy.deepcopy(next_slot_payload)
        if schema and not blocked_reasons:
            try:
                normalize_slot_schema_stages(schema)
                normalized_slot_payload = self._normalize_payload("slot_schemas", next_slot_payload)
            except ConfigRegistryError as error:
                blocked_reasons.append(str(error))
        active_overrides = {
            "slot_schemas": normalized_slot_payload,
            "attribute_resolution_profiles": profile_payload,
        }
        validations = {
            "slot_schemas": self.validate_payload(
                "slot_schemas",
                normalized_slot_payload,
                active_overrides=active_overrides,
            ),
            "attribute_resolution_profiles": self.validate_payload(
                "attribute_resolution_profiles",
                profile_payload,
                active_overrides=active_overrides,
            ),
        }
        for domain, validation in validations.items():
            if validation.get("status") != "valid":
                blocked_reasons.extend(f"{domain}: {error}" for error in validation.get("errors") or [])

        summary = {
            "slot_schema_id": slot_schema_id,
            "orphan_slots_repaired": orphan_slots,
            "orphan_stage_links_cleared": orphan_stage_links,
            "affected_scenarios": affected_scenarios,
        }
        return {
            "schema_version": "1.0",
            "status": "blocked" if blocked_reasons else "ready",
            "dry_run": True,
            "summary": summary,
            "blocked_reasons": list(dict.fromkeys(blocked_reasons)),
            "validations": validations,
            "payloads": {
                "slot_schemas": normalized_slot_payload,
                "attribute_resolution_profiles": profile_payload,
            },
        }

    def _build_legacy_slot_resolution_cleanup_plan(
        self,
        *,
        slot_schema_id: str,
        slot_ids: list[str] | None,
        profile_ids: list[str] | None,
    ) -> dict[str, Any]:
        slot_payload = self.active_payload("slot_schemas")
        profile_payload = self.active_payload("attribute_resolution_profiles")
        scenarios_payload = self.active_payload("service_scenarios")
        schemas = slot_payload.get("slot_schemas", [])
        profiles = profile_payload.get("profiles", [])
        schema = next((item for item in schemas if item.get("slot_schema_id") == slot_schema_id), None)
        blocked_reasons: list[str] = []
        requested_slot_ids = {str(slot_id).strip() for slot_id in slot_ids or [] if str(slot_id).strip()}
        requested_profile_ids = {str(profile_id).strip() for profile_id in profile_ids or [] if str(profile_id).strip()}
        profile_by_id = {profile["profile_id"]: profile for profile in profiles}
        schema_found = schema is not None
        if not schema_found:
            blocked_reasons.append(f"Схема слотов не найдена: {slot_schema_id}")
            schema = {"slot_schema_id": slot_schema_id, "display_name": slot_schema_id, "stages": [], "slots": []}

        schema_slot_ids = {slot["slot_id"] for slot in schema.get("slots", [])}
        for slot_id in sorted(requested_slot_ids - schema_slot_ids):
            blocked_reasons.append(f"Слот отсутствует в схеме {slot_schema_id}: {slot_id}")
        for profile_id in sorted(requested_profile_ids):
            profile = profile_by_id.get(profile_id)
            if not profile:
                blocked_reasons.append(f"Профиль не найден: {profile_id}")
                continue
            profile_schema_id = profile.get("slot_schema_id")
            if profile_schema_id and profile_schema_id != slot_schema_id:
                blocked_reasons.append(
                    f"Профиль {profile_id} относится к другой схеме слотов: {profile_schema_id}"
                )
                continue
            requested_slot_ids.update(
                output.get("slot_id")
                for output in profile.get("output_slots_order", [])
                if output.get("slot_id") in schema_slot_ids
            )

        for stage in slot_schema_stages(schema):
            for slot in stage.get("slots") or []:
                if slot.get("resolution_profile_id") in requested_profile_ids:
                    requested_slot_ids.add(slot["slot_id"])

        if not requested_slot_ids and not requested_profile_ids:
            blocked_reasons.append("Выберите хотя бы один слот или профиль для очистки.")

        affected_profile_ids = set(requested_profile_ids)
        for profile in profiles:
            if profile.get("slot_schema_id") != slot_schema_id:
                continue
            output_ids = {output.get("slot_id") for output in profile.get("output_slots_order", []) if output.get("slot_id")}
            if output_ids & requested_slot_ids or profile.get("target_slot_id") in requested_slot_ids:
                affected_profile_ids.add(profile["profile_id"])

        for other_schema in schemas:
            if other_schema.get("slot_schema_id") == slot_schema_id:
                continue
            for profile_id in slot_schema_resolution_profile_ids(other_schema):
                if profile_id in affected_profile_ids:
                    blocked_reasons.append(
                        f"Профиль {profile_id} также используется в схеме {other_schema.get('slot_schema_id')}."
                    )

        if not schema_found:
            return {
                "schema_version": "1.0",
                "status": "blocked",
                "dry_run": True,
                "summary": {
                    "slot_schema_id": slot_schema_id,
                    "slots_to_remove": [],
                    "profiles_to_delete": [],
                    "profiles_to_update": [],
                    "stage_profile_links_to_clear": [],
                    "affected_scenarios": [],
                },
                "blocked_reasons": list(dict.fromkeys(blocked_reasons)),
                "validations": {},
                "payloads": {
                    "slot_schemas": slot_payload,
                    "attribute_resolution_profiles": profile_payload,
                },
            }

        next_slot_payload = copy.deepcopy(slot_payload)
        next_profile_payload = copy.deepcopy(profile_payload)
        next_schema = next(
            item for item in next_slot_payload.get("slot_schemas", [])
            if item.get("slot_schema_id") == slot_schema_id
        )
        next_profiles = next_profile_payload.get("profiles", [])
        profiles_to_delete: set[str] = set()
        profiles_to_update: set[str] = set()
        cleared_stage_links: list[dict[str, str]] = []
        removed_slots: list[dict[str, str]] = []

        for stage in slot_schema_stages(next_schema):
            kept_slots = []
            for slot in stage.get("slots") or []:
                if slot.get("slot_id") in requested_slot_ids:
                    removed_slots.append({
                        "slot_id": slot["slot_id"],
                        "display_name": slot.get("display_name", slot["slot_id"]),
                        "stage_id": stage.get("stage_id", ""),
                    })
                    continue
                kept_slots.append(slot)
            stage["slots"] = kept_slots

        for profile in list(next_profiles):
            profile_id = profile["profile_id"]
            if profile_id not in affected_profile_ids:
                continue
            original_outputs = profile.get("output_slots_order", [])
            remaining_outputs = [
                copy.deepcopy(output)
                for output in original_outputs
                if output.get("slot_id") not in requested_slot_ids
            ]
            should_delete = profile_id in requested_profile_ids or not remaining_outputs
            if should_delete:
                profiles_to_delete.add(profile_id)
                continue
            if profile.get("target_slot_id") not in {output.get("slot_id") for output in remaining_outputs}:
                required_output = next((output for output in remaining_outputs if output.get("required_for_success")), None)
                if required_output is None:
                    required_output = remaining_outputs[0]
                    required_output["required_for_success"] = True
                profile["target_slot_id"] = required_output["slot_id"]
            if not any(output.get("required_for_success") for output in remaining_outputs):
                remaining_outputs[0]["required_for_success"] = True
            for index, output in enumerate(remaining_outputs, start=1):
                output["order"] = index
            profile["output_slots_order"] = remaining_outputs
            profiles_to_update.add(profile_id)

        if profiles_to_delete:
            next_profile_payload["profiles"] = [
                profile for profile in next_profiles if profile["profile_id"] not in profiles_to_delete
            ]

        for stage in list(slot_schema_stages(next_schema)):
            profile_id = stage.get("resolution_profile_id")
            if profile_id in profiles_to_delete:
                cleared_stage_links.append({
                    "stage_id": stage.get("stage_id", ""),
                    "profile_id": profile_id,
                })
                stage.pop("resolution_profile_id", None)
            if not stage.get("slots") and not stage.get("resolution_profile_id"):
                next_schema["stages"].remove(stage)

        for stage in slot_schema_stages(next_schema):
            for slot in stage.get("slots") or []:
                profile_id = slot.get("resolution_profile_id")
                if profile_id in profiles_to_delete:
                    blocked_reasons.append(
                        f"Слот {slot['slot_id']} останется со ссылкой на удаляемый профиль {profile_id}."
                    )

        if not slot_schema_stages(next_schema):
            blocked_reasons.append(f"Схема {slot_schema_id} останется без этапов.")

        normalization_errors: list[str] = []
        try:
            normalize_slot_schema_stages(next_schema)
        except ConfigRegistryError as error:
            normalization_errors.append(str(error))
            blocked_reasons.append(str(error))

        if normalization_errors:
            validations = {
                "slot_schemas": {
                    "schema_version": "1.0",
                    "domain": "slot_schemas",
                    "contract_name": CONFIG_DOMAINS["slot_schemas"].contract_name,
                    "status": "invalid",
                    "validated_at": utc_now(),
                    "errors": normalization_errors,
                    "gates": [
                        {
                            "gate_id": "cleanup_normalization",
                            "status": "failed",
                            "message": "Нормализация схемы слотов после очистки не выполнена.",
                        }
                    ],
                },
                "attribute_resolution_profiles": {
                    "schema_version": "1.0",
                    "domain": "attribute_resolution_profiles",
                    "contract_name": CONFIG_DOMAINS["attribute_resolution_profiles"].contract_name,
                    "status": "skipped",
                    "validated_at": utc_now(),
                    "errors": [],
                    "gates": [
                        {
                            "gate_id": "cleanup_normalization",
                            "status": "skipped",
                            "message": "Валидация профилей пропущена из-за невалидной схемы слотов.",
                        }
                    ],
                },
            }
            affected_scenarios = [
                {
                    "scenario_id": scenario["scenario_id"],
                    "display_name": scenario.get("display_name", scenario["scenario_id"]),
                }
                for scenario in scenarios_payload.get("scenarios", [])
                if scenario.get("slot_schema_id") == slot_schema_id
            ]
            return {
                "schema_version": "1.0",
                "status": "blocked",
                "dry_run": True,
                "summary": {
                    "slot_schema_id": slot_schema_id,
                    "slots_to_remove": removed_slots,
                    "profiles_to_delete": [
                        {
                            "profile_id": profile_id,
                            "display_name": profile_by_id.get(profile_id, {}).get("display_name", profile_id),
                        }
                        for profile_id in sorted(profiles_to_delete)
                    ],
                    "profiles_to_update": [
                        {
                            "profile_id": profile_id,
                            "display_name": profile_by_id.get(profile_id, {}).get("display_name", profile_id),
                        }
                        for profile_id in sorted(profiles_to_update - profiles_to_delete)
                    ],
                    "stage_profile_links_to_clear": cleared_stage_links,
                    "affected_scenarios": affected_scenarios,
                },
                "blocked_reasons": list(dict.fromkeys(blocked_reasons)),
                "validations": validations,
                "payloads": {
                    "slot_schemas": next_slot_payload,
                    "attribute_resolution_profiles": next_profile_payload,
                },
            }

        normalized_slot_payload = self._normalize_payload("slot_schemas", next_slot_payload)
        overrides_for_profile_normalization = {"slot_schemas": normalized_slot_payload}
        token = _ACTIVE_PAYLOAD_OVERRIDES.set(overrides_for_profile_normalization)
        try:
            normalized_profile_payload = self._normalize_payload("attribute_resolution_profiles", next_profile_payload)
        finally:
            _ACTIVE_PAYLOAD_OVERRIDES.reset(token)

        active_overrides = {
            "slot_schemas": normalized_slot_payload,
            "attribute_resolution_profiles": normalized_profile_payload,
        }
        validations = {
            "slot_schemas": self.validate_payload(
                "slot_schemas",
                normalized_slot_payload,
                active_overrides=active_overrides,
            ),
            "attribute_resolution_profiles": self.validate_payload(
                "attribute_resolution_profiles",
                normalized_profile_payload,
                active_overrides=active_overrides,
            ),
        }
        for domain, validation in validations.items():
            if validation.get("status") != "valid":
                blocked_reasons.extend(f"{domain}: {error}" for error in validation.get("errors") or [])

        affected_scenarios = [
            {
                "scenario_id": scenario["scenario_id"],
                "display_name": scenario.get("display_name", scenario["scenario_id"]),
            }
            for scenario in scenarios_payload.get("scenarios", [])
            if scenario.get("slot_schema_id") == slot_schema_id
        ]
        summary = {
            "slot_schema_id": slot_schema_id,
            "slots_to_remove": removed_slots,
            "profiles_to_delete": [
                {
                    "profile_id": profile_id,
                    "display_name": profile_by_id.get(profile_id, {}).get("display_name", profile_id),
                }
                for profile_id in sorted(profiles_to_delete)
            ],
            "profiles_to_update": [
                {
                    "profile_id": profile_id,
                    "display_name": profile_by_id.get(profile_id, {}).get("display_name", profile_id),
                }
                for profile_id in sorted(profiles_to_update - profiles_to_delete)
            ],
            "stage_profile_links_to_clear": cleared_stage_links,
            "affected_scenarios": affected_scenarios,
        }
        status = "blocked" if blocked_reasons else "ready"
        return {
            "schema_version": "1.0",
            "status": status,
            "dry_run": True,
            "summary": summary,
            "blocked_reasons": list(dict.fromkeys(blocked_reasons)),
            "validations": validations,
            "payloads": {
                "slot_schemas": normalized_slot_payload,
                "attribute_resolution_profiles": normalized_profile_payload,
            },
        }

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

    def validate_payload(
        self,
        domain: str,
        payload: dict[str, Any],
        *,
        active_overrides: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        self._require_domain(domain)
        errors: list[str] = []
        contract_name = CONFIG_DOMAINS[domain].contract_name
        overrides = self._validation_overrides(active_overrides)
        token = None
        if overrides is not None:
            token = _ACTIVE_PAYLOAD_OVERRIDES.set(overrides)
        try:
            errors.extend(self._pre_validate_payload(domain, payload))
            normalized_payload = self._normalize_payload(domain, payload)
            errors.extend(self.contracts.validate(contract_name, normalized_payload))
            if not errors:
                errors.extend(self._cross_validate(domain, normalized_payload))
        finally:
            if token is not None:
                _ACTIVE_PAYLOAD_OVERRIDES.reset(token)
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

    @staticmethod
    def _pre_validate_payload(domain: str, payload: dict[str, Any]) -> list[str]:
        if not isinstance(payload, dict):
            return []
        errors: list[str] = []
        if domain == "capabilities":
            for index, capability in enumerate(payload.get("capabilities") or [], start=1):
                if not isinstance(capability, dict):
                    continue
                capability_id = str(capability.get("capability_id") or f"capabilities[{index}]")
                async_contracts = capability.get("async_event_contracts") or {}
                if isinstance(async_contracts, dict):
                    for event_type in async_contracts:
                        if not EXTERNAL_EVENT_TYPE_RE.match(str(event_type)):
                            errors.append(
                                f"{capability_id} async_event_contracts.{event_type} несовместим с ExternalEvent.event_type."
                            )
                policy = capability.get("default_completion_policy") or {}
                expected_event_type = policy.get("expected_event_type") if isinstance(policy, dict) else None
                if expected_event_type and not EXTERNAL_EVENT_TYPE_RE.match(str(expected_event_type)):
                    errors.append(
                        f"{capability_id} default_completion_policy.expected_event_type={expected_event_type} "
                        "несовместим с ExternalEvent.event_type."
                    )
            return errors
        if domain != "interaction_channels":
            return errors
        channels = payload.get("channels")
        if not isinstance(channels, list):
            return errors
        for index, channel in enumerate(channels, start=1):
            if not isinstance(channel, dict):
                continue
            channel_id = channel.get("channel_id") or f"channels[{index}]"
            parameter_ids = [
                str(parameter.get("parameter_id"))
                for parameter in channel.get("channel_parameters", [])
                if isinstance(parameter, dict) and parameter.get("parameter_id")
            ]
            seen: set[str] = set()
            duplicates: set[str] = set()
            for parameter_id in parameter_ids:
                if parameter_id in seen:
                    duplicates.add(parameter_id)
                seen.add(parameter_id)
            for parameter_id in sorted(duplicates):
                errors.append(f"{channel_id} содержит дублирующийся параметр канала: {parameter_id}")
        return errors

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

    def delete_invalid_drafts(
        self,
        *,
        domain: str,
        operator_id: str,
    ) -> dict[str, Any]:
        self._require_domain(domain)
        if not operator_id:
            raise ConfigRegistryError("operator_id обязателен для очистки invalid drafts.")
        with self._connect() as connection:
            rows = connection.execute(
                """
                select draft_id, draft_json
                from config_drafts
                where domain = ?
                  and created_by = ?
                  and status = 'invalid'
                order by updated_at desc, draft_id desc
                """,
                (domain, operator_id),
            ).fetchall()
            draft_ids = [str(row["draft_id"]) for row in rows]
            if draft_ids:
                connection.executemany(
                    "delete from config_drafts where draft_id = ?",
                    [(draft_id,) for draft_id in draft_ids],
                )
        return {
            "schema_version": "1.0",
            "domain": domain,
            "operator_id": operator_id,
            "deleted_count": len(draft_ids),
            "deleted_draft_ids": draft_ids,
        }

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
        if domain == "workflow_states":
            return self._validate_workflow_state_catalog(payload)
        if domain == "workflow_transitions":
            return self._validate_workflow_transition_rules(payload)
        if domain == "prompts":
            return self._validate_prompt_catalog(payload)
        if domain == "interaction_channels":
            return self._validate_interaction_channels(payload)
        if domain == "attribute_resolution_profiles":
            return self._validate_attribute_resolution_profiles(payload)
        if domain == "capabilities":
            return self._validate_capability_catalog(payload)
        if domain == "mcp_environments":
            return self._validate_mcp_environment_catalog(payload)
        if domain == "capability_bindings":
            return self._validate_capability_binding_catalog(payload)
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
        if domain == "prompt_packs":
            return self._validate_prompt_packs(payload)
        if domain == "escalation_policies":
            return self._validate_escalation_policies(payload)
        return []

    def _validate_json_schema_field(self, owner: str, schema_key: str, schema: Any) -> list[str]:
        if not isinstance(schema, dict):
            return [f"{owner} {schema_key} должна быть JSON Schema object."]
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as error:
            return [f"{owner} {schema_key} невалидна: {error.message}"]
        return []

    def _validate_capability_catalog(self, payload: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        capability_ids = [capability["capability_id"] for capability in payload.get("capabilities", [])]
        errors.extend(
            f"Дублируется capability_id: {capability_id}"
            for capability_id in self._duplicates(capability_ids)
        )
        for capability in payload.get("capabilities", []):
            capability_id = capability["capability_id"]
            for schema_key in ("input_schema", "output_schema", "diagnostic_schema"):
                errors.extend(self._validate_json_schema_field(capability_id, schema_key, capability.get(schema_key)))
            async_contracts = capability.get("async_event_contracts") or {}
            if "async" in set(capability.get("execution_modes") or []) and not async_contracts:
                errors.append(f"{capability_id} поддерживает async, но не содержит async_event_contracts.")
            for event_type in async_contracts:
                if not EXTERNAL_EVENT_TYPE_RE.match(str(event_type)):
                    errors.append(
                        f"{capability_id} async_event_contracts.{event_type} несовместим с ExternalEvent.event_type."
                    )
            policy = capability.get("default_completion_policy") or {}
            if policy.get("mode") == "external_event":
                expected_event_type = policy.get("expected_event_type")
                if not expected_event_type:
                    errors.append(f"{capability_id} default_completion_policy.external_event требует expected_event_type.")
                elif not EXTERNAL_EVENT_TYPE_RE.match(str(expected_event_type)):
                    errors.append(
                        f"{capability_id} default_completion_policy.expected_event_type={expected_event_type} "
                        "несовместим с ExternalEvent.event_type."
                    )
                elif expected_event_type not in async_contracts:
                    errors.append(
                        f"{capability_id} default_completion_policy.expected_event_type={expected_event_type} "
                        "не найден в async_event_contracts."
                    )
            for event_type, async_contract in async_contracts.items():
                if "success" not in set(async_contract.get("statuses") or []):
                    errors.append(f"{capability_id}/{event_type} должен разрешать status=success.")
                for schema_key in ("result_schema", "progress_schema", "error_schema"):
                    schema = async_contract.get(schema_key)
                    if schema:
                        errors.extend(
                            self._validate_json_schema_field(
                                f"{capability_id}/{event_type}",
                                schema_key,
                                schema,
                            )
                        )
        return errors

    def _validate_mcp_environment_catalog(self, payload: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        capability_ids = {
            capability["capability_id"]
            for capability in self.active_payload("capabilities").get("capabilities", [])
        }
        environment_ids = [environment["environment_id"] for environment in payload.get("environments", [])]
        errors.extend(
            f"Дублируется environment_id: {environment_id}"
            for environment_id in self._duplicates(environment_ids)
        )
        for environment in payload.get("environments", []):
            environment_id = environment["environment_id"]
            tier = environment.get("environment_tier")
            auth_mode = environment.get("auth_mode")
            if tier == "prod" and auth_mode not in {"oidc_client_credentials", "oidc_workload_identity"}:
                errors.append(f"{environment_id} prod MCP должен использовать OIDC auth_mode.")
            if tier in {"staging", "prod"} and auth_mode == "dev_bearer_token":
                errors.append(f"{environment_id} {tier} MCP не может использовать dev_bearer_token.")
            if auth_mode in {"oidc_client_credentials", "oidc_workload_identity"} and not environment.get("oidc_audience"):
                errors.append(f"{environment_id} OIDC MCP требует oidc_audience.")
            if environment.get("transport") == "stdio" and environment.get("status") == "active":
                errors.append(f"{environment_id} active external MCP не должен использовать stdio transport.")
            health_check = environment.get("health_check") or {}
            if health_check.get("mode") == "http_get" and not health_check.get("path"):
                errors.append(f"{environment_id} health_check.mode=http_get требует path.")
            for capability_id in environment.get("allowed_capabilities") or []:
                if capability_id not in capability_ids:
                    errors.append(f"{environment_id} ссылается на неизвестную capability: {capability_id}.")
        return errors

    def _validate_capability_binding_catalog(self, payload: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        capabilities = {
            capability["capability_id"]: capability
            for capability in self.active_payload("capabilities").get("capabilities", [])
        }
        environments = {
            environment["environment_id"]: environment
            for environment in self.active_payload("mcp_environments").get("environments", [])
        }
        binding_ids = [binding["binding_id"] for binding in payload.get("bindings", [])]
        errors.extend(
            f"Дублируется binding_id: {binding_id}"
            for binding_id in self._duplicates(binding_ids)
        )
        active_pairs: set[tuple[str, str]] = set()
        required_async_context = {
            "case_id",
            "run_id",
            "wait_id",
            "correlation_id",
            "capability_id",
            "contract_version",
            "expected_event_type",
            "idempotency_key_base",
        }
        for binding in payload.get("bindings", []):
            binding_id = binding["binding_id"]
            capability_id = binding["capability_id"]
            environment_id = binding["environment_id"]
            capability = capabilities.get(capability_id)
            environment = environments.get(environment_id)
            if not capability:
                errors.append(f"{binding_id} ссылается на неизвестную capability: {capability_id}.")
                continue
            if not environment:
                errors.append(f"{binding_id} ссылается на неизвестное MCP-окружение: {environment_id}.")
                continue
            if binding["execution_mode"] not in set(capability.get("execution_modes") or []):
                errors.append(
                    f"{binding_id} execution_mode={binding['execution_mode']} не разрешен capability {capability_id}."
                )
            allowed_capabilities = set(environment.get("allowed_capabilities") or [])
            if allowed_capabilities and capability_id not in allowed_capabilities:
                errors.append(f"{binding_id} capability {capability_id} не разрешена для {environment_id}.")
            if binding.get("status") == "active":
                if capability.get("status") != "active":
                    errors.append(f"{binding_id} active binding требует active capability {capability_id}.")
                if environment.get("status") != "active":
                    errors.append(f"{binding_id} active binding требует active MCP-окружение {environment_id}.")
                pair = (capability_id, binding["execution_mode"])
                if pair in active_pairs:
                    errors.append(
                        f"Для {capability_id}/{binding['execution_mode']} найдено больше одной active binding."
                    )
                active_pairs.add(pair)
            required_inputs = set(schema_required(capability.get("input_schema") or {}))
            missing_inputs = sorted(required_inputs - set((binding.get("input_mapping") or {}).keys()))
            if missing_inputs:
                errors.append(
                    f"{binding_id} input_mapping не покрывает required inputs capability {capability_id}: "
                    f"{', '.join(missing_inputs)}."
                )
            unknown_inputs = sorted(
                field
                for field in (binding.get("input_mapping") or {})
                if not schema_allows_mapping_path(capability.get("input_schema") or {}, field)
            )
            if unknown_inputs:
                errors.append(
                    f"{binding_id} input_mapping ссылается на неизвестные inputs capability {capability_id}: "
                    f"{', '.join(unknown_inputs)}."
                )
            required_outputs = set(schema_required(capability.get("output_schema") or {}))
            missing_outputs = sorted(required_outputs - set((binding.get("output_mapping") or {}).keys()))
            if missing_outputs:
                errors.append(
                    f"{binding_id} output_mapping не покрывает required outputs capability {capability_id}: "
                    f"{', '.join(missing_outputs)}."
                )
            unknown_outputs = sorted(
                field
                for field in (binding.get("output_mapping") or {})
                if not schema_allows_mapping_path(capability.get("output_schema") or {}, field)
            )
            if unknown_outputs:
                errors.append(
                    f"{binding_id} output_mapping ссылается на неизвестные outputs capability {capability_id}: "
                    f"{', '.join(unknown_outputs)}."
                )
            if binding["execution_mode"] == "async":
                missing_context = sorted(required_async_context - set((binding.get("async_context_mapping") or {}).keys()))
                if missing_context:
                    errors.append(
                        f"{binding_id} async_context_mapping не покрывает обязательные поля: "
                        f"{', '.join(missing_context)}."
                    )
                policy = capability.get("default_completion_policy") or {}
                expected_event_type = policy.get("expected_event_type")
                if expected_event_type and expected_event_type not in (capability.get("async_event_contracts") or {}):
                    errors.append(
                        f"{binding_id} expected_event_type={expected_event_type} отсутствует в capability contract."
                    )
        return errors

    def _validate_tool_catalog(self, payload: dict[str, Any]) -> list[str]:
        _ = payload
        return ["tool_catalog удален; используйте capabilities и capability_bindings."]

    def _validate_integration_endpoint_catalog(self, payload: dict[str, Any]) -> list[str]:
        _ = payload
        return ["integration_endpoints удалены; используйте mcp_environments."]

    def _validate_tool_catalog_usage(self, payload: dict[str, Any]) -> list[str]:
        _ = payload
        return ["tool_catalog удален; используйте capabilities и capability_bindings."]

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
        if active_provider_id and provider_ids and active_provider_id not in provider_ids:
            errors.append(f"active_provider неизвестен: {active_provider_id}")
        enabled_providers = [
            provider
            for provider in providers.values()
            if provider.get("enabled")
        ]
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
        if provider_aliases and default_alias not in provider_aliases:
            errors.append("default_model_alias должен совпадать с alias включенного backend.")
        active_provider = providers.get(active_provider_id or "")
        if enabled_providers and active_provider and not active_provider.get("enabled"):
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

    def _validate_removed_workflow_catalog(self, payload: dict[str, Any]) -> list[str]:
        _ = payload
        return ["legacy workflow catalogs удалены; внешнее исполнение настраивается через mcp_environments/capabilities/capability_bindings."]

    def _validate_interaction_channels(self, payload: dict[str, Any]) -> list[str]:
        errors = []
        channels = payload["channels"]
        channel_ids = [channel["channel_id"] for channel in channels]
        for channel_id in self._duplicates(channel_ids):
            errors.append(f"Дублируется channel_id: {channel_id}")
        debug_channels = [channel for channel in channels if channel["channel_id"] == "debug"]
        if channels and not debug_channels:
            errors.append("Системный канал debug должен присутствовать в каталоге.")
        elif len(debug_channels) == 1:
            errors.extend(self._validate_debug_channel_immutable(debug_channels[0]))

        for channel in channels:
            channel_id = channel["channel_id"]
            allowed_no_answer = self._channel_no_answer_actions_for_mode(channel["mode"], channel.get("capabilities"))
            waiting = channel["waiting_policy"]
            if waiting["on_no_answer"] not in allowed_no_answer:
                errors.append(
                    f"{channel_id}.waiting_policy.on_no_answer={waiting['on_no_answer']} "
                    f"не подходит для режима канала {channel['mode']}."
                )
            if waiting["discussion_timeout_seconds"] and (
                waiting["discussion_timeout_seconds"] <= waiting["first_reminder_after_seconds"]
            ):
                errors.append(f"{channel_id} timeout обсуждения должен быть больше первого напоминания.")
            parameter_ids = [parameter["parameter_id"] for parameter in channel.get("channel_parameters", [])]
            for parameter_id in self._duplicates(parameter_ids):
                errors.append(f"{channel_id} содержит дублирующийся параметр канала: {parameter_id}")

        scenario_payload = self.active_payload("service_scenarios")
        scenario_refs = self._collect_channel_scenario_refs(scenario_payload)
        missing_refs = sorted(scenario_refs - set(channel_ids))
        for channel_id in missing_refs:
            errors.append(f"Канал используется сценариями, но отсутствует в каталоге: {channel_id}")
        return errors

    @staticmethod
    def _validate_debug_channel_immutable(channel: dict[str, Any]) -> list[str]:
        canonical = next(
            item for item in default_interaction_channels()["channels"] if item["channel_id"] == "debug"
        )
        immutable_fields = (
            "channel_id",
            "display_name",
            "mode",
            "description",
            "capabilities",
            "technical_profile",
            "channel_parameters",
            "waiting_policy",
            "enabled",
        )
        errors = []
        for field in immutable_fields:
            if channel.get(field) != canonical.get(field):
                errors.append(f"debug.{field} является системным и не должен изменяться.")
        return errors

    @staticmethod
    def _channel_no_answer_actions_for_mode(mode: str, capabilities: dict[str, Any] | None = None) -> set[str]:
        if mode == "online_interactive":
            return {"create_draft", "call_specialist"}
        if mode == "offline_interactive":
            actions = {"save_context"}
            if (capabilities or {}).get("supports_work_order_creation", True):
                actions.add("create_work_order")
            return actions
        if mode == "debug":
            return {"debug_stop"}
        return {"debug_stop"}

    def _validate_attribute_resolution_profiles(self, payload: dict[str, Any]) -> list[str]:
        errors = []
        profiles = payload["profiles"]
        profile_ids = [profile["profile_id"] for profile in profiles]
        for profile_id in self._duplicates(profile_ids):
            errors.append(f"Дублируется profile_id: {profile_id}")

        tool_by_name: dict[str, dict[str, Any]] = {}
        endpoint_by_id: dict[str, dict[str, Any]] = {}
        interaction_channels = self.active_payload("interaction_channels")["channels"]
        slot_schema_by_id = self._by_id(
            self.active_payload("slot_schemas")["slot_schemas"],
            "slot_schema_id",
        )
        known_slot_ids = {
            slot["slot_id"]
            for schema in self.active_payload("slot_schemas")["slot_schemas"]
            for slot in schema.get("slots", [])
        }
        capability_by_id = self._by_id(
            self.active_payload("capabilities").get("capabilities", []),
            "capability_id",
        )

        for profile in profiles:
            profile_id = profile["profile_id"]
            slot_schema = slot_schema_by_id.get(profile.get("slot_schema_id", ""))
            profile_slot_ids = {
                slot["slot_id"]
                for slot in (slot_schema or {}).get("slots", [])
            }
            if not slot_schema:
                errors.append(f"{profile_id} ссылается на неизвестную slot_schema_id: {profile.get('slot_schema_id')}")
            output_slot_ids = [slot["slot_id"] for slot in profile.get("output_slots_order", [])]
            target_slot_id = profile.get("target_slot_id")
            declared_slot_ids = set(output_slot_ids)
            if target_slot_id:
                declared_slot_ids.add(target_slot_id)
            for slot_id in declared_slot_ids:
                if slot_id in known_slot_ids and slot_id not in profile_slot_ids:
                    errors.append(
                        f"{profile_id}: выходной слот {slot_id} отсутствует в выбранном сценарии профиля. "
                        "Добавьте слот в сценарий обработки и активируйте его перед активацией профиля."
                    )
            if target_slot_id and target_slot_id not in output_slot_ids:
                errors.append(f"{profile_id} target_slot_id должен входить в output_slots_order.")
            for slot_id in self._duplicates(output_slot_ids):
                errors.append(f"{profile_id} содержит дублирующийся выходной слот: {slot_id}")
            orders = [slot["order"] for slot in profile.get("output_slots_order", [])]
            for order in self._duplicates(orders):
                errors.append(f"{profile_id} содержит дублирующийся порядок выходного слота: {order}")
            confidence_thresholds = profile.get("confidence_thresholds", {})
            base_threshold = profile.get("confidence_threshold")
            auto_fill_threshold = confidence_thresholds.get("auto_fill", base_threshold if base_threshold is not None else 0.0)
            clarification_threshold = confidence_thresholds.get("clarification", base_threshold if base_threshold is not None else 0.0)
            operator_threshold = confidence_thresholds.get("operator_handoff", 0)
            if auto_fill_threshold < clarification_threshold:
                errors.append(f"{profile_id} auto_fill threshold не должен быть ниже clarification threshold.")
            if clarification_threshold < operator_threshold:
                errors.append(f"{profile_id} clarification threshold не должен быть ниже operator_handoff threshold.")
            errors.extend(
                validate_confidence_overrides(
                    DEFAULT_CONFIDENCE_THRESHOLDS,
                    profile_confidence_thresholds(profile),
                    f"{profile_id}.confidence_thresholds",
                )
            )

            human_policy = profile["human_resolution_policy"]
            if human_policy.get("action") not in {"ask_client", "escalate_operator"}:
                errors.append(f"{profile_id} human_resolution_policy.action должен быть ask_client или escalate_operator.")
            if not human_policy.get("message_template"):
                errors.append(f"{profile_id} human_resolution_policy должен содержать message_template.")

            reference_context = build_execution_reference_context(
                slot_schema=slot_schema or {"slots": []},
                output_slots=output_slot_ids,
                capabilities=list(capability_by_id.values()),
                steps=profile.get("enrichment_steps", []),
                channels=interaction_channels,
            )
            seen_steps: dict[str, dict[str, Any]] = {}
            last_step_tool: dict[str, Any] | None = None
            for index, enrichment_step in enumerate(profile.get("enrichment_steps", []), start=1):
                step_label = f"{profile_id}.enrichment_steps[{index}]"
                step_id = enrichment_step.get("step_id") or f"step{index}"
                if step_id in seen_steps:
                    errors.append(f"{profile_id} содержит дублирующийся step_id: {step_id}")
                if enrichment_step.get("configuration_instruction"):
                    step_reference_context = build_execution_reference_context(
                        slot_schema=slot_schema or {"slots": []},
                        output_slots=output_slot_ids,
                        capabilities=list(capability_by_id.values()),
                        steps=profile.get("enrichment_steps", []),
                        allowed_steps=list(seen_steps.values()),
                        channels=interaction_channels,
                    )
                    errors.extend(
                        validate_template_refs(
                            enrichment_step.get("configuration_instruction"),
                            step_reference_context,
                            label=f"{step_label}.configuration_instruction",
                        )
                    )
                capability_id = enrichment_step.get("capability_id")
                if capability_id:
                    capability = capability_by_id.get(capability_id)
                    if not capability:
                        errors.append(f"{step_label} ссылается на неизвестную capability: {capability_id}.")
                    else:
                        completion_policy = enrichment_step.get("completion_policy") or {}
                        if completion_policy.get("mode") == "external_event":
                            expected_event_type = completion_policy.get("expected_event_type")
                            async_contracts = capability.get("async_event_contracts") or {}
                            if "async" not in set(capability.get("execution_modes") or []):
                                errors.append(f"{step_label} использует external_event для sync-only capability {capability_id}.")
                            elif not expected_event_type:
                                errors.append(f"{step_label}.completion_policy должен содержать expected_event_type.")
                            elif expected_event_type not in async_contracts:
                                available_events = ", ".join(sorted(async_contracts)) or "нет"
                                errors.append(
                                    f"{step_label}.completion_policy ссылается на отсутствующий "
                                    f"async_event_contracts.{expected_event_type} в capability {capability_id}. "
                                    f"Доступные события: {available_events}."
                                )
                            elif async_contracts[expected_event_type].get("contract_status") == "broken":
                                errors.append(
                                    f"{step_label}.completion_policy использует broken async_event_contracts."
                                    f"{expected_event_type}."
                                )
                        elif completion_policy.get("mode") == "sync" and "sync" not in set(capability.get("execution_modes") or []):
                            errors.append(f"{step_label} использует sync для capability {capability_id}, которая не поддерживает sync.")

                        input_mapping = enrichment_step.get("input_mapping", {})
                        configured_parameters = {}
                        if isinstance(input_mapping, dict):
                            for parameter, source_ref in input_mapping.items():
                                source, separator, source_value = str(source_ref).partition(":")
                                if separator == ":" and source_value:
                                    configured_parameters[parameter] = (
                                        source_value if source == "constant" else f"configured:{source}"
                                    )
                        effective_parameters, _applied_defaults = apply_schema_parameter_defaults(
                            capability.get("input_schema", {}),
                            configured_parameters,
                        )
                        for required_group in missing_required_parameter_groups(
                            capability.get("input_schema", {}),
                            effective_parameters,
                        ):
                            errors.append(
                                f'{profile_id}.enrichment_steps[{index}] '
                                f'Профиль "{profile.get("display_name")}" ({profile_id}) -> '
                                f'Шаг {index} "{enrichment_step.get("step_name") or step_id}" ({step_id}) -> '
                                f'capability "{capability.get("display_name") or capability_id}" '
                                f'({capability_id}) не заполняет обязательный параметр: '
                                f'{format_required_parameter_group(required_group)}.'
                            )
                        input_names = set(schema_properties(capability.get("input_schema", {})))
                        input_names.update(schema_required(capability.get("input_schema", {})))
                        for parameter, source_ref in input_mapping.items():
                            if input_names and parameter not in input_names:
                                errors.append(
                                    f"{step_label}.input_mapping.{parameter} заполняет параметр вне "
                                    f"input_schema capability {capability_id}."
                                )
                            source, separator, value = str(source_ref).partition(":")
                            if separator != ":" or source not in {"slot", "output", "step", "case", "constant", "secret"} or not value:
                                errors.append(
                                    f"{step_label}.input_mapping.{parameter} должен иметь формат "
                                    "slot:<slot_id>, output:<slot_id>, case:<field>, step:<ref>, constant:<value> или secret:<ref>."
                                )
                            elif source == "slot" and value not in profile_slot_ids:
                                errors.append(
                                    f"{step_label}.input_mapping.{parameter}: входной слот {value} "
                                    "отсутствует в выбранном сценарии профиля."
                                )
                        output_schema = capability.get("output_schema", {})
                        for slot_id, field_path in (enrichment_step.get("output_mapping") or {}).items():
                            if slot_id not in output_slot_ids:
                                if slot_id not in profile_slot_ids:
                                    errors.append(
                                        f"{step_label}.output_mapping.{slot_id}: слот не найден в выбранном "
                                        "сценарии профиля. Добавьте слот в сценарий и в блок "
                                        "\"Выходные слоты и порядок заполнения\" либо удалите mapping из шага."
                                    )
                                else:
                                    errors.append(
                                        f"{step_label}.output_mapping.{slot_id}: слот не выбран как выходной "
                                        "слот профиля. Добавьте его в блок \"Выходные слоты и порядок заполнения\" "
                                        "либо удалите mapping из шага."
                                    )
                            elif slot_id not in profile_slot_ids:
                                errors.append(
                                    f"{step_label}.output_mapping.{slot_id}: выходной слот отсутствует "
                                    "в выбранном сценарии профиля. Добавьте слот в сценарий обработки "
                                    "и активируйте его перед активацией профиля."
                                )
                            if not schema_declares_path(output_schema, str(field_path), allow_nested_additional=True):
                                errors.append(
                                    f"{step_label}.output_mapping.{slot_id} ссылается на неизвестное "
                                    f"поле результата capability {capability_id}: {field_path}."
                                )
                    seen_steps[step_id] = enrichment_step
                    continue

                errors.append(
                    f"{step_label} должен использовать capability_id/input_mapping/output_mapping; "
                    "старый operation binding удален."
                )
                seen_steps[step_id] = enrichment_step
                continue

            if output_slot_ids and profile.get("enrichment_steps"):
                for rule in profile.get("output_slots_order", []):
                    source_ref = output_source_hint_reference(rule.get("source_hint"), profile.get("enrichment_steps", []))
                    if source_ref.get("error"):
                        errors.append(f"{profile_id} output_slots_order.{rule['slot_id']}: {source_ref['error']}")
                        continue
                    if source_ref.get("capability_id"):
                        capability = capability_by_id.get(source_ref.get("capability_id") or "")
                        field = source_ref.get("field")
                        if not capability:
                            errors.append(
                                f"{profile_id} output_slots_order.{rule['slot_id']} "
                                f"ссылается на неизвестную capability: {source_ref.get('capability_id')}."
                            )
                        elif not schema_declares_path(
                            capability.get("output_schema", {}),
                            field,
                            allow_nested_additional=True,
                        ):
                            errors.append(
                                f"{profile_id} output_slots_order.{rule['slot_id']} "
                                f"ссылается на неизвестное поле результата capability "
                                f"{source_ref.get('capability_id')}: {field}."
                            )
                        continue
                    errors.append(
                        f"{profile_id} output_slots_order.{rule['slot_id']} использует удаленный source_hint. "
                        "Используйте source_hint вида "
                        "${step.<step_id>.capability.<capability_id>.output.<field>}."
                    )

            llm_script = profile["llm_resolution_script"]
            if not llm_script.get("script_text"):
                errors.append(f"{profile_id} llm_resolution_script должен содержать script_text.")
            errors.extend(
                validate_template_refs(
                    llm_script.get("script_text"),
                    reference_context,
                    label=f"{profile_id}.llm_resolution_script.script_text",
                )
            )
            response_contract = llm_script.get("response_contract", {})
            for required_key in ("decision", "filled_slots", "confidence", "next_question", "reason"):
                if required_key not in response_contract:
                    errors.append(f"{profile_id} llm_resolution_script.response_contract должен содержать {required_key}.")
            errors.extend(
                validate_template_refs(
                    human_policy.get("message_template"),
                    reference_context,
                    label=f"{profile_id}.human_resolution_policy.message_template",
                )
            )

            fallback = profile.get("fallback", {"action": "operator_handoff"})
            if fallback["action"] == "ask_user" and not fallback.get("question"):
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
        prompt_pack_ids = set(
            self._by_id(self.active_payload("prompt_packs")["packs"], "prompt_pack_id")
        )
        escalation_policy_ids = set(
            self._by_id(self.active_payload("escalation_policies")["policies"], "policy_id")
        )
        channel_by_id = self._by_id(self.active_payload("interaction_channels")["channels"], "channel_id")
        channel_ids = set(channel_by_id)
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
            if scenario["prompt_pack_id"] not in prompt_pack_ids:
                errors.append(f"{scenario_id} ссылается на неизвестный prompt_pack_id: {scenario['prompt_pack_id']}")
            if scenario["escalation_policy_id"] not in escalation_policy_ids:
                errors.append(
                    f"{scenario_id} ссылается на неизвестную escalation_policy_id: "
                    f"{scenario['escalation_policy_id']}"
                )
            default_channel_id = scenario.get("default_channel_id", "debug")
            allowed_channel_ids = scenario.get("allowed_channel_ids") or [default_channel_id]
            if default_channel_id not in channel_ids:
                errors.append(f"{scenario_id} ссылается на неизвестный default_channel_id: {default_channel_id}")
            for channel_id in allowed_channel_ids:
                if channel_id not in channel_ids:
                    errors.append(f"{scenario_id} ссылается на неизвестный allowed_channel_id: {channel_id}")
            if default_channel_id not in allowed_channel_ids:
                errors.append(f"{scenario_id} default_channel_id должен входить в allowed_channel_ids.")
        return errors

    def _validate_slot_schemas(self, payload: dict[str, Any]) -> list[str]:
        errors = []
        schemas = payload["slot_schemas"]
        schema_ids = [schema["slot_schema_id"] for schema in schemas]
        for schema_id in self._duplicates(schema_ids):
            errors.append(f"Дублируется slot_schema_id: {schema_id}")
        priority_order = {"who": 0, "what": 1, "when": 2, "where": 3, "context": 4}
        system_confidence_defaults = self.system_confidence_defaults()
        profile_by_id = self._by_id(
            self.active_payload("attribute_resolution_profiles")["profiles"],
            "profile_id",
        )
        for schema in schemas:
            stages = slot_schema_stages(schema)
            stage_ids = [stage["stage_id"] for stage in stages]
            for stage_id in self._duplicates(stage_ids):
                errors.append(f"{schema['slot_schema_id']} содержит дублирующийся stage_id: {stage_id}")
            stage_orders = [stage["order"] for stage in stages]
            for stage_order in self._duplicates(stage_orders):
                errors.append(f"{schema['slot_schema_id']} содержит дублирующийся order этапа: {stage_order}")
            for stage in stages:
                stage_profile_id = stage.get("resolution_profile_id")
                if not (stage.get("slots") or []) and not stage_profile_id:
                    errors.append(
                        f"{schema['slot_schema_id']} stage {stage['stage_id']} должен содержать slots "
                        "или resolution_profile_id."
                    )
                if stage_profile_id:
                    profile = profile_by_id.get(stage_profile_id)
                    if not profile:
                        errors.append(
                            f"{schema['slot_schema_id']} stage {stage['stage_id']} ссылается на неизвестный profile_id: {stage_profile_id}"
                        )
                    elif profile.get("slot_schema_id") != schema["slot_schema_id"]:
                        errors.append(
                            f"{schema['slot_schema_id']} stage {stage['stage_id']} ссылается на профиль "
                            f"{stage_profile_id} другой схемы: {profile.get('slot_schema_id')}"
                        )
            slot_by_id = self._by_id(schema["slots"], "slot_id")
            for slot_id in self._duplicates([slot["slot_id"] for slot in schema["slots"]]):
                errors.append(f"{schema['slot_schema_id']} содержит дублирующийся slot_id: {slot_id}")
            active_profiles_for_schema = [
                profile
                for profile in profile_by_id.values()
                if profile.get("slot_schema_id") == schema["slot_schema_id"]
            ]
            reference_context = build_execution_reference_context(
                slot_schema=schema,
                channels=self.active_payload("interaction_channels")["channels"],
            )
            for slot in schema["slots"]:
                fill_method = slot_fill_method(slot)
                profile_id = slot.get("resolution_profile_id")
                if fill_method != "llm_extraction" and slot.get("confidence_overrides"):
                    errors.append(
                        f"{schema['slot_schema_id']} slot {slot['slot_id']}.confidence_overrides "
                        "допустим только для способа llm_extraction."
                    )
                errors.extend(
                    validate_confidence_overrides(
                        system_confidence_defaults,
                        slot.get("confidence_overrides"),
                        f"{schema['slot_schema_id']} slot {slot['slot_id']}.confidence_overrides",
                    )
                )
                required_field = SLOT_METHOD_REQUIRED_FIELD.get(fill_method)
                if required_field and not slot.get(required_field):
                    errors.append(
                        f"{schema['slot_schema_id']} slot {slot['slot_id']} со способом {fill_method} "
                        f"должен иметь поле {required_field}."
                    )
                allowed_fields = SLOT_METHOD_ALLOWED_FIELDS.get(fill_method, set())
                for field in sorted(SLOT_CONTEXT_FIELDS - allowed_fields):
                    if field in slot:
                        errors.append(
                            f"{schema['slot_schema_id']} slot {slot['slot_id']} со способом {fill_method} "
                            f"не должен иметь поле {field}."
                        )
                for template_field in ("user_question", "extraction_instruction", "operator_hint"):
                    if slot.get(template_field):
                        errors.extend(
                            validate_template_refs(
                                slot.get(template_field),
                                reference_context,
                                label=f"{schema['slot_schema_id']} slot {slot['slot_id']}.{template_field}",
                            )
                        )
                if fill_method == "resolution_profile":
                    if not profile_id:
                        errors.append(f"{schema['slot_schema_id']} slot {slot['slot_id']} должен иметь resolution_profile_id.")
                    else:
                        profile = profile_by_id.get(profile_id)
                        if not profile:
                            errors.append(f"{schema['slot_schema_id']} slot {slot['slot_id']} ссылается на неизвестный profile_id: {profile_id}")
                        elif slot["slot_id"] not in [item["slot_id"] for item in profile.get("output_slots_order", [])]:
                            errors.append(f"{schema['slot_schema_id']} slot {slot['slot_id']} не входит в output_slots_order профиля {profile_id}.")
            for slot_id in schema["required_slots"]:
                slot = slot_by_id.get(slot_id)
                if not slot:
                    errors.append(f"{schema['slot_schema_id']} содержит неизвестный required slot: {slot_id}")
                    continue
            for slot_id in schema["auto_fill_slots"]:
                slot = slot_by_id.get(slot_id)
                if not slot:
                    errors.append(f"{schema['slot_schema_id']} содержит неизвестный auto-fill slot: {slot_id}")
                elif slot_fill_method(slot) in {"user_question", "operator_manual"}:
                    errors.append(f"{schema['slot_schema_id']} auto-fill slot {slot_id} не может заполняться вопросом или вручную.")
            for profile in active_profiles_for_schema:
                for output in profile.get("output_slots_order", []):
                    output_slot = output.get("slot_id")
                    if output_slot and output_slot not in slot_by_id:
                        errors.append(
                            f"{schema['slot_schema_id']} slot {output_slot} используется профилем "
                            f"{profile['profile_id']} и не может отсутствовать в схеме."
                        )
            previous_priority = -1
            for slot_id in schema["question_order"]:
                slot = slot_by_id.get(slot_id)
                if not slot:
                    errors.append(f"{schema['slot_schema_id']} содержит неизвестный slot в question_order: {slot_id}")
                    continue
                if slot_fill_method(slot) not in {"user_question", "resolution_profile", "operator_manual"}:
                    errors.append(
                        f"{schema['slot_schema_id']} slot {slot_id} не должен входить в question_order "
                        f"для способа {slot_fill_method(slot)}."
                    )
                current_priority = priority_order[slot["priority_group"]]
                if current_priority < previous_priority:
                    errors.append(
                        f"{schema['slot_schema_id']} нарушает порядок вопросов кто -> что -> когда: {slot_id}"
                    )
                previous_priority = current_priority
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
            if confidence["llm_min"] > confidence["rules_min"]:
                errors.append(f"{route['route_id']} llm_min не должен быть выше rules_min.")
            rules = route.get("rules", {}).get("rule_items", [])
            seen_rules: set[tuple[str, str, str]] = set()
            for index, rule in enumerate(rules, start=1):
                rule_key = (
                    normalized_match_text(rule.get("text", "")),
                    rule.get("match_type", ""),
                    rule.get("polarity", ""),
                )
                if rule_key in seen_rules:
                    errors.append(f"{route['route_id']} содержит дублирующееся правило классификации #{index}: {rule.get('text')}")
                seen_rules.add(rule_key)
                if rule.get("polarity") == "negative" and rule.get("required"):
                    errors.append(f"{route['route_id']} negative rule #{index} не может быть обязательным.")
                if rule.get("polarity") == "positive" and rule.get("blocking"):
                    errors.append(f"{route['route_id']} positive rule #{index} не может быть блокирующим.")
        return errors

    def _validate_orchestrator_policy(self, payload: dict[str, Any]) -> list[str]:
        errors = []
        errors.extend(
            validate_confidence_thresholds(
                payload.get("confidence_defaults"),
                "orchestrator_policy.confidence_defaults",
                require_all=True,
            )
        )
        policy_ids = [policy["policy_id"] for policy in payload["policies"]]
        for policy_id in self._duplicates(policy_ids):
            errors.append(f"Дублируется policy_id: {policy_id}")
        for policy in payload["policies"]:
            if policy["consecutive_capability_errors_to_escalate"] > policy["max_iterations"]:
                errors.append(f"{policy['policy_id']} лимит ошибок capability не может быть выше max_iterations.")
        return errors

    def _validate_prompt_packs(self, payload: dict[str, Any]) -> list[str]:
        errors = []
        pack_ids = [pack["prompt_pack_id"] for pack in payload["packs"]]
        for pack_id in self._duplicates(pack_ids):
            errors.append(f"Дублируется prompt_pack_id: {pack_id}")
        required_blocks = {
            "role_context",
            "behavior_principles",
            "slot_schemas",
            "classification_confidence",
            "orchestration",
            "capability_rules",
            "escalation_response",
        }
        for pack in payload["packs"]:
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
        for policy in payload["policies"]:
            if not policy.get("handoff_conditions"):
                errors.append(f"{policy['policy_id']} handoff_conditions должен быть непустым.")
            handoff_package = set(policy.get("handoff_package") or [])
            if not handoff_package:
                errors.append(f"{policy['policy_id']} handoff_package должен быть непустым.")
            for required_item in ("slots", "user_notification"):
                if required_item not in handoff_package:
                    errors.append(f"{policy['policy_id']} handoff package должен содержать {required_item}.")
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

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _require_domain(self, domain: str) -> None:
        if domain not in CONFIG_DOMAINS:
            raise ConfigRegistryError(f"Неизвестный домен конфигурации: {domain}")

    def _scenario_by_id(self) -> dict[str, dict[str, Any]]:
        return self._by_id(
            self.active_payload("service_scenarios")["scenarios"],
            "scenario_id",
        )

    @staticmethod
    def _collect_channel_scenario_refs(payload: dict[str, Any]) -> set[str]:
        refs: set[str] = set()
        for scenario in payload.get("scenarios", []):
            default_channel_id = scenario.get("default_channel_id")
            if default_channel_id:
                refs.add(default_channel_id)
            refs.update(scenario.get("allowed_channel_ids", []))
        return refs

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
                "prompt_pack_id": f"prompt.{item['scenario_id']}",
                "escalation_policy_id": f"escalation.{item['scenario_id']}",
                "default_channel_id": "debug",
                "allowed_channel_ids": ["messenger_bot", "service_desk", "debug"],
                "audit_required": True,
                "log_required": True,
                "tags": ["mvp"],
            }
            for item in DEFAULT_SCENARIOS
        ],
    }


def default_interaction_channels() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "channels": [
            {
                "channel_id": "messenger_bot",
                "display_name": "Мессенджер-бот",
                "mode": "online_interactive",
                "description": "Онлайн-канал с прямым диалогом с клиентом: уточняющие вопросы уходят клиенту, ожидание короткое, при незавершенном уточнении сохраняется контекст, а при эскалации подключается оператор.",
                "capabilities": normalize_channel_capabilities(
                    None,
                    channel_id="messenger_bot",
                    mode="online_interactive",
                ),
                "technical_profile": normalize_channel_technical_profile(None, channel_id="messenger_bot"),
                "channel_parameters": normalize_channel_parameters(None, channel_id="messenger_bot"),
                "waiting_policy": {
                    "first_reminder_after_seconds": 180,
                    "discussion_timeout_seconds": 480,
                    "sla_elapsed_percent_threshold": 0,
                    "on_no_answer": "create_draft",
                    "auto_close_requires_client_confirmation": True,
                    "pause_sla_on_client_wait": True,
                    "client_wait_auto_close_after_hours": 24,
                },
                "enabled": True,
            },
            {
                "channel_id": "service_desk",
                "display_name": "Сервисдеск",
                "mode": "offline_interactive",
                "description": "Логический канал заказчика Сервисдеск. Текущий MVP использует Kafka-контракт ОПЕРУ.ИТ для постановки задач и получения результата; прямые вопросы клиенту или оператору этим контрактом пока не поддержаны.",
                "capabilities": normalize_channel_capabilities(
                    DEFAULT_SERVICEDESK_CHANNEL_CAPABILITIES,
                    channel_id="service_desk",
                    mode="offline_interactive",
                ),
                "technical_profile": normalize_channel_technical_profile(None, channel_id="service_desk"),
                "channel_parameters": normalize_channel_parameters(None, channel_id="service_desk"),
                "waiting_policy": {
                    "first_reminder_after_seconds": 3600,
                    "discussion_timeout_seconds": 14400,
                    "sla_elapsed_percent_threshold": 30,
                    "on_no_answer": "create_work_order",
                    "auto_close_requires_client_confirmation": True,
                    "pause_sla_on_client_wait": True,
                    "client_wait_auto_close_after_hours": 24,
                },
                "enabled": True,
            },
            {
                "channel_id": "debug",
                "display_name": "Отладочный режим",
                "mode": "debug",
                "description": "Локальный режим MVP: вопросы показывает интерфейс оператора, а эскалация останавливает сценарий с диагностическим сообщением без внешнего исполнения.",
                "capabilities": normalize_channel_capabilities(
                    None,
                    channel_id="debug",
                    mode="debug",
                ),
                "technical_profile": normalize_channel_technical_profile(None, channel_id="debug"),
                "channel_parameters": normalize_channel_parameters(None, channel_id="debug"),
                "waiting_policy": {
                    "first_reminder_after_seconds": 0,
                    "discussion_timeout_seconds": 0,
                    "sla_elapsed_percent_threshold": 0,
                    "on_no_answer": "debug_stop",
                    "auto_close_requires_client_confirmation": True,
                    "pause_sla_on_client_wait": True,
                    "client_wait_auto_close_after_hours": 24,
                },
                "enabled": True,
            },
        ],
    }


SENSITIVE_CHANNEL_DEBUG_PARTS = {
    "secret",
    "token",
    "password",
    "api_key",
    "apikey",
    "credential",
    "hmac",
}


def is_sensitive_channel_debug_ref(value: str | None) -> bool:
    normalized = str(value or "").lower()
    return any(part in normalized for part in SENSITIVE_CHANNEL_DEBUG_PARTS)


def channel_debug_parameter_state(
    interaction_channel: dict[str, Any] | None,
    channel_variables: dict[str, Any],
) -> list[dict[str, Any]]:
    if not isinstance(interaction_channel, dict):
        return []
    channel_id = str(interaction_channel.get("channel_id") or "").strip()
    values = (channel_variables.get(channel_id) or {}) if isinstance(channel_variables, dict) else {}
    result: list[dict[str, Any]] = []
    for parameter in interaction_channel.get("channel_parameters", []):
        if not isinstance(parameter, dict):
            continue
        parameter_id = str(parameter.get("parameter_id") or "").strip()
        if not parameter_id:
            continue
        source = str(parameter.get("source") or "").strip()
        is_secret = (
            bool(parameter.get("secret"))
            or is_sensitive_channel_debug_ref(parameter_id)
            or is_sensitive_channel_debug_ref(source)
        )
        has_value = parameter_id in values and values.get(parameter_id) not in (None, "", [], {})
        if is_secret:
            status = "secret"
        elif has_value:
            status = "resolved"
        elif source:
            status = "missing"
        else:
            status = "unmapped"
        item = {
            "parameter_id": parameter_id,
            "display_name": parameter.get("display_name") or parameter_id,
            "direction": parameter.get("direction") or "input",
            "source": source,
            "status": status,
        }
        if has_value and not is_secret:
            item["value"] = copy.deepcopy(values[parameter_id])
        result.append(item)
    return result


def _slot(
    slot_id: str,
    display_name: str,
    priority_group: str,
    *,
    required: bool = True,
    fill_method: str = "user_question",
    resolution_profile_id: str | None = None,
    user_question: str | None = None,
    case_source_ref: str | None = None,
    extraction_instruction: str | None = None,
    fallback_question: str | None = None,
    operator_hint: str | None = None,
    examples: list[str] | None = None,
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
    if user_question:
        result["user_question"] = user_question
    if case_source_ref:
        result["case_source_ref"] = case_source_ref
    if extraction_instruction:
        result["extraction_instruction"] = extraction_instruction
    if fallback_question:
        result["fallback_question"] = fallback_question
    if operator_hint:
        result["operator_hint"] = operator_hint
    if examples:
        result["examples"] = examples
    return result


def _slot_schema(slot_schema_id: str, display_name: str, slots: list[dict[str, Any]]) -> dict[str, Any]:
    priority_order = {"who": 0, "what": 1, "when": 2, "where": 3, "context": 4}
    question_candidates = [
        (index, slot)
        for index, slot in enumerate(slots)
        if slot.get("required") and slot_fill_method(slot) in {"user_question", "resolution_profile", "operator_manual"}
    ]
    question_order = [
        slot["slot_id"]
        for index, slot in sorted(
            question_candidates,
            key=lambda item: (priority_order.get(item[1].get("priority_group"), 99), item[0]),
        )
    ]
    return {
        "slot_schema_id": slot_schema_id,
        "display_name": display_name,
        "stages": [
            {
                "stage_id": "stage.collect_context",
                "display_name": "Сбор и разрешение слотов",
                "description": "Базовый этап планирования, в котором собираются обязательные и производные слоты.",
                "order": 1,
                "slots": copy.deepcopy(slots),
            },
        ],
        "required_slots": [slot["slot_id"] for slot in slots if slot.get("required")],
        "auto_fill_slots": [
            slot["slot_id"]
            for slot in slots
            if slot_fill_method(slot) not in {"user_question", "operator_manual"}
        ],
        "question_order": question_order,
        "slots": copy.deepcopy(slots),
    }


def default_slot_schemas() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "slot_schemas": [
            _slot_schema(
                "slot.password_reset",
                "Слоты сброса пароля",
                [
                    _slot(
                        "user_login",
                        "Логин пользователя",
                        "who",
                        fill_method="resolution_profile",
                        resolution_profile_id="profile.password_reset.login_from_ad",
                        fallback_question="Уточните ФИО, должность или табельный номер пользователя.",
                    ),
                    _slot("account_type", "Тип учетной записи", "what", user_question="Для какой учетной записи нужен сброс?"),
                    _slot(
                        "user_id",
                        "Идентификатор пользователя",
                        "who",
                        required=False,
                        fill_method="resolution_profile",
                        resolution_profile_id="profile.password_reset.login_from_ad",
                    ),
                ],
            ),
            _slot_schema(
                "slot.software_issue",
                "Слоты проблемы с приложением",
                [
                    _slot("user_login", "Логин пользователя", "who", user_question="Уточните логин пользователя."),
                    _slot("app_name", "Приложение", "what", user_question="С каким приложением проблема?"),
                    _slot("error_text", "Текст ошибки", "what", user_question="Какой текст ошибки видит пользователь?"),
                    _slot(
                        "device_name",
                        "Имя устройства",
                        "context",
                        required=False,
                        fill_method="resolution_profile",
                        resolution_profile_id="profile.software_issue.device_from_ad",
                    ),
                ],
            ),
            _slot_schema(
                "slot.hardware_issue",
                "Слоты проблемы с устройством",
                [
                    _slot("user_login", "Логин пользователя", "who", user_question="Уточните логин пользователя."),
                    _slot("device_id", "ID устройства", "what", user_question="Уточните имя или инвентарный номер устройства."),
                    _slot("symptom", "Симптом", "what", user_question="Что именно не работает?"),
                    _slot(
                        "device_model",
                        "Модель устройства",
                        "context",
                        required=False,
                        fill_method="resolution_profile",
                        resolution_profile_id="profile.hardware_issue.device_from_cmdb",
                    ),
                ],
            ),
            _slot_schema(
                "slot.network_issue",
                "Слоты сетевой проблемы",
                [
                    _slot("user_login", "Логин пользователя", "who", user_question="Уточните логин пользователя."),
                    _slot("symptom", "Симптом", "what", user_question="Что именно недоступно?"),
                    _slot("affected_users", "Затронутые пользователи", "what", user_question="Сколько пользователей затронуто?"),
                    _slot("location", "Локация", "where", user_question="Где наблюдается проблема?"),
                    _slot(
                        "subnet",
                        "Подсеть",
                        "context",
                        required=False,
                        fill_method="resolution_profile",
                        resolution_profile_id="profile.network_issue.subnet_from_cmdb",
                    ),
                ],
            ),
            _slot_schema(
                "slot.access_request",
                "Слоты запроса доступа",
                [
                    _slot("user_login", "Логин пользователя", "who", user_question="Уточните логин пользователя."),
                    _slot("resource_name", "Ресурс", "what", user_question="К какому ресурсу нужен доступ?"),
                    _slot("business_reason", "Обоснование", "what", user_question="Уточните бизнес-обоснование доступа."),
                    _slot("approver_login", "Согласующий", "who", user_question="Кто должен согласовать доступ?"),
                    _slot(
                        "user_id",
                        "Идентификатор пользователя",
                        "who",
                        required=False,
                        fill_method="resolution_profile",
                        resolution_profile_id="profile.access_request.user_from_ad",
                    ),
                ],
            ),
            _slot_schema(
                "slot.unknown",
                "Слоты неизвестного сценария",
                [
                    _slot("user_login", "Логин пользователя", "who", user_question="Уточните логин пользователя."),
                    _slot("symptom", "Описание проблемы", "what", user_question="Опишите проблему одной фразой."),
                ],
            ),
        ],
    }


def default_capabilities() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "capabilities": [
            {
                "capability_id": "provider_channel_repair_monitor",
                "display_name": "Мониторинг ремонта канала провайдера",
                "status": "active",
                "description": (
                    "Запускает внешний MCP-исполнитель ремонта канала провайдера, ожидает ответ провайдера "
                    "и возвращает canonical данные для продолжения сценария."
                ),
                "contract_version": "1.0",
                "execution_modes": ["async"],
                "input_schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["problem_url", "service_request", "from", "reply_to"],
                    "properties": {
                        "problem_url": {"type": "string", "minLength": 1},
                        "service_request": {"type": "string", "minLength": 1},
                        "problem_host": {"type": "string"},
                        "from": {"type": "string", "minLength": 1},
                        "reply_to": {"type": "string", "minLength": 1},
                        "template_id": {"type": "string"},
                        "poll_interval_minutes": {"type": "integer", "minimum": 1},
                        "timeout_minutes": {"type": "integer", "minimum": 1},
                    },
                },
                "output_schema": {
                    "type": "object",
                    "additionalProperties": True,
                    "required": ["provider_mail_body"],
                    "properties": {
                        "provider_mail_body": {"type": "string", "minLength": 1},
                        "provider_mail_subject": {"type": "string"},
                        "provider_ticket_number": {"type": "string"},
                        "polling_diagnostic": {"type": "object", "additionalProperties": True},
                        "zabbix_status": {"type": "string"},
                    },
                },
                "async_event_contracts": {
                    "provider_channel_repair_monitor.completed": {
                        "display_name": "Результат мониторинга ремонта канала провайдера",
                        "description": "Progress или terminal результат внешнего MCP-исполнителя.",
                        "statuses": ["progress", "success", "error", "timeout", "cancelled"],
                        "result_schema": {
                            "type": "object",
                            "additionalProperties": True,
                            "properties": {
                                "provider_mail_body": {"type": "string"},
                                "provider_mail_subject": {"type": "string"},
                                "provider_ticket_number": {"type": "string"},
                                "polling_diagnostic": {"type": "object", "additionalProperties": True},
                                "zabbix_status": {"type": "string"},
                                "message": {"type": "string"},
                            },
                        },
                        "progress_schema": {
                            "type": "object",
                            "additionalProperties": True,
                            "properties": {
                                "polling_diagnostic": {"type": "object", "additionalProperties": True},
                                "message": {"type": "string"},
                            },
                        },
                        "error_schema": {
                            "type": "object",
                            "additionalProperties": True,
                            "properties": {
                                "code": {"type": "string"},
                                "message": {"type": "string"},
                            },
                        },
                        "contract_version": "1.0",
                        "contract_status": "valid",
                    }
                },
                "default_completion_policy": {
                    "mode": "external_event",
                    "expected_event_type": "provider_channel_repair_monitor.completed",
                    "max_wait_seconds": 3600,
                    "timeout_action": "escalate_operator",
                },
                "diagnostic_schema": {
                    "type": "object",
                    "additionalProperties": True,
                    "properties": {
                        "external_execution_id": {"type": "string"},
                        "correlation_id": {"type": "string"},
                        "phase": {"type": "string"},
                        "last_checked_resource": {"type": "string"},
                    },
                },
            },
            {
                "capability_id": "zabbix_problem_update",
                "display_name": "Обновление проблемы Zabbix",
                "status": "active",
                "description": (
                    "Передает внешнему MCP-исполнителю команду обновить/дополнить проблему Zabbix "
                    "сообщением из сценария."
                ),
                "contract_version": "1.0",
                "execution_modes": ["sync"],
                "input_schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["problem_url", "message"],
                    "properties": {
                        "problem_url": {"type": "string", "minLength": 1},
                        "message": {"type": "string", "minLength": 1},
                    },
                },
                "output_schema": {
                    "type": "object",
                    "additionalProperties": True,
                    "required": ["status"],
                    "properties": {
                        "status": {"type": "string"},
                        "message": {"type": "string"},
                        "eventid": {"type": "string"},
                        "triggerid": {"type": "string"},
                        "zabbix_origin": {"type": "string"},
                        "problem": {"type": "object", "additionalProperties": True},
                    },
                },
                "async_event_contracts": {},
                "default_completion_policy": {
                    "mode": "sync",
                    "max_wait_seconds": 0,
                    "timeout_action": "resume_agent",
                },
                "diagnostic_schema": {
                    "type": "object",
                    "additionalProperties": True,
                    "properties": {
                        "external_execution_id": {"type": "string"},
                        "phase": {"type": "string"},
                    },
                },
            },
            {
                "capability_id": "zabbix_problem_status_wait",
                "display_name": "Ожидание восстановления проблемы Zabbix",
                "status": "active",
                "description": (
                    "Ожидает во внешнем MCP-окружении восстановления проблемы Zabbix и возвращает canonical статус."
                ),
                "contract_version": "1.0",
                "execution_modes": ["async"],
                "input_schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["problem_url", "poll_interval_minutes", "timeout_minutes"],
                    "properties": {
                        "problem_url": {"type": "string", "minLength": 1},
                        "poll_interval_minutes": {"type": "integer", "minimum": 1},
                        "timeout_minutes": {"type": "integer", "minimum": 1},
                        "request_id": {"type": "string"},
                    },
                },
                "output_schema": {
                    "type": "object",
                    "additionalProperties": True,
                    "required": ["status"],
                    "properties": {
                        "status": {"type": "string"},
                        "timed_out": {"type": "boolean"},
                        "message": {"type": "string"},
                        "zabbix_status": {"type": "object", "additionalProperties": True},
                        "started_at": {"type": "string"},
                        "finished_at": {"type": "string"},
                        "poll_interval_minutes": {"type": "integer"},
                        "timeout_minutes": {"type": "integer"},
                    },
                },
                "async_event_contracts": {
                    "zabbix_problem_status_wait.completed": {
                        "display_name": "Результат ожидания восстановления Zabbix",
                        "description": "Progress или terminal результат ожидания восстановления проблемы Zabbix.",
                        "statuses": ["progress", "success", "error", "timeout", "cancelled"],
                        "result_schema": {
                            "type": "object",
                            "additionalProperties": True,
                            "properties": {
                                "status": {"type": "string"},
                                "timed_out": {"type": "boolean"},
                                "message": {"type": "string"},
                                "zabbix_status": {"type": "object", "additionalProperties": True},
                            },
                        },
                        "progress_schema": {
                            "type": "object",
                            "additionalProperties": True,
                            "properties": {
                                "message": {"type": "string"},
                                "zabbix_status": {"type": "object", "additionalProperties": True},
                            },
                        },
                        "error_schema": {
                            "type": "object",
                            "additionalProperties": True,
                            "properties": {
                                "code": {"type": "string"},
                                "message": {"type": "string"},
                            },
                        },
                        "contract_version": "1.0",
                        "contract_status": "valid",
                    },
                },
                "default_completion_policy": {
                    "mode": "external_event",
                    "expected_event_type": "zabbix_problem_status_wait.completed",
                    "max_wait_seconds": 86400,
                    "timeout_action": "escalate_operator",
                },
                "diagnostic_schema": {
                    "type": "object",
                    "additionalProperties": True,
                    "properties": {
                        "external_execution_id": {"type": "string"},
                        "correlation_id": {"type": "string"},
                        "phase": {"type": "string"},
                    },
                },
            },
        ],
    }


def default_mcp_environments() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "environments": [
            {
                "environment_id": "mcp.provider_ops",
                "display_name": "Provider operations MCP",
                "status": "active",
                "environment_tier": "dev",
                "transport": "streamable_http",
                "base_url": os.getenv("MCP_PROVIDER_OPS_BASE_URL", "http://hostmachine:9000/mcp"),
                "auth_mode": "dev_bearer_token",
                "auth_ref": "env:MCP_PROVIDER_OPS_TOKEN",
                "allowed_capabilities": [
                    "provider_channel_repair_monitor",
                    "zabbix_problem_update",
                    "zabbix_problem_status_wait",
                ],
                "health_check": {
                    "mode": "http_get",
                    "path": "/health",
                    "timeout_seconds": 5,
                },
                "discovery_policy": {
                    "mode": "manual",
                },
            }
        ],
    }


def default_capability_bindings() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "bindings": [
            {
                "binding_id": "binding.provider_channel_repair_monitor.primary",
                "capability_id": "provider_channel_repair_monitor",
                "environment_id": "mcp.provider_ops",
                "mcp_tool_name": "provider_channel_repair_monitor",
                "execution_mode": "async",
                "status": "active",
                "input_mapping": {
                    "problem_url": "problem_url",
                    "service_request": "service_request",
                    "problem_host": "problem_host",
                    "from": "from",
                    "reply_to": "reply_to",
                },
                "output_mapping": {
                    "provider_mail_body": "provider_mail_body",
                    "provider_mail_subject": "provider_mail_subject",
                    "provider_ticket_number": "provider_ticket_number",
                    "polling_diagnostic": "polling_diagnostic",
                    "zabbix_status": "zabbix_status",
                },
                "async_context_mapping": {
                    "case_id": "async_context.case_id",
                    "run_id": "async_context.run_id",
                    "wait_id": "async_context.wait_id",
                    "correlation_id": "async_context.correlation_id",
                    "capability_id": "async_context.capability_id",
                    "contract_version": "async_context.contract_version",
                    "expected_event_type": "async_context.expected_event_type",
                    "idempotency_key_base": "async_context.idempotency_key_base",
                },
            },
            {
                "binding_id": "binding.zabbix_problem_update.primary",
                "capability_id": "zabbix_problem_update",
                "environment_id": "mcp.provider_ops",
                "mcp_tool_name": "zabbix_problem_update",
                "execution_mode": "sync",
                "status": "active",
                "input_mapping": {
                    "problem_url": "problem_url",
                    "message": "message",
                },
                "output_mapping": {
                    "status": "status",
                    "message": "message",
                    "eventid": "eventid",
                    "triggerid": "triggerid",
                    "zabbix_origin": "zabbix_origin",
                    "problem": "problem",
                },
                "async_context_mapping": {},
            },
            {
                "binding_id": "binding.zabbix_problem_status_wait.primary",
                "capability_id": "zabbix_problem_status_wait",
                "environment_id": "mcp.provider_ops",
                "mcp_tool_name": "zabbix_problem_status_wait",
                "execution_mode": "async",
                "status": "active",
                "input_mapping": {
                    "problem_url": "problem_url",
                    "poll_interval_minutes": "poll_interval_minutes",
                    "timeout_minutes": "timeout_minutes",
                    "request_id": "request_id",
                },
                "output_mapping": {
                    "status": "status",
                    "timed_out": "timed_out",
                    "message": "message",
                    "zabbix_status": "zabbix_status",
                    "started_at": "started_at",
                    "finished_at": "finished_at",
                    "poll_interval_minutes": "poll_interval_minutes",
                    "timeout_minutes": "timeout_minutes",
                },
                "async_context_mapping": {
                    "case_id": "async_context.case_id",
                    "run_id": "async_context.run_id",
                    "wait_id": "async_context.wait_id",
                    "correlation_id": "async_context.correlation_id",
                    "capability_id": "async_context.capability_id",
                    "contract_version": "async_context.contract_version",
                    "expected_event_type": "async_context.expected_event_type",
                    "idempotency_key_base": "async_context.idempotency_key_base",
                },
            },
        ],
    }


def default_attribute_resolution_profiles() -> dict[str, Any]:
    def candidate_profile(
        profile_id: str,
        display_name: str,
        description: str,
        slot_schema_id: str,
        target_slot_id: str,
        output_slots: list[str],
        input_attributes: list[dict[str, Any]],
        candidate_source: dict[str, Any],
        result_policy: dict[str, Any],
        clarification_question: str,
        *,
        status: str = "active",
        confidence_threshold: float = 0.7,
        max_attempts: int = 1,
        fallback_action: str = "ask_user",
    ) -> dict[str, Any]:
        parameter_mapping = slot_parameter_mapping_from_legacy(
            candidate_source.get("parameter_mapping", {}),
            input_attributes,
        )
        resolver_operation = {
            "source_type": candidate_source.get("source_type", "disabled"),
            "parameter_mapping": parameter_mapping,
        }
        for key in ("tool_name", "endpoint_id", "operation_id", "history_filter"):
            if candidate_source.get(key):
                resolver_operation[key] = candidate_source[key]
        result_entity = operation_result_entity_from_policy(resolver_operation, result_policy)
        enrichment_steps = enrichment_steps_from_legacy(resolver_operation, result_entity)
        output_order = output_slots_order_from_policy(target_slot_id, output_slots, result_policy)
        human_policy = {
            "action": "ask_client",
            "message_template": clarification_question,
        }
        profile = {
            "profile_id": profile_id,
            "display_name": display_name,
            "status": status,
            "description": description,
            "slot_schema_id": slot_schema_id,
            "target_slot_id": target_slot_id,
            "use_llm_after_steps": True,
            "enrichment_steps": enrichment_steps,
            "output_slots_order": normalize_output_slot_order(output_order, target_slot_id),
            "llm_resolution_script": {
                "script_text": (
                    "Выбери результат операции и заполни выходные слоты по порядку. "
                    "Если результат неоднозначен или обязательный слот не заполнен, сформулируй один уточняющий вопрос."
                ),
                "response_contract": default_resolution_response_contract(),
            },
            "human_resolution_policy": human_policy,
            "fallback": {
                "action": fallback_action,
                "question": clarification_question,
            },
            "confidence_threshold": confidence_threshold,
            "confidence_thresholds": {
                "auto_fill": max(confidence_threshold, 0.85),
                "clarification": confidence_threshold,
                "operator_handoff": 0.5,
            },
            "max_attempts": max_attempts,
        }
        profile["llm_resolution_script"]["script_text"] = default_resolution_script_text(profile)
        return profile

    return {
        "schema_version": "1.0",
        "profiles": [
            candidate_profile(
                "profile.password_reset.login_from_ad",
                "Поиск логина в AD по ФИО",
                "Заполняет логин и идентификатор пользователя для сброса пароля: извлекает признаки личности, ищет результаты в AD и задает уточнение при неоднозначности.",
                "slot.password_reset",
                "user_login",
                ["user_login", "user_id"],
                [
                    resolution_attribute("login_candidate", display_name="Логин из текста", source="llm", extraction_instruction="Извлеки возможный логин пользователя из текста обращения."),
                    resolution_attribute("last_name", display_name="Фамилия", source="llm", extraction_instruction="Извлеки фамилию пользователя."),
                    resolution_attribute("first_name", display_name="Имя", source="llm", extraction_instruction="Извлеки имя пользователя."),
                    resolution_attribute("middle_name", display_name="Отчество", source="llm", extraction_instruction="Извлеки отчество пользователя."),
                    resolution_attribute("email", display_name="Email", source="llm", extraction_instruction="Извлеки email пользователя."),
                    resolution_attribute("department", display_name="Подразделение", source="operator_answer", required=False),
                    resolution_attribute("employee_number", display_name="Табельный номер", source="operator_answer", required=False),
                    resolution_attribute("title", display_name="Должность", source="operator_answer", required=False),
                ],
                {
                    "source_type": "capability_call",
                    "tool_name": "search_ad_users",
                    "endpoint_id": "mock",
                    "operation_id": "search_ad_users",
                    "parameter_mapping": {
                        "login": "attribute:login_candidate",
                        "last_name": "attribute:last_name",
                        "first_name": "attribute:first_name",
                        "middle_name": "attribute:middle_name",
                        "department": "attribute:department",
                        "employee_number": "attribute:employee_number",
                    },
                },
                default_result_policy("search_ad_users", "user_login"),
                "Уточните должность, подразделение или табельный номер пользователя.",
                confidence_threshold=0.75,
                max_attempts=2,
                fallback_action="operator_handoff",
            ),
            candidate_profile(
                "profile.software_issue.device_from_ad",
                "Устройство пользователя из AD",
                "Определяет основное устройство пользователя по логину через профиль AD.",
                "slot.software_issue",
                "device_name",
                ["device_name"],
                [resolution_attribute("user_login", display_name="Логин пользователя", source="slot", source_ref="user_login", required=True)],
                {
                    "source_type": "capability_call",
                    "tool_name": "search_ad_users",
                    "endpoint_id": "mock",
                    "operation_id": "search_ad_users",
                    "parameter_mapping": {"login": "attribute:user_login"},
                },
                {
                    **default_result_policy("search_ad_users", "device_name"),
                    "target_value_path": "device_name",
                    "output_mapping": {},
                },
                "Уточните имя устройства пользователя.",
                max_attempts=2,
            ),
            candidate_profile(
                "profile.hardware_issue.device_from_cmdb",
                "Устройство из CMDB",
                "Заполняет модель устройства по имени или инвентарному номеру через CMDB.",
                "slot.hardware_issue",
                "device_model",
                ["device_model"],
                [resolution_attribute("device_id", display_name="ID устройства", source="slot", source_ref="device_id", required=True)],
                {
                    "source_type": "capability_call",
                    "tool_name": "query_cmdb_object",
                    "endpoint_id": "mock",
                    "operation_id": "query_cmdb_object",
                    "parameter_mapping": {"object_ref": "attribute:device_id"},
                },
                default_result_policy("query_cmdb_object", "device_model"),
                "Уточните модель устройства, если она известна.",
            ),
            candidate_profile(
                "profile.network_issue.subnet_from_cmdb",
                "Подсеть по локации из CMDB",
                "Определяет подсеть по локации для сетевого инцидента.",
                "slot.network_issue",
                "subnet",
                ["subnet"],
                [resolution_attribute("location", display_name="Локация", source="slot", source_ref="location", required=True)],
                {
                    "source_type": "capability_call",
                    "tool_name": "query_cmdb_object",
                    "endpoint_id": "mock",
                    "operation_id": "query_cmdb_object",
                    "parameter_mapping": {"object_ref": "attribute:location"},
                },
                default_result_policy("query_cmdb_object", "subnet"),
                "Не удалось определить подсеть по локации. Уточните техническую локацию или передайте обращение специалисту.",
                fallback_action="operator_handoff",
            ),
            candidate_profile(
                "profile.access_request.user_from_ad",
                "Пользователь запроса доступа из AD",
                "Заполняет идентификатор пользователя для запроса доступа по логину.",
                "slot.access_request",
                "user_id",
                ["user_id"],
                [resolution_attribute("user_login", display_name="Логин пользователя", source="slot", source_ref="user_login", required=True)],
                {
                    "source_type": "capability_call",
                    "tool_name": "search_ad_users",
                    "endpoint_id": "mock",
                    "operation_id": "search_ad_users",
                    "parameter_mapping": {"login": "attribute:user_login"},
                },
                {
                    **default_result_policy("search_ad_users", "user_id"),
                    "target_value_path": "user_id",
                    "output_mapping": {},
                },
                "Уточните логин пользователя для запроса доступа.",
            ),
            candidate_profile(
                "profile.history.password_reset.resolved",
                "История успешных сбросов пароля",
                "Ищет похожие закрытые заявки сброса пароля только в разрешенном сценарии и только с подтвержденным качеством.",
                "slot.password_reset",
                "account_type",
                ["account_type"],
                [resolution_attribute("user_login", display_name="Логин пользователя", source="slot", source_ref="user_login", required=True)],
                {
                    "source_type": "ticket_history",
                    "parameter_mapping": {"user_login": "attribute:user_login"},
                    "history_filter": {
                        "ticket_statuses": ["resolved", "closed"],
                        "time_window_days": 180,
                        "min_quality": "accepted",
                        "similarity_threshold": 0.78,
                        "allowed_fields": ["account_type"],
                        "excluded_categories": ["security_incident", "vip_case"],
                    },
                },
                {
                    "result_type": "list",
                    "list_path": "tickets",
                    "target_value_path": "account_type",
                    "confidence_path": "confidence",
                    "display_value_path": "ticket_id",
                    "output_mapping": {},
                },
                "Для какой учетной записи нужен сброс?",
                status="planned",
                confidence_threshold=0.78,
            ),
        ],
    }


def default_classification_routes() -> dict[str, Any]:
    scenario_names = {
        item["scenario_id"]: item["display_name"]
        for item in DEFAULT_SCENARIOS
    }
    route_data = [
        (
            "password_reset",
            "P3",
            "auto_agent",
            "Сброс пароля через runbook после подтверждения в MVP.",
            "pending_approval",
            [
                classification_rule("сброс пароля", match_type="phrase", weight=0.9, explanation="Прямая фраза сброса пароля."),
                classification_rule("забыл пароль", match_type="phrase", weight=0.8, explanation="Пользователь сообщает, что забыл пароль."),
                classification_rule("пароль", match_type="word", weight=0.6, explanation="Упоминание пароля."),
                classification_rule("войти", match_type="word", weight=0.4, explanation="Проблема входа часто связана с паролем."),
                classification_rule("доступ", match_type="word", polarity="negative", weight=0.7, explanation="Запрос доступа относится к другому маршруту."),
                classification_rule("vpn", match_type="word", polarity="negative", weight=0.7, explanation="VPN чаще относится к сетевому маршруту."),
            ],
        ),
        (
            "software_issue",
            "P2",
            "agent_with_confirmation",
            "Диагностика приложения агентом и подтверждение человеком.",
            "pending_approval",
            [
                classification_rule("не запускается", match_type="phrase", weight=0.8, explanation="Признак проблемы запуска приложения."),
                classification_rule("ошибка", match_type="word", weight=0.5, explanation="Пользователь сообщает об ошибке приложения."),
                classification_rule("приложение", match_type="word", weight=0.6, explanation="Явное упоминание приложения."),
                classification_rule("пароль", match_type="word", polarity="negative", weight=0.6, explanation="Пароль относится к маршруту сброса пароля."),
                classification_rule("сеть", match_type="word", polarity="negative", weight=0.5, explanation="Сеть относится к сетевому маршруту."),
            ],
        ),
        (
            "hardware_issue",
            "P3",
            "agent_with_confirmation",
            "Проверка устройства и эскалация оператору при необходимости.",
            "pending_approval",
            [
                classification_rule("ноутбук", match_type="word", weight=0.7, explanation="Упоминание пользовательского устройства."),
                classification_rule("устройство", match_type="word", weight=0.5, explanation="Общий аппаратный признак."),
                classification_rule("принтер", match_type="word", weight=0.7, explanation="Принтер относится к аппаратной поддержке."),
                classification_rule("экран", match_type="word", weight=0.5, explanation="Частый аппаратный симптом."),
                classification_rule("пароль", match_type="word", polarity="negative", weight=0.7, explanation="Пароль относится к маршруту сброса пароля."),
            ],
        ),
        (
            "network_issue",
            "P1",
            "human_review",
            "Передача сетевого обращения оператору для ручной проверки приоритета и масштаба.",
            "escalation_required",
            [
                classification_rule("не работает vpn", match_type="phrase", weight=0.9, explanation="Прямой сетевой симптом VPN."),
                classification_rule("нет сети", match_type="phrase", weight=0.9, explanation="Прямой сетевой симптом."),
                classification_rule("vpn", match_type="word", weight=0.7, explanation="Упоминание VPN."),
                classification_rule("сеть", match_type="word", weight=0.6, explanation="Упоминание сети."),
                classification_rule("недоступно", match_type="word", weight=0.4, explanation="Симптом недоступности."),
                classification_rule("пароль", match_type="word", polarity="negative", weight=0.7, explanation="Пароль относится к маршруту сброса пароля."),
            ],
        ),
        (
            "access_request",
            "P3",
            "approver",
            "Запрос руководителю на согласование доступа.",
            "pending_approval",
            [
                classification_rule("запрос доступа", match_type="phrase", weight=0.9, explanation="Прямая фраза запроса доступа."),
                classification_rule("доступ", match_type="word", weight=0.7, explanation="Упоминание доступа."),
                classification_rule("права", match_type="word", weight=0.6, explanation="Упоминание прав доступа."),
                classification_rule("группа", match_type="word", weight=0.5, explanation="Группа доступа."),
                classification_rule("пароль", match_type="word", polarity="negative", weight=0.7, explanation="Пароль относится к маршруту сброса пароля."),
            ],
        ),
        (
            "unknown",
            "P4",
            "human_review",
            "Передача человеку с подсказками по вероятным категориям.",
            "escalation_required",
            [
                classification_rule("помогите", match_type="word", weight=0.4, explanation="Общее обращение без явной категории."),
                classification_rule("проблема", match_type="word", weight=0.3, explanation="Общее описание проблемы."),
                classification_rule("непонятно", match_type="word", weight=0.5, explanation="Пользователь не может сформулировать категорию."),
            ],
        ),
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
                    "rule_items": rule_items,
                },
                "top_categories_on_low_confidence": 3,
            }
            for scenario_id, priority, route, action, workflow_state_id, rule_items in route_data
        ],
    }


def default_orchestrator_policy() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "confidence_defaults": copy.deepcopy(DEFAULT_CONFIDENCE_THRESHOLDS),
        "editor_reference_hints": normalize_editor_reference_hints(None),
        "policies": [
            {
                "policy_id": f"policy.{item['scenario_id']}",
                "display_name": f"Политика оркестрации: {item['display_name']}",
                "max_iterations": 6,
                "consecutive_capability_errors_to_escalate": 2,
                "stop_conditions": [
                    "all_required_slots_filled",
                    "capability_success",
                    "clarification_required",
                    "handoff_required",
                    "iteration_limit",
                    "consecutive_capability_errors",
                ],
                "allowed_orchestration_action_groups": [
                    "read_diagnostics",
                    "knowledge_search",
                    "external_status_check",
                    "action_preparation",
                    "state_changing_actions",
                    "communication_handoff",
                ],
            }
            for item in DEFAULT_SCENARIOS
        ],
    }


def default_prompt_packs() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "packs": [
            {
                "prompt_pack_id": f"prompt.{item['scenario_id']}",
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
        "behavior_principles": "Задавай один вопрос за раз. Не раскрывай внутренние capability-вызовы клиенту. Пиши без жаргона и фиксируй недостающие данные.",
        "slot_schemas": "Собирай слоты в порядке кто -> что -> когда. Используй auto-fill источники до вопроса клиенту. Напоминания, timeout ожидания и действия при отсутствии ответа применяй из выбранного канала взаимодействия.",
        "classification_confidence": "Сначала используй правила классификации с позитивными и негативными признаками. Если confidence ниже 0.85, используй LLM few-shot. Если ниже 0.70, передай человеку с топ-3 категориями. Если ниже 0.50, не принимай финальное решение автоматически.",
        "orchestration": "Используй цикл оркестрации. Максимум 6 итераций. При двух ошибках capability подряд запускай действие эскалации выбранного канала.",
        "capability_rules": "Проверяй required slots и parameter bindings перед каждым capability-вызовом. Action-вызовы выполняются только в рамках политики исполнения.",
        "escalation_response": "Передавай оператору через канал эскалации полный пакет: слоты, историю capability, результаты capability, гипотезу причины, остаток SLA и текст уведомления клиента.",
    }


def build_prompt_preview(prompt_pack: dict[str, Any]) -> str:
    block_titles = {
        "role_context": "1. Роль и контекст",
        "behavior_principles": "2. Принципы поведения",
        "slot_schemas": "3. Схемы слотов",
        "classification_confidence": "4. Классификация и confidence",
        "orchestration": "5. Оркестрация",
        "capability_rules": "6. Правила capability",
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
                    "requires_capability_success": True,
                },
                "handoff_conditions": [
                    "two_capability_errors",
                    "iteration_limit",
                    "confidence_below_050",
                    "policy_blocked",
                ],
                "handoff_package": [
                    "slots",
                    "capability_history",
                    "capability_results",
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
                "prompt_id": "capability_selection.default",
                "prompt_type": "capability_selection",
                "display_name": "Выбор capability",
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
            "capability_selection": default_alias,
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
            "system_prompts": {
                "slot_resolution": DEFAULT_SLOT_RESOLUTION_PROMPT_TEMPLATE,
                "capability_step_assist": DEFAULT_CAPABILITY_STEP_ASSIST_PROMPT_TEMPLATE,
            },
        },
        "runtime": {
            "active_backend": active_provider,
            "openai_api_key_configured": secret_env_configured(openai_key_env),
        },
    }
