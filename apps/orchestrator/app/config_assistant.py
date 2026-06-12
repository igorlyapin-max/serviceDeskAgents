from __future__ import annotations

import re
from typing import Any

from .config_registry import schema_properties, schema_required


def _normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _id(value: str | None) -> str:
    raw = re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(value or "").strip().lower()).strip("_.-")
    if not raw:
        return "result"
    if not re.match(r"^[a-z]", raw):
        raw = f"result_{raw}"
    return raw[:160]


def _find_by_id(items: list[dict[str, Any]], key: str, value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    return next((item for item in items if item.get(key) == value), None)


def _operation_schema_fields(schema: dict[str, Any] | None) -> list[dict[str, Any]]:
    properties = schema_properties(schema or {})
    required = set(schema_required(schema or {}))
    return [
        {
            "field_id": field_id,
            "display_name": property_schema.get("title") or _humanize(field_id),
            "field_type": _schema_type(property_schema),
            "description": property_schema.get("description", ""),
            "required": field_id in required,
        }
        for field_id, property_schema in properties.items()
    ]


def _schema_type(schema: dict[str, Any] | None) -> str:
    value = (schema or {}).get("type")
    if isinstance(value, list):
        value = next((item for item in value if item != "null"), None)
    return value if value in {"string", "number", "boolean", "object", "array"} else "unknown"


def _humanize(value: str) -> str:
    return str(value or "").replace("_", " ").replace("-", " ").strip().capitalize() or "Значение"


def _tool_by_name(tools: list[dict[str, Any]], react_call: str | None, instruction: str) -> dict[str, Any] | None:
    if react_call:
        return _find_by_id(tools, "tool_name", react_call)
    normalized_instruction = _normalize_text(instruction)
    for tool in tools:
        if _normalize_text(tool.get("tool_name")) in normalized_instruction:
            return tool
    return tools[0] if tools else None


def _slot_by_label(slots: list[dict[str, Any]], value: str | None) -> dict[str, Any] | None:
    normalized = _normalize_text(value)
    if not normalized:
        return None
    for slot in slots:
        if normalized in {_normalize_text(slot.get("slot_id")), _normalize_text(slot.get("display_name"))}:
            return slot
    return None


def _slot_for_parameter(parameter: str, slots: list[dict[str, Any]], instruction: str) -> dict[str, Any] | None:
    explicit = re.search(
        rf"(?:в\s+)?(?:параметр\s+)?{re.escape(parameter)}\s+"
        r"(?:передай|заполни|заполнить|=|<-|из)\s+"
        r"(?:слот\s+)?[\"«]?([^\"».\n]+)[\"»]?",
        instruction or "",
        flags=re.IGNORECASE,
    )
    if explicit:
        slot = _slot_by_label(slots, explicit.group(1).strip(" .,:;"))
        if slot:
            return slot
    parameter_norm = _normalize_text(parameter)
    for slot in slots:
        if slot.get("slot_id") == parameter:
            return slot
    aliases = {
        "user_fio": ("fio", "full_name", "name", "фио", "фамилия"),
        "full_name": ("fio", "user_fio", "фио", "фамилия"),
        "fio": ("user_fio", "full_name", "фио", "фамилия"),
        "login": ("user_login", "логин"),
        "user_login": ("login", "логин"),
        "email": ("email", "почта", "mail"),
    }
    search_terms = aliases.get(parameter_norm, (parameter_norm,))
    for slot in slots:
        slot_text = f"{slot.get('slot_id', '')} {slot.get('display_name', '')}".lower()
        if any(term in slot_text for term in search_terms):
            return slot
    return None


def _result_field_for_slot(slot: dict[str, Any] | None, fields: list[dict[str, Any]], instruction: str) -> str | None:
    normalized_instruction = _normalize_text(instruction)
    for field in fields:
        field_id = str(field.get("field_id") or "")
        if field_id and field_id.lower() in normalized_instruction:
            return field_id
    if slot:
        slot_id = str(slot.get("slot_id") or "")
        for field in fields:
            field_id = str(field.get("field_id") or "")
            if field_id == slot_id or field_id.endswith(slot_id) or slot_id.endswith(field_id):
                return field_id
    return fields[0]["field_id"] if fields else None


def _target_slots(slots: list[dict[str, Any]], instruction: str, requested: list[str] | None = None) -> list[dict[str, Any]]:
    result = []
    seen = set()
    for slot_id in requested or []:
        slot = _find_by_id(slots, "slot_id", slot_id)
        if slot and slot_id not in seen:
            seen.add(slot_id)
            result.append(slot)
    if result:
        return result
    explicit_patterns = [
        r"(?:заполн(?:и|ить|яем)|сохран(?:и|ить|яем))\s+(?:слот\s+)?[\"«]?([^\"».\n]+?)[\"»]?\s+(?:из|полем|поле|значением)",
        r"(?:целевой\s+слот|слот-приемник)\s+[\"«]?([^\"».\n]+)[\"»]?",
    ]
    for pattern in explicit_patterns:
        for match in re.findall(pattern, instruction or "", flags=re.IGNORECASE):
            slot = _slot_by_label(slots, match.strip(" .,:;"))
            if slot and slot["slot_id"] not in seen:
                seen.add(slot["slot_id"])
                result.append(slot)
    if result:
        return result
    for match in re.findall(
        r"(?:заполн(?:и|ить|яем)|целевой\s+слот|слот-приемник)\s+(?:слот\s+)?[\"«]?([^\"».]+)[\"»]?",
        instruction or "",
        flags=re.IGNORECASE,
    ):
        slot = _slot_by_label(slots, match.strip(" .,:;"))
        if slot and slot["slot_id"] not in seen:
            seen.add(slot["slot_id"])
            result.append(slot)
    if result:
        return result
    return [slot for slot in slots if slot.get("required")][:1]


def _extract_entity_name(instruction: str, fallback: str) -> str:
    match = re.search(
        r"(?:сохран(?:и|ить|яем|яем результат)?(?:\s+результат)?\s+как|result\s+as)\s+([A-Za-z][A-Za-z0-9_.-]*)",
        instruction or "",
        flags=re.IGNORECASE,
    )
    return _id(match.group(1) if match else fallback)


def _on_error_from_instruction(instruction: str, default: str = "continue_to_llm") -> str:
    text = _normalize_text(instruction)
    if "оператор" in text or "эскалац" in text or "переда" in text:
        return "escalate_operator"
    if "клиент" in text or "уточн" in text or "вопрос" in text:
        return "stop_and_ask_client"
    return default


def _failure_action_from_instruction(instruction: str, *, ambiguous: bool) -> str:
    text = _normalize_text(instruction)
    keyword_present = ("несколько" in text or "неоднознач" in text) if ambiguous else ("нет результат" in text or "не найден" in text)
    if keyword_present and ("оператор" in text or "эскалац" in text or "переда" in text):
        return "operator_handoff"
    if keyword_present and ("клиент" in text or "уточн" in text or "вопрос" in text):
        return "ask_client"
    return "ask_client" if ambiguous else "continue"


def compile_slot_autofill_profile(
    *,
    instruction: str,
    slot_schema: dict[str, Any],
    tools: list[dict[str, Any]],
    react_call: str | None = None,
    target_slots: list[str] | None = None,
) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []
    slots = slot_schema.get("slots", [])
    read_only_tools = [tool for tool in tools if tool.get("action_type") == "read_only"]
    tool = _tool_by_name(read_only_tools, react_call, instruction)
    if not tool:
        errors.append("Не найден read-only ReAct-вызов для профиля автозаполнения.")
        tool = {}
    parameters = list(schema_properties(tool.get("parameters_schema", {})).keys())
    required_parameters = set(schema_required(tool.get("parameters_schema", {})))
    input_mapping: dict[str, str] = {}
    for parameter in parameters:
        slot = _slot_for_parameter(parameter, slots, instruction)
        if slot:
            input_mapping[parameter] = f"slot:{slot['slot_id']}"
        elif parameter in required_parameters:
            errors.append(f"Не удалось подобрать слот для обязательного параметра ReAct-вызова: {parameter}.")
        else:
            warnings.append(f"Не удалось подобрать источник для необязательного параметра: {parameter}.")

    result_fields = _operation_schema_fields(tool.get("result_schema", {}))
    selected_targets = _target_slots(slots, instruction, target_slots)
    output_mapping = []
    for slot in selected_targets:
        field_id = _result_field_for_slot(slot, result_fields, instruction)
        if not field_id:
            errors.append(f"Не удалось подобрать поле результата для слота {slot.get('slot_id')}.")
            continue
        output_mapping.append(
            {
                "result_field": field_id,
                "target_slot": slot["slot_id"],
                "required_for_success": bool(slot.get("required", True)),
            }
        )
    if not output_mapping:
        errors.append("Не удалось сформировать ни одного выходного маппинга в слот.")

    structure = {
        "react_call": tool.get("tool_name", react_call or ""),
        "accept_policy": "single_result" if "единствен" in _normalize_text(instruction) or "один" in _normalize_text(instruction) else "always",
        "input_mapping": input_mapping,
        "output_mapping": output_mapping,
        "on_no_result": _failure_action_from_instruction(instruction, ambiguous=False),
        "on_ambiguous_result": _failure_action_from_instruction(instruction, ambiguous=True),
        "configuration_instruction": instruction,
        "generated_structure_metadata": {
            "generator": "config_assistant",
            "mode": "deterministic",
            "source": "slot_autofill_instruction",
        },
    }
    return {
        "schema_version": "1.0",
        "structure": structure,
        "references": {
            "slot_schema_id": slot_schema.get("slot_schema_id"),
            "react_call": structure["react_call"],
            "input_parameters": parameters,
            "result_fields": [field["field_id"] for field in result_fields],
            "target_slots": [item["target_slot"] for item in output_mapping],
        },
        "warnings": warnings,
        "validation_errors": errors,
    }


def compile_attribute_resolution_step(
    *,
    instruction: str,
    slot_schema: dict[str, Any],
    tools: list[dict[str, Any]],
    react_call: str | None = None,
    step_name: str | None = None,
    previous_steps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []
    slots = slot_schema.get("slots", [])
    tool = _tool_by_name(tools, react_call, instruction)
    if not tool:
        errors.append("Не найден ReAct-вызов для шага разрешения атрибута.")
        tool = {}
    parameters = list(schema_properties(tool.get("parameters_schema", {})).keys())
    required_parameters = set(schema_required(tool.get("parameters_schema", {})))
    parameter_mapping: dict[str, str] = {}
    entity_refs = re.findall(r"entity:([A-Za-z][A-Za-z0-9_.-]*(?:\.\d+)?(?:\.[A-Za-z][A-Za-z0-9_.-]*)*)", instruction or "")
    previous_entity_names = [step.get("result_entity_name") for step in previous_steps or [] if step.get("result_entity_name")]
    for parameter in parameters:
        explicit = re.search(
            rf"(?:параметр\s+)?{re.escape(parameter)}\s+(?:передай|заполни|=|<-)\s+((?:slot|entity|output|constant|secret):[A-Za-z0-9_.:-]+)",
            instruction or "",
            flags=re.IGNORECASE,
        )
        if explicit:
            parameter_mapping[parameter] = explicit.group(1).rstrip(".,;")
            continue
        slot = _slot_for_parameter(parameter, slots, instruction)
        if slot:
            parameter_mapping[parameter] = f"slot:{slot['slot_id']}"
            continue
        if entity_refs:
            parameter_mapping[parameter] = f"entity:{entity_refs[0]}"
            continue
        if previous_entity_names and parameter in {"login", "user_login", "user_id"}:
            parameter_mapping[parameter] = f"entity:{previous_entity_names[0]}.{parameter}"
            continue
        if parameter in required_parameters:
            errors.append(f"Не удалось подобрать источник для обязательного параметра шага: {parameter}.")
        else:
            warnings.append(f"Не удалось подобрать источник для необязательного параметра шага: {parameter}.")

    fallback_entity = _id((tool.get("tool_name") or "result").replace("get_", "").replace("search_", ""))
    entity_name = _extract_entity_name(instruction, fallback_entity)
    result_fields = [
        {
            "field_id": field["field_id"],
            "display_name": field["display_name"],
            "field_type": field["field_type"],
            "description": field.get("description", ""),
        }
        for field in _operation_schema_fields(tool.get("result_schema", {}))
    ]
    if not result_fields:
        result_fields = [{"field_id": "value", "display_name": "Значение", "field_type": "unknown", "description": ""}]
        warnings.append("Контракт результата ReAct-вызова пустой; добавлено поле value.")

    resolved_step_name = step_name or ""
    if not resolved_step_name:
        match = re.search(r"шаг\s*[:.-]\s*([^\n.]+)", instruction or "", flags=re.IGNORECASE)
        resolved_step_name = (match.group(1).strip() if match else "") or f"Получить {_humanize(entity_name)}"
    structure = {
        "step_name": resolved_step_name[:240],
        "react_call": tool.get("tool_name", react_call or ""),
        "parameter_mapping": parameter_mapping,
        "result_entity_name": entity_name,
        "result_entity_description": f"Результат ReAct-вызова {tool.get('tool_name') or react_call or 'не выбран'}.",
        "result_fields": result_fields,
        "on_error": _on_error_from_instruction(instruction),
        "configuration_instruction": instruction,
        "generated_structure_metadata": {
            "generator": "config_assistant",
            "mode": "deterministic",
            "source": "attribute_resolution_step_instruction",
        },
    }
    return {
        "schema_version": "1.0",
        "structure": structure,
        "references": {
            "slot_schema_id": slot_schema.get("slot_schema_id"),
            "react_call": structure["react_call"],
            "input_parameters": parameters,
            "result_entity_name": entity_name,
            "result_fields": [field["field_id"] for field in result_fields],
        },
        "warnings": warnings,
        "validation_errors": errors,
    }
