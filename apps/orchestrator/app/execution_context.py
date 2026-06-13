from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from typing import Any


TEMPLATE_REF_RE = re.compile(r"\$\{([^{}]+)\}")
PARAM_REACT_REF_RE = re.compile(
    r"^paramReAct\.(?P<react_call>[A-Za-z][A-Za-z0-9_.-]*)\."
    r"(?P<kind>input|output)\.(?P<path>[A-Za-z0-9_][A-Za-z0-9_.-]*)$"
)
STEP_REF_RE = re.compile(
    r"^step\.(?P<step_id>step[1-9][0-9]*)\.react\."
    r"(?P<react_call>[A-Za-z][A-Za-z0-9_.-]*)\."
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
    "3": {"react_plan", "iterations", "stop_conditions"},
    "4": {"ready_tool_launches", "blocked_tool_launches", "tool_results", "planned_waits"},
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


def template_refs(text: str | None) -> list[str]:
    return [match.strip() for match in TEMPLATE_REF_RE.findall(str(text or "")) if match.strip()]


def schema_properties(schema: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return {}
    properties = schema.get("properties", {})
    return properties if isinstance(properties, dict) else {}


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
    steps_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
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
    steps: list[dict[str, Any]] | None = None,
    allowed_steps: list[dict[str, Any]] | None = None,
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
        steps_by_id={
            str(step.get("step_id") or f"step{index}"): step
            for index, step in enumerate(step_items, start=1)
        },
        allowed_step_ids=allowed_step_ids,
    )


def _path_label(path: str) -> str:
    return path.replace(".", " -> ")


def _tool_path_schema(tool: dict[str, Any], kind: str) -> dict[str, Any]:
    return tool.get("parameters_schema" if kind == "input" else "result_schema") or {}


def _validate_tool_path(
    *,
    ref: str,
    context: ExecutionReferenceContext,
    react_call: str,
    kind: str,
    path: str,
) -> str | None:
    tool = context.tools_by_name.get(react_call)
    if not tool:
        return f"Ссылка ${{{ref}}} указывает на неизвестный ReAct-вызов: {react_call}."
    schema = _tool_path_schema(tool, kind)
    if schema_properties(schema) and not schema_declares_path(schema, path):
        human_kind = "входной параметр" if kind == "input" else "поле результата"
        return (
            f"Ссылка ${{{ref}}} указывает на неизвестный {human_kind} "
            f"ReAct-вызова {react_call}: {_path_label(path)}."
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
            "Используйте step:<step_id>.react.<react_call>.output.<field>."
        )
    for ref in template_refs(text):
        parts = [part for part in ref.split(".") if part]
        if not parts:
            continue
        namespace = parts[0]
        if namespace == "entity":
            errors.append(
                f"{label}: ссылка ${{{ref}}} использует устаревший тип entity. "
                "Используйте ${step.<step_id>.react.<react_call>.output.<field>}."
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
        if namespace == "ReAct":
            react_call = ".".join(parts[1:])
            if not react_call:
                errors.append(f"{label}: ссылка ${{{ref}}} должна указывать ReAct.<react_call>.")
            elif react_call not in context.tools_by_name:
                errors.append(f"{label}: ссылка ${{{ref}}} указывает на неизвестный ReAct-вызов: {react_call}.")
            continue
        if namespace == "paramReAct":
            match = PARAM_REACT_REF_RE.match(ref)
            if not match:
                errors.append(
                    f"{label}: ссылка ${{{ref}}} должна иметь формат "
                    "${paramReAct.<react_call>.input.<parameter>} или "
                    "${paramReAct.<react_call>.output.<field>}."
                )
                continue
            error = _validate_tool_path(
                ref=ref,
                context=context,
                react_call=match.group("react_call"),
                kind=match.group("kind"),
                path=match.group("path"),
            )
            if error:
                errors.append(f"{label}: {error}")
            continue
        if namespace == "step":
            match = STEP_REF_RE.match(ref)
            if not match:
                errors.append(
                    f"{label}: ссылка ${{{ref}}} должна иметь формат "
                    "${step.<step_id>.react.<react_call>.input.<parameter>} или "
                    "${step.<step_id>.react.<react_call>.output.<field>}."
                )
                continue
            step_id = match.group("step_id")
            react_call = match.group("react_call")
            step = context.steps_by_id.get(step_id)
            if not step or (context.allowed_step_ids is not None and step_id not in context.allowed_step_ids):
                errors.append(f"{label}: ссылка ${{{ref}}} указывает на недоступный предыдущий шаг: {step_id}.")
                continue
            if step.get("react_call") and step.get("react_call") != react_call:
                errors.append(
                    f"{label}: ссылка ${{{ref}}} ожидает ReAct-вызов {react_call} "
                    f"в {step_id}, но там настроен {step.get('react_call')}."
                )
                continue
            error = _validate_tool_path(
                ref=ref,
                context=context,
                react_call=react_call,
                kind=match.group("kind"),
                path=match.group("path"),
            )
            if error:
                errors.append(f"{label}: {error}")
            continue
        errors.append(f"{label}: неизвестный тип ссылки ${{{ref}}}.")
    return errors


def _is_sensitive_ref(ref: str) -> bool:
    normalized = ref.lower()
    return any(part in normalized for part in SENSITIVE_REF_PARTS)


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


def resolve_template_ref(ref: str, values: dict[str, Any]) -> Any:
    parts = [part for part in ref.split(".") if part]
    if not parts or _is_sensitive_ref(ref):
        return None
    namespace = parts[0]
    if namespace in {"slot", "output"}:
        slot_id = ".".join(parts[1:])
        slot_value = (values.get(namespace) or values.get("slot") or {}).get(slot_id)
        return slot_value.get("value") if isinstance(slot_value, dict) and "value" in slot_value else slot_value
    if namespace in {"case", "wait", "stage"}:
        return _lookup_path(values.get(namespace), parts[1:])
    if namespace == "step":
        match = STEP_REF_RE.match(ref)
        if not match:
            return None
        step = (values.get("step") or {}).get(match.group("step_id")) or {}
        react = (step.get("react") or {}).get(match.group("react_call")) or {}
        return _lookup_path(react.get(match.group("kind")), match.group("path").split("."))
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
) -> dict[str, Any]:
    return {
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
