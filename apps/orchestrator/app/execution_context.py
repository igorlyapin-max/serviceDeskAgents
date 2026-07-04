from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from typing import Any


TEMPLATE_REF_RE = re.compile(r"\$\{([^{}]+)\}")
PARAM_CAPABILITY_REF_RE = re.compile(
    r"^paramCapability\.(?P<capability_id>[A-Za-z][A-Za-z0-9_.-]*)\."
    r"(?P<kind>input|output)\.(?P<path>[A-Za-z0-9_][A-Za-z0-9_.-]*)$"
)
STEP_CAPABILITY_REF_RE = re.compile(
    r"^step\.(?P<step_id>step[1-9][0-9]*)\.capability\."
    r"(?P<capability_id>[A-Za-z][A-Za-z0-9_.-]*)\."
    r"(?P<kind>input|output)\.(?P<path>[A-Za-z0-9_][A-Za-z0-9_.-]*)$"
)

DEFAULT_CASE_FIELDS = {
    "case_id",
    "ticket_id",
    "description",
    "input_text",
    "scenario_id",
    "channel_id",
    "priority",
    "user",
    "created_at",
    "updated_at",
}

DEFAULT_WAIT_FIELDS = {
    "wait_id",
    "wait_type",
    "status",
    "correlation_id",
    "deadline_at",
    "reason",
    "result_transport",
    "result_topic",
    "expected_event_type",
    "payload",
    "origin",
}

DEFAULT_STAGE_FIELDS = {
    "0": {"input_text", "slots", "slot_values", "normalization"},
    "1": {"attribute_resolution", "resolution_state", "slot_values", "enrichment"},
    "2": {"classification", "route_id", "route", "priority", "confidence"},
    "3": {"orchestration", "iterations", "stop_conditions"},
    "4": {"ready_tool_launches", "blocked_tool_launches", "capability_results", "planned_waits"},
    "5": {"final_decision", "client_question", "operator_escalation", "agent_outcome"},
}

SENSITIVE_REF_PARTS = {
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "credentials",
    "key",
    "password",
    "secret",
    "token",
    "ключ",
    "пароль",
    "секрет",
    "токен",
}
CHANNEL_SAFE_KEY_FIELDS = {"task_key", "message_key", "message_key_parameter"}


def template_refs(text: str | None) -> list[str]:
    return [match.strip() for match in TEMPLATE_REF_RE.findall(str(text or "")) if match.strip()]


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
    return [str(item) for item in required] if isinstance(required, list) else []


def schema_type(schema: dict[str, Any] | None) -> str | None:
    if not isinstance(schema, dict):
        return None
    value = schema.get("type")
    if isinstance(value, list):
        return next((str(item) for item in value if item != "null"), None)
    return str(value) if value else None


def schema_declares_path(schema: dict[str, Any] | None, path: str | None) -> bool:
    if not isinstance(schema, dict) or not path:
        return False
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
        elif raw_part.isdigit():
            continue
        if not current:
            return False
        properties = schema_properties(current)
        if raw_part not in properties:
            return False
        current = properties[raw_part]
    return True


@dataclass
class ExecutionReferenceContext:
    slot_ids: set[str] = field(default_factory=set)
    output_slot_ids: set[str] = field(default_factory=set)
    tools_by_name: dict[str, dict[str, Any]] = field(default_factory=dict)
    capabilities_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    steps_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    channel_fields_by_id: dict[str, set[str]] = field(default_factory=dict)
    allowed_step_ids: set[str] | None = None
    case_fields: set[str] = field(default_factory=lambda: set(DEFAULT_CASE_FIELDS))
    wait_fields: set[str] = field(default_factory=lambda: set(DEFAULT_WAIT_FIELDS))
    stage_fields: dict[str, set[str]] = field(
        default_factory=lambda: {key: set(value) for key, value in DEFAULT_STAGE_FIELDS.items()}
    )


def build_execution_reference_context(
    *,
    slot_schema: dict[str, Any] | None = None,
    slots: list[dict[str, Any]] | None = None,
    output_slots: list[str] | None = None,
    tools: list[dict[str, Any]] | None = None,
    capabilities: list[dict[str, Any]] | None = None,
    steps: list[dict[str, Any]] | None = None,
    allowed_steps: list[dict[str, Any]] | None = None,
    channels: list[dict[str, Any]] | None = None,
) -> ExecutionReferenceContext:
    source_slots = slots if slots is not None else (slot_schema or {}).get("slots", [])
    step_items = list(steps or [])
    allowed_step_ids = None
    if allowed_steps is not None:
        allowed_step_ids = {
            str(step.get("step_id") or f"step{index}")
            for index, step in enumerate(allowed_steps, start=1)
        }
    return ExecutionReferenceContext(
        slot_ids={str(slot.get("slot_id") or "") for slot in source_slots if slot.get("slot_id")},
        output_slot_ids={str(item) for item in (output_slots or []) if item},
        tools_by_name={
            str(tool.get("tool_name")): tool
            for tool in tools or []
            if tool.get("tool_name")
        },
        capabilities_by_id={
            str(capability.get("capability_id")): capability
            for capability in capabilities or []
            if capability.get("capability_id")
        },
        steps_by_id={
            str(step.get("step_id") or f"step{index}"): step
            for index, step in enumerate(step_items, start=1)
        },
        channel_fields_by_id={
            str(channel.get("channel_id")): channel_reference_fields(channel)
            for channel in channels or []
            if channel.get("channel_id")
        },
        allowed_step_ids=allowed_step_ids,
    )


def channel_reference_fields(channel: dict[str, Any]) -> set[str]:
    fields = {
        "channel_id",
        "display_name",
        "mode",
    }
    technical_profile = channel.get("technical_profile")
    if isinstance(technical_profile, dict):
        fields.update(
            str(key)
            for key in technical_profile
            if key and not _is_sensitive_ref(str(key))
        )
    for parameter in channel.get("channel_parameters", []):
        if isinstance(parameter, dict) and parameter.get("parameter_id"):
            fields.add(str(parameter["parameter_id"]))
    return fields


def _path_label(path: str) -> str:
    return path.replace(".", " -> ")


def _capability_path_schema(capability: dict[str, Any], kind: str) -> dict[str, Any]:
    return capability.get("input_schema" if kind == "input" else "output_schema") or {}


def _validate_capability_path(
    *,
    ref: str,
    context: ExecutionReferenceContext,
    capability_id: str,
    kind: str,
    path: str,
) -> str | None:
    capability = context.capabilities_by_id.get(capability_id)
    if not capability:
        return f"Ссылка ${{{ref}}} указывает на неизвестную capability: {capability_id}."
    schema = _capability_path_schema(capability, kind)
    if schema_properties(schema) and not schema_declares_path(schema, path):
        human_kind = "входной параметр" if kind == "input" else "поле результата"
        return (
            f"Ссылка ${{{ref}}} указывает на неизвестный {human_kind} "
            f"capability {capability_id}: {_path_label(path)}."
        )
    return None


def validate_template_refs(
    text: str | None,
    context: ExecutionReferenceContext,
    *,
    label: str = "template",
) -> list[str]:
    errors: list[str] = []
    if re.search(r"\bentity:", str(text or ""), flags=re.IGNORECASE):
        errors.append(
            f"{label}: ссылки entity:<name> устарели. "
            "Используйте ${step.<step_id>.capability.<capability_id>.output.<field>}."
        )
    for ref in template_refs(text):
        parts = [part for part in ref.split(".") if part]
        if not parts:
            continue
        namespace = parts[0]
        if namespace == "entity":
            errors.append(
                f"{label}: ссылка ${{{ref}}} использует устаревший тип entity. "
                "Используйте ${step.<step_id>.capability.<capability_id>.output.<field>}."
            )
            continue
        if namespace == "slot":
            slot_id = ".".join(parts[1:])
            if not slot_id:
                errors.append(f"{label}: ссылка ${{{ref}}} должна указывать slot.<slot_id>.")
            elif slot_id not in context.slot_ids:
                errors.append(f"{label}: ссылка ${{{ref}}} указывает на неизвестный слот: {slot_id}.")
            continue
        if namespace == "output":
            slot_id = ".".join(parts[1:])
            known_output_slots = context.output_slot_ids or context.slot_ids
            if not slot_id:
                errors.append(f"{label}: ссылка ${{{ref}}} должна указывать output.<slot_id>.")
            elif slot_id not in known_output_slots:
                errors.append(f"{label}: ссылка ${{{ref}}} указывает на неизвестный выходной слот: {slot_id}.")
            continue
        if namespace == "case":
            case_field = parts[1] if len(parts) > 1 else ""
            if not case_field:
                errors.append(f"{label}: ссылка ${{{ref}}} должна указывать case.<field>.")
            elif case_field not in context.case_fields:
                errors.append(f"{label}: ссылка ${{{ref}}} указывает на неизвестное поле обращения: {case_field}.")
            continue
        if namespace == "wait":
            wait_field = parts[1] if len(parts) > 1 else ""
            if not wait_field:
                errors.append(f"{label}: ссылка ${{{ref}}} должна указывать wait.<field>.")
            elif wait_field not in context.wait_fields:
                errors.append(f"{label}: ссылка ${{{ref}}} указывает на неизвестное поле ожидания: {wait_field}.")
            continue
        if namespace == "channel":
            channel_id = parts[1] if len(parts) > 1 else ""
            channel_field = parts[2] if len(parts) > 2 else ""
            channel_fields = context.channel_fields_by_id.get(channel_id)
            if not channel_id or channel_fields is None:
                errors.append(f"{label}: ссылка ${{{ref}}} указывает на неизвестный канал: {channel_id or 'н/д'}.")
            elif not channel_field:
                errors.append(f"{label}: ссылка ${{{ref}}} должна указывать channel.<channel_id>.<parameter>.")
            elif channel_field not in channel_fields:
                errors.append(f"{label}: ссылка ${{{ref}}} указывает на неизвестный параметр канала {channel_id}: {channel_field}.")
            continue
        if namespace == "stage":
            stage_id = parts[1] if len(parts) > 1 else ""
            field_name = parts[2] if len(parts) > 2 else ""
            stage_fields = context.stage_fields.get(stage_id)
            if not stage_id or stage_fields is None:
                errors.append(f"{label}: ссылка ${{{ref}}} указывает на неизвестный этап: {stage_id or 'н/д'}.")
            elif not field_name:
                errors.append(f"{label}: ссылка ${{{ref}}} должна указывать stage.<number>.<field>.")
            elif field_name not in stage_fields:
                errors.append(f"{label}: ссылка ${{{ref}}} указывает на неизвестное поле этапа {stage_id}: {field_name}.")
            continue
        if namespace == "Capability":
            capability_id = ".".join(parts[1:])
            if not capability_id:
                errors.append(f"{label}: ссылка ${{{ref}}} должна указывать Capability.<capability_id>.")
            elif capability_id not in context.capabilities_by_id:
                errors.append(f"{label}: ссылка ${{{ref}}} указывает на неизвестную capability: {capability_id}.")
            continue
        if namespace == "paramCapability":
            match = PARAM_CAPABILITY_REF_RE.match(ref)
            if not match:
                errors.append(
                    f"{label}: ссылка ${{{ref}}} должна иметь формат "
                    "${paramCapability.<capability_id>.input.<parameter>} или "
                    "${paramCapability.<capability_id>.output.<field>}."
                )
                continue
            error = _validate_capability_path(
                ref=ref,
                context=context,
                capability_id=match.group("capability_id"),
                kind=match.group("kind"),
                path=match.group("path"),
            )
            if error:
                errors.append(f"{label}: {error}")
            continue
        if namespace == "step":
            capability_match = STEP_CAPABILITY_REF_RE.match(ref)
            if not capability_match:
                errors.append(
                    f"{label}: ссылка ${{{ref}}} должна иметь формат "
                    "${step.<step_id>.capability.<capability_id>.input|output.<field>}."
                )
                continue
            step_id = capability_match.group("step_id")
            capability_id = capability_match.group("capability_id")
            step = context.steps_by_id.get(step_id)
            if not step or (context.allowed_step_ids is not None and step_id not in context.allowed_step_ids):
                errors.append(f"{label}: ссылка ${{{ref}}} указывает на недоступный предыдущий шаг: {step_id}.")
                continue
            if step.get("capability_id") and step.get("capability_id") != capability_id:
                errors.append(
                    f"{label}: ссылка ${{{ref}}} ожидает capability {capability_id} "
                    f"в {step_id}, но там настроена {step.get('capability_id')}."
                )
                continue
            error = _validate_capability_path(
                ref=ref,
                context=context,
                capability_id=capability_id,
                kind=capability_match.group("kind"),
                path=capability_match.group("path"),
            )
            if error:
                errors.append(f"{label}: {error}")
            continue
        errors.append(f"{label}: неизвестный тип ссылки ${{{ref}}}.")
    return errors


def _is_sensitive_ref(ref: str) -> bool:
    normalized = ref.lower()
    return any(part in normalized for part in SENSITIVE_REF_PARTS)


def _is_sensitive_channel_field(ref: str) -> bool:
    return _is_sensitive_ref(ref) and ref not in CHANNEL_SAFE_KEY_FIELDS


def _compact_public_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _compact_public_value(item)
            for key, item in value.items()
            if not _is_sensitive_ref(str(key))
        }
    if isinstance(value, list):
        return [_compact_public_value(item) for item in value[:20]]
    return value


def _lookup_path(value: Any, path: list[str]) -> Any:
    current = value
    for part in path:
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            current = current[int(part)] if int(part) < len(current) else None
        else:
            return None
    return current


def _first_wait_correlation(planned_waits: list[dict[str, Any]]) -> str | None:
    for wait in planned_waits:
        if isinstance(wait, dict) and wait.get("correlation_id"):
            return str(wait["correlation_id"])
    return None


def _channel_source_value(
    source: str,
    technical_profile: dict[str, Any],
    planned_waits: list[dict[str, Any]],
) -> Any:
    source = str(source or "").strip()
    if source.startswith("technical_profile."):
        return _lookup_path(technical_profile, source.split(".")[1:])
    if source == "kafka.message_key":
        return _first_wait_correlation(planned_waits)
    if source == "public.ittask.invalid":
        return technical_profile.get("invalid_topic")
    if source == "TaskTemp_PasswordMsg.personalID":
        return None
    if source == "TaskResultCode":
        return None
    if source == "TaskResultMessage":
        return None
    return None


def build_channel_variable_context(
    interaction_channel: dict[str, Any] | None,
    planned_waits: list[dict[str, Any]],
    channel_parameter_values: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(interaction_channel, dict):
        return {}
    channel_id = str(interaction_channel.get("channel_id") or "").strip()
    if not channel_id:
        return {}
    technical_profile = interaction_channel.get("technical_profile") or {}
    if not isinstance(technical_profile, dict):
        technical_profile = {}

    values: dict[str, Any] = {}
    for field in ("channel_id", "display_name", "mode"):
        if interaction_channel.get(field) not in (None, "", [], {}):
            values[field] = copy.deepcopy(interaction_channel[field])
    for field, value in technical_profile.items():
        if value not in (None, "", [], {}) and not _is_sensitive_channel_field(str(field)):
            values[str(field)] = copy.deepcopy(value)

    correlation_id = _first_wait_correlation(planned_waits)
    if correlation_id:
        values.setdefault("task_key", correlation_id)
        values.setdefault("task_number", correlation_id)

    for parameter in interaction_channel.get("channel_parameters", []):
        if not isinstance(parameter, dict):
            continue
        parameter_id = str(parameter.get("parameter_id") or "").strip()
        if not parameter_id or parameter.get("secret") or _is_sensitive_channel_field(parameter_id):
            continue
        value = _channel_source_value(str(parameter.get("source") or ""), technical_profile, planned_waits)
        if value not in (None, "", [], {}):
            values[parameter_id] = copy.deepcopy(value)

    declared_parameters = {
        str(parameter.get("parameter_id") or "").strip(): parameter
        for parameter in interaction_channel.get("channel_parameters", [])
        if isinstance(parameter, dict) and parameter.get("parameter_id")
    }
    override_ids: set[str] = set()
    for parameter_id, value in (channel_parameter_values or {}).items():
        parameter_id = str(parameter_id or "").strip()
        if not parameter_id or value in (None, "", [], {}):
            continue
        parameter = declared_parameters.get(parameter_id) or {}
        if parameter.get("secret") or _is_sensitive_channel_field(parameter_id):
            continue
        values[parameter_id] = copy.deepcopy(value)
        override_ids.add(parameter_id)
    if "task_key" in override_ids and "task_number" not in override_ids:
        values["task_number"] = copy.deepcopy(values["task_key"])
    elif "task_number" in override_ids and "task_key" not in override_ids:
        values["task_key"] = copy.deepcopy(values["task_number"])
    elif values.get("task_key") not in (None, "", [], {}) and values.get("task_number") in (None, "", [], {}):
        values["task_number"] = copy.deepcopy(values["task_key"])
    elif values.get("task_number") not in (None, "", [], {}) and values.get("task_key") in (None, "", [], {}):
        values["task_key"] = copy.deepcopy(values["task_number"])

    return {"channel": {channel_id: values}} if values else {}


def resolve_template_ref(ref: str, values: dict[str, Any]) -> Any:
    parts = [part for part in ref.split(".") if part]
    if not parts:
        return None
    namespace = parts[0]
    if namespace == "channel":
        channel_id = parts[1] if len(parts) > 1 else ""
        field_name = parts[2] if len(parts) > 2 else ""
        if _is_sensitive_ref(ref) and field_name not in {"task_key", "message_key", "message_key_parameter"}:
            return None
        return _lookup_path((values.get("channel") or {}).get(channel_id), parts[2:])
    if _is_sensitive_ref(ref):
        return None
    if namespace in {"slot", "output"}:
        slot_id = ".".join(parts[1:])
        slot_value = (values.get(namespace) or values.get("slot") or {}).get(slot_id)
        return slot_value.get("value") if isinstance(slot_value, dict) and "value" in slot_value else slot_value
    if namespace in {"case", "wait", "stage"}:
        return _lookup_path(values.get(namespace), parts[1:])
    if namespace == "step":
        match = STEP_CAPABILITY_REF_RE.match(ref)
        if not match:
            return None
        step = (values.get("step") or {}).get(match.group("step_id")) or {}
        capability = (step.get("capability") or {}).get(match.group("capability_id")) or {}
        return _lookup_path(capability.get(match.group("kind")), match.group("path").split("."))
    return None


def render_template(text: str | None, values: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        ref = match.group(1).strip()
        value = resolve_template_ref(ref, values)
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            return json.dumps(_compact_public_value(value), ensure_ascii=False, sort_keys=True)
        return str(value)

    return TEMPLATE_REF_RE.sub(replace, str(text or ""))


def build_simulation_variable_context(
    *,
    scenario_id: str,
    input_text: str,
    slot_values: dict[str, Any],
    resolution_state: dict[str, Any],
    classification: dict[str, Any],
    ready_tool_launches: list[dict[str, Any]],
    blocked_tool_launches: list[dict[str, Any]],
    planned_waits: list[dict[str, Any]],
    final_decision: str,
    agent_outcome: dict[str, Any] | None = None,
    interaction_channel: dict[str, Any] | None = None,
    channel_parameter_values: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = {
        "case": {
            "scenario_id": scenario_id,
            "input_text": input_text,
            "priority": classification.get("priority"),
        },
        "slot": copy.deepcopy(slot_values),
        "stage": {
            "0": {
                "input_text": input_text,
                "slot_values": copy.deepcopy(slot_values),
            },
            "1": {
                "resolution_state": copy.deepcopy(resolution_state),
                "slot_values": copy.deepcopy(slot_values),
            },
            "2": {
                "classification": copy.deepcopy(classification),
                "route_id": classification.get("route_id"),
                "route": classification.get("route"),
                "priority": classification.get("priority"),
                "confidence": classification.get("confidence"),
            },
            "4": {
                "ready_tool_launches": copy.deepcopy(ready_tool_launches),
                "blocked_tool_launches": copy.deepcopy(blocked_tool_launches),
                "planned_waits": copy.deepcopy(planned_waits),
            },
            "5": {
                "final_decision": final_decision,
                "agent_outcome": copy.deepcopy(agent_outcome or {}),
            },
        },
        "wait": copy.deepcopy(planned_waits[0] if planned_waits else {}),
    }
    context.update(build_channel_variable_context(
        interaction_channel,
        planned_waits,
        channel_parameter_values=channel_parameter_values,
    ))
    return context
