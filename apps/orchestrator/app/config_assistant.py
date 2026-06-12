from __future__ import annotations

import re
from typing import Any

from .config_registry import schema_properties, schema_required


def _normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _find_by_id(items: list[dict[str, Any]], key: str, value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    return next((item for item in items if item.get(key) == value), None)


def _template_refs(instruction: str) -> list[str]:
    return [match.strip() for match in re.findall(r"\$\{([^{}]+)\}", instruction or "") if match.strip()]


def _template_ref_parts(ref: str) -> list[str]:
    return [part for part in str(ref or "").split(".") if part]


def _template_react_calls(instruction: str) -> list[str]:
    calls = []
    for ref in _template_refs(instruction):
        parts = _template_ref_parts(ref)
        if len(parts) == 2 and parts[0] == "ReAct":
            calls.append(parts[1])
    return calls


def _template_param_calls(instruction: str) -> list[str]:
    calls = []
    for ref in _template_refs(instruction):
        parsed = _template_param_ref(ref)
        if parsed:
            calls.append(parsed["call"])
    return calls


def _template_slot_ids(instruction: str) -> list[str]:
    slot_ids = []
    for ref in _template_refs(instruction):
        parts = _template_ref_parts(ref)
        if len(parts) == 2 and parts[0] == "slot":
            slot_ids.append(parts[1])
    return slot_ids


def _template_param_ref_pattern(kind: str) -> str:
    return (
        r"\$\{paramReAct\."
        r"(?P<call>[A-Za-z][A-Za-z0-9_.-]*)\."
        rf"{kind}\."
        r"(?P<name>[A-Za-z][A-Za-z0-9_.-]*)\}"
    )


def _template_param_ref(ref: str) -> dict[str, str] | None:
    match = re.match(
        r"^paramReAct\.(?P<call>[A-Za-z][A-Za-z0-9_.-]*)\.(?P<kind>input|output)\.(?P<name>[A-Za-z][A-Za-z0-9_.-]*)$",
        ref or "",
    )
    return match.groupdict() if match else None


def _template_step_ref(ref: str) -> dict[str, str] | None:
    match = re.match(
        r"^step\.(?P<step_id>step[1-9][0-9]*)\.react\."
        r"(?P<call>[A-Za-z][A-Za-z0-9_.-]*)\."
        r"(?P<kind>input|output)\."
        r"(?P<name>[A-Za-z0-9_][A-Za-z0-9_.-]*)$",
        ref or "",
    )
    return match.groupdict() if match else None


def _binding_from_template_ref(ref: str) -> str | None:
    step_ref = _template_step_ref(ref)
    if step_ref:
        return (
            f"step:{step_ref['step_id']}.react.{step_ref['call']}."
            f"{step_ref['kind']}.{step_ref['name']}"
        )
    parts = _template_ref_parts(ref)
    if len(parts) >= 2 and parts[0] in {"slot", "output"}:
        return f"{parts[0]}:{'.'.join(parts[1:])}"
    return None


def _template_source_for_parameter(parameter: str, instruction: str, react_call: str | None = None) -> str | None:
    param_pattern = _template_param_ref_pattern("input")
    source_pattern = r"\$\{(?P<source>(?:slot|output|step)\.[^{}]+)\}"
    patterns = [
        rf"{param_pattern}\s*(?:<-|=|из|from)\s*{source_pattern}",
        rf"{source_pattern}\s*(?:->|=>|в|to)\s*{param_pattern}",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, instruction or "", flags=re.IGNORECASE):
            if match.group("name") != parameter:
                continue
            if react_call and match.group("call") != react_call:
                continue
            binding = _binding_from_template_ref(match.group("source"))
            if binding:
                return binding
    return None


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
    for template_call in _template_react_calls(instruction):
        tool = _find_by_id(tools, "tool_name", template_call)
        if tool:
            return tool
    for template_call in _template_param_calls(instruction):
        tool = _find_by_id(tools, "tool_name", template_call)
        if tool:
            return tool
    normalized_instruction = _normalize_text(instruction)
    for tool in tools:
        tool_name = _normalize_text(tool.get("tool_name"))
        display_name = _normalize_text(tool.get("display_name"))
        if (tool_name and tool_name in normalized_instruction) or (display_name and display_name in normalized_instruction):
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


def _slot_for_parameter(
    parameter: str,
    slots: list[dict[str, Any]],
    instruction: str,
    react_call: str | None = None,
) -> dict[str, Any] | None:
    explicit_source = _template_source_for_parameter(parameter, instruction, react_call)
    if explicit_source:
        parsed_source, _, parsed_value = explicit_source.partition(":")
        if parsed_source == "slot":
            slot = _slot_by_label(slots, parsed_value)
            if slot:
                return slot
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


def _result_field_for_slot(
    slot: dict[str, Any] | None,
    fields: list[dict[str, Any]],
    instruction: str,
    react_call: str | None = None,
) -> str | None:
    if slot:
        slot_labels = {_normalize_text(slot.get("slot_id")), _normalize_text(slot.get("display_name"))}
        field_ids = {str(field.get("field_id") or "") for field in fields}
        for hint in _output_mapping_hints(instruction, react_call):
            if _normalize_text(hint["target"]) in slot_labels and hint["field"] in field_ids:
                return hint["field"]
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


def _output_mapping_hints(instruction: str, react_call: str | None = None) -> list[dict[str, str]]:
    hints: list[dict[str, str]] = []
    output_pattern = _template_param_ref_pattern("output")
    slot_pattern = r"\$\{slot\.(?P<slot>[A-Za-z][A-Za-z0-9_.-]*)\}"
    for pattern in [
        rf"{slot_pattern}\s*(?:<-|=|из|from)\s*{output_pattern}",
        rf"{output_pattern}\s*(?:->|=>|в|to)\s*{slot_pattern}",
    ]:
        for match in re.finditer(pattern, instruction or "", flags=re.IGNORECASE):
            if react_call and match.group("call") != react_call:
                continue
            hints.append({"target": match.group("slot"), "field": match.group("name")})
    for section in re.findall(r"(?:выходы?|outputs?)\s*:\s*([^.\n]+)", instruction or "", flags=re.IGNORECASE):
        for target, field in re.findall(r"([A-Za-z][A-Za-z0-9_.-]*)\s*<-\s*([A-Za-z][A-Za-z0-9_.-]*)", section):
            hints.append({"target": target, "field": field})
    return hints


def _target_slots(
    slots: list[dict[str, Any]],
    instruction: str,
    requested: list[str] | None = None,
    react_call: str | None = None,
) -> list[dict[str, Any]]:
    result = []
    seen = set()
    for slot_id in requested or []:
        slot = _find_by_id(slots, "slot_id", slot_id)
        if slot and slot_id not in seen:
            seen.add(slot_id)
            result.append(slot)
    if result:
        return result
    for hint in _output_mapping_hints(instruction, react_call):
        slot = _slot_by_label(slots, hint["target"])
        if slot and slot["slot_id"] not in seen:
            seen.add(slot["slot_id"])
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
    for slot_id in _template_slot_ids(instruction):
        slot = _slot_by_label(slots, slot_id)
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


def _on_error_from_instruction(instruction: str, default: str = "continue_to_llm") -> str:
    text = _normalize_text(instruction)
    if "оператор" in text or "эскалац" in text or "переда" in text:
        return "escalate_operator"
    if "клиент" in text or "уточн" in text or "вопрос" in text:
        return "stop_and_ask_client"
    return default


def _failure_clause(instruction: str, *, ambiguous: bool) -> str:
    text = str(instruction or "").lower()
    trigger = (
        r"(?:несколько\s+результат(?:а|ов)?|неоднознач\w*)"
        if ambiguous
        else r"(?:нет\s+результат(?:а|ов)?|не\s+найден\w*)"
    )
    match = re.search(trigger, text)
    if not match:
        return ""
    end_positions = [pos for pos in (text.find(".", match.start()), text.find(";", match.start()), text.find("\n", match.start())) if pos >= 0]
    end = min(end_positions) if end_positions else len(text)
    return _normalize_text(text[match.start():end])


def _failure_action_from_instruction(instruction: str, *, ambiguous: bool) -> str:
    clause = _failure_clause(instruction, ambiguous=ambiguous)
    if not clause:
        return "ask_client" if ambiguous else "continue"
    if "продолж" in clause:
        return "continue"
    if "оператор" in clause or "эскалац" in clause or "переда" in clause:
        return "operator_handoff"
    if "клиент" in clause or "уточн" in clause or "вопрос" in clause:
        return "ask_client"
    return "ask_client" if ambiguous else "continue"


def _run_order_from_instruction(instruction: str) -> tuple[int | None, str | None]:
    match = re.search(
        r"(?:порядок\s+запуска|run[_\s-]?order)\s*[:=]?\s*(\d+)",
        instruction or "",
        flags=re.IGNORECASE,
    )
    if not match:
        return None, None
    value = int(match.group(1))
    if 1 <= value <= 100:
        return value, None
    return None, f"Порядок запуска {value} вне диапазона 1..100."


def _template_reference_errors(
    *,
    instruction: str,
    slots: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    tool: dict[str, Any] | None = None,
    previous_steps: list[dict[str, Any]] | None = None,
) -> list[str]:
    errors: list[str] = []
    slot_ids = {str(slot.get("slot_id") or "") for slot in slots}
    tool_names = {str(item.get("tool_name") or "") for item in tools}
    selected_tool = tool or {}
    selected_tool_name = str(selected_tool.get("tool_name") or "")
    tools_by_name = {str(item.get("tool_name") or ""): item for item in tools if item.get("tool_name")}
    previous_steps_by_id = {
        str(step.get("step_id") or f"step{index}"): step
        for index, step in enumerate(previous_steps or [], start=1)
    }
    for ref in _template_refs(instruction):
        parts = _template_ref_parts(ref)
        if not parts:
            continue
        if parts[0] == "slot":
            slot_id = ".".join(parts[1:])
            if slot_id not in slot_ids:
                errors.append(f"Ссылка ${{{ref}}} указывает на неизвестный слот: {slot_id}.")
        elif parts[0] == "ReAct":
            tool_name = ".".join(parts[1:])
            if tool_name not in tool_names:
                errors.append(f"Ссылка ${{{ref}}} указывает на неизвестный ReAct-вызов: {tool_name}.")
        elif parts[0] == "paramReAct":
            parsed_param = _template_param_ref(ref)
            if len(parts) == 3 and parts[1] in {"input", "output"}:
                errors.append(
                    f"Ссылка ${{{ref}}} использует короткую форму. "
                    "Укажите владельца параметра: ${paramReAct.<react_call>.input.<parameter>} "
                    "или ${paramReAct.<react_call>.output.<field>}."
                )
                continue
            if not parsed_param:
                errors.append(
                    f"Ссылка ${{{ref}}} должна иметь формат "
                    "${paramReAct.<react_call>.input.<parameter>} или ${paramReAct.<react_call>.output.<field>}."
                )
                continue
            ref_tool_name = parsed_param["call"]
            ref_tool = tools_by_name.get(ref_tool_name)
            if not ref_tool:
                errors.append(f"Ссылка ${{{ref}}} указывает на неизвестный ReAct-вызов: {ref_tool_name}.")
                continue
            if selected_tool_name and ref_tool_name != selected_tool_name:
                errors.append(
                    f"Ссылка ${{{ref}}} относится к ReAct-вызову {ref_tool_name}, "
                    f"но текущий профиль/шаг использует {selected_tool_name}."
                )
                continue
            kind = parsed_param["kind"]
            name = parsed_param["name"]
            if kind == "input":
                input_names = set(schema_properties(ref_tool.get("parameters_schema", {})).keys())
                if input_names and name not in input_names:
                    errors.append(f"Ссылка ${{{ref}}} указывает на неизвестный входной параметр ReAct-вызова {ref_tool_name}: {name}.")
            elif kind == "output":
                output_names = set(field["field_id"] for field in _operation_schema_fields(ref_tool.get("result_schema", {})))
                if output_names and name not in output_names:
                    errors.append(f"Ссылка ${{{ref}}} указывает на неизвестное поле результата ReAct-вызова {ref_tool_name}: {name}.")
        elif parts[0] == "entity":
            errors.append(
                f"Ссылка ${{{ref}}} использует устаревший тип entity. "
                "Используйте ${step.<step_id>.react.<react_call>.output.<field>}."
            )
        elif parts[0] == "step":
            parsed_step = _template_step_ref(ref)
            if not parsed_step:
                errors.append(
                    f"Ссылка ${{{ref}}} должна иметь формат "
                    "${step.<step_id>.react.<react_call>.input.<parameter>} "
                    "или ${step.<step_id>.react.<react_call>.output.<field>}."
                )
                continue
            ref_step = previous_steps_by_id.get(parsed_step["step_id"])
            if not ref_step:
                errors.append(f"Ссылка ${{{ref}}} указывает на неизвестный предыдущий шаг: {parsed_step['step_id']}.")
                continue
            if ref_step.get("react_call") != parsed_step["call"]:
                errors.append(
                    f"Ссылка ${{{ref}}} ожидает ReAct-вызов {parsed_step['call']} "
                    f"в {parsed_step['step_id']}, но там настроен {ref_step.get('react_call')}."
                )
                continue
            ref_tool = tools_by_name.get(parsed_step["call"])
            if ref_tool and parsed_step["kind"] == "input":
                input_names = set(schema_properties(ref_tool.get("parameters_schema", {})).keys())
                if input_names and parsed_step["name"] not in input_names:
                    errors.append(
                        f"Ссылка ${{{ref}}} указывает на неизвестный входной параметр "
                        f"ReAct-вызова {parsed_step['call']}: {parsed_step['name']}."
                    )
            elif ref_tool and parsed_step["kind"] == "output":
                output_names = set(field["field_id"] for field in _operation_schema_fields(ref_tool.get("result_schema", {})))
                output_name = parsed_step["name"].split(".")[-1]
                if output_names and parsed_step["name"] not in output_names and output_name not in output_names:
                    errors.append(
                        f"Ссылка ${{{ref}}} указывает на неизвестное поле результата "
                        f"ReAct-вызова {parsed_step['call']}: {parsed_step['name']}."
                    )
        else:
            errors.append(f"Неизвестный тип ссылки ${{{ref}}}.")
    return errors


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
    errors.extend(_template_reference_errors(instruction=instruction, slots=slots, tools=read_only_tools, tool=tool))
    parameters = list(schema_properties(tool.get("parameters_schema", {})).keys())
    required_parameters = set(schema_required(tool.get("parameters_schema", {})))
    input_mapping: dict[str, str] = {}
    selected_react_call = tool.get("tool_name") or react_call
    for parameter in parameters:
        explicit_source = _template_source_for_parameter(parameter, instruction, selected_react_call)
        if explicit_source:
            input_mapping[parameter] = explicit_source
            continue
        slot = _slot_for_parameter(parameter, slots, instruction, selected_react_call)
        if slot:
            input_mapping[parameter] = f"slot:{slot['slot_id']}"
        elif parameter in required_parameters:
            errors.append(f"Не удалось подобрать слот для обязательного параметра ReAct-вызова: {parameter}.")
        else:
            warnings.append(f"Не удалось подобрать источник для необязательного параметра: {parameter}.")

    result_fields = _operation_schema_fields(tool.get("result_schema", {}))
    selected_targets = _target_slots(slots, instruction, target_slots, selected_react_call)
    output_mapping = []
    for slot in selected_targets:
        field_id = _result_field_for_slot(slot, result_fields, instruction, selected_react_call)
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

    run_order, run_order_warning = _run_order_from_instruction(instruction)
    if run_order_warning:
        warnings.append(run_order_warning)

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
            "source_instruction": instruction,
        },
    }
    if run_order is not None:
        structure["run_order"] = run_order
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
    errors.extend(_template_reference_errors(instruction=instruction, slots=slots, tools=tools, tool=tool, previous_steps=previous_steps))
    parameters = list(schema_properties(tool.get("parameters_schema", {})).keys())
    required_parameters = set(schema_required(tool.get("parameters_schema", {})))
    parameter_mapping: dict[str, str] = {}
    selected_react_call = tool.get("tool_name") or react_call
    if re.search(r"\bentity:", instruction or "", flags=re.IGNORECASE):
        errors.append(
            "Ссылки entity:<name> устарели. Используйте step:<step_id>.react.<react_call>.output.<field>."
        )
    for parameter in parameters:
        explicit_source = _template_source_for_parameter(parameter, instruction, selected_react_call)
        if explicit_source:
            parameter_mapping[parameter] = explicit_source
            continue
        explicit = re.search(
            rf"(?:параметр\s+)?{re.escape(parameter)}\s+(?:передай|заполни|=|<-)\s+((?:slot|output|step|constant|secret):[A-Za-z0-9_.:-]+)",
            instruction or "",
            flags=re.IGNORECASE,
        )
        if explicit:
            parameter_mapping[parameter] = explicit.group(1).rstrip(".,;")
            continue
        slot = _slot_for_parameter(parameter, slots, instruction, selected_react_call)
        if slot:
            parameter_mapping[parameter] = f"slot:{slot['slot_id']}"
            continue
        if parameter in required_parameters:
            errors.append(f"Не удалось подобрать источник для обязательного параметра шага: {parameter}.")
        else:
            warnings.append(f"Не удалось подобрать источник для необязательного параметра шага: {parameter}.")

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
        call_label = tool.get("display_name") or tool.get("tool_name") or react_call or "результат"
        resolved_step_name = (match.group(1).strip() if match else "") or f"Получить {_humanize(call_label)}"
    structure = {
        "step_id": f"step{len(previous_steps or []) + 1}",
        "step_name": resolved_step_name[:240],
        "react_call": tool.get("tool_name", react_call or ""),
        "parameter_mapping": parameter_mapping,
        "on_error": _on_error_from_instruction(instruction),
        "configuration_instruction": instruction,
        "generated_structure_metadata": {
            "generator": "config_assistant",
            "mode": "deterministic",
            "source": "attribute_resolution_step_instruction",
            "result_fields": result_fields,
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
        },
        "warnings": warnings,
        "validation_errors": errors,
    }
