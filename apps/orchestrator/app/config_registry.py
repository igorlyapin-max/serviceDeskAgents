from __future__ import annotations

import copy
import json
import os
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request

from jsonschema import Draft202012Validator, SchemaError

from .action_gates import DEFAULT_STATE_DB_PATH, utc_now
from .contracts import CONTRACTS_ROOT, ContractRegistry, ContractValidationError, load_json
from .http_client import urlopen_with_retry
from .privacy import redact_for_llm


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
    "autofill_source_ref",
    "examples",
}

SLOT_METHOD_ALLOWED_FIELDS = {
    "user_question": {"user_question"},
    "case": {"case_source_ref"},
    "llm_extraction": {"extraction_instruction", "examples"},
    "slot_autofill": {"autofill_source_ref"},
    "resolution_profile": {"resolution_profile_id", "fallback_question"},
    "operator_manual": {"operator_hint"},
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

AGENT_OUTCOME_LABELS = {
    "success": "Успешно",
    "needs_review": "Нужна проверка данных",
    "waiting": "Ожидает клиента",
    "escalated": "Эскалировано",
    "error": "Ошибка",
}

AGENT_OUTCOME_NEXT_STEPS = {
    "success": "Проверьте заполненные данные и подготовленные ReAct-вызовы.",
    "needs_review": "Проверьте спорные данные, недостающие слоты или ожидающие подтверждения действия.",
    "waiting": "Передайте клиенту уточняющий вопрос и продолжите обработку после ответа.",
    "escalated": "Проверьте пакет передачи и передайте обращение в настроенный канал эскалации.",
    "error": "Исправьте конфигурацию, mock или контракт и повторите тестовый прогон.",
}

SIMULATION_RUN_MODES = {
    "config_check": {
        "display_name": "Проверка конфигурации",
        "allow_llm": False,
        "allow_readonly_integrations": False,
        "allow_mock_integrations": False,
        "allow_action_with_approval": False,
    },
    "llm": {
        "display_name": "С моделью",
        "allow_llm": True,
        "allow_readonly_integrations": False,
        "allow_mock_integrations": False,
        "allow_action_with_approval": False,
    },
    "llm_readonly": {
        "display_name": "С моделью и безопасными интеграциями",
        "allow_llm": True,
        "allow_readonly_integrations": True,
        "allow_mock_integrations": True,
        "allow_action_with_approval": False,
    },
    "approval_debug": {
        "display_name": "Отладочный запуск с подтверждениями",
        "allow_llm": True,
        "allow_readonly_integrations": True,
        "allow_mock_integrations": True,
        "allow_action_with_approval": True,
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
    "n8n.diagnostics": "n8n",
    "n8n.identity": "n8n",
    "n8n.systemcenter.runbooks": "n8n",
}

ENDPOINT_DISPLAY_NAME_OVERRIDES = {
    "mock": "Тестовое подключение интеграций",
    "n8n": "n8n webhook AI ServiceDesk",
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


def schema_properties(schema: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return {}
    properties = schema.get("properties", {})
    return properties if isinstance(properties, dict) else {}


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
        if not current:
            return None
        properties = schema_properties(current)
        current = properties.get(raw_part)
        if current is None:
            return None
    return current


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


def default_parameter_mapping(
    tool: dict[str, Any],
    operation: dict[str, Any] | None = None,
) -> dict[str, str]:
    operation_schema = operation.get("request_schema") if operation else None
    operation_names = list(dict.fromkeys([
        *schema_required(operation_schema),
        *schema_properties(operation_schema).keys(),
    ]))
    tool_schema = tool.get("parameters_schema", {})
    tool_names = set(schema_required(tool_schema))
    tool_names.update(schema_properties(tool_schema))
    if not operation_names:
        operation_names = list(dict.fromkeys([
            *schema_required(tool_schema),
            *schema_properties(tool_schema).keys(),
        ]))
    result = {}
    for name in operation_names:
        if name in tool_names:
            result[name] = f"react:{name}"
        elif name == "login" and "user_login" in tool_names:
            result[name] = "react:user_login"
    return result


def default_result_mapping(
    tool: dict[str, Any],
    operation: dict[str, Any] | None = None,
) -> dict[str, str]:
    tool_schema = tool.get("result_schema", {})
    response_schema = operation.get("response_schema") if operation else None
    response_properties = schema_properties(response_schema)
    result = {}
    for name in dict.fromkeys([
        *schema_required(tool_schema),
        *schema_properties(tool_schema).keys(),
    ]):
        if name in response_properties:
            result[name] = name
    return result


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
    elif simulation.get("awaiting_client_response") or simulation.get("next_question"):
        status = "waiting"
        summary = "Агенту не хватает данных: сформирован вопрос клиенту."
    elif (
        missing_slots
        or low_confidence_slots
        or ambiguous_resolution
        or final_decision in {"pending_auto_fill", "waiting_operator_approval"}
    ):
        status = "needs_review"
        summary = "Агент дошел до спорного состояния: требуется проверка данных или подтверждение действия."
    else:
        status = "success"
        summary = "Агент собрал обязательные данные и не нашел блокирующих проблем в тестовом прогоне."

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
        "ready_react_calls": [
            compact_agent_dict(
                {
                    "react_call": item.get("tool_name"),
                    "endpoint_id": item.get("endpoint_id"),
                    "operation_id": item.get("operation_id"),
                    "status": item.get("status", "ready"),
                    "parameters": item.get("parameters"),
                }
            )
            for item in ready_calls
        ],
        "blocked_react_calls": [
            compact_agent_dict(
                {
                    "react_call": item.get("tool_name"),
                    "endpoint_id": item.get("endpoint_id"),
                    "operation_id": item.get("operation_id"),
                    "block_reasons": item.get("block_reasons"),
                    "missing_slots": item.get("missing_slots"),
                    "missing_parameter_slots": item.get("missing_parameter_slots"),
                    "unknown_required_slots": item.get("unknown_required_slots"),
                }
            )
            for item in blocked_calls
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


CANONICAL_REACT_PARAMETER_SCHEMAS = {
    "check_zabbix_status": object_schema(["target_ref"], {"target_ref": string_property()}),
    "query_cmdb_object": object_schema(["object_ref"], {"object_ref": string_property()}),
    "get_service_owner": object_schema(["target_ref"], {"target_ref": string_property()}),
    "search_known_incidents": object_schema(["query"], {"query": string_property()}),
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
            "users": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
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

    canonical_schema = canonical_react_parameter_schema(tool_name)
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


def canonical_react_parameter_schema(tool_name: str | None) -> dict[str, Any] | None:
    schema = CANONICAL_REACT_PARAMETER_SCHEMAS.get(str(tool_name or ""))
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
        for key in ("base_url", "base_url_env", "auth", "disabled_reason"):
            if not target.get(key) and endpoint.get(key):
                target[key] = endpoint[key]
        target["enabled"] = bool(target.get("enabled", False) or endpoint.get("enabled", False))

    payload["endpoints"] = list(endpoints_by_id.values())
    return payload


def slot_fill_method(slot: dict[str, Any]) -> str:
    if slot.get("fill_method"):
        return slot["fill_method"]
    return LEGACY_SLOT_SOURCE_METHODS.get(slot.get("source"), "resolution_profile")


def normalize_slot_definition(slot: dict[str, Any]) -> None:
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
    if fill_method == "slot_autofill":
        return {"autofill_source_ref": slot.get("autofill_source_ref")}
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


def normalize_simulation_options(
    *,
    run_mode: str | None = None,
    allow_llm: bool | None = None,
    allow_readonly_integrations: bool | None = None,
    allow_mock_integrations: bool | None = None,
    allow_action_with_approval: bool | None = None,
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
    ):
        if value is not None:
            options[key] = bool(value)
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


def resolved_dry_run_parameters(
    mapping: dict[str, Any],
    *,
    provided: dict[str, Any],
    slot_values: dict[str, Any] | None = None,
    enrichment_entities: dict[str, Any] | None = None,
    output_values: dict[str, Any] | None = None,
) -> dict[str, Any]:
    parameters: dict[str, Any] = {}
    slots = slot_values or {}
    entities = enrichment_entities or {}
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
        elif source == "entity":
            entity_name, _, field_path = source_value.partition(".")
            entity_result = (entities.get(entity_name) or {}).get("result")
            value = value_at_path(entity_result, field_path) if field_path else entity_result
        elif source == "constant":
            value = source_value
        elif source == "secret":
            value = "секрет скрыт"
        parameters[parameter] = value if value not in (None, "") else source_ref
    return parameters


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
        "messages": build_slot_extraction_prompt(scenario=scenario, slots=slots, text=redaction.text),
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


def normalize_attribute_resolution_profile(profile: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(profile)
    result.pop("allowed_scenarios", None)
    target_slot_id = result.get("target_slot_id") or result.get("output_slots", ["value"])[0]

    legacy_steps = result.pop("steps", [])
    result.pop("resolution_mode", None)
    result.pop("attempt_scope", None)
    legacy_ambiguity = result.pop("ambiguity_policy", {})
    legacy_handoff_package = result.pop("operator_handoff_package", None)
    legacy_candidate_mapping = result.pop("candidate_mapping", None)

    if "input_slots" not in result:
        input_slots: list[dict[str, Any]] = []
        seen_slots: set[str] = set()
        legacy_input_slots = result.pop("input_slots", [])
        for slot_id in legacy_input_slots:
            if slot_id in seen_slots:
                continue
            seen_slots.add(slot_id)
            input_slots.append({
                "slot_id": slot_id,
                "required_for_operation": True,
                "can_ask_user": True,
                "description": f"Входной слот {humanize_config_id(slot_id)}.",
            })
        for attribute in result.get("input_attributes", []):
            if attribute.get("source") != "slot":
                continue
            slot_id = attribute.get("source_ref") or attribute.get("attribute_id")
            if not slot_id or slot_id in seen_slots:
                continue
            seen_slots.add(slot_id)
            input_slots.append({
                "slot_id": slot_id,
                "required_for_operation": bool(attribute.get("required", True)),
                "can_ask_user": True,
                "description": attribute.get("display_name") or humanize_config_id(slot_id),
            })
        if not input_slots:
            input_slots.append({
                "slot_id": target_slot_id,
                "required_for_operation": False,
                "can_ask_user": True,
                "description": f"Основной слот {humanize_config_id(target_slot_id)}.",
            })
        result["input_slots"] = input_slots

    if "resolver_operation" not in result:
        tool_step = next((step for step in legacy_steps if step.get("type") == "tool_call"), None)
        history_step = next((step for step in legacy_steps if step.get("type") == "ticket_history_search"), None)
        candidate_source = result.get("candidate_source")
        if candidate_source:
            normalize_endpoint_reference(candidate_source)
            resolver_operation = {
                "source_type": candidate_source.get("source_type", "disabled"),
                "tool_name": candidate_source.get("tool_name"),
                "endpoint_id": candidate_source.get("endpoint_id"),
                "operation_id": candidate_source.get("operation_id"),
                "parameter_mapping": slot_parameter_mapping_from_legacy(
                    candidate_source.get("parameter_mapping", {}),
                    result.get("input_attributes", []),
                ),
            }
            if candidate_source.get("history_filter"):
                resolver_operation["history_filter"] = candidate_source["history_filter"]
        elif tool_step:
            resolver_operation = {
                "source_type": "react_call",
                "tool_name": tool_step.get("tool_name"),
                "endpoint_id": normalize_endpoint_id(tool_step.get("endpoint_id")),
                "operation_id": tool_step.get("operation_id"),
                "parameter_mapping": slot_parameter_mapping_from_legacy(
                    tool_step.get("parameter_bindings", {}),
                    result.get("input_attributes", []),
                ),
            }
        elif history_step:
            resolver_operation = {
                "source_type": "ticket_history",
                "history_filter": history_step.get("history_filter", {}),
                "parameter_mapping": {},
            }
        else:
            resolver_operation = {
                "source_type": "disabled",
                "parameter_mapping": {},
            }
        resolver_operation["parameter_mapping"] = resolver_operation.get("parameter_mapping", {})
        result["resolver_operation"] = compact_config_dict(resolver_operation, keep_empty={"parameter_mapping"})

    result_policy = result.get("result_policy") or result_policy_from_candidate_mapping(
        legacy_candidate_mapping,
        result.get("resolver_operation", {}).get("tool_name"),
        target_slot_id,
    )
    if "operation_result_entity" not in result:
        result["operation_result_entity"] = operation_result_entity_from_policy(
            result.get("resolver_operation", {}),
            result_policy,
        )
    if "enrichment_steps" not in result:
        result["enrichment_steps"] = enrichment_steps_from_legacy(
            result.get("resolver_operation", {}),
            result.get("operation_result_entity", {}),
        )
    if "output_slots_order" not in result:
        output_slots = result.get("output_slots") or [target_slot_id]
        result["output_slots_order"] = output_slots_order_from_policy(
            target_slot_id,
            output_slots,
            result_policy,
        )
    if target_slot_id not in [item["slot_id"] for item in result["output_slots_order"]]:
        result["output_slots_order"].insert(
            0,
            {
                "slot_id": target_slot_id,
                "order": 1,
                "required_for_success": True,
                "source_hint": target_slot_id,
                "fallback": "ask_clarification",
            },
        )
    result["output_slots_order"] = normalize_output_slot_order(result["output_slots_order"], target_slot_id)

    fallback = result.setdefault(
        "fallback",
        {
            "action": "operator_handoff",
            "question": "Не удалось однозначно заполнить атрибут.",
        },
    )
    if "human_resolution_policy" not in result:
        clarification_question = (
            result.get("clarification_policy", {}).get("question")
            or legacy_ambiguity.get("question")
            or fallback.get("question")
            or "Уточните данные для заполнения атрибута."
        )
        output_slot_ids = [item["slot_id"] for item in result["output_slots_order"]]
        input_slot_ids = [item["slot_id"] for item in result["input_slots"]]
        clarification_slots = [
            slot_id
            for slot_id in (
                result.get("clarification_policy", {}).get("ask_for_attributes")
                or legacy_ambiguity.get("ask_for_attributes")
                or input_slot_ids
            )
            if slot_id in input_slot_ids or slot_id in output_slot_ids
        ] or input_slot_ids[:1] or output_slot_ids[:1]
        handoff_package = [
            slot_id
            for slot_id in (
                result.get("handoff_policy", {}).get("package")
                or legacy_handoff_package
                or [*input_slot_ids, *output_slot_ids]
            )
            if slot_id in input_slot_ids or slot_id in output_slot_ids
        ] or output_slot_ids[:1]
        result["human_resolution_policy"] = {
            "clarification_question": clarification_question,
            "clarification_slots": clarification_slots,
            "handoff_package": handoff_package,
            "handoff_action": result.get("handoff_policy", {}).get("action", "operator_handoff"),
            "fallback_action": fallback.get("action", "operator_handoff"),
        }
    if "llm_resolution_script" not in result:
        result["llm_resolution_script"] = {
            "script_text": default_resolution_script_text(result),
            "response_contract": default_resolution_response_contract(),
        }

    for legacy_key in (
        "input_attributes",
        "candidate_source",
        "result_policy",
        "decision_policy",
        "clarification_policy",
        "handoff_policy",
        "output_slots",
        "resolver_operation",
        "operation_result_entity",
    ):
        result.pop(legacy_key, None)
    result.setdefault("max_attempts", 1)
    result.setdefault("audit_required", True)
    result.setdefault("log_required", True)
    return result


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
    if resolver_operation.get("source_type") != "react_call" or not resolver_operation.get("tool_name"):
        return []
    entity_name = result_entity.get("entity_name") or resolver_operation.get("operation_id") or "result"
    return [
        {
            "step_name": f"Получить {humanize_config_id(entity_name)}",
            "react_call": resolver_operation["tool_name"],
            "parameter_mapping": resolver_operation.get("parameter_mapping", {}),
            "result_entity_name": entity_name,
            "result_entity_description": result_entity.get("entity_description")
            or f"Результат ReAct-вызова {humanize_config_id(resolver_operation['tool_name'])}.",
            "result_fields": result_entity.get("available_fields", []),
            "on_error": "continue_to_llm",
        }
    ]


def result_entity_from_enrichment_step(step: dict[str, Any] | None) -> dict[str, Any]:
    step = step or {}
    return {
        "entity_name": step.get("result_entity_name") or "result",
        "entity_description": step.get("result_entity_description") or "Результат ReAct-вызова.",
        "available_fields": step.get("result_fields", []),
    }


def output_slots_order_from_policy(
    target_slot_id: str,
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


def normalize_output_slot_order(items: list[dict[str, Any]], target_slot_id: str) -> list[dict[str, Any]]:
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
            "source_hint": item.get("source_hint") or slot_id,
            "fallback": item.get("fallback") or ("ask_clarification" if slot_id == target_slot_id else "leave_empty"),
        })
    return normalized


def normalize_slot_autofill_profile(profile: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(profile)
    result.setdefault("status", "draft")
    result["enabled"] = result.get("status") == "active"
    result.setdefault("run_order", 1)
    result.setdefault("accept_policy", "single_result")
    result.setdefault("input_mapping", {})
    result.setdefault("output_mapping", [])
    result.setdefault("on_no_result", "continue")
    result.setdefault("on_ambiguous_result", "ask_client")
    normalized_output = []
    seen: set[tuple[str, str]] = set()
    for item in result.get("output_mapping", []):
        result_field = item.get("result_field")
        target_slot = item.get("target_slot")
        if not result_field or not target_slot:
            continue
        key = (result_field, target_slot)
        if key in seen:
            continue
        seen.add(key)
        normalized_output.append(
            {
                "result_field": result_field,
                "target_slot": target_slot,
                "required_for_success": bool(item.get("required_for_success", False)),
            }
        )
    result["output_mapping"] = normalized_output
    return result


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
    entity_names = ", ".join(
        step.get("result_entity_name", "result")
        for step in profile.get("enrichment_steps", [])
    ) or "нет результатов ReAct-вызовов"
    return (
        "Проанализируй входные слоты и именованные результаты ReAct-вызовов. "
        f"Доступные сущности результата: {entity_names}. "
        f"Заполняй только разрешенные выходные слоты: {output_slots or profile.get('target_slot_id')}. "
        "Если результат однозначный, верни decision=fill и filled_slots. "
        "Если данных недостаточно или кандидатов несколько, верни decision=ask_clarification и один уточняющий вопрос. "
        "Если уверенно решить нельзя после попыток, верни decision=handoff."
    )


def operation_response_items(
    operation_result: dict[str, Any],
    result_entity: dict[str, Any],
) -> tuple[int, dict[str, Any] | None, dict[str, Any]]:
    entity_name = result_entity.get("entity_name")
    if entity_name:
        raw = value_at_path(operation_result, entity_name)
        if isinstance(raw, list):
            return len(raw), (raw[0] if raw else None), {
                "result_type": "list",
                "entity_name": entity_name,
                "item_count": len(raw),
                "source_status": "mock_output",
            }
        if isinstance(raw, dict):
            return 1, raw, {
                "result_type": "object",
                "entity_name": entity_name,
                "object_found": True,
                "source_status": "mock_output",
            }
    for key, value in operation_result.items():
        if isinstance(value, list):
            return len(value), (value[0] if value else None), {
                "result_type": "list",
                "entity_name": key,
                "item_count": len(value),
                "source_status": "mock_output",
            }
    object_found = operation_result.get("object_found")
    if object_found is False:
        return 0, None, {
            "result_type": "object",
            "entity_name": entity_name or "result",
            "object_found": False,
            "source_status": "mock_output",
        }
    return 1, operation_result, {
        "result_type": "object",
        "entity_name": entity_name or "result",
        "object_found": True,
        "source_status": "mock_output",
    }


def operation_result_value(result_item: dict[str, Any] | None, source_hint: str, entity_name: str | None = None) -> Any:
    if not result_item or not source_hint:
        return None
    hint = str(source_hint).replace("[]", "")
    if entity_name and hint.startswith(f"{entity_name}."):
        hint = hint[len(entity_name) + 1 :]
    return value_at_path(result_item, hint)


def is_missing_autofill_value(value: Any) -> bool:
    return value is None or value == "" or value == []


def simulated_llm_resolution_decision(
    *,
    profile: dict[str, Any],
    result_item: dict[str, Any] | None,
    count: int,
    confidence: float,
    effective_thresholds: dict[str, float],
) -> dict[str, Any]:
    human_policy = profile["human_resolution_policy"]
    enrichment_steps = profile.get("enrichment_steps", [])
    entity_name = enrichment_steps[-1].get("result_entity_name") if enrichment_steps else None
    output_values = {}
    if count == 1 and result_item:
        for rule in profile["output_slots_order"]:
            value = operation_result_value(result_item, rule.get("source_hint", ""), entity_name)
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
    return {
        "decision": "ask_clarification",
        "status": "question_required",
        "filled_slots": {},
        "confidence": confidence,
        "next_question": human_policy["clarification_question"],
        "reason": reason,
    }


def resolution_profile_question(profile: dict[str, Any]) -> str | None:
    human_policy = profile.get("human_resolution_policy", {})
    if human_policy.get("clarification_question"):
        return human_policy["clarification_question"]
    return profile.get("fallback", {}).get("question")


def resolution_profile_current_step(profile: dict[str, Any]) -> dict[str, Any] | None:
    for step in profile.get("steps", []):
        if step["type"] in {"clarification", "operator_handoff", "escalate"}:
            return step
    return profile.get("steps", [None])[-1]


def tool_usage_refs(
    tool_name: str,
    matrix_payload: dict[str, Any],
    resolution_payload: dict[str, Any],
    channels_payload: dict[str, Any],
    slot_autofill_payload: dict[str, Any] | None = None,
) -> list[str]:
    refs = []
    for matrix in matrix_payload.get("matrices", []):
        for launch in matrix.get("launches", []):
            if launch.get("tool_name") == tool_name:
                refs.append(f"matrix:{matrix.get('matrix_id')}/{launch.get('launch_id')}")
    for profile in resolution_payload.get("profiles", []):
        if any(step.get("react_call") == tool_name for step in profile.get("enrichment_steps", [])):
            refs.append(f"attribute_resolution_profile:{profile.get('profile_id')}")
    for profile in (slot_autofill_payload or {}).get("profiles", []):
        if profile.get("react_call") == tool_name:
            refs.append(f"slot_autofill_profile:{profile.get('profile_id')}")
    for channel in channels_payload.get("channels", []):
        for action_key in ("question_delivery", "incomplete_discussion_action", "escalation_action"):
            if channel.get(action_key, {}).get("tool_name") == tool_name:
                refs.append(f"interaction_channel:{channel.get('channel_id')}/{action_key}")
        for profile in channel.get("action_profiles", []):
            if profile.get("action", {}).get("tool_name") == tool_name:
                refs.append(f"interaction_channel:{channel.get('channel_id')}/profile:{profile.get('profile_id')}")
    return refs


def endpoint_operation_usage_refs(
    endpoint_id: str,
    operation_id: str,
    tools_payload: dict[str, Any],
    workflows_payload: dict[str, Any],
) -> list[str]:
    refs = []
    for tool in tools_payload.get("tools", []):
        for binding in tool.get("endpoint_bindings", []):
            if binding.get("endpoint_id") == endpoint_id and binding.get("operation_id") == operation_id:
                refs.append(f"react_call:{tool.get('tool_name')}")
    for workflow in workflows_payload.get("workflows", []):
        if workflow.get("endpoint_id") == endpoint_id and operation_id in workflow.get("operations", []):
            refs.append(f"n8n_workflow:{workflow.get('workflow_id')}")
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
    "tool_launch_matrix": ConfigDomain(
        domain="tool_launch_matrix",
        title="Матрица запуска ReAct-вызовов",
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
        title="Каталог ReAct-вызовов ИИ",
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
    "slot_autofill_profiles": ConfigDomain(
        domain="slot_autofill_profiles",
        title="Профили автозаполнения слотов",
        contract_name="slot_autofill_profiles",
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
        if domain == "interaction_channels":
            return default_interaction_channels()
        if domain == "attribute_resolution_profiles":
            return default_attribute_resolution_profiles()
        if domain == "slot_autofill_profiles":
            return default_slot_autofill_profiles()
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
                scenario.setdefault("default_channel_id", "debug")
                scenario.setdefault("allowed_channel_ids", ["messenger_bot", "service_desk", "debug"])
                if scenario.get("confidence_overrides") is not None:
                    scenario["confidence_overrides"] = normalize_confidence_thresholds(
                        scenario.get("confidence_overrides"),
                    )
        elif domain == "tools":
            endpoint_by_id = {
                endpoint["endpoint_id"]: endpoint
                for endpoint in self.active_payload("integration_endpoints").get("endpoints", [])
            }
            for tool in normalized.get("tools", []):
                tool.get("policy", {}).pop("allowed_environments", None)
                tool.setdefault("contract_version", "1.0")
                tool.setdefault("contract_status", "valid")
                tool.setdefault("result_schema", default_response_schema())
                canonical_schema = canonical_react_parameter_schema(tool.get("tool_name"))
                if canonical_schema:
                    tool["parameters_schema"] = canonical_schema
                seen_bindings: set[tuple[str | None, str | None]] = set()
                normalized_bindings = []
                for binding in tool.get("endpoint_bindings", []):
                    normalize_endpoint_binding(binding)
                    endpoint = endpoint_by_id.get(binding.get("endpoint_id"))
                    operation = endpoint.get("operations", {}).get(binding.get("operation_id")) if endpoint else None
                    if operation:
                        normalize_operation_definition(binding.get("operation_id"), operation)
                    if canonical_schema:
                        binding["parameter_mapping"] = default_parameter_mapping(tool, operation)
                    else:
                        binding.setdefault("parameter_mapping", default_parameter_mapping(tool, operation))
                    binding.setdefault("result_mapping", default_result_mapping(tool, operation))
                    binding_key = (binding.get("endpoint_id"), binding.get("operation_id"))
                    if binding_key in seen_bindings:
                        continue
                    seen_bindings.add(binding_key)
                    normalized_bindings.append(binding)
                tool["endpoint_bindings"] = normalized_bindings
        elif domain == "attribute_resolution_profiles":
            normalized["profiles"] = [
                normalize_attribute_resolution_profile(profile)
                for profile in normalized.get("profiles", [])
            ]
        elif domain == "slot_autofill_profiles":
            normalized["profiles"] = [
                normalize_slot_autofill_profile(profile)
                for profile in normalized.get("profiles", [])
            ]
        elif domain == "slot_schemas":
            for slot_schema in normalized.get("slot_schemas", []):
                slot_schema.pop("scenario_id", None)
                for slot in slot_schema.get("slots", []):
                    normalize_slot_definition(slot)
                    if slot.get("confidence_overrides") is not None:
                        slot["confidence_overrides"] = normalize_confidence_thresholds(
                            slot.get("confidence_overrides"),
                        )
        elif domain == "classification_routes":
            route_mapping = {
                "agent_l1": "agent_with_confirmation",
                "l1_hint": "human_review",
                "l2_major_incident": "major_incident",
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
            for policy in normalized.get("policies", []):
                scenario_id = policy.pop("scenario_id", None)
                policy.setdefault("display_name", f"ReAct-политика: {scenario_names.get(scenario_id or '', policy['policy_id'])}")
        elif domain == "tool_launch_matrix" and "launches" in normalized:
            grouped_launches: dict[str, list[dict[str, Any]]] = {}
            for launch in normalized.get("launches", []):
                launch_copy = copy.deepcopy(launch)
                scenario_id = launch_copy.pop("scenario_id", "custom")
                normalize_endpoint_reference(launch_copy)
                normalize_tool_launch_parameter_bindings(launch_copy)
                grouped_launches.setdefault(scenario_id, []).append(launch_copy)
            normalized = {
                "schema_version": normalized.get("schema_version", "1.0"),
                "matrices": [
                    {
                        "matrix_id": f"matrix.{scenario_id}",
                        "display_name": f"Матрица ReAct-вызовов: {scenario_names.get(scenario_id, scenario_id)}",
                        "launches": launches,
                    }
                    for scenario_id, launches in grouped_launches.items()
                ],
            }
        elif domain == "tool_launch_matrix":
            for matrix in normalized.get("matrices", []):
                matrix.setdefault("display_name", f"Матрица ReAct-вызовов: {matrix['matrix_id']}")
                for launch in matrix.get("launches", []):
                    launch.pop("scenario_id", None)
                    normalize_endpoint_reference(launch)
                    normalize_tool_launch_parameter_bindings(launch)
        elif domain == "escalation_policies":
            for policy in normalized.get("policies", []):
                scenario_id = policy.pop("scenario_id", None)
                policy.setdefault("display_name", f"Решение и эскалация: {scenario_names.get(scenario_id or '', policy['policy_id'])}")
                policy.pop("channel_profile_mapping", None)
                policy.get("major_incident", {}).pop("notify_on_call", None)
        elif domain == "interaction_channels":
            for channel in normalized.get("channels", []):
                channel.setdefault("action_profiles", default_channel_action_profiles(channel))
                for action_key in ("question_delivery", "incomplete_discussion_action", "escalation_action"):
                    normalize_endpoint_reference(channel.get(action_key, {}))
                for profile in channel.get("action_profiles", []):
                    normalize_endpoint_reference(profile.get("action", {}))
        elif domain == "integration_endpoints":
            normalized = merge_legacy_integration_endpoints(normalized)
            for endpoint in normalized.get("endpoints", []):
                for operation_id, operation in endpoint.get("operations", {}).items():
                    normalize_operation_definition(operation_id, operation)
                    operation.setdefault("display_name", humanize_config_id(operation_id))
                    operation.setdefault(
                        "description",
                        f"Техническая операция подключения {endpoint['endpoint_id']}.",
                    )
        elif domain == "n8n_workflows":
            for workflow in normalized.get("workflows", []):
                normalize_endpoint_reference(workflow)
                if workflow.get("callback_endpoint_id"):
                    workflow["callback_endpoint_id"] = normalize_endpoint_id(workflow["callback_endpoint_id"])
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
        interaction_channel = self._by_id(
            self.active_payload("interaction_channels")["channels"],
            "channel_id",
        ).get(scenario.get("default_channel_id", "debug"))
        profile_by_id = self._by_id(
            self.active_payload("attribute_resolution_profiles")["profiles"],
            "profile_id",
        )
        slot_autofill_profiles = [
            profile
            for profile in self.active_payload("slot_autofill_profiles").get("profiles", [])
            if profile.get("slot_schema_id") == scenario["slot_schema_id"]
            and profile.get("enabled", True)
        ]
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
                if slot_fill_method(slot) == "slot_autofill":
                    mapped = any(
                        slot["slot_id"] == item.get("target_slot")
                        for profile in slot_autofill_profiles
                        for item in profile.get("output_mapping", [])
                    )
                    if not mapped:
                        missing.append(f"slot_autofill_profile:{slot['slot_id']}")
            for launch in launches:
                for required_slot_id in launch.get("required_slots", []):
                    if required_slot_id not in slot_ids:
                        missing.append(f"tool_launch_required_slot:{launch['launch_id']}:{required_slot_id}")
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
        channel_action_profiles = resolve_channel_action_profiles(interaction_channel)
        return {
            "schema_version": "1.0",
            "scenario": scenario,
            "slot_schema": slot_schema,
            "attribute_resolution_profiles": scenario_profiles,
            "slot_autofill_profiles": slot_autofill_profiles,
            "route": route,
            "orchestrator_policy": policy,
            "tool_launch_matrix": tool_launch_matrix,
            "tool_launches": launches,
            "interaction_channel": interaction_channel,
            "channel_action_profiles": channel_action_profiles,
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
        tool_catalog = self.active_payload("tools")
        endpoint_catalog = self.active_payload("integration_endpoints")
        tool_by_name = self._by_id(tool_catalog["tools"], "tool_name")
        endpoint_by_id = self._by_id(endpoint_catalog["endpoints"], "endpoint_id")

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
        matrix = detail.get("tool_launch_matrix") if detail else None
        launches = detail.get("tool_launches", []) if detail else []
        prompt_pack = detail.get("prompt_pack") if detail else None
        escalation_policy = detail.get("escalation_policy") if detail else None
        channel = detail.get("interaction_channel") if detail else None
        launch_tool_names = sorted({launch.get("tool_name") for launch in launches if launch.get("tool_name")})
        launch_tools = [tool_by_name[tool_name] for tool_name in launch_tool_names if tool_name in tool_by_name]
        endpoint_ids = sorted({
            binding.get("endpoint_id")
            for tool in launch_tools
            for binding in tool.get("endpoint_bindings", [])
            if binding.get("endpoint_id")
        })
        launch_endpoints = [
            endpoint_by_id[endpoint_id]
            for endpoint_id in endpoint_ids
            if endpoint_id in endpoint_by_id
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
                "0. Слоты",
                x=250,
                y=210,
                step_number=0,
                status=item_status(slot_schema) if detail else "valid",
                description="Сбор обязательных данных: один вопрос за раз, приоритет кто -> что -> когда.",
                config_refs=[
                    config_ref(
                        domain="slot_schemas",
                        title="Схема слотов",
                        item=slot_schema,
                        id_key="slot_schema_id",
                        view_name="scenarioSlots",
                    ),
                ],
                metrics=[
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
                "1. Разрешение атрибутов",
                x=460,
                y=210,
                step_number=1,
                status="valid" if not detail or profiles else "partial",
                description="Заполнение атрибутов через входные слоты, ReAct-операции, LLM-правило, уточнение у клиента и эскалацию оператору.",
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
                "react_planning",
                "3. ReAct-планирование",
                x=880,
                y=210,
                step_number=3,
                status=item_status(policy) if detail else "valid",
                description="Цикл Думай -> Действуй -> Наблюдай со стоп-условиями и лимитом итераций.",
                config_refs=[
                    config_ref(
                        domain="orchestrator_policy",
                        title="Политика ReAct",
                        item=policy,
                        id_key="policy_id",
                        view_name="scenarioReact",
                    ),
                ],
                metrics=[
                    {
                        "label": "Итераций",
                        "value": policy.get("max_iterations") if policy else "н/д",
                    },
                    {
                        "label": "Ошибок до стопа",
                        "value": policy.get("consecutive_tool_errors_to_escalate") if policy else "н/д",
                    },
                ] if detail else [],
            ),
            node(
                "tool_use",
                "4. ReAct-вызовы и матрица запуска",
                x=1090,
                y=210,
                step_number=4,
                status=item_status(matrix) if detail else "valid",
                description="Выбор разрешенных ReAct-вызовов, уровня запуска, обязательных слотов и согласований.",
                config_refs=[
                    config_ref(
                        domain="tool_launch_matrix",
                        title="Матрица запуска",
                        item=matrix,
                        id_key="matrix_id",
                        view_name="scenarioTools",
                    ),
                ],
                metrics=[
                    {
                        "label": "Запусков",
                        "value": len(launches),
                    },
                    {
                        "label": "ReAct-вызовов",
                        "value": len(launch_tool_names),
                    },
                ] if detail else [],
            ),
            node(
                "endpoint_contracts",
                "Контракты endpoint",
                x=1090,
                y=370,
                node_type="configuration",
                description="Технические endpoint-операции и привязка их ответа к результату ReAct-вызова.",
                config_refs=[
                    *[
                        {
                            "domain": "tools",
                            "title": "ReAct-вызов",
                            "id": tool["tool_name"],
                            "display_name": tool.get("description") or tool["tool_name"],
                            "view": "reactCalls",
                        }
                        for tool in launch_tools
                    ],
                    *[
                        {
                            "domain": "integration_endpoints",
                            "title": "Endpoint",
                            "id": endpoint["endpoint_id"],
                            "display_name": endpoint.get("display_name") or endpoint["endpoint_id"],
                            "view": "integrations",
                        }
                        for endpoint in launch_endpoints
                    ],
                ],
                metrics=[
                    {
                        "label": "Endpoint",
                        "value": len(launch_endpoints),
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
                description="Финальное решение: автозакрытие, ожидание ответа клиента, эскалация оператору или Major Incident.",
                config_refs=[
                    config_ref(
                        domain="escalation_policies",
                        title="Политика решения",
                        item=escalation_policy,
                        id_key="policy_id",
                        view_name="scenarioEscalation",
                    ),
                ],
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
            edge("prompt_pack", "react_planning", "ReAct-правила", edge_type="support"),
            edge("interaction_channel", "slot_filling", "доставка вопросов", edge_type="support"),
            edge("slot_filling", "attribute_resolution", "нужны атрибуты"),
            edge("attribute_resolution", "waiting", "вопрос клиенту", condition="не хватает данных", edge_type="support"),
            edge("waiting", "slot_filling", "ответ клиента", condition="возобновить сценарий", edge_type="loop"),
            edge("attribute_resolution", "classification", "слоты готовы"),
            edge("classification", "react_planning", "маршрут выбран"),
            edge("classification", "escalation", "эскалация оператору", condition="major incident или низкая уверенность"),
            edge("react_planning", "tool_use", "выбран ReAct-вызов"),
            edge("endpoint_contracts", "tool_use", "binding и result mapping", edge_type="support"),
            edge("tool_use", "react_planning", "наблюдение", condition="итерация продолжается", edge_type="loop"),
            edge("react_planning", "decision", "стоп-условие"),
            edge("tool_use", "decision", "результат действия"),
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
        thresholds.update(normalize_confidence_thresholds((scenario or {}).get("confidence_overrides")))
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

    def _slot_candidate_value(
        self,
        *,
        slot_id: str,
        provided: dict[str, Any],
        llm_result_by_slot: dict[str, dict[str, Any]],
        autofill_values: dict[str, dict[str, Any]],
        thresholds_by_slot: dict[str, dict[str, float]],
    ) -> Any:
        if slot_id in provided:
            return provided[slot_id]
        if slot_id in autofill_values:
            return autofill_values[slot_id].get("value")
        llm_result = llm_result_by_slot.get(slot_id)
        if llm_result:
            threshold = thresholds_by_slot.get(slot_id, DEFAULT_CONFIDENCE_THRESHOLDS)["min_extraction_confidence"]
            if llm_result.get("value") is not None and llm_result.get("confidence", 0.0) >= threshold:
                return llm_result.get("value")
        return None

    def _simulate_slot_autofill_profile(
        self,
        *,
        profile: dict[str, Any],
        provided: dict[str, Any],
        llm_result_by_slot: dict[str, dict[str, Any]],
        autofill_values: dict[str, dict[str, Any]],
        thresholds_by_slot: dict[str, dict[str, float]],
        simulation_options: dict[str, Any],
        execution_trace: list[dict[str, Any]],
    ) -> dict[str, Any]:
        tool_by_name = self._by_id(self.active_payload("tools")["tools"], "tool_name")
        endpoint_by_id = self._by_id(
            self.active_payload("integration_endpoints")["endpoints"],
            "endpoint_id",
        )
        tool = tool_by_name.get(profile.get("react_call", ""))
        binding = (tool or {}).get("endpoint_bindings", [None])[0]
        endpoint_id = (binding or {}).get("endpoint_id")
        operation_id = (binding or {}).get("operation_id")
        endpoint = endpoint_by_id.get(endpoint_id or "")
        operation = (endpoint or {}).get("operations", {}).get(operation_id or "")
        default_result = {
            "profile_id": profile["profile_id"],
            "profile_name": profile["display_name"],
            "react_call": profile.get("react_call"),
            "status": "pending",
            "output_values": {},
            "filled_slots": [],
            "missing_parameters": [],
            "missing_required_result_fields": [],
            "missing_required_slots": [],
            "result_summary": None,
            "reason": "",
        }
        if not tool or not binding or not endpoint or not operation:
            append_trace(
                execution_trace,
                step="1",
                status="blocked",
                title=f"Автозаполнение слотов: {profile['display_name']}",
                message="ReAct-вызов или его привязка к endpoint-операции не найдены.",
                details={"react_call": profile.get("react_call"), "endpoint_id": endpoint_id, "operation_id": operation_id},
            )
            return {**default_result, "status": "blocked_by_configuration", "reason": "ReAct-вызов автозаполнения не настроен."}
        if tool.get("action_type") != "read_only":
            append_trace(
                execution_trace,
                step="1",
                status="blocked",
                title=f"Автозаполнение слотов: {profile['display_name']}",
                message="Автозаполнение допускает только read-only ReAct-вызовы.",
            )
            return {**default_result, "status": "blocked_by_configuration", "reason": "ReAct-вызов не является read-only."}

        adapter_type = endpoint.get("adapter_type")
        if adapter_type == "mock" and not simulation_options["allow_mock_integrations"]:
            append_trace(
                execution_trace,
                step="1",
                status="skipped",
                title=f"Автозаполнение слотов: {profile['display_name']}",
                message="Mock-интеграции выключены в выбранном режиме тестового прогона.",
                details={"endpoint_id": endpoint_id, "operation_id": operation_id},
            )
            return {**default_result, "status": "skipped", "reason": "Mock-интеграции выключены в выбранном режиме тестового прогона."}
        if adapter_type != "mock" and not simulation_options["allow_readonly_integrations"]:
            append_trace(
                execution_trace,
                step="1",
                status="skipped",
                title=f"Автозаполнение слотов: {profile['display_name']}",
                message="Внешние read-only интеграции выключены в выбранном режиме тестового прогона.",
                details={"endpoint_id": endpoint_id, "operation_id": operation_id},
            )
            return {**default_result, "status": "skipped", "reason": "Read-only интеграции выключены в выбранном режиме тестового прогона."}

        parameters: dict[str, Any] = {}
        missing_parameters: list[str] = []
        required_parameters = set(tool.get("parameters_schema", {}).get("required", []))
        for parameter, source_ref in profile.get("input_mapping", {}).items():
            source, separator, source_value = str(source_ref).partition(":")
            if separator != ":":
                continue
            value: Any = None
            if source == "slot":
                value = self._slot_candidate_value(
                    slot_id=source_value,
                    provided=provided,
                    llm_result_by_slot=llm_result_by_slot,
                    autofill_values=autofill_values,
                    thresholds_by_slot=thresholds_by_slot,
                )
            elif source in {"case", "context"}:
                value = f"{source}:{source_value}"
            elif source == "constant":
                value = source_value
            elif source == "secret":
                value = "секрет скрыт"
            if value in (None, "") and parameter in required_parameters:
                missing_parameters.append(parameter)
            elif value not in (None, ""):
                parameters[parameter] = value

        if missing_parameters:
            append_trace(
                execution_trace,
                step="1",
                status="blocked",
                title=f"Автозаполнение слотов: {profile['display_name']}",
                message=f"Не заполнены обязательные параметры ReAct-вызова: {', '.join(missing_parameters)}.",
                details={
                    "react_call": profile.get("react_call"),
                    "endpoint_id": endpoint_id,
                    "operation_id": operation_id,
                    "parameters": parameters,
                    "missing_parameters": missing_parameters,
                    "result": {"status": "not_executed", "reason": "Не заполнены обязательные параметры ReAct-вызова."},
                },
            )
            return {
                **default_result,
                "status": "missing_parameters",
                "missing_parameters": missing_parameters,
                "reason": "Не заполнены обязательные параметры ReAct-вызова автозаполнения.",
            }

        mock_output = copy.deepcopy(operation.get("mock_output") or {})
        if not mock_output:
            append_trace(
                execution_trace,
                step="1",
                status="blocked",
                title=f"Автозаполнение слотов: {profile['display_name']}",
                message="В dry-run нет mock_output для ReAct-вызова автозаполнения.",
                details={
                    "react_call": profile.get("react_call"),
                    "endpoint_id": endpoint_id,
                    "operation_id": operation_id,
                    "parameters": parameters,
                    "result": {"status": "not_executed", "reason": "Для endpoint-операции не задан mock_output."},
                },
            )
            return {**default_result, "status": "blocked_by_configuration", "reason": "Нет mock_output для dry-run."}

        candidate_count = mock_output.get("candidate_count")
        if candidate_count is None:
            candidate_count = 1 if mock_output else 0
        accept_policy = profile.get("accept_policy", "single_result")
        if accept_policy == "single_result" and candidate_count != 1:
            reason = "Операция не вернула результатов." if candidate_count == 0 else "Операция вернула несколько результатов."
            append_trace(
                execution_trace,
                step="1",
                status="blocked",
                title=f"Автозаполнение слотов: {profile['display_name']}",
                message=reason,
                details={
                    "react_call": profile.get("react_call"),
                    "endpoint_id": endpoint_id,
                    "operation_id": operation_id,
                    "parameters": parameters,
                    "result": mock_output,
                    "candidate_count": candidate_count,
                },
            )
            return {
                **default_result,
                "status": "ambiguous" if candidate_count > 1 else "no_result",
                "result_summary": {"candidate_count": candidate_count, "source": f"{endpoint_id}/{operation_id}"},
                "reason": reason,
            }

        output_values = {}
        filled_slot_values = []
        missing_required_result_fields = []
        for item in profile.get("output_mapping", []):
            value = value_at_path(mock_output, item["result_field"])
            if is_missing_autofill_value(value):
                if item.get("required_for_success"):
                    missing_required_result_fields.append(
                        {
                            "result_field": item["result_field"],
                            "target_slot": item["target_slot"],
                        }
                    )
                continue
            else:
                output_values[item["target_slot"]] = value
                filled_slot_values.append(
                    {
                        "result_field": item["result_field"],
                        "target_slot": item["target_slot"],
                        "value": value,
                    }
                )
        if missing_required_result_fields:
            missing_slots = sorted({item["target_slot"] for item in missing_required_result_fields})
            append_trace(
                execution_trace,
                step="1",
                status="blocked",
                title=f"Автозаполнение слотов: {profile['display_name']}",
                message="Не вернулись обязательные для профиля поля результата.",
                details={
                    "react_call": profile.get("react_call"),
                    "endpoint_id": endpoint_id,
                    "operation_id": operation_id,
                    "parameters": parameters,
                    "result": mock_output,
                    "output_values": output_values,
                    "filled_slot_values": filled_slot_values,
                    "missing_required_result_fields": missing_required_result_fields,
                    "output_slots": sorted(output_values),
                    "candidate_count": candidate_count,
                },
            )
            return {
                **default_result,
                "status": "missing_required_result_field",
                "output_values": output_values,
                "filled_slot_values": filled_slot_values,
                "filled_slots": sorted(output_values),
                "missing_required_result_fields": missing_required_result_fields,
                "missing_required_slots": missing_slots,
                "result_summary": {"candidate_count": candidate_count, "source": f"{endpoint_id}/{operation_id}"},
                "reason": "Не вернулись поля результата, обязательные для успешного автозаполнения профиля.",
            }
        filled_summary = "; ".join(
            f"{item['target_slot']} = {compact_trace_value(item['value'])} (из {item['result_field']})"
            for item in filled_slot_values
        )
        append_trace(
            execution_trace,
            step="1",
            status="completed" if output_values else "blocked",
            title=f"Автозаполнение слотов: {profile['display_name']}",
            message=(
                f"ReAct-вызов {profile.get('react_call')} заполнил: {filled_summary}."
                if filled_summary
                else f"ReAct-вызов {profile.get('react_call')} не заполнил слоты."
            ),
            details={
                "react_call": profile.get("react_call"),
                "endpoint_id": endpoint_id,
                "operation_id": operation_id,
                "parameters": parameters,
                "result": mock_output,
                "output_values": output_values,
                "filled_slot_values": filled_slot_values,
                "output_slots": sorted(output_values),
                "candidate_count": candidate_count,
            },
        )
        return {
            **default_result,
            "status": "filled" if output_values else "no_result",
            "output_values": output_values,
            "filled_slot_values": filled_slot_values,
            "filled_slots": sorted(output_values),
            "result_summary": {"candidate_count": candidate_count, "source": f"{endpoint_id}/{operation_id}"},
            "reason": (
                "Значения получены из детерминированного ReAct-автозаполнения."
                if output_values
                else "Операция не вернула значений для выбранных слотов."
            ),
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
            "status": "question_required" if question else "resolution_pending",
            "decision": "ask_clarification" if question else "operator_handoff",
            "attempt": 1,
            "max_attempts": profile["max_attempts"],
            "pending_question": question,
            "input_slots": profile.get("input_slots", []),
            "enrichment_steps": enrichment_steps,
            "enrichment_entities": {},
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
                message="Для профиля не настроено обогащение контекста через ReAct-вызовы.",
                details={"enrichment_steps": 0},
            )
            return {
                **default_result,
                "reason": "Обогащение контекста не настроено для выбранного профиля.",
            }

        endpoint_by_id = self._by_id(
            self.active_payload("integration_endpoints")["endpoints"],
            "endpoint_id",
        )
        tool_by_name = self._by_id(self.active_payload("tools")["tools"], "tool_name")
        enrichment_entities: dict[str, Any] = {}
        last_step: dict[str, Any] | None = None
        last_mock_output: dict[str, Any] | None = None
        last_endpoint_id = ""
        last_operation_id = ""

        for step_index, enrichment_step in enumerate(enrichment_steps, start=1):
            tool_name = enrichment_step.get("react_call")
            tool = tool_by_name.get(tool_name or "")
            binding = (tool or {}).get("endpoint_bindings", [None])[0]
            endpoint_id = (binding or {}).get("endpoint_id")
            operation_id = (binding or {}).get("operation_id")
            endpoint = endpoint_by_id.get(endpoint_id or "")
            operation = (endpoint or {}).get("operations", {}).get(operation_id or "")
            adapter_type = (endpoint or {}).get("adapter_type")
            if not tool or not binding or not endpoint or not operation:
                append_trace(
                    execution_trace,
                    step="1",
                    status="blocked",
                    title=f"Обогащение контекста: {enrichment_step.get('step_name') or profile['display_name']}",
                    message="ReAct-вызов или его привязка к endpoint-операции не найдены.",
                    details={"react_call": tool_name, "endpoint_id": endpoint_id, "operation_id": operation_id},
                )
                return {
                    **default_result,
                    "enrichment_entities": enrichment_entities,
                    "status": "blocked_by_configuration",
                    "decision": "handoff",
                    "reason": "ReAct-вызов обогащения контекста или его привязка не найдены.",
                }
            parameter_sources = enrichment_step.get("parameter_mapping", {})
            parameters = resolved_dry_run_parameters(
                parameter_sources,
                provided=provided,
                slot_values=slot_values,
                enrichment_entities=enrichment_entities,
            )
            if adapter_type == "mock" and not simulation_options["allow_mock_integrations"]:
                append_trace(
                    execution_trace,
                    step="1",
                    status="skipped",
                    title=f"Обогащение контекста: {enrichment_step.get('step_name') or profile['display_name']}",
                    message="Mock-интеграции выключены в выбранном режиме тестового прогона.",
                    details={
                        "react_call": tool_name,
                        "endpoint_id": endpoint_id,
                        "operation_id": operation_id,
                        "parameter_sources": parameter_sources,
                        "parameters": parameters,
                        "result": {"status": "not_executed", "reason": "Mock-интеграции выключены в выбранном режиме."},
                    },
                )
                return {
                    **default_result,
                    "enrichment_entities": enrichment_entities,
                    "reason": "Mock-интеграции выключены в выбранном режиме тестового прогона.",
                }
            if adapter_type != "mock" and not simulation_options["allow_readonly_integrations"]:
                append_trace(
                    execution_trace,
                    step="1",
                    status="skipped",
                    title=f"Обогащение контекста: {enrichment_step.get('step_name') or profile['display_name']}",
                    message="Внешние read-only интеграции выключены в выбранном режиме тестового прогона.",
                    details={
                        "react_call": tool_name,
                        "endpoint_id": endpoint_id,
                        "operation_id": operation_id,
                        "parameter_sources": parameter_sources,
                        "parameters": parameters,
                        "result": {"status": "not_executed", "reason": "Read-only интеграции выключены в выбранном режиме."},
                    },
                )
                return {
                    **default_result,
                    "enrichment_entities": enrichment_entities,
                    "reason": "Внешние read-only интеграции выключены в выбранном режиме тестового прогона.",
                }

            mock_output = copy.deepcopy(operation.get("mock_output") or {})
            if not mock_output:
                append_trace(
                    execution_trace,
                    step="1",
                    status="blocked",
                    title=f"Обогащение контекста: {enrichment_step.get('step_name') or profile['display_name']}",
                    message="В dry-run нет mock_output для ReAct-вызова обогащения контекста.",
                    details={
                        "react_call": tool_name,
                        "endpoint_id": endpoint_id,
                        "operation_id": operation_id,
                        "parameter_sources": parameter_sources,
                        "parameters": parameters,
                        "result": {"status": "not_executed", "reason": "Для endpoint-операции не задан mock_output."},
                    },
                )
                return {
                    **default_result,
                    "enrichment_entities": enrichment_entities,
                    "status": "blocked_by_configuration",
                    "decision": "handoff",
                    "reason": "В dry-run нет mock_output для ReAct-вызова обогащения контекста.",
                }

            entity_name = enrichment_step["result_entity_name"]
            enrichment_entities[entity_name] = {
                "step_name": enrichment_step.get("step_name"),
                "react_call": tool_name,
                "endpoint_id": endpoint_id,
                "operation_id": operation_id,
                "result": mock_output,
            }
            append_trace(
                execution_trace,
                step="1",
                status="completed",
                title=f"Обогащение контекста: {enrichment_step.get('step_name') or entity_name}",
                message=f"ReAct-вызов {tool_name} сохранил результат как {entity_name}.",
                details={
                    "step_index": step_index,
                    "react_call": tool_name,
                    "endpoint_id": endpoint_id,
                    "operation_id": operation_id,
                    "parameter_sources": parameter_sources,
                    "parameters": parameters,
                    "result": mock_output,
                    "result_entity_name": entity_name,
                },
            )
            last_step = enrichment_step
            last_mock_output = mock_output
            last_endpoint_id = endpoint_id or ""
            last_operation_id = operation_id or ""

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
                "enrichment_entities": enrichment_entities,
                "status": "blocked_by_configuration",
                "decision": "handoff",
                "reason": "Обогащение контекста не вернуло результата.",
            }

        result_entity = result_entity_from_enrichment_step(last_step)
        count, result_item, result_summary = operation_response_items(last_mock_output, result_entity)
        confidence = result_confidence(result_item, {"confidence_path": "confidence"})
        if not simulation_options["allow_llm"]:
            llm_decision = {
                "decision": "await_llm_rule",
                "status": "llm_resolution_pending",
                "filled_slots": {},
                "confidence": confidence,
                "next_question": question or human_policy["clarification_question"],
                "reason": "Режим тестового прогона не разрешает выполнение LLM-правила разрешения атрибута.",
            }
        else:
            llm_decision = simulated_llm_resolution_decision(
                profile=profile,
                result_item=result_item,
                count=count,
                confidence=confidence,
                effective_thresholds=effective_thresholds,
            )
        output_values = llm_decision.get("filled_slots", {})
        status = llm_decision.get("status", "question_required")
        decision = llm_decision.get("decision", "ask_clarification")
        reason = llm_decision.get("reason", "")

        append_trace(
            execution_trace,
            step="1",
            status="completed" if status == "filled" else "blocked",
            title=f"Разрешение атрибута: {profile['display_name']}",
            message=f"Результатов обогащения: {count}; решение LLM-правила: {decision}.",
            details={
                "enrichment_steps": len(enrichment_steps),
                "entity_name": result_entity.get("entity_name"),
                "confidence": confidence,
                "result": llm_decision,
                "output_slots": sorted(output_values),
            },
        )
        return {
            **default_result,
            "status": status,
            "decision": decision,
            "candidate_count": count,
            "candidate_confidence": confidence,
            "enrichment_entities": enrichment_entities,
            "output_values": output_values,
            "llm_decision": llm_decision,
            "pending_question": llm_decision.get("next_question") or question,
            "result_summary": {
                **result_summary,
                "count": count,
                "source": f"{last_endpoint_id}/{last_operation_id}",
            },
            "reason": reason,
        }

    def simulate_scenario(
        self,
        scenario_id: str,
        *,
        text: str,
        provided_slots: dict[str, Any] | None = None,
        run_mode: str | None = None,
        allow_llm: bool | None = None,
        allow_readonly_integrations: bool | None = None,
        allow_mock_integrations: bool | None = None,
        allow_action_with_approval: bool | None = None,
    ) -> dict[str, Any]:
        detail = self.scenario_detail(scenario_id)
        slot_schema = detail["slot_schema"] or {"slots": [], "question_order": []}
        known_slot_ids = {slot["slot_id"] for slot in slot_schema["slots"]}
        simulation_options = normalize_simulation_options(
            run_mode=run_mode,
            allow_llm=allow_llm,
            allow_readonly_integrations=allow_readonly_integrations,
            allow_mock_integrations=allow_mock_integrations,
            allow_action_with_approval=allow_action_with_approval,
        )
        execution_trace: list[dict[str, Any]] = []
        append_trace(
            execution_trace,
            step="0",
            status="started",
            title="Режим тестового прогона",
            message=simulation_options["display_name"],
            details={
                key: simulation_options[key]
                for key in (
                    "run_mode",
                    "allow_llm",
                    "allow_readonly_integrations",
                    "allow_mock_integrations",
                    "allow_action_with_approval",
                )
            },
        )
        profile_by_id = self._by_id(
            detail.get("attribute_resolution_profiles", []),
            "profile_id",
        )
        provided = provided_slots or {}
        llm_slots = [
            slot
            for slot in slot_schema["slots"]
            if slot_fill_method(slot) == "llm_extraction"
            and slot["slot_id"] not in provided
        ]
        llm_result_by_slot: dict[str, dict[str, Any]] = {}
        llm_error: dict[str, Any] | None = None
        if llm_slots and simulation_options["allow_llm"]:
            model_result = invoke_slot_extraction_model(
                model_config=self.active_payload("model_routing"),
                scenario=detail["scenario"],
                slots=llm_slots,
                text=text,
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
                        "provider": model_result.get("provider"),
                        "model": model_result.get("model"),
                        "duration_ms": model_result.get("duration_ms"),
                        "usage": model_result.get("usage", {}),
                        "redaction": model_result.get("redaction", {}),
                        "parameters": {"slot_ids": [slot["slot_id"] for slot in llm_slots]},
                        "result": llm_result_by_slot,
                    },
                )
            else:
                llm_error = model_result.get("error", {})
                append_trace(
                    execution_trace,
                    step="1",
                    status="error",
                    title="Извлечение слотов моделью",
                    message=llm_error.get("message", "Модель недоступна."),
                    details={
                        "provider": model_result.get("provider"),
                        "model": model_result.get("model"),
                        "code": llm_error.get("code"),
                        "redaction": model_result.get("redaction", {}),
                    },
                )
        elif llm_slots:
            append_trace(
                execution_trace,
                step="1",
                status="skipped",
                title="Извлечение слотов моделью",
                message="Режим тестового прогона не разрешает вызов LLM.",
                details={"slot_ids": [slot["slot_id"] for slot in llm_slots]},
            )
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
        autofill_values: dict[str, dict[str, Any]] = {}
        slot_autofill_steps = []
        for profile in sorted(detail.get("slot_autofill_profiles", []), key=lambda item: item.get("run_order", 999)):
            profile_result = self._simulate_slot_autofill_profile(
                profile=profile,
                provided=provided,
                llm_result_by_slot=llm_result_by_slot,
                autofill_values=autofill_values,
                thresholds_by_slot=thresholds_by_slot,
                simulation_options=simulation_options,
                execution_trace=execution_trace,
            )
            slot_autofill_steps.append(profile_result)
            for slot_id, value in profile_result.get("output_values", {}).items():
                if slot_id in provided:
                    continue
                autofill_values[slot_id] = {
                    "value": value,
                    "profile_id": profile["profile_id"],
                    "profile_name": profile["display_name"],
                    "react_call": profile.get("react_call"),
                    "reason": profile_result.get("reason"),
                }
        slot_values = {}
        missing_slots = []
        resolution_steps = []
        resolution_state = {}
        seen_resolution_profile_ids = set()
        profile_results: dict[str, dict[str, Any]] = {}
        for slot in slot_schema["slots"]:
            slot_id = slot["slot_id"]
            fill_method = slot_fill_method(slot)
            profile = profile_by_id.get(slot.get("resolution_profile_id", ""))
            effective_thresholds = self.effective_confidence_thresholds(
                scenario=detail["scenario"],
                slot=slot,
                profile=profile,
                include_profile=fill_method == "resolution_profile",
            )
            if slot_id in provided:
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
            elif slot_id in autofill_values:
                autofill_value = autofill_values[slot_id]
                slot_values[slot_id] = {
                    "status": "filled_by_slot_autofill",
                    "value": autofill_value.get("value"),
                    "fill_method": fill_method,
                    "source": "slot_autofill",
                    "slot_autofill_profile_id": autofill_value.get("profile_id"),
                    "react_call": autofill_value.get("react_call"),
                    "reason": autofill_value.get("reason"),
                    "effective_confidence_thresholds": effective_thresholds,
                    **slot_source_summary(slot),
                }
            elif fill_method == "resolution_profile":
                profile_id = profile["profile_id"] if profile else slot.get("resolution_profile_id")
                profile_result = None
                if profile:
                    if profile["profile_id"] not in profile_results:
                        profile_results[profile["profile_id"]] = self.simulate_attribute_resolution_profile(
                            profile=profile,
                            slot_schema=slot_schema,
                            provided=provided,
                            simulation_options=simulation_options,
                            effective_thresholds=effective_thresholds,
                            execution_trace=execution_trace,
                            slot_values=slot_values,
                        )
                    profile_result = profile_results[profile["profile_id"]]

                output_value = (profile_result or {}).get("output_values", {}).get(slot_id)
                if output_value is not None:
                    slot_values[slot_id] = {
                        "status": "filled_by_profile",
                        "value": output_value,
                        "fill_method": fill_method,
                        "source": "resolution_profile",
                        "resolution_profile_id": profile_id,
                        "confidence": (profile_result or {}).get("candidate_confidence"),
                        "reason": (profile_result or {}).get("reason"),
                        "effective_confidence_thresholds": effective_thresholds,
                        **slot_source_summary(slot),
                    }
                else:
                    slot_values[slot_id] = {
                        "status": (profile_result or {}).get("status", "resolution_pending"),
                        "value": None,
                        "fill_method": fill_method,
                        "source": "resolution_profile",
                        "resolution_profile_id": profile_id,
                        "effective_confidence_thresholds": effective_thresholds,
                        "reason": (profile_result or {}).get(
                            "reason",
                            "Профиль разрешения атрибута ожидает результат операции или уточнение.",
                        ),
                        **slot_source_summary(slot),
                    }
                    if slot["required"]:
                        missing_slots.append(slot_id)

                if profile and profile["profile_id"] not in seen_resolution_profile_ids:
                    seen_resolution_profile_ids.add(profile["profile_id"])
                    state_summary = {
                        "slot_id": slot_id,
                        **profile_result,
                    }
                    resolution_state[slot_id] = state_summary
                    resolution_steps.append(state_summary)
            elif fill_method in {"case", "llm_extraction"}:
                if fill_method == "llm_extraction":
                    extracted = llm_result_by_slot.get(slot_id)
                    if extracted:
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
                            "fill_method": fill_method,
                            "source": "llm",
                            "confidence": confidence,
                            "threshold_decision": decision,
                            "reason": extracted["reason"],
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
                                "confidence": confidence,
                                "min_extraction_confidence": effective_thresholds["min_extraction_confidence"],
                                "auto_accept_confidence": effective_thresholds["auto_accept_confidence"],
                                "decision": decision,
                            },
                        )
                        if slot["required"] and not accepted:
                            missing_slots.append(slot_id)
                    elif llm_error:
                        slot_values[slot_id] = {
                            "status": "model_unavailable",
                            "value": None,
                            "fill_method": fill_method,
                            "source": "llm",
                            "error": llm_error,
                            "reason": "Модель не вернула результат для слота.",
                            "effective_confidence_thresholds": effective_thresholds,
                            **slot_source_summary(slot),
                        }
                        if slot["required"]:
                            missing_slots.append(slot_id)
                    else:
                        slot_values[slot_id] = {
                            "status": "extraction_pending",
                            "value": None,
                            "fill_method": fill_method,
                            "source": "llm",
                            "reason": "Вызов модели не выполнялся в выбранном режиме тестового прогона.",
                            "effective_confidence_thresholds": effective_thresholds,
                            **slot_source_summary(slot),
                        }
                        if slot["required"]:
                            missing_slots.append(slot_id)
                else:
                    slot_values[slot_id] = {
                        "status": "auto_fill_candidate",
                        "value": None,
                        "fill_method": fill_method,
                        "source": "case",
                        "reason": "Чтение из данных обращения пока не выполняется в dry-run.",
                        "effective_confidence_thresholds": effective_thresholds,
                        **slot_source_summary(slot),
                    }
                    if slot["required"]:
                        missing_slots.append(slot_id)
            elif slot["required"]:
                slot_values[slot_id] = {
                    "status": "missing",
                    "value": None,
                    "fill_method": fill_method,
                    "reason": "Для обязательного слота нет заполненного значения.",
                    "effective_confidence_thresholds": effective_thresholds,
                    **slot_source_summary(slot),
                }
                missing_slots.append(slot_id)
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
        ready_launches = []
        blocked_launches = []
        next_allowed_actions = []
        tool_by_name = self._by_id(self.active_payload("tools")["tools"], "tool_name")
        endpoint_by_id = self._by_id(self.active_payload("integration_endpoints")["endpoints"], "endpoint_id")
        for launch in detail["tool_launches"]:
            tool = tool_by_name.get(launch["tool_name"], {})
            endpoint = endpoint_by_id.get(launch.get("endpoint_id"), {})
            unknown_required_slots = [
                slot_id
                for slot_id in launch["required_slots"]
                if slot_id not in known_slot_ids
            ]
            missing_for_launch = [
                slot_id
                for slot_id in launch["required_slots"]
                if slot_id in known_slot_ids and slot_id in missing_slots
            ]
            parameters = {}
            missing_parameter_slots = []
            for parameter_name, source_ref in launch.get("parameter_bindings", {}).items():
                source, separator, source_value = str(source_ref).partition(":")
                if separator != ":" or not source_value:
                    continue
                if source == "constant":
                    parameters[parameter_name] = source_value
                elif source == "slot":
                    slot_value = slot_values.get(source_value, {}).get("value")
                    if slot_value not in (None, ""):
                        parameters[parameter_name] = slot_value
                    else:
                        missing_parameter_slots.append(source_value)
                elif source == "secret":
                    parameters[parameter_name] = "секрет скрыт"
                elif source in {"case", "context"}:
                    parameters[parameter_name] = f"{source}:{source_value}"
            is_read_only = tool.get("action_type") == "read_only"
            is_mock_endpoint = endpoint.get("adapter_type") == "mock"
            block_reasons = []
            if unknown_required_slots:
                block_reasons.append("required slot отсутствует в схеме")
            if missing_for_launch:
                block_reasons.append("required slot не заполнен")
            if missing_parameter_slots:
                block_reasons.append("параметр вызова не заполнен")
            if is_read_only:
                if not simulation_options["allow_readonly_integrations"]:
                    block_reasons.append("read-only интеграции не разрешены выбранным режимом")
                if is_mock_endpoint and not simulation_options["allow_mock_integrations"]:
                    block_reasons.append("mock-интеграции не разрешены выбранным режимом")
            elif not simulation_options["allow_action_with_approval"]:
                block_reasons.append("action-вызов доступен только в режиме с подтверждениями")
            launch_summary = {
                "launch_id": launch["launch_id"],
                "tool_name": launch["tool_name"],
                "execution_level": launch["execution_level"],
                "target_execution_level": launch["target_execution_level"],
                "missing_slots": missing_for_launch,
                "unknown_required_slots": unknown_required_slots,
                "missing_parameter_slots": missing_parameter_slots,
                "parameters": parameters,
                "action_type": tool.get("action_type"),
                "endpoint_id": launch.get("endpoint_id"),
                "operation_id": launch.get("operation_id"),
                "block_reasons": block_reasons,
            }
            if block_reasons:
                append_trace(
                    execution_trace,
                    step="4",
                    status="blocked",
                    title=f"ReAct-вызов {launch['tool_name']}",
                    message="; ".join(block_reasons),
                    details={
                        "react_call": launch["tool_name"],
                        "endpoint_id": launch.get("endpoint_id"),
                        "operation_id": launch.get("operation_id"),
                        "launch_id": launch["launch_id"],
                        "parameters": parameters,
                        "missing_slots": missing_for_launch,
                        "unknown_required_slots": unknown_required_slots,
                        "missing_parameter_slots": missing_parameter_slots,
                        "result": {"status": "not_executed", "reason": "Вызов заблокирован условиями тестового прогона."},
                    },
                )
                blocked_launches.append(launch_summary)
            else:
                if not is_read_only and simulation_options["allow_action_with_approval"]:
                    launch_summary["status"] = "approval_required"
                    next_allowed_actions.append(
                        {
                            "action": "request_operator_approval",
                            "launch_id": launch["launch_id"],
                            "tool_name": launch["tool_name"],
                            "parameters": parameters,
                        }
                    )
                    append_trace(
                        execution_trace,
                        step="4",
                        status="approval_required",
                        title=f"ReAct-вызов {launch['tool_name']}",
                        message="Action-вызов подготовлен и требует подтверждения оператора.",
                        details={
                            "react_call": launch["tool_name"],
                            "endpoint_id": launch.get("endpoint_id"),
                            "operation_id": launch.get("operation_id"),
                            "launch_id": launch["launch_id"],
                            "parameters": parameters,
                            "result": {"status": "approval_required"},
                        },
                    )
                else:
                    launch_summary["status"] = "ready"
                    append_trace(
                        execution_trace,
                        step="4",
                        status="ready",
                        title=f"ReAct-вызов {launch['tool_name']}",
                        message="Вызов готов в выбранном режиме тестового прогона.",
                        details={
                            "react_call": launch["tool_name"],
                            "endpoint_id": launch.get("endpoint_id"),
                            "operation_id": launch.get("operation_id"),
                            "launch_id": launch["launch_id"],
                            "parameters": parameters,
                            "result": {"status": "prepared", "reason": "Вызов не исполнялся, только подготовлен в dry-run."},
                        },
                    )
                ready_launches.append(launch_summary)
        interaction_channel = detail.get("interaction_channel") or {}
        channel_action_profiles = detail.get("channel_action_profiles") or {}
        standard_profile = channel_action_profiles.get("standard_handoff") or {}
        missing_slot_set = set(missing_slots)
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
        elif missing_slots:
            final_decision = "pending_auto_fill"
        elif blocking_configuration:
            final_decision = "blocked_by_configuration"
        elif any(item.get("status") == "approval_required" for item in ready_launches):
            final_decision = "waiting_operator_approval"
        else:
            final_decision = "ready_for_react"
        client_question = {
            "required": bool(next_question),
            "question": next_question,
            "delivery": interaction_channel.get("question_delivery"),
            "waiting_policy": interaction_channel.get("waiting_policy"),
            "resume_after_answer": bool(next_question),
            "semantic": "client_clarification",
        }
        operator_escalation_required = (
            final_decision == "blocked_by_configuration"
            or classification.get("decision_level") == "human_required"
            or classification.get("route") in {"human_review", "major_incident"}
        )
        operator_escalation_reason = None
        if operator_escalation_required:
            if final_decision == "blocked_by_configuration":
                operator_escalation_reason = "Конфигурация или параметры ReAct-вызова не позволяют продолжить автообработку."
            elif classification.get("route") == "major_incident":
                operator_escalation_reason = "Маршрут требует немедленной обработки как Major Incident."
            elif classification.get("decision_level") == "human_required":
                operator_escalation_reason = "Уверенность классификации ниже порога самостоятельного решения."
            else:
                operator_escalation_reason = "Маршрут требует участия оператора."
        escalation_action = standard_profile.get("action") or interaction_channel.get("escalation_action")
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
        simulation_result = {
            "schema_version": "1.0",
            "scenario_id": scenario_id,
            "input_text": text,
            "run_mode": simulation_options["run_mode"],
            "simulation_options": simulation_options,
            "interaction_channel": interaction_channel,
            "channel_action_profiles": channel_action_profiles,
            "question_delivery": interaction_channel.get("question_delivery"),
            "waiting_policy": interaction_channel.get("waiting_policy"),
            "incomplete_discussion_action": interaction_channel.get("incomplete_discussion_action"),
            "escalation_action": escalation_action,
            "slot_values": slot_values,
            "missing_slots": missing_slots,
            "next_question": next_question,
            "next_client_question": next_question,
            "client_question": client_question,
            "awaiting_client_response": bool(next_question),
            "operator_escalation": operator_escalation,
            "escalation_package": escalation_package if operator_escalation_required else None,
            "slot_autofill": slot_autofill_steps,
            "attribute_resolution": resolution_steps,
            "resolution_state": resolution_state,
            "classification": classification,
            "ready_tool_launches": ready_launches,
            "blocked_tool_launches": blocked_launches,
            "next_allowed_actions": next_allowed_actions,
            "execution_trace": execution_trace,
            "final_decision": final_decision,
            "dry_run": True,
        }
        simulation_result["agent_outcome"] = build_agent_outcome_from_simulation(simulation_result)
        return simulation_result

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
        if domain == "interaction_channels":
            return self._validate_interaction_channels(payload)
        if domain == "attribute_resolution_profiles":
            return self._validate_attribute_resolution_profiles(payload)
        if domain == "slot_autofill_profiles":
            return self._validate_slot_autofill_profiles(payload)
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
        endpoint_catalog = self.active_payload("integration_endpoints")
        endpoint_by_id = {
            endpoint["endpoint_id"]: endpoint
            for endpoint in endpoint_catalog["endpoints"]
        }
        tool_names = [tool["tool_name"] for tool in payload["tools"]]
        for tool_name in self._duplicates(tool_names):
            errors.append(f"Дублируется tool_name: {tool_name}")

        for tool in payload["tools"]:
            tool_name = tool["tool_name"]
            if tool.get("contract_status") == "broken":
                refs = tool_usage_refs(
                    tool_name,
                    self.active_payload("tool_launch_matrix"),
                    self.active_payload("attribute_resolution_profiles"),
                    self.active_payload("interaction_channels"),
                    self.active_payload("slot_autofill_profiles"),
                )
                if refs:
                    errors.append(f"{tool_name} имеет contract_status=broken и используется: {', '.join(refs)}.")
            for schema_key in ("parameters_schema", "result_schema"):
                try:
                    Draft202012Validator.check_schema(tool[schema_key])
                except SchemaError as error:
                    errors.append(f"{tool_name} {schema_key} невалидна: {error.message}")
            binding_keys = [
                f"{binding['endpoint_id']}::{binding['operation_id']}"
                for binding in tool["endpoint_bindings"]
            ]
            for binding_key in self._duplicates(binding_keys):
                errors.append(f"{tool_name} содержит дублирующуюся привязку endpoint/operation: {binding_key}")
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
                    continue
                operation = endpoint["operations"][binding["operation_id"]]
                errors.extend(self._validate_binding_parameter_mapping(tool, binding, operation))
        errors.extend(self._validate_tool_catalog_usage(payload))
        return errors

    def _validate_integration_endpoint_catalog(self, payload: dict[str, Any]) -> list[str]:
        endpoint_ids = [endpoint["endpoint_id"] for endpoint in payload["endpoints"]]
        errors = [f"Дублируется endpoint_id: {endpoint_id}" for endpoint_id in self._duplicates(endpoint_ids)]
        endpoint_by_id = {
            endpoint["endpoint_id"]: endpoint
            for endpoint in payload["endpoints"]
        }
        for endpoint in payload["endpoints"]:
            if endpoint.get("enabled") and endpoint.get("adapter_type") not in {"mock", "n8n_webhook"}:
                errors.append(
                    f"{endpoint['endpoint_id']} adapter_type={endpoint['adapter_type']} пока не исполняется; "
                    "включенными могут быть только mock или n8n_webhook."
                )
            for operation_id, operation in endpoint["operations"].items():
                if operation.get("contract_status") == "broken":
                    refs = endpoint_operation_usage_refs(
                        endpoint["endpoint_id"],
                        operation_id,
                        self.active_payload("tools"),
                        self.active_payload("n8n_workflows"),
                    )
                    if refs:
                        errors.append(
                            f"{endpoint['endpoint_id']}/{operation_id} имеет contract_status=broken "
                            f"и используется: {', '.join(refs)}."
                        )
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
                if operation.get("mock_output") is not None:
                    validator = Draft202012Validator(operation["response_schema"])
                    for error in validator.iter_errors(operation["mock_output"]):
                        errors.append(
                            f"{endpoint['endpoint_id']}/{operation_id} mock_output не соответствует response_schema: "
                            f"{error.message}"
                        )
                for example in operation.get("mock_examples", []):
                    validator = Draft202012Validator(operation["response_schema"])
                    for error in validator.iter_errors(example.get("response_example", {})):
                        errors.append(
                            f"{endpoint['endpoint_id']}/{operation_id} mock_example "
                            f"{example.get('example_id')} не соответствует response_schema: {error.message}"
                        )
        for tool in self.active_payload("tools")["tools"]:
            for binding in tool["endpoint_bindings"]:
                endpoint = endpoint_by_id.get(binding["endpoint_id"])
                if not endpoint:
                    errors.append(
                        f"{tool['tool_name']} ссылается на отсутствующий endpoint_id: {binding['endpoint_id']}"
                    )
                    continue
                if binding["operation_id"] not in endpoint["operations"]:
                    errors.append(
                        f"{tool['tool_name']} ссылается на отсутствующую operation "
                        f"{binding['operation_id']} для endpoint {binding['endpoint_id']}"
                    )
                    continue
                errors.extend(
                    self._validate_binding_parameter_mapping(
                        tool,
                        binding,
                        endpoint["operations"][binding["operation_id"]],
                    )
                )
        for workflow in self.active_payload("n8n_workflows")["workflows"]:
            endpoint = endpoint_by_id.get(workflow["endpoint_id"])
            if not endpoint:
                errors.append(
                    f"Workflow n8n {workflow['workflow_id']} ссылается на отсутствующий endpoint_id: "
                    f"{workflow['endpoint_id']}"
                )
            else:
                for operation_id in workflow.get("operations", []):
                    if operation_id not in endpoint["operations"]:
                        errors.append(
                            f"Workflow n8n {workflow['workflow_id']} ссылается на отсутствующую operation "
                            f"{operation_id} для endpoint {workflow['endpoint_id']}"
                        )
            callback_endpoint_id = workflow.get("callback_endpoint_id")
            if callback_endpoint_id and callback_endpoint_id not in endpoint_by_id:
                errors.append(
                    f"Workflow n8n {workflow['workflow_id']} ссылается на отсутствующий callback_endpoint_id: "
                    f"{callback_endpoint_id}"
                )
        return errors

    @staticmethod
    def _validate_binding_parameter_mapping(
        tool: dict[str, Any],
        binding: dict[str, Any],
        operation: dict[str, Any],
    ) -> list[str]:
        errors = []
        tool_name = tool["tool_name"]
        operation_id = binding.get("operation_id")
        endpoint_id = binding.get("endpoint_id")
        mapping = binding.get("parameter_mapping", {})
        if not isinstance(mapping, dict):
            return [f"{tool_name}/{endpoint_id}/{operation_id} parameter_mapping должен быть object."]

        operation_schema = operation.get("request_schema", default_request_schema())
        operation_properties = schema_properties(operation_schema)
        operation_required = schema_required(operation_schema)
        tool_parameter_names = set(schema_required(tool.get("parameters_schema")))
        tool_parameter_names.update(schema_properties(tool.get("parameters_schema")))

        missing_required = [
            parameter
            for parameter in operation_required
            if parameter not in mapping
        ]
        for parameter in missing_required:
            errors.append(
                f"{tool_name}/{endpoint_id}/{operation_id} не заполняет обязательный параметр операции: {parameter}"
            )

        if operation_schema.get("additionalProperties") is False:
            for parameter in mapping:
                if parameter not in operation_properties:
                    errors.append(
                        f"{tool_name}/{endpoint_id}/{operation_id} маппит параметр вне request_schema операции: {parameter}"
                    )

        for target_parameter, source_ref in mapping.items():
            source, separator, source_value = str(source_ref).partition(":")
            if separator != ":" or source not in {"react", "constant", "secret"} or not source_value:
                errors.append(
                    f"{tool_name}/{endpoint_id}/{operation_id} parameter_mapping.{target_parameter} "
                    "должен иметь формат react:<param>, constant:<value> или secret:<env>."
                )
                continue
            if source == "react" and source_value not in tool_parameter_names:
                errors.append(
                    f"{tool_name}/{endpoint_id}/{operation_id} parameter_mapping.{target_parameter} "
                    f"ссылается на отсутствующий параметр ReAct-вызова: {source_value}"
                )
                continue
            if source == "react":
                operation_parameter_schema = operation_properties.get(target_parameter)
                react_parameter_schema = schema_properties(tool.get("parameters_schema")).get(source_value)
                if not schemas_are_type_compatible(react_parameter_schema, operation_parameter_schema):
                    errors.append(
                        f"{tool_name}/{endpoint_id}/{operation_id} parameter_mapping.{target_parameter} "
                        f"имеет несовместимые типы: ReAct {schema_type(react_parameter_schema)} -> endpoint {schema_type(operation_parameter_schema)}"
                    )

        result_mapping = binding.get("result_mapping", {})
        if not isinstance(result_mapping, dict):
            errors.append(f"{tool_name}/{endpoint_id}/{operation_id} result_mapping должен быть object.")
            return errors

        tool_result_schema = tool.get("result_schema", default_response_schema())
        operation_response_schema = operation.get("response_schema", default_response_schema())
        tool_result_properties = schema_properties(tool_result_schema)
        required_result_fields = schema_required(tool_result_schema)
        missing_result_fields = [
            field_name
            for field_name in required_result_fields
            if field_name not in result_mapping
        ]
        for field_name in missing_result_fields:
            errors.append(
                f"{tool_name}/{endpoint_id}/{operation_id} не маппит обязательное поле результата ReAct-вызова: {field_name}"
            )

        if tool_result_schema.get("additionalProperties") is False:
            for field_name in result_mapping:
                if field_name not in tool_result_properties:
                    errors.append(
                        f"{tool_name}/{endpoint_id}/{operation_id} result_mapping.{field_name} "
                        "маппит поле вне result_schema ReAct-вызова."
                    )

        for react_field, endpoint_path in result_mapping.items():
            target_schema = tool_result_properties.get(react_field)
            source_schema = schema_at_path(operation_response_schema, endpoint_path)
            if react_field not in tool_result_properties:
                errors.append(
                    f"{tool_name}/{endpoint_id}/{operation_id} result_mapping.{react_field} "
                    "ссылается на отсутствующее поле result_schema ReAct-вызова."
                )
                continue
            if not source_schema:
                errors.append(
                    f"{tool_name}/{endpoint_id}/{operation_id} result_mapping.{react_field} "
                    f"ссылается на отсутствующее поле response_schema операции: {endpoint_path}"
                )
                continue
            if not schemas_are_type_compatible(source_schema, target_schema):
                errors.append(
                    f"{tool_name}/{endpoint_id}/{operation_id} result_mapping.{react_field} "
                    f"имеет несовместимые типы: endpoint {schema_type(source_schema)} -> ReAct {schema_type(target_schema)}"
                )
        return errors

    @staticmethod
    def _tool_binding_exists(
        tool: dict[str, Any],
        endpoint_id: str | None,
        operation_id: str | None,
    ) -> bool:
        return any(
            binding["endpoint_id"] == endpoint_id and binding["operation_id"] == operation_id
            for binding in tool.get("endpoint_bindings", [])
        )

    def _validate_tool_catalog_usage(self, payload: dict[str, Any]) -> list[str]:
        errors = []
        tool_by_name = {
            tool["tool_name"]: tool
            for tool in payload["tools"]
        }
        for matrix in self.active_payload("tool_launch_matrix")["matrices"]:
            for launch in matrix["launches"]:
                tool = tool_by_name.get(launch["tool_name"])
                if not tool:
                    errors.append(
                        f"Матрица {matrix['matrix_id']} ссылается на отсутствующий tool_name: "
                        f"{launch['tool_name']}"
                    )
                    continue
                if not tool.get("endpoint_bindings"):
                    errors.append(
                        f"Матрица {matrix['matrix_id']} / {launch['launch_id']} ссылается на ReAct-вызов "
                        f"{launch['tool_name']} без привязки операции"
                    )
        for profile in self.active_payload("attribute_resolution_profiles")["profiles"]:
            for step in profile.get("enrichment_steps", []):
                tool_name = step.get("react_call")
                if not tool_name:
                    continue
                tool = tool_by_name.get(tool_name)
                if not tool:
                    errors.append(
                        f"Профиль разрешения {profile['profile_id']} ссылается на отсутствующий ReAct-вызов: "
                        f"{tool_name}"
                    )
                    continue
                if not tool.get("endpoint_bindings"):
                    errors.append(
                        f"Профиль разрешения {profile['profile_id']} ссылается на ReAct-вызов "
                        f"{tool_name} без привязки операции"
                    )
        for channel in self.active_payload("interaction_channels")["channels"]:
            for action_key in ("question_delivery", "incomplete_discussion_action", "escalation_action"):
                action = channel[action_key]
                tool_name = action.get("tool_name")
                if not tool_name:
                    continue
                tool = tool_by_name.get(tool_name)
                if not tool:
                    errors.append(f"{channel['channel_id']}.{action_key} ссылается на неизвестный tool_name: {tool_name}")
                elif not tool.get("endpoint_bindings"):
                    errors.append(f"{channel['channel_id']}.{action_key} ссылается на ReAct-вызов {tool_name} без привязки операции")
            for profile in channel.get("action_profiles", []):
                action = profile["action"]
                tool_name = action.get("tool_name")
                if not tool_name:
                    continue
                tool = tool_by_name.get(tool_name)
                if not tool:
                    errors.append(
                        f"{channel['channel_id']}.action_profiles.{profile['profile_id']} "
                        f"ссылается на неизвестный tool_name: {tool_name}"
                    )
                elif not tool.get("endpoint_bindings"):
                    errors.append(
                        f"{channel['channel_id']}.action_profiles.{profile['profile_id']} "
                        f"ссылается на ReAct-вызов {tool_name} без привязки операции"
                    )
        return errors

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
        endpoint_by_id = {
            endpoint["endpoint_id"]: endpoint
            for endpoint in self.active_payload("integration_endpoints")["endpoints"]
        }
        for workflow in payload["workflows"]:
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
                    f"Workflow n8n {workflow['workflow_id']} ссылается на неизвестный callback_endpoint_id: "
                    f"{callback_endpoint_id}"
                )
        return errors

    def _validate_interaction_channels(self, payload: dict[str, Any]) -> list[str]:
        errors = []
        channels = payload["channels"]
        channel_ids = [channel["channel_id"] for channel in channels]
        for channel_id in self._duplicates(channel_ids):
            errors.append(f"Дублируется channel_id: {channel_id}")

        tool_by_name = {
            tool["tool_name"]: tool
            for tool in self.active_payload("tools")["tools"]
        }
        for channel in channels:
            channel_id = channel["channel_id"]
            allowed_actions = self._channel_action_types_for_mode(channel["mode"])
            allowed_no_answer = self._channel_no_answer_actions_for_mode(channel["mode"])
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
            profile_ids = [profile["profile_id"] for profile in channel.get("action_profiles", [])]
            for profile_id in self._duplicates(profile_ids):
                errors.append(f"{channel_id} содержит дублирующийся action profile: {profile_id}")
            errors.extend(self._validate_required_channel_action_profiles(channel))
            for action_key in ("question_delivery", "incomplete_discussion_action", "escalation_action"):
                action = channel[action_key]
                if action["action_type"] not in allowed_actions:
                    errors.append(
                        f"{channel_id}.{action_key}.action_type={action['action_type']} "
                        f"не подходит для режима канала {channel['mode']}."
                    )
                errors.extend(self._validate_channel_action_binding(tool_by_name, action, f"{channel_id}.{action_key}"))
            for profile in channel.get("action_profiles", []):
                label = f"{channel_id}.action_profiles.{profile['profile_id']}"
                if profile["action"]["action_type"] not in allowed_actions:
                    errors.append(
                        f"{label}.action_type={profile['action']['action_type']} "
                        f"не подходит для режима канала {channel['mode']}."
                    )
                errors.extend(self._validate_channel_action_binding(tool_by_name, profile["action"], label))

        scenario_payload = self.active_payload("service_scenarios")
        scenario_refs = self._collect_channel_scenario_refs(scenario_payload)
        missing_refs = sorted(scenario_refs - set(channel_ids))
        for channel_id in missing_refs:
            errors.append(f"Канал используется сценариями, но отсутствует в каталоге: {channel_id}")
        return errors

    @staticmethod
    def _channel_action_types_for_mode(mode: str) -> set[str]:
        if mode == "online_interactive":
            return {"ask_end_user", "create_draft", "call_specialist", "notify_on_call"}
        if mode == "offline_interactive":
            return {"ask_operator", "save_context", "create_work_order"}
        if mode == "debug":
            return {"show_debug_message", "debug_stop"}
        return {"debug_stop"}

    @staticmethod
    def _channel_no_answer_actions_for_mode(mode: str) -> set[str]:
        if mode == "online_interactive":
            return {"create_draft", "call_specialist"}
        if mode == "offline_interactive":
            return {"save_context", "create_work_order"}
        if mode == "debug":
            return {"debug_stop"}
        return {"debug_stop"}

    @staticmethod
    def _validate_required_channel_action_profiles(channel: dict[str, Any]) -> list[str]:
        errors = []
        required_event_types = {"standard_handoff", "no_answer", "major_incident", "policy_blocked"}
        event_counts: dict[str, int] = {}
        for profile in channel.get("action_profiles", []):
            event_type = profile["event_type"]
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
        for event_type in sorted(required_event_types):
            count = event_counts.get(event_type, 0)
            if count == 0:
                errors.append(f"{channel['channel_id']} не содержит обязательный action profile event_type={event_type}.")
            elif count > 1:
                errors.append(f"{channel['channel_id']} содержит несколько action profile для event_type={event_type}.")
        for event_type, count in event_counts.items():
            if event_type not in required_event_types and count > 1:
                errors.append(f"{channel['channel_id']} содержит несколько action profile для event_type={event_type}.")
        return errors

    def _validate_channel_action_binding(
        self,
        tool_by_name: dict[str, dict[str, Any]],
        action: dict[str, Any],
        label: str,
    ) -> list[str]:
        errors = []
        tool_name = action.get("tool_name")
        if not tool_name:
            return errors
        tool = tool_by_name.get(tool_name)
        if not tool:
            errors.append(f"{label} ссылается на неизвестный tool_name: {tool_name}")
            return errors
        endpoint_id = action.get("endpoint_id")
        operation_id = action.get("operation_id")
        if endpoint_id or operation_id:
            matching_binding = next(
                (
                    binding
                    for binding in tool["endpoint_bindings"]
                    if binding["endpoint_id"] == endpoint_id
                    and binding["operation_id"] == operation_id
                ),
                None,
            )
            if not matching_binding:
                errors.append(
                    f"{label} не имеет tool binding для "
                    f"endpoint_id={endpoint_id} operation_id={operation_id}."
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
        endpoint_by_id = self._by_id(
            self.active_payload("integration_endpoints")["endpoints"],
            "endpoint_id",
        )

        for profile in profiles:
            profile_id = profile["profile_id"]
            input_slot_ids = [slot["slot_id"] for slot in profile.get("input_slots", [])]
            output_slot_ids = [slot["slot_id"] for slot in profile.get("output_slots_order", [])]
            declared_slot_ids = set(input_slot_ids) | set(output_slot_ids)
            if profile["target_slot_id"] not in output_slot_ids:
                errors.append(f"{profile_id} target_slot_id должен входить в output_slots_order.")
            for slot_id in self._duplicates(input_slot_ids):
                errors.append(f"{profile_id} содержит дублирующийся входной слот: {slot_id}")
            for slot_id in self._duplicates(output_slot_ids):
                errors.append(f"{profile_id} содержит дублирующийся выходной слот: {slot_id}")
            orders = [slot["order"] for slot in profile.get("output_slots_order", [])]
            for order in self._duplicates(orders):
                errors.append(f"{profile_id} содержит дублирующийся порядок выходного слота: {order}")
            if not any(slot.get("required_for_success") for slot in profile.get("output_slots_order", [])):
                errors.append(f"{profile_id} должен иметь хотя бы один обязательный выходной слот.")

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
            if not human_policy.get("clarification_question"):
                errors.append(f"{profile_id} human_resolution_policy должен содержать clarification_question.")
            if not human_policy.get("clarification_slots"):
                errors.append(f"{profile_id} human_resolution_policy должен содержать clarification_slots.")
            for slot_id in human_policy.get("clarification_slots", []):
                if slot_id not in declared_slot_ids:
                    errors.append(f"{profile_id} human_resolution_policy.clarification_slots содержит необъявленный слот: {slot_id}")
            for slot_id in human_policy.get("handoff_package", []):
                if slot_id not in declared_slot_ids:
                    errors.append(f"{profile_id} human_resolution_policy.handoff_package содержит необъявленный слот: {slot_id}")

            seen_entities: set[str] = set()
            entity_names = [step["result_entity_name"] for step in profile.get("enrichment_steps", [])]
            for entity_name in self._duplicates(entity_names):
                errors.append(f"{profile_id} содержит дублирующуюся сущность результата: {entity_name}")
            for index, enrichment_step in enumerate(profile.get("enrichment_steps", []), start=1):
                step_label = f"{profile_id}.enrichment_steps[{index}]"
                tool = tool_by_name.get(enrichment_step.get("react_call"))
                if not tool:
                    errors.append(f"{step_label} ссылается на неизвестный ReAct-вызов: {enrichment_step.get('react_call')}")
                elif not tool.get("endpoint_bindings"):
                    errors.append(f"{step_label} ReAct-вызов {enrichment_step.get('react_call')} не имеет привязки операции.")
                for parameter, source_ref in enrichment_step.get("parameter_mapping", {}).items():
                    source, separator, value = str(source_ref).partition(":")
                    if separator != ":" or source not in {"slot", "output", "entity", "constant", "secret"} or not value:
                        errors.append(
                            f"{step_label}.parameter_mapping.{parameter} должен иметь формат "
                            "slot:<slot_id>, output:<slot_id>, entity:<entity[.field]>, constant:<value> или secret:<ref>."
                        )
                        continue
                    if source == "slot" and value not in input_slot_ids:
                        errors.append(
                            f"{step_label}.parameter_mapping.{parameter} ссылается на слот вне входных слотов профиля: {value}"
                        )
                    elif source == "output" and value not in output_slot_ids:
                        errors.append(
                            f"{step_label}.parameter_mapping.{parameter} ссылается на неизвестный выходной слот: {value}"
                        )
                    elif source == "entity":
                        entity_name = value.split(".", 1)[0]
                        if entity_name not in seen_entities:
                            errors.append(
                                f"{step_label}.parameter_mapping.{parameter} ссылается на сущность, "
                                f"которая еще не объявлена предыдущими шагами: {entity_name}"
                            )
                field_ids = [field["field_id"] for field in enrichment_step.get("result_fields", [])]
                for field_id in self._duplicates(field_ids):
                    errors.append(f"{step_label} содержит дублирующееся поле результата: {field_id}")
                seen_entities.add(enrichment_step["result_entity_name"])

            llm_script = profile["llm_resolution_script"]
            if not llm_script.get("script_text"):
                errors.append(f"{profile_id} llm_resolution_script должен содержать script_text.")
            response_contract = llm_script.get("response_contract", {})
            for required_key in ("decision", "filled_slots", "confidence", "next_question", "reason"):
                if required_key not in response_contract:
                    errors.append(f"{profile_id} llm_resolution_script.response_contract должен содержать {required_key}.")

            fallback = profile.get("fallback", {"action": "operator_handoff"})
            if fallback["action"] == "ask_user" and not fallback.get("question"):
                errors.append(f"{profile_id} fallback ask_user должен содержать question.")
        return errors

    def _validate_slot_autofill_profiles(self, payload: dict[str, Any]) -> list[str]:
        errors = []
        profiles = payload.get("profiles", [])
        profile_ids = [profile["profile_id"] for profile in profiles]
        for profile_id in self._duplicates(profile_ids):
            errors.append(f"Дублируется profile_id: {profile_id}")

        slot_schema_by_id = self._by_id(
            self.active_payload("slot_schemas")["slot_schemas"],
            "slot_schema_id",
        )
        tool_by_name = self._by_id(self.active_payload("tools")["tools"], "tool_name")
        for profile in profiles:
            profile_id = profile["profile_id"]
            slot_schema = slot_schema_by_id.get(profile["slot_schema_id"])
            slot_ids = {slot["slot_id"] for slot in slot_schema.get("slots", [])} if slot_schema else set()
            if not slot_schema:
                errors.append(f"{profile_id} ссылается на неизвестную схему слотов: {profile['slot_schema_id']}")

            tool = tool_by_name.get(profile.get("react_call"))
            if not tool:
                errors.append(f"{profile_id} ссылается на неизвестный ReAct-вызов: {profile.get('react_call')}")
                result_field_roots: set[str] = set()
                required_parameters: set[str] = set()
            else:
                if tool.get("action_type") != "read_only":
                    errors.append(f"{profile_id} должен использовать только read-only ReAct-вызов.")
                if not tool.get("endpoint_bindings"):
                    errors.append(f"{profile_id} ReAct-вызов {tool.get('tool_name')} не имеет привязки операции.")
                result_schema = tool.get("result_schema") or {}
                result_field_roots = set(result_schema.get("properties", {}).keys())
                required_parameters = set(tool.get("parameters_schema", {}).get("required", []))

            mapped_parameters = set(profile.get("input_mapping", {}).keys())
            for parameter in sorted(required_parameters - mapped_parameters):
                errors.append(f"{profile_id} input_mapping не заполняет обязательный параметр ReAct-вызова: {parameter}")

            for parameter, source_ref in profile.get("input_mapping", {}).items():
                source, separator, value = str(source_ref).partition(":")
                if separator != ":" or source not in {"slot", "case", "context", "constant", "secret"} or not value:
                    errors.append(
                        f"{profile_id} input_mapping.{parameter} должен быть ссылкой "
                        "slot:<slot_id>, case:<path>, context:<path>, constant:<value> или secret:<ref>."
                    )
                    continue
                if source == "slot" and slot_schema and value not in slot_ids:
                    errors.append(f"{profile_id} input_mapping.{parameter} ссылается на неизвестный слот: {value}")

            mapped_targets = [item["target_slot"] for item in profile.get("output_mapping", [])]
            for target_slot in self._duplicates(mapped_targets):
                errors.append(f"{profile_id} содержит дублирующийся целевой слот: {target_slot}")
            for item in profile.get("output_mapping", []):
                target_slot = item["target_slot"]
                result_field = item["result_field"]
                if slot_schema and target_slot not in slot_ids:
                    errors.append(f"{profile_id} заполняет отсутствующий слот схемы {profile['slot_schema_id']}: {target_slot}")
                root_field = result_field.split(".", 1)[0]
                if result_field_roots and root_field not in result_field_roots:
                    errors.append(
                        f"{profile_id} output_mapping.{target_slot} ссылается на поле вне контракта результата: {result_field}"
                    )
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
        channel_by_id = self._by_id(self.active_payload("interaction_channels")["channels"], "channel_id")
        channel_ids = set(channel_by_id)
        system_confidence_defaults = self.system_confidence_defaults()
        for scenario in scenarios:
            scenario_id = scenario["scenario_id"]
            errors.extend(
                validate_confidence_overrides(
                    system_confidence_defaults,
                    scenario.get("confidence_overrides"),
                    f"{scenario_id}.confidence_overrides",
                )
            )
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
            default_channel_id = scenario.get("default_channel_id", "debug")
            allowed_channel_ids = scenario.get("allowed_channel_ids") or [default_channel_id]
            if default_channel_id not in channel_ids:
                errors.append(f"{scenario_id} ссылается на неизвестный default_channel_id: {default_channel_id}")
            else:
                for channel_error in self._validate_required_channel_action_profiles(channel_by_id[default_channel_id]):
                    errors.append(f"{scenario_id}: {channel_error}")
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
        for schema in schemas:
            slot_by_id = self._by_id(schema["slots"], "slot_id")
            for slot_id in self._duplicates([slot["slot_id"] for slot in schema["slots"]]):
                errors.append(f"{schema['slot_schema_id']} содержит дублирующийся slot_id: {slot_id}")
            profile_by_id = self._by_id(
                self.active_payload("attribute_resolution_profiles")["profiles"],
                "profile_id",
            )
            active_autofill_profiles = [
                profile
                for profile in self.active_payload("slot_autofill_profiles").get("profiles", [])
                if profile.get("slot_schema_id") == schema["slot_schema_id"]
            ]
            for slot in schema["slots"]:
                fill_method = slot_fill_method(slot)
                profile_id = slot.get("resolution_profile_id")
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
                if fill_method == "resolution_profile":
                    if not profile_id:
                        errors.append(f"{schema['slot_schema_id']} slot {slot['slot_id']} должен иметь resolution_profile_id.")
                    else:
                        profile = profile_by_id.get(profile_id)
                        if not profile:
                            errors.append(f"{schema['slot_schema_id']} slot {slot['slot_id']} ссылается на неизвестный profile_id: {profile_id}")
                        elif slot["slot_id"] not in [item["slot_id"] for item in profile.get("output_slots_order", [])]:
                            errors.append(f"{schema['slot_schema_id']} slot {slot['slot_id']} не входит в output_slots_order профиля {profile_id}.")
                        else:
                            profile_input_slot_ids = [
                                input_slot["slot_id"]
                                for input_slot in profile.get("input_slots", [])
                            ]
                            for profile_slot_id in profile_input_slot_ids:
                                if profile_slot_id not in slot_by_id:
                                    errors.append(
                                        f"{schema['slot_schema_id']} профиль {profile_id} требует отсутствующий input slot: "
                                        f"{profile_slot_id}"
                                    )
            for profile in active_autofill_profiles:
                for mapping in profile.get("output_mapping", []):
                    target_slot = mapping.get("target_slot")
                    if target_slot not in slot_by_id:
                        errors.append(
                            f"{schema['slot_schema_id']} профиль автозаполнения {profile['profile_id']} "
                            f"заполняет отсутствующий slot: {target_slot}"
                        )
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
            if confidence["llm_min"] > confidence["rules_min"]:
                errors.append(f"{route['route_id']} llm_min не должен быть выше rules_min.")
            rules = route.get("rules", {}).get("rule_items", [])
            positive_rules = [rule for rule in rules if rule.get("polarity") == "positive"]
            if not positive_rules:
                errors.append(f"{route['route_id']} должен содержать хотя бы одно позитивное правило классификации.")
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
            if policy["consecutive_tool_errors_to_escalate"] > policy["max_iterations"]:
                errors.append(f"{policy['policy_id']} лимит ошибок ReAct-вызовов не может быть выше max_iterations.")
            if not policy["allowed_react_action_groups"]:
                errors.append(f"{policy['policy_id']} должен содержать хотя бы одну группу действий ReAct.")
            if not policy["stop_conditions"]:
                errors.append(f"{policy['policy_id']} должен содержать хотя бы одно стоп-условие.")
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
                if launch["execution_level"] != launch["target_execution_level"]:
                    errors.append(
                        f"{launch['launch_id']} должен иметь одинаковые execution_level и target_execution_level; "
                        "целевой режим запуска больше не редактируется отдельно."
                    )
                if launch["execution_level"] == "approver_approval":
                    errors.append(
                        f"{launch['launch_id']} использует approver_approval, но flow согласующего пока не реализован."
                    )
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
                        if binding["endpoint_id"] == launch["endpoint_id"]
                        and binding["operation_id"] == launch["operation_id"]
                    ),
                    None,
                )
                if not matching_binding:
                    errors.append(
                        f"{launch['launch_id']} не имеет binding для endpoint_id={launch['endpoint_id']} "
                        f"operation_id={launch['operation_id']}"
                    )
                if launch["execution_level"] == "auto" and tool["action_type"] == "action":
                    if tool["policy"].get("approval_required_hint") or not tool["policy"].get("auto_execution_eligible"):
                        errors.append(f"{launch['launch_id']} не может быть auto в текущей policy ReAct-вызова.")
                if launch["risk_level"] == "blocked" and launch["execution_level"] != "blocked":
                    errors.append(f"{launch['launch_id']} с risk_level=blocked должен иметь execution_level=blocked.")
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
            "react_planning",
            "tool_rules",
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
        required_package = {
            "slots",
            "user_notification",
        }
        for policy in payload["policies"]:
            package = set(policy["handoff_package"])
            missing = required_package - package
            if missing:
                errors.append(f"{policy['policy_id']} handoff package должен содержать: {', '.join(sorted(missing))}")
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
                "tool_launch_matrix_id": f"matrix.{item['scenario_id']}",
                "prompt_pack_id": f"prompt.{item['scenario_id']}",
                "escalation_policy_id": f"escalation.{item['scenario_id']}",
                "default_channel_id": "debug",
                "allowed_channel_ids": ["messenger_bot", "service_desk", "debug"],
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
                "question_delivery": {
                    "action_type": "ask_end_user",
                    "message_template": "{question}",
                },
                "waiting_policy": {
                    "first_reminder_after_seconds": 180,
                    "discussion_timeout_seconds": 480,
                    "sla_elapsed_percent_threshold": 0,
                    "on_no_answer": "create_draft",
                },
                "incomplete_discussion_action": {
                    "action_type": "create_draft",
                    "message_template": "Создать черновик заявки и сохранить контекст клиентского уточнения.",
                },
                "escalation_action": {
                    "action_type": "call_specialist",
                    "message_template": "Позвать специалиста в диалог с полным контекстом сценария.",
                },
                "action_profiles": default_channel_action_profiles({
                    "channel_id": "messenger_bot",
                    "escalation_action": {
                        "action_type": "call_specialist",
                        "message_template": "Позвать специалиста в диалог с полным контекстом сценария.",
                    },
                }),
                "audit_required": True,
                "enabled": True,
            },
            {
                "channel_id": "service_desk",
                "display_name": "Сервисдеск",
                "mode": "offline_interactive",
                "description": "Офлайн-интерактивный канал сервисдеска: уточняющие вопросы фиксируются в заявке, ожидание длиннее и зависит от SLA, эскалация создает наряд по назначенному правилу.",
                "question_delivery": {
                    "action_type": "ask_operator",
                    "message_template": "{question}",
                },
                "waiting_policy": {
                    "first_reminder_after_seconds": 3600,
                    "discussion_timeout_seconds": 14400,
                    "sla_elapsed_percent_threshold": 30,
                    "on_no_answer": "create_work_order",
                },
                "incomplete_discussion_action": {
                    "action_type": "save_context",
                    "message_template": "Сохранить контекст и ожидать следующего обновления заявки.",
                },
                "escalation_action": {
                    "action_type": "create_work_order",
                    "message_template": "Создать наряд ответственному специалисту с пакетом эскалации.",
                },
                "action_profiles": default_channel_action_profiles({
                    "channel_id": "service_desk",
                    "escalation_action": {
                        "action_type": "create_work_order",
                        "message_template": "Создать наряд ответственному специалисту с пакетом эскалации.",
                    },
                }),
                "audit_required": True,
                "enabled": True,
            },
            {
                "channel_id": "debug",
                "display_name": "Отладочный режим",
                "mode": "debug",
                "description": "Локальный режим MVP: вопросы показывает интерфейс оператора, а эскалация останавливает сценарий с диагностическим сообщением без внешнего исполнения.",
                "question_delivery": {
                    "action_type": "show_debug_message",
                    "message_template": "{question}",
                },
                "waiting_policy": {
                    "first_reminder_after_seconds": 0,
                    "discussion_timeout_seconds": 0,
                    "sla_elapsed_percent_threshold": 0,
                    "on_no_answer": "debug_stop",
                },
                "incomplete_discussion_action": {
                    "action_type": "debug_stop",
                    "message_template": "Остановить dry-run и показать оператору недостающий контекст клиентского уточнения.",
                },
                "escalation_action": {
                    "action_type": "debug_stop",
                    "message_template": "Остановить сценарий и показать причину эскалации оператору.",
                },
                "action_profiles": default_channel_action_profiles({
                    "channel_id": "debug",
                    "escalation_action": {
                        "action_type": "debug_stop",
                        "message_template": "Остановить сценарий и показать причину эскалации оператору.",
                    },
                }),
                "audit_required": True,
                "enabled": True,
            },
        ],
    }


def default_channel_action_profiles(channel: dict[str, Any]) -> list[dict[str, Any]]:
    channel_id = channel.get("channel_id")
    legacy_escalation_action = channel.get("escalation_action") or {
        "action_type": "debug_stop",
        "message_template": "Остановить сценарий и показать причину эскалации оператору.",
    }
    if channel_id == "messenger_bot":
        return [
            _channel_action_profile("standard_handoff", "Эскалация: подключить оператора к чату", "standard_handoff", legacy_escalation_action),
            _channel_action_profile("no_answer", "Клиент не ответил: создать черновик", "no_answer", {
                "action_type": "create_draft",
                "message_template": "Создать черновик заявки и сохранить контекст клиентского уточнения.",
            }),
            _channel_action_profile("major_incident", "Major Incident: оповестить дежурных", "major_incident", {
                "action_type": "notify_on_call",
                "message_template": "Оповестить дежурную команду и приложить пакет Major Incident.",
            }),
            _channel_action_profile("policy_blocked", "Политика заблокировала автоисполнение", "policy_blocked", legacy_escalation_action),
        ]
    if channel_id == "service_desk":
        return [
            _channel_action_profile("standard_handoff", "Эскалация: создать наряд", "standard_handoff", legacy_escalation_action),
            _channel_action_profile("no_answer", "Клиент не ответил: создать наряд", "no_answer", {
                "action_type": "create_work_order",
                "message_template": "Создать наряд по незавершенному уточнению и приложить контекст.",
            }),
            _channel_action_profile("major_incident", "Major Incident: создать наряд дежурной группе", "major_incident", {
                "action_type": "create_work_order",
                "message_template": "Создать срочный наряд дежурной группе с пакетом Major Incident.",
            }),
            _channel_action_profile("policy_blocked", "Политика заблокировала автоисполнение", "policy_blocked", legacy_escalation_action),
        ]
    return [
        _channel_action_profile("standard_handoff", "Отладка: эскалация оператору", "standard_handoff", legacy_escalation_action),
        _channel_action_profile("no_answer", "Отладка: клиент не ответил", "no_answer", {
            "action_type": "debug_stop",
            "message_template": "Остановить dry-run из-за отсутствия ответа клиента.",
        }),
        _channel_action_profile("major_incident", "Отладка: Major Incident", "major_incident", {
            "action_type": "debug_stop",
            "message_template": "Остановить сценарий и показать оператору причину Major Incident.",
        }),
        _channel_action_profile("policy_blocked", "Отладка: policy blocked", "policy_blocked", legacy_escalation_action),
    ]


def _channel_action_profile(
    profile_id: str,
    display_name: str,
    event_type: str,
    action: dict[str, Any],
) -> dict[str, Any]:
    return {
        "profile_id": profile_id,
        "display_name": display_name,
        "event_type": event_type,
        "action": action,
    }


def resolve_channel_action_profiles(
    channel: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    if not channel:
        return {}
    return {
        profile["event_type"]: profile
        for profile in channel.get("action_profiles", [])
    }


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
            },
            {
                "slot_schema_id": "slot.software_issue",
                "display_name": "Слоты проблемы с приложением",
                "required_slots": ["user_login", "app_name", "error_text"],
                "auto_fill_slots": ["device_name"],
                "question_order": ["user_login", "app_name", "error_text"],
                "timeouts": common_timeouts,
                "slots": [
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
            },
            {
                "slot_schema_id": "slot.hardware_issue",
                "display_name": "Слоты проблемы с устройством",
                "required_slots": ["user_login", "device_id", "symptom"],
                "auto_fill_slots": ["device_model"],
                "question_order": ["user_login", "device_id", "symptom"],
                "timeouts": common_timeouts,
                "slots": [
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
            },
            {
                "slot_schema_id": "slot.network_issue",
                "display_name": "Слоты сетевой проблемы",
                "required_slots": ["user_login", "location", "symptom", "affected_users"],
                "auto_fill_slots": ["subnet"],
                "question_order": ["user_login", "symptom", "affected_users", "location"],
                "timeouts": common_timeouts,
                "slots": [
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
            },
            {
                "slot_schema_id": "slot.access_request",
                "display_name": "Слоты запроса доступа",
                "required_slots": ["user_login", "resource_name", "business_reason", "approver_login"],
                "auto_fill_slots": ["user_id"],
                "question_order": ["user_login", "approver_login", "resource_name", "business_reason"],
                "timeouts": common_timeouts,
                "slots": [
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
            },
            {
                "slot_schema_id": "slot.unknown",
                "display_name": "Слоты неизвестного сценария",
                "required_slots": ["user_login", "symptom"],
                "auto_fill_slots": [],
                "question_order": ["user_login", "symptom"],
                "timeouts": common_timeouts,
                "slots": [
                    _slot("user_login", "Логин пользователя", "who", user_question="Уточните логин пользователя."),
                    _slot("symptom", "Описание проблемы", "what", user_question="Опишите проблему одной фразой."),
                ],
            },
        ],
    }


def default_slot_autofill_profiles() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "profiles": [],
    }


def default_attribute_resolution_profiles() -> dict[str, Any]:
    def candidate_profile(
        profile_id: str,
        display_name: str,
        description: str,
        target_slot_id: str,
        output_slots: list[str],
        input_attributes: list[dict[str, Any]],
        candidate_source: dict[str, Any],
        result_policy: dict[str, Any],
        clarification_question: str,
        clarification_attributes: list[str],
        *,
        status: str = "active",
        handoff_package: list[str] | None = None,
        confidence_threshold: float = 0.7,
        max_attempts: int = 1,
        fallback_action: str = "ask_user",
    ) -> dict[str, Any]:
        input_slots = []
        seen_input_slots = set()
        for attribute in input_attributes:
            if attribute.get("source") != "slot":
                continue
            slot_id = attribute.get("source_ref") or attribute.get("attribute_id")
            if not slot_id or slot_id in seen_input_slots:
                continue
            seen_input_slots.add(slot_id)
            input_slots.append({
                "slot_id": slot_id,
                "required_for_operation": bool(attribute.get("required", True)),
                "can_ask_user": True,
                "description": attribute.get("display_name") or humanize_config_id(slot_id),
            })
        if not input_slots:
            input_slots.append({
                "slot_id": target_slot_id,
                "required_for_operation": False,
                "can_ask_user": True,
                "description": f"Слот для разрешения: {humanize_config_id(target_slot_id)}.",
            })
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
            "clarification_question": clarification_question,
            "clarification_slots": [
                slot_id
                for slot_id in clarification_attributes
                if slot_id in {item["slot_id"] for item in input_slots} or slot_id in output_slots
            ] or [input_slots[0]["slot_id"]],
            "handoff_package": [
                slot_id
                for slot_id in (handoff_package or [*output_slots, *[item["slot_id"] for item in input_slots]])
                if slot_id in {item["slot_id"] for item in input_slots} or slot_id in output_slots
            ] or output_slots[:1],
            "handoff_action": "operator_handoff",
            "fallback_action": fallback_action,
        }
        profile = {
            "profile_id": profile_id,
            "display_name": display_name,
            "status": status,
            "description": description,
            "target_slot_id": target_slot_id,
            "input_slots": input_slots,
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
            "audit_required": True,
            "log_required": True,
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
                    "source_type": "react_call",
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
                ["department", "employee_number", "title"],
                handoff_package=[
                    "login_candidate",
                    "last_name",
                    "first_name",
                    "middle_name",
                    "email",
                    "department",
                    "employee_number",
                    "title",
                    "user_login",
                    "user_id",
                ],
                confidence_threshold=0.75,
                max_attempts=2,
                fallback_action="operator_handoff",
            ),
            candidate_profile(
                "profile.software_issue.device_from_ad",
                "Устройство пользователя из AD",
                "Определяет основное устройство пользователя по логину через профиль AD.",
                "device_name",
                ["device_name"],
                [resolution_attribute("user_login", display_name="Логин пользователя", source="slot", source_ref="user_login", required=True)],
                {
                    "source_type": "react_call",
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
                ["device_name"],
                max_attempts=2,
            ),
            candidate_profile(
                "profile.hardware_issue.device_from_cmdb",
                "Устройство из CMDB",
                "Заполняет модель устройства по имени или инвентарному номеру через CMDB.",
                "device_model",
                ["device_model"],
                [resolution_attribute("device_id", display_name="ID устройства", source="slot", source_ref="device_id", required=True)],
                {
                    "source_type": "react_call",
                    "tool_name": "query_cmdb_object",
                    "endpoint_id": "mock",
                    "operation_id": "query_cmdb_object",
                    "parameter_mapping": {"object_ref": "attribute:device_id"},
                },
                default_result_policy("query_cmdb_object", "device_model"),
                "Уточните модель устройства, если она известна.",
                ["device_model"],
            ),
            candidate_profile(
                "profile.network_issue.subnet_from_cmdb",
                "Подсеть по локации из CMDB",
                "Определяет подсеть по локации для сетевого инцидента.",
                "subnet",
                ["subnet"],
                [resolution_attribute("location", display_name="Локация", source="slot", source_ref="location", required=True)],
                {
                    "source_type": "react_call",
                    "tool_name": "query_cmdb_object",
                    "endpoint_id": "mock",
                    "operation_id": "query_cmdb_object",
                    "parameter_mapping": {"object_ref": "attribute:location"},
                },
                default_result_policy("query_cmdb_object", "subnet"),
                "Не удалось определить подсеть по локации. Уточните техническую локацию или передайте обращение специалисту.",
                ["location"],
                fallback_action="operator_handoff",
            ),
            candidate_profile(
                "profile.access_request.user_from_ad",
                "Пользователь запроса доступа из AD",
                "Заполняет идентификатор пользователя для запроса доступа по логину.",
                "user_id",
                ["user_id"],
                [resolution_attribute("user_login", display_name="Логин пользователя", source="slot", source_ref="user_login", required=True)],
                {
                    "source_type": "react_call",
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
                ["user_login"],
            ),
            candidate_profile(
                "profile.history.password_reset.resolved",
                "История успешных сбросов пароля",
                "Ищет похожие закрытые заявки сброса пароля только в разрешенном сценарии и только с подтвержденным качеством.",
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
                ["account_type"],
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
            "major_incident",
            "Немедленная проверка массовости и запуск процедуры Major Incident при затронутых пользователях.",
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
        "policies": [
            {
                "policy_id": f"policy.{item['scenario_id']}",
                "display_name": f"ReAct-политика: {item['display_name']}",
                "max_iterations": 6,
                "consecutive_tool_errors_to_escalate": 2,
                "stop_conditions": [
                    "all_required_slots_filled",
                    "tool_success",
                    "clarification_required",
                    "handoff_required",
                    "iteration_limit",
                    "consecutive_tool_errors",
                ],
                "allowed_react_action_groups": [
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
                ["user_login"],
                {
                    "runbook_code": "constant:password_reset",
                    "user_login": "slot:user_login",
                },
                "operator_approval",
                "operator_approval",
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
                    "runbook_code": "constant:software_diagnostic",
                    "user_login": "slot:user_login",
                    "device_name": "slot:device_name",
                    "app_name": "slot:app_name",
                    "error_text": "slot:error_text",
                },
                "operator_approval",
                "operator_approval",
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
                    "object_ref": "slot:device_id",
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
                    "target_ref": "slot:location",
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
                    "target_ref": "slot:resource_name",
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
                "display_name": f"Матрица ReAct-вызовов: {scenario_names.get(scenario_id, scenario_id)}",
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
    endpoint_id: str,
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
        "endpoint_id": endpoint_id,
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
        "behavior_principles": "Задавай один вопрос за раз. Не раскрывай внутренние ReAct-вызовы клиенту. Пиши без жаргона и фиксируй недостающие данные.",
        "slot_schemas": "Собирай слоты в порядке кто -> что -> когда. Используй auto-fill источники до вопроса клиенту. При таймауте 3 минуты напомни, при 8 минутах сохрани черновик.",
        "classification_confidence": "Сначала используй правила классификации с позитивными и негативными признаками. Если confidence ниже 0.85, используй LLM few-shot. Если ниже 0.70, передай человеку с топ-3 категориями. Если ниже 0.50, не принимай финальное решение автоматически.",
        "react_planning": "Используй цикл Думай -> Действуй -> Наблюдай. Максимум 6 итераций. При двух ошибках ReAct-вызовов подряд запускай действие эскалации выбранного канала.",
        "tool_rules": "Проверяй required slots и parameter bindings перед каждым ReAct-вызовом ИИ. Action-вызовы в MVP запускаются только после подтверждения оператора.",
        "escalation_response": "Передавай оператору через канал эскалации полный пакет: слоты, историю ReAct, результаты ReAct-вызовов, гипотезу причины, остаток SLA и текст уведомления клиента.",
    }


def build_prompt_preview(prompt_pack: dict[str, Any]) -> str:
    block_titles = {
        "role_context": "1. Роль и контекст",
        "behavior_principles": "2. Принципы поведения",
        "slot_schemas": "3. Схемы слотов",
        "classification_confidence": "4. Классификация и confidence",
        "react_planning": "5. ReAct и планирование",
        "tool_rules": "6. Правила ReAct-вызовов",
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
                "handoff_conditions": [
                    "two_tool_errors",
                    "iteration_limit",
                    "confidence_below_050",
                    "affected_users_threshold",
                    "policy_blocked",
                ],
                "major_incident": {
                    "affected_users_threshold": 10,
                },
                "handoff_package": [
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
                "display_name": "Выбор ReAct-вызова ИИ",
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
