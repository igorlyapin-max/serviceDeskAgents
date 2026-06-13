from __future__ import annotations

import copy
import contextvars
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
from .execution_context import (
    build_execution_reference_context,
    build_simulation_variable_context,
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

STEP_SOURCE_REF_RE = re.compile(
    r"^(step[1-9][0-9]*)\.react\.([a-z][a-z0-9_.-]*)\.(input|output)\.([A-Za-z0-9_][A-Za-z0-9_.-]*)$"
)

DEFAULT_CLIENT_WAITING_POLICY = {
    "auto_close_requires_client_confirmation": True,
    "pause_sla_on_client_wait": True,
    "client_wait_auto_close_after_hours": 24,
}

DEFAULT_EXTERNAL_EVENT_RESULT_TOPIC = "external.events"

AGENT_OUTCOME_LABELS = {
    "success": "Завершено автоматически",
    "needs_review": "Требуется эскалация",
    "waiting": "Вопрос клиенту",
    "escalated": "Требуется эскалация",
    "error": "Ошибка",
}

AGENT_OUTCOME_NEXT_STEPS = {
    "success": "Автообработка завершена; проверьте трассу и итоговые данные при необходимости.",
    "needs_review": "Передайте обращение оператору вместе с контекстом и трассой обработки.",
    "waiting": "Передайте клиенту уточняющий вопрос и продолжите обработку после ответа.",
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


def normalize_enrichment_step_launch(enrichment_step: dict[str, Any]) -> None:
    legacy_launch = enrichment_step.pop("launch", None)
    if isinstance(legacy_launch, dict):
        enrichment_step.setdefault("endpoint_id", legacy_launch.get("endpoint_id"))
        enrichment_step.setdefault("operation_id", legacy_launch.get("operation_id"))
        enrichment_step.setdefault("completion_policy", legacy_launch.get("completion_policy"))

    has_launch_fields = any(
        enrichment_step.get(field) not in (None, "", {}, [])
        for field in ("endpoint_id", "operation_id", "completion_policy")
    )
    if not has_launch_fields:
        for field in ("endpoint_id", "operation_id", "completion_policy"):
            if enrichment_step.get(field) in (None, "", {}, []):
                enrichment_step.pop(field, None)
        return
    launch = {
        "tool_name": enrichment_step.get("react_call"),
        "endpoint_id": enrichment_step.get("endpoint_id"),
        "operation_id": enrichment_step.get("operation_id"),
        "completion_policy": enrichment_step.get("completion_policy") or {},
    }
    normalize_tool_launch_completion_policy(launch)
    if launch.get("endpoint_id"):
        enrichment_step["endpoint_id"] = launch["endpoint_id"]
    if launch.get("operation_id"):
        enrichment_step["operation_id"] = launch["operation_id"]
    enrichment_step["completion_policy"] = launch["completion_policy"]
    for field in ("endpoint_id", "operation_id"):
        if enrichment_step.get(field) in (None, "", {}, []):
            enrichment_step.pop(field, None)


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
        elif source == "step":
            match = STEP_SOURCE_REF_RE.match(source_value)
            if match:
                step_id, react_call, kind, field_path = match.groups()
                step_record = step_results.get(step_id)
                if step_record and step_record.get("react_call") != react_call:
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


def step_source_ref(step: dict[str, Any], field_path: str, *, kind: str = "output") -> str:
    step_id = step.get("step_id") or "step1"
    react_call = step.get("react_call") or "react_call"
    return f"step:{step_id}.react.{react_call}.{kind}.{field_path}"


def step_template_ref(step: dict[str, Any], field_path: str, *, kind: str = "output") -> str:
    step_id = step.get("step_id") or "step1"
    react_call = step.get("react_call") or "react_call"
    return f"${{step.{step_id}.react.{react_call}.{kind}.{field_path}}}"


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
    result["status"] = "active"
    result["use_llm_after_steps"] = bool(result.get("use_llm_after_steps", True))
    result.pop("allowed_scenarios", None)
    output_slots = [slot_id for slot_id in result.get("output_slots", []) if slot_id]
    target_slot_id = result.get("target_slot_id") or (output_slots[0] if output_slots else None)

    legacy_steps = result.pop("steps", [])
    result.pop("resolution_mode", None)
    result.pop("attempt_scope", None)
    result.pop("ambiguity_policy", None)
    result.pop("operator_handoff_package", None)
    legacy_candidate_mapping = result.pop("candidate_mapping", None)
    result.pop("input_slots", None)

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
    entity_step_by_name: dict[str, dict[str, Any]] = {}
    normalized_enrichment_steps = []
    for index, enrichment_step in enumerate(result.get("enrichment_steps", []), start=1):
        enrichment_step = copy.deepcopy(enrichment_step)
        step_id = str(enrichment_step.get("step_id") or "")
        if not re.match(r"^step[1-9][0-9]*$", step_id):
            enrichment_step["step_id"] = f"step{index}"
        legacy_entity_name = enrichment_step.pop("result_entity_name", None)
        enrichment_step.pop("result_entity_description", None)
        enrichment_step.pop("result_fields", None)
        enrichment_step["parameter_mapping"] = migrate_entity_parameter_mapping(
            enrichment_step.get("parameter_mapping", {}),
            entity_step_by_name,
        )
        if enrichment_step.get("configuration_instruction"):
            enrichment_step["configuration_instruction"] = migrate_entity_template_refs(
                enrichment_step.get("configuration_instruction"),
                entity_step_by_name,
            )
        normalize_enrichment_step_launch(enrichment_step)
        normalized_enrichment_steps.append(enrichment_step)
        if legacy_entity_name and enrichment_step.get("react_call"):
            entity_step_by_name[str(legacy_entity_name)] = {
                "step_id": enrichment_step["step_id"],
                "react_call": enrichment_step["react_call"],
            }
    result["enrichment_steps"] = normalized_enrichment_steps
    if "output_slots_order" not in result:
        result["output_slots_order"] = output_slots_order_from_policy(
            target_slot_id,
            output_slots,
            result_policy,
        )
    if target_slot_id and target_slot_id not in [item["slot_id"] for item in result["output_slots_order"]]:
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
    else:
        result["llm_resolution_script"]["script_text"] = migrate_entity_template_refs(
            result["llm_resolution_script"].get("script_text"),
            entity_step_by_name,
        )

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
    result.pop("audit_required", None)
    result.pop("log_required", None)
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
    operation_name = result_entity.get("entity_name") or resolver_operation.get("operation_id") or resolver_operation["tool_name"]
    return [
        {
            "step_id": "step1",
            "step_name": f"Получить {humanize_config_id(operation_name)}",
            "react_call": resolver_operation["tool_name"],
            "endpoint_id": resolver_operation.get("endpoint_id"),
            "operation_id": resolver_operation.get("operation_id"),
            "completion_policy": copy.deepcopy(resolver_operation.get("completion_policy") or {}),
            "parameter_mapping": resolver_operation.get("parameter_mapping", {}),
            "on_error": "continue_to_llm",
        }
    ]


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


def normalize_output_slot_order(items: list[dict[str, Any]], target_slot_id: str | None) -> list[dict[str, Any]]:
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
        f"{step.get('step_id', f'step{index}')}.react.{step.get('react_call', 'react_call')}.output.<field>"
        for index, step in enumerate(profile.get("enrichment_steps", []), start=1)
    ) or "нет результатов ReAct-вызовов"
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
) -> dict[str, Any]:
    output_values = {}
    if count == 1 and result_item:
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
) -> dict[str, Any]:
    output_values = {}
    if count == 1 and result_item:
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
            "reason": "Выходные слоты заполнены прямым маппингом результата ReAct-вызова.",
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


def tool_usage_refs(
    tool_name: str,
    resolution_payload: dict[str, Any],
    channels_payload: dict[str, Any],
) -> list[str]:
    refs = []
    for profile in resolution_payload.get("profiles", []):
        if any(step.get("react_call") == tool_name for step in profile.get("enrichment_steps", [])):
            refs.append(f"attribute_resolution_profile:{profile.get('profile_id')}")
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
            return copy.deepcopy(overrides[domain])
        return self.active_config(domain)["payload"]

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
        if origin.get("kind") != "react_call":
            return
        snapshot = self._wait_contract_snapshot(wait)
        if snapshot:
            endpoint_id = snapshot.get("endpoint_id")
            operation_id = snapshot.get("operation_id")
            async_contracts = {
                snapshot.get("event_type"): copy.deepcopy(snapshot.get("async_event_contract") or {})
            }
        else:
            endpoint_id = origin.get("endpoint_id")
            operation_id = origin.get("operation_id")
            if not endpoint_id or not operation_id:
                return
            endpoint = self._by_id(self.active_payload("integration_endpoints")["endpoints"], "endpoint_id").get(endpoint_id)
            operation = (endpoint or {}).get("operations", {}).get(operation_id)
            if not operation:
                raise ContractValidationError(
                    "external_event_result",
                    [f"Не найдена endpoint-операция для ожидания: {endpoint_id}/{operation_id}."],
                )
            async_contracts = operation.get("async_event_contracts") or {}
        if not async_contracts:
            return
        event_type = event.get("event_type")
        async_contract = async_contracts.get(event_type)
        if not async_contract:
            raise ContractValidationError(
                "external_event_result",
                [f"{endpoint_id}/{operation_id} не содержит async_event_contracts.{event_type}."],
            )
        errors = []
        if async_contract.get("contract_status") == "broken":
            errors.append(f"{endpoint_id}/{operation_id}/{event_type} имеет contract_status=broken.")
        status = event.get("status")
        allowed_statuses = set(async_contract.get("statuses") or [])
        if allowed_statuses and status not in allowed_statuses:
            errors.append(
                f"{endpoint_id}/{operation_id}/{event_type} не допускает status={status}; "
                f"разрешено: {', '.join(sorted(allowed_statuses))}."
            )
        schema_key = {
            "success": "result_schema",
            "progress": "progress_schema",
            "error": "error_schema",
        }.get(status)
        payload_key = "error" if status == "error" else "result"
        schema = async_contract.get(schema_key or "") if schema_key else None
        if status == "progress" and not schema:
            schema = async_contract.get("result_schema")
            schema_key = "result_schema"
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

    def external_event_contract_snapshot(
        self,
        *,
        endpoint_id: str,
        operation_id: str,
        event_type: str,
    ) -> dict[str, Any]:
        endpoint = self._by_id(self.active_payload("integration_endpoints")["endpoints"], "endpoint_id").get(endpoint_id)
        operation = (endpoint or {}).get("operations", {}).get(operation_id)
        async_contract = (operation or {}).get("async_event_contracts", {}).get(event_type)
        if not operation or not async_contract:
            raise ContractValidationError(
                "external_event_result",
                [f"Не найден async_event_contracts.{event_type} для {endpoint_id}/{operation_id}."],
            )
        return {
            "schema_version": "1.0",
            "endpoint_id": endpoint_id,
            "operation_id": operation_id,
            "operation_contract_version": operation.get("contract_version"),
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
        if domain == "service_scenarios":
            for scenario in normalized.get("scenarios", []):
                scenario.pop("tool_launch_matrix_id", None)
                scenario.setdefault("default_channel_id", "debug")
                scenario.setdefault("allowed_channel_ids", ["messenger_bot", "service_desk", "debug"])
                scenario.setdefault("audit_required", True)
                scenario.setdefault("log_required", True)
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
        elif domain == "escalation_policies":
            for policy in normalized.get("policies", []):
                scenario_id = policy.pop("scenario_id", None)
                policy.setdefault("display_name", f"Решение и эскалация: {scenario_names.get(scenario_id or '', policy['policy_id'])}")
                policy.setdefault("auto_close", {})
                policy["auto_close"].setdefault("requires_tool_success", True)
                policy["auto_close"].pop("requires_user_confirmation", None)
                policy.pop("waiting", None)
                policy.pop("channel_profile_mapping", None)
                policy.get("major_incident", {}).pop("notify_on_call", None)
        elif domain == "interaction_channels":
            legacy_waiting_defaults = self._legacy_client_waiting_defaults()
            for channel in normalized.get("channels", []):
                channel.pop("audit_required", None)
                channel["waiting_policy"] = normalize_channel_waiting_policy(
                    channel.get("waiting_policy"),
                    legacy_waiting_defaults,
                )
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

    def _n8n_delivery_defaults_by_operation(self) -> dict[tuple[str, str], dict[str, str]]:
        try:
            workflows = self.active_payload("n8n_workflows").get("workflows", [])
        except Exception:
            workflows = self.default_config("n8n_workflows").get("workflows", [])
        defaults: dict[tuple[str, str], dict[str, str]] = {}
        for workflow in workflows:
            endpoint_id = workflow.get("endpoint_id")
            delivery = workflow.get("result_delivery") or {}
            default_transport = delivery.get("default_transport")
            default_topic = delivery.get("default_result_topic") or DEFAULT_EXTERNAL_EVENT_RESULT_TOPIC
            for operation_id in workflow.get("operations") or []:
                if endpoint_id and operation_id:
                    defaults[(endpoint_id, operation_id)] = {
                        "result_transport": default_transport or "http_callback",
                        "result_topic": default_topic,
                    }
        return defaults

    def _profile_step_launch(
        self,
        *,
        profile: dict[str, Any],
        step: dict[str, Any],
        tool_by_name: dict[str, dict[str, Any]],
        endpoint_by_id: dict[str, dict[str, Any]],
        delivery_defaults: dict[tuple[str, str], dict[str, str]],
    ) -> dict[str, Any]:
        tool_name = step.get("react_call")
        tool = tool_by_name.get(tool_name or "")
        binding = select_tool_binding(
            tool,
            endpoint_id=step.get("endpoint_id"),
            operation_id=step.get("operation_id"),
        )
        endpoint_id = (binding or {}).get("endpoint_id") or step.get("endpoint_id")
        operation_id = (binding or {}).get("operation_id") or step.get("operation_id")
        endpoint = endpoint_by_id.get(endpoint_id or "")
        operation = (endpoint or {}).get("operations", {}).get(operation_id or "")
        policy = copy.deepcopy(step.get("completion_policy") or {})
        if policy.get("mode") == "external_event":
            defaults = delivery_defaults.get((endpoint_id or "", operation_id or ""), {})
            policy.setdefault("result_transport", defaults.get("result_transport") or "http_callback")
            policy.setdefault("result_topic", defaults.get("result_topic") or DEFAULT_EXTERNAL_EVENT_RESULT_TOPIC)
        launch = {
            "tool_name": tool_name,
            "endpoint_id": endpoint_id,
            "operation_id": operation_id,
            "completion_policy": policy,
        }
        normalize_tool_launch_completion_policy(launch)
        completion_policy = launch.get("completion_policy", {})
        if completion_policy.get("mode") == "external_event":
            defaults = delivery_defaults.get((endpoint_id or "", operation_id or ""), {})
            completion_policy.setdefault("result_topic", defaults.get("result_topic") or DEFAULT_EXTERNAL_EVENT_RESULT_TOPIC)
        parameter_mapping = copy.deepcopy(step.get("parameter_mapping") or {})
        return {
            "launch_id": f"{profile.get('profile_id')}.{step.get('step_id')}",
            "profile_id": profile.get("profile_id"),
            "profile_name": profile.get("display_name"),
            "step_id": step.get("step_id"),
            "step_name": step.get("step_name"),
            "tool_name": tool_name,
            "action_type": (tool or {}).get("action_type", "read_only"),
            "endpoint_id": endpoint_id,
            "operation_id": operation_id,
            "adapter_type": (endpoint or {}).get("adapter_type"),
            "parameter_bindings": parameter_mapping,
            "required_slots": source_ref_slot_ids(parameter_mapping),
            "completion_policy": completion_policy,
            "endpoint_exists": bool(endpoint),
            "operation_exists": bool(operation),
        }

    def _profile_tool_launches(self, profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        tool_by_name = self._by_id(self.active_payload("tools")["tools"], "tool_name")
        endpoint_by_id = self._by_id(
            self.active_payload("integration_endpoints")["endpoints"],
            "endpoint_id",
        )
        delivery_defaults = self._n8n_delivery_defaults_by_operation()
        launches: list[dict[str, Any]] = []
        for profile in profiles:
            for step in profile.get("enrichment_steps", []):
                if not step.get("react_call"):
                    continue
                launches.append(
                    self._profile_step_launch(
                        profile=profile,
                        step=step,
                        tool_by_name=tool_by_name,
                        endpoint_by_id=endpoint_by_id,
                        delivery_defaults=delivery_defaults,
                    )
                )
        return launches

    @staticmethod
    def _planned_wait_for_launch(launch: dict[str, Any]) -> dict[str, Any] | None:
        policy = launch.get("completion_policy") or {}
        if policy.get("mode") != "external_event":
            return None
        return {
            "wait_type": "external_event_wait",
            "react_call": launch.get("tool_name"),
            "endpoint_id": launch.get("endpoint_id"),
            "operation_id": launch.get("operation_id"),
            "expected_event_type": policy.get("expected_event_type"),
            "result_transport": policy.get("result_transport"),
            "result_topic": policy.get("result_topic") or DEFAULT_EXTERNAL_EVENT_RESULT_TOPIC,
            "max_wait_seconds": policy.get("max_wait_seconds"),
            "timeout_action": policy.get("timeout_action"),
        }

    def _simulate_profile_launches(
        self,
        launches: list[dict[str, Any]],
        *,
        slot_values: dict[str, Any],
        missing_slots: list[str],
        simulation_options: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        ready_launches: list[dict[str, Any]] = []
        blocked_launches: list[dict[str, Any]] = []
        next_allowed_actions: list[dict[str, Any]] = []
        missing_slot_set = set(missing_slots)
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
            if not launch.get("endpoint_exists") or not launch.get("operation_exists"):
                item["status"] = "blocked_by_configuration"
                blocked_launches.append(item)
                continue
            if missing_parameter_slots:
                item["status"] = "blocked_by_missing_slots"
                blocked_launches.append(item)
                continue
            if launch.get("action_type") == "action" and not simulation_options.get("allow_action_with_approval"):
                item["status"] = "approval_required"
            else:
                item["status"] = "ready"
            ready_launches.append(item)
            action_extensions = {
                "endpoint_id": launch.get("endpoint_id"),
                "operation_id": launch.get("operation_id"),
                "completion_policy": launch.get("completion_policy"),
                "source_profile_id": launch.get("profile_id"),
                "source_step_id": launch.get("step_id"),
            }
            action_extensions = {
                key: value
                for key, value in action_extensions.items()
                if value not in (None, "", {}, [])
            }
            next_allowed_actions.append(
                {
                    "tool_name": launch.get("tool_name"),
                    "action_id": f"{launch.get('launch_id')}.action",
                    "action_type": launch.get("action_type"),
                    "parameters": {},
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
        interaction_channel = self._by_id(
            self.active_payload("interaction_channels")["channels"],
            "channel_id",
        ).get(scenario.get("default_channel_id", "debug"))
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
            if profile_id in profile_by_id
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
            for stage in slot_schema_stages(slot_schema):
                profile_id = stage.get("resolution_profile_id")
                if profile_id and profile_id not in profile_by_id:
                    missing.append(f"attribute_resolution_profile:{stage['stage_id']}")
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
            "route": route,
            "orchestrator_policy": policy,
            "tool_launches": tool_launches,
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
        prompt_pack = detail.get("prompt_pack") if detail else None
        escalation_policy = detail.get("escalation_policy") if detail else None
        channel = detail.get("interaction_channel") if detail else None
        stage_count = len(slot_schema_stages(slot_schema)) if slot_schema else 0
        profile_tool_names = sorted({
            step.get("react_call")
            for profile in profiles
            for step in profile.get("enrichment_steps", [])
            if step.get("react_call")
        })
        profile_tools = [tool_by_name[tool_name] for tool_name in profile_tool_names if tool_name in tool_by_name]
        endpoint_ids = sorted({
            binding.get("endpoint_id")
            for tool in profile_tools
            for binding in tool.get("endpoint_bindings", [])
            if binding.get("endpoint_id")
        })
        profile_endpoints = [
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
                "1. Разрешение слотов",
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
                "endpoint_contracts",
                "Контракты endpoint",
                x=1090,
                y=370,
                node_type="configuration",
                description="Технические endpoint-операции, которые используются enrichment шагами профилей разрешения.",
                config_refs=[
                    *[
                        {
                            "domain": "tools",
                            "title": "ReAct-вызов",
                            "id": tool["tool_name"],
                            "display_name": tool.get("description") or tool["tool_name"],
                            "view": "reactCalls",
                        }
                        for tool in profile_tools
                    ],
                    *[
                        {
                            "domain": "integration_endpoints",
                            "title": "Endpoint",
                            "id": endpoint["endpoint_id"],
                            "display_name": endpoint.get("display_name") or endpoint["endpoint_id"],
                            "view": "integrations",
                        }
                        for endpoint in profile_endpoints
                    ],
                ],
                metrics=[
                    {
                        "label": "Endpoint",
                        "value": len(profile_endpoints),
                    },
                    {
                        "label": "ReAct-вызовов",
                        "value": len(profile_tool_names),
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
                description="Системные правила финального решения, ожидания клиента, handoff оператору и Major Incident.",
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
            edge("endpoint_contracts", "attribute_resolution", "enrichment steps", edge_type="support"),
            edge("react_planning", "decision", "стоп-условие"),
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
        delivery_defaults = self._n8n_delivery_defaults_by_operation()
        enrichment_step_results: dict[str, Any] = {}
        last_step: dict[str, Any] | None = None
        last_mock_output: dict[str, Any] | None = None
        last_endpoint_id = ""
        last_operation_id = ""

        for step_index, enrichment_step in enumerate(enrichment_steps, start=1):
            tool_name = enrichment_step.get("react_call")
            tool = tool_by_name.get(tool_name or "")
            binding = select_tool_binding(
                tool,
                endpoint_id=enrichment_step.get("endpoint_id"),
                operation_id=enrichment_step.get("operation_id"),
            )
            endpoint_id = (binding or {}).get("endpoint_id")
            operation_id = (binding or {}).get("operation_id")
            endpoint = endpoint_by_id.get(endpoint_id or "")
            operation = (endpoint or {}).get("operations", {}).get(operation_id or "")
            adapter_type = (endpoint or {}).get("adapter_type")
            launch = self._profile_step_launch(
                profile=profile,
                step=enrichment_step,
                tool_by_name=tool_by_name,
                endpoint_by_id=endpoint_by_id,
                delivery_defaults=delivery_defaults,
            )
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
                    "enrichment_step_results": enrichment_step_results,
                    "status": "blocked_by_configuration",
                    "decision": "handoff",
                    "reason": "ReAct-вызов обогащения контекста или его привязка не найдены.",
                }
            parameter_sources = enrichment_step.get("parameter_mapping", {})
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
                        "react_call": tool_name,
                        "endpoint_id": endpoint_id,
                        "operation_id": operation_id,
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
                        "Не удалось разрешить параметры из предыдущих шагов: "
                        f"{', '.join(unresolved_step_parameters)}."
                    ),
                }
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
                    "enrichment_step_results": enrichment_step_results,
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
                    "enrichment_step_results": enrichment_step_results,
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
                    "enrichment_step_results": enrichment_step_results,
                    "status": "blocked_by_configuration",
                    "decision": "handoff",
                    "reason": "В dry-run нет mock_output для ReAct-вызова обогащения контекста.",
                }

            step_id = enrichment_step.get("step_id") or f"step{step_index}"
            enrichment_step_results[step_id] = {
                "step_id": step_id,
                "step_name": enrichment_step.get("step_name"),
                "react_call": tool_name,
                "endpoint_id": endpoint_id,
                "operation_id": operation_id,
                "parameters": parameters,
                "result": mock_output,
                "completion_policy": launch.get("completion_policy"),
            }
            append_trace(
                execution_trace,
                step="1",
                status="completed",
                title=f"Обогащение контекста: {enrichment_step.get('step_name') or step_id}",
                message=f"ReAct-вызов {tool_name} выполнил шаг {step_id}.",
                details={
                    "step_index": step_index,
                    "step_id": step_id,
                    "react_call": tool_name,
                    "endpoint_id": endpoint_id,
                    "operation_id": operation_id,
                    "completion_policy": launch.get("completion_policy"),
                    "parameter_sources": parameter_sources,
                    "parameters": parameters,
                    "result": mock_output,
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
                "enrichment_step_results": enrichment_step_results,
                "status": "blocked_by_configuration",
                "decision": "handoff",
                "reason": "Обогащение контекста не вернуло результата.",
            }

        last_tool = tool_by_name.get(last_step.get("react_call") or "")
        count, result_item, result_summary = operation_response_items(
            last_mock_output,
            (last_tool or {}).get("result_schema"),
            profile.get("output_slots_order", []),
        )
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
        confidence = result_confidence(result_item, {"confidence_path": "confidence"})
        if not profile.get("use_llm_after_steps", True):
            llm_decision = None
            resolution_decision = direct_mapping_resolution_decision(
                profile=profile,
                result_item=result_item,
                result_summary=result_summary,
                count=count,
                confidence=confidence,
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
        stages = slot_schema_stages(slot_schema)
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
        slot_values = {}
        missing_slots = []
        resolution_steps = []
        resolution_state = {}
        seen_resolution_profile_ids = set()
        profile_results: dict[str, dict[str, Any]] = {}
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
        for stage in stages:
            profile_id = stage.get("resolution_profile_id")
            if not profile_id:
                continue
            profile = profile_by_id.get(profile_id)
            if not profile:
                continue
            if profile_id not in profile_results:
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
            output_values = profile_result.get("output_values", {})
            for slot_id, output_value in output_values.items():
                if slot_id in known_slot_ids and output_value not in (None, ""):
                    slot_values[slot_id] = {
                        "status": "filled_by_stage_profile",
                        "value": output_value,
                        "fill_method": "resolution_profile",
                        "source": "stage_resolution_profile",
                        "resolution_profile_id": profile_id,
                        "confidence": profile_result.get("candidate_confidence"),
                        "reason": profile_result.get("reason"),
                        "effective_confidence_thresholds": self.system_confidence_defaults(),
                    }
                    if slot_id in missing_slots:
                        missing_slots.remove(slot_id)
            if profile_id not in seen_resolution_profile_ids:
                seen_resolution_profile_ids.add(profile_id)
                state_summary = {
                    "stage_id": stage.get("stage_id"),
                    "profile_id": profile_id,
                    **profile_result,
                }
                resolution_state[stage.get("stage_id") or profile_id] = state_summary
                resolution_steps.append(state_summary)
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
            missing_slots=missing_slots,
            simulation_options=simulation_options,
        )
        interaction_channel = detail.get("interaction_channel") or {}
        channel_action_profiles = detail.get("channel_action_profiles") or {}
        standard_profile = channel_action_profiles.get("standard_handoff") or {}
        missing_slot_set = set(missing_slots)
        resolution_operator_handoffs = [
            item
            for item in resolution_steps
            if item.get("status") == "operator_handoff" or item.get("decision") == "handoff"
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
            or final_decision == "operator_handoff"
            or classification.get("decision_level") == "human_required"
            or classification.get("route") in {"human_review", "major_incident"}
        )
        operator_escalation_reason = None
        if operator_escalation_required:
            if final_decision == "blocked_by_configuration":
                operator_escalation_reason = "Конфигурация или параметры ReAct-вызова не позволяют продолжить автообработку."
            elif final_decision == "operator_handoff":
                operator_escalation_reason = "Профиль разрешения слота настроен на эскалацию оператору."
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
            "attribute_resolution": resolution_steps,
            "resolution_state": resolution_state,
            "classification": classification,
            "ready_tool_launches": ready_launches,
            "blocked_tool_launches": blocked_launches,
            "planned_waits": [
                item["planned_wait"]
                for item in [*ready_launches, *blocked_launches]
                if item.get("planned_wait")
            ],
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
        )
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
        normalized_payload = self._normalize_payload(draft["domain"], draft["payload"])
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
        self._save_draft(draft)
        return version

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
                    self.active_payload("attribute_resolution_profiles"),
                    self.active_payload("interaction_channels"),
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
            transport_security = endpoint_transport_security(endpoint)
            if contains_transport_delivery_selector(transport_security):
                errors.append(
                    f"{endpoint['endpoint_id']} transport_security описывает защиту транспорта и не должен "
                    "содержать selected_transport или result_transport."
                )
            if endpoint.get("adapter_type") == "n8n_webhook":
                http_security = transport_security.get("http") if isinstance(transport_security, dict) else {}
                kafka_security = transport_security.get("kafka") if isinstance(transport_security, dict) else {}
                if not isinstance(http_security, dict) or not http_security:
                    errors.append(f"{endpoint['endpoint_id']} n8n_webhook должен содержать transport_security.http.")
                else:
                    if http_security.get("policy") != "admin_configured":
                        errors.append(f"{endpoint['endpoint_id']} transport_security.http.policy должен быть admin_configured.")
                    if http_security.get("production_recommended_scheme") != "https":
                        errors.append(
                            f"{endpoint['endpoint_id']} transport_security.http.production_recommended_scheme "
                            "должен быть https."
                        )
                if not isinstance(kafka_security, dict) or not kafka_security:
                    errors.append(f"{endpoint['endpoint_id']} n8n_webhook должен содержать transport_security.kafka.")
                else:
                    if kafka_security.get("policy") != "admin_configured":
                        errors.append(f"{endpoint['endpoint_id']} transport_security.kafka.policy должен быть admin_configured.")
                    protocols = set(kafka_security.get("supported_security_protocols") or [])
                    if not {"SASL_SSL", "SSL"}.issubset(protocols):
                        errors.append(
                            f"{endpoint['endpoint_id']} transport_security.kafka.supported_security_protocols "
                            "должен включать SASL_SSL и SSL."
                        )
                    auth = set(kafka_security.get("supported_auth") or [])
                    if not {"sasl", "mtls"}.issubset(auth):
                        errors.append(
                            f"{endpoint['endpoint_id']} transport_security.kafka.supported_auth "
                            "должен включать sasl и mtls."
                        )
            contract_source = endpoint.get("contract_source") or {}
            if contract_source.get("enabled") and endpoint.get("adapter_type") != "n8n_webhook":
                errors.append(
                    f"{endpoint['endpoint_id']} содержит активный contract_source; "
                    "импорт OpenAPI поддерживается только для adapter_type=n8n_webhook."
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
                async_contracts = operation.get("async_event_contracts") or {}
                for event_type, async_contract in async_contracts.items():
                    if async_contract.get("contract_status") == "broken":
                        refs = endpoint_operation_async_usage_refs(
                            endpoint["endpoint_id"],
                            operation_id,
                            event_type,
                            self.active_payload("attribute_resolution_profiles"),
                        )
                        if refs:
                            errors.append(
                                f"{endpoint['endpoint_id']}/{operation_id}/{event_type} имеет "
                                f"contract_status=broken и используется: {', '.join(refs)}."
                            )
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
                elif (step.get("endpoint_id") or step.get("operation_id")) and not select_tool_binding(
                    tool,
                    endpoint_id=step.get("endpoint_id"),
                    operation_id=step.get("operation_id"),
                ):
                    errors.append(
                        f"Профиль разрешения {profile['profile_id']}.{step.get('step_id')} "
                        f"ссылается на отсутствующий binding {step.get('endpoint_id')}/{step.get('operation_id')}"
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
        slot_schema_by_id = self._by_id(
            self.active_payload("slot_schemas")["slot_schemas"],
            "slot_schema_id",
        )
        known_slot_ids = {
            slot["slot_id"]
            for schema in self.active_payload("slot_schemas")["slot_schemas"]
            for slot in schema.get("slots", [])
        }

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
                    errors.append(f"{profile_id} ссылается на слот вне выбранной схемы {profile.get('slot_schema_id')}: {slot_id}")
            if target_slot_id and target_slot_id not in output_slot_ids:
                errors.append(f"{profile_id} target_slot_id должен входить в output_slots_order.")
            for slot_id in self._duplicates(output_slot_ids):
                errors.append(f"{profile_id} содержит дублирующийся выходной слот: {slot_id}")
            orders = [slot["order"] for slot in profile.get("output_slots_order", [])]
            for order in self._duplicates(orders):
                errors.append(f"{profile_id} содержит дублирующийся порядок выходного слота: {order}")
            if output_slot_ids and not any(slot.get("required_for_success") for slot in profile.get("output_slots_order", [])):
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
            if human_policy.get("action") not in {"ask_client", "escalate_operator"}:
                errors.append(f"{profile_id} human_resolution_policy.action должен быть ask_client или escalate_operator.")
            if not human_policy.get("message_template"):
                errors.append(f"{profile_id} human_resolution_policy должен содержать message_template.")

            reference_context = build_execution_reference_context(
                slot_schema=slot_schema or {"slots": []},
                output_slots=output_slot_ids,
                tools=list(tool_by_name.values()),
                steps=profile.get("enrichment_steps", []),
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
                        tools=list(tool_by_name.values()),
                        steps=profile.get("enrichment_steps", []),
                        allowed_steps=list(seen_steps.values()),
                    )
                    errors.extend(
                        validate_template_refs(
                            enrichment_step.get("configuration_instruction"),
                            step_reference_context,
                            label=f"{step_label}.configuration_instruction",
                        )
                    )
                tool = tool_by_name.get(enrichment_step.get("react_call"))
                binding = None
                endpoint = None
                operation = None
                if not tool:
                    errors.append(f"{step_label} ссылается на неизвестный ReAct-вызов: {enrichment_step.get('react_call')}")
                elif not tool.get("endpoint_bindings"):
                    errors.append(f"{step_label} ReAct-вызов {enrichment_step.get('react_call')} не имеет привязки операции.")
                else:
                    binding = select_tool_binding(
                        tool,
                        endpoint_id=enrichment_step.get("endpoint_id"),
                        operation_id=enrichment_step.get("operation_id"),
                    )
                    if not binding:
                        errors.append(
                            f"{step_label} ReAct-вызов {enrichment_step.get('react_call')} не имеет binding "
                            f"{enrichment_step.get('endpoint_id')}/{enrichment_step.get('operation_id')}."
                        )
                    else:
                        endpoint = endpoint_by_id.get(binding.get("endpoint_id") or "")
                        operation = (endpoint or {}).get("operations", {}).get(binding.get("operation_id") or "")
                        if not endpoint or not operation:
                            errors.append(
                                f"{step_label} ссылается на отсутствующую endpoint-операцию "
                                f"{binding.get('endpoint_id')}/{binding.get('operation_id')}."
                            )
                    last_step_tool = tool
                completion_policy = enrichment_step.get("completion_policy") or {}
                if completion_policy.get("mode") == "external_event":
                    expected_event_type = completion_policy.get("expected_event_type")
                    async_contract = (operation or {}).get("async_event_contracts", {}).get(expected_event_type or "")
                    if not expected_event_type:
                        errors.append(f"{step_label}.completion_policy должен содержать expected_event_type.")
                    elif not async_contract:
                        errors.append(
                            f"{step_label}.completion_policy ссылается на отсутствующий async_event_contracts."
                            f"{expected_event_type}."
                        )
                    elif async_contract.get("contract_status") == "broken":
                        errors.append(
                            f"{step_label}.completion_policy использует broken async_event_contracts."
                            f"{expected_event_type}."
                        )
                for parameter, source_ref in enrichment_step.get("parameter_mapping", {}).items():
                    if tool:
                        parameter_schema = tool.get("parameters_schema", {})
                        parameter_names = set(schema_properties(parameter_schema))
                        parameter_names.update(schema_required(parameter_schema))
                        if parameter_names and parameter not in parameter_names:
                            errors.append(
                                f"{step_label}.parameter_mapping.{parameter} заполняет параметр вне "
                                f"parameters_schema ReAct-вызова {tool.get('tool_name')}."
                            )
                    source, separator, value = str(source_ref).partition(":")
                    if separator != ":" or source not in {"slot", "output", "step", "constant", "secret"} or not value:
                        errors.append(
                            f"{step_label}.parameter_mapping.{parameter} должен иметь формат "
                            "slot:<slot_id>, output:<slot_id>, "
                            "step:<step_id>.react.<react_call>.input|output.<field>, constant:<value> или secret:<ref>."
                        )
                        continue
                    if source == "slot" and value not in profile_slot_ids:
                        errors.append(
                            f"{step_label}.parameter_mapping.{parameter} ссылается на слот вне выбранной схемы: {value}"
                        )
                    elif source == "output" and value not in output_slot_ids:
                        errors.append(
                            f"{step_label}.parameter_mapping.{parameter} ссылается на неизвестный выходной слот: {value}"
                        )
                    elif source == "step":
                        step_match = STEP_SOURCE_REF_RE.match(value)
                        if not step_match:
                            errors.append(
                                f"{step_label}.parameter_mapping.{parameter} должен ссылаться на step как "
                                "step:<step_id>.react.<react_call>.input|output.<field>."
                            )
                        else:
                            ref_step_id, ref_react_call, _, _ = step_match.groups()
                            ref_step = seen_steps.get(ref_step_id)
                            if not ref_step:
                                errors.append(
                                    f"{step_label}.parameter_mapping.{parameter} ссылается на шаг, "
                                    f"который еще не выполнен: {ref_step_id}"
                                )
                            elif ref_step.get("react_call") != ref_react_call:
                                errors.append(
                                    f"{step_label}.parameter_mapping.{parameter} ожидает ReAct-вызов "
                                    f"{ref_react_call} в {ref_step_id}, но там настроен {ref_step.get('react_call')}."
                                )
                            else:
                                ref_tool = tool_by_name.get(ref_react_call)
                                _, _, ref_kind, field_path = step_match.groups()
                                if ref_tool and ref_kind == "input" and not schema_declares_path(
                                    ref_tool.get("parameters_schema", {}),
                                    field_path,
                                ):
                                    errors.append(
                                        f"{step_label}.parameter_mapping.{parameter} ссылается на неизвестный "
                                        f"входной параметр {ref_react_call}: {field_path}"
                                    )
                                if ref_tool and ref_kind == "output" and not schema_declares_path(
                                    ref_tool.get("result_schema", {}),
                                    field_path,
                                ):
                                    errors.append(
                                        f"{step_label}.parameter_mapping.{parameter} ссылается на неизвестное "
                                        f"поле результата {ref_react_call}: {field_path}"
                                    )
                seen_steps[step_id] = enrichment_step

            if last_step_tool and output_slot_ids:
                result_path, selector_error = operation_result_selector_path(
                    last_step_tool.get("result_schema", {}),
                    profile.get("output_slots_order", []),
                )
                if selector_error:
                    errors.append(f"{profile_id} результат последнего ReAct-вызова неоднозначен: {selector_error}")
                selected_schema = selected_operation_result_schema(last_step_tool.get("result_schema", {}), result_path)
                for rule in profile.get("output_slots_order", []):
                    source_hint = rule.get("source_hint")
                    local_hint = operation_result_local_hint(source_hint, {"result_path": result_path})
                    if local_hint and selected_schema and not schema_declares_path(
                        selected_schema,
                        local_hint,
                    ):
                        errors.append(
                            f"{profile_id} output_slots_order.{rule['slot_id']} ссылается на поле вне "
                            f"контракта результата ReAct-вызова {last_step_tool.get('tool_name')}: {source_hint}"
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
                if not stage.get("slots") and not stage_profile_id:
                    errors.append(
                        f"{schema['slot_schema_id']} stage {stage['stage_id']} должен содержать slots или resolution_profile_id."
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
                "question_delivery": {
                    "action_type": "ask_end_user",
                    "message_template": "{question}",
                },
                "waiting_policy": {
                    "first_reminder_after_seconds": 180,
                    "discussion_timeout_seconds": 480,
                    "sla_elapsed_percent_threshold": 0,
                    "on_no_answer": "create_draft",
                    "auto_close_requires_client_confirmation": True,
                    "pause_sla_on_client_wait": True,
                    "client_wait_auto_close_after_hours": 24,
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
                    "auto_close_requires_client_confirmation": True,
                    "pause_sla_on_client_wait": True,
                    "client_wait_auto_close_after_hours": 24,
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
                    "auto_close_requires_client_confirmation": True,
                    "pause_sla_on_client_wait": True,
                    "client_wait_auto_close_after_hours": 24,
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
                    "source_type": "react_call",
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
                    "source_type": "react_call",
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
        "slot_schemas": "Собирай слоты в порядке кто -> что -> когда. Используй auto-fill источники до вопроса клиенту. Напоминания, timeout ожидания и действия при отсутствии ответа применяй из выбранного канала взаимодействия.",
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
            "system_prompts": {
                "slot_resolution": DEFAULT_SLOT_RESOLUTION_PROMPT_TEMPLATE,
            },
        },
        "runtime": {
            "active_backend": active_provider,
            "openai_api_key_configured": secret_env_configured(openai_key_env),
        },
    }
