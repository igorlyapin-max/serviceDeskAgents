from __future__ import annotations

import re
from typing import Any

from .config_registry import (
    canonical_react_parameter_schema,
    constant_source_ref,
    enrichment_step_result_schema,
    format_required_parameter_group,
    react_visible_parameter_schema,
    schema_declares_path,
    schema_properties,
    schema_parameter_default,
    schema_required,
    schema_required_parameter_groups,
    select_tool_binding,
)


def _normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _find_by_id(items: list[dict[str, Any]], key: str, value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    return next((item for item in items if item.get(key) == value), None)


def _react_parameter_schema(tool: dict[str, Any] | None) -> dict[str, Any]:
    canonical_schema = canonical_react_parameter_schema((tool or {}).get("tool_name"))
    if canonical_schema:
        return canonical_schema
    return react_visible_parameter_schema((tool or {}).get("parameters_schema"))


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


def _instruction_react_calls(instruction: str) -> list[str]:
    calls: list[str] = []
    seen: set[str] = set()
    for call in [*_template_react_calls(instruction), *_template_param_calls(instruction)]:
        if call and call not in seen:
            seen.add(call)
            calls.append(call)
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
    if len(parts) >= 2 and parts[0] in {"slot", "output", "case"}:
        return f"{parts[0]}:{'.'.join(parts[1:])}"
    return None


def _constant_binding_from_raw(value: str | None) -> str | None:
    raw_value = str(value or "").strip()
    if not raw_value:
        return None
    if raw_value.startswith("${") or re.match(r"^(?:slot|output|step|case|constant|secret):", raw_value):
        return None
    constant = raw_value.rstrip(".,;")
    if (
        (constant.startswith('"') and constant.endswith('"'))
        or (constant.startswith("'") and constant.endswith("'"))
        or (constant.startswith("«") and constant.endswith("»"))
    ):
        constant = constant[1:-1].strip()
    if not constant:
        return None
    return f"constant:{constant}"


def _template_ref_at(value: str, position: int) -> tuple[str, int] | None:
    if not value.startswith("${", position):
        return None
    end = value.find("}", position + 2)
    if end == -1:
        return None
    return value[position + 2:end].strip(), end + 1


def _input_value_start(value: str, position: int) -> int | None:
    match = re.match(r"\s*(?:<-|=|из|from)\s*", value[position:], flags=re.IGNORECASE)
    return position + match.end() if match else None


def _input_value_end(value: str, position: int) -> int:
    boundaries = [len(value)]
    for pattern in (
        r"\s+\$\{paramReAct\.",
        r"\s+\$\{(?:slot|output|step|case)\.",
        r"\s+результат\b",
        r"\s+если\b",
        r"\n",
    ):
        match = re.search(pattern, value[position:], flags=re.IGNORECASE)
        if match:
            boundaries.append(position + match.start())
    return min(boundaries)


def _template_input_parameter_names(instruction: str, react_call: str | None = None) -> set[str]:
    result: set[str] = set()
    for ref in _template_refs(instruction):
        parsed = _template_param_ref(ref)
        if not parsed or parsed["kind"] != "input":
            continue
        if react_call and parsed["call"] != react_call:
            continue
        result.add(parsed["name"])
    return result


def _template_input_bindings(instruction: str, react_call: str | None = None) -> dict[str, str]:
    text = instruction or ""
    param_pattern = _template_param_ref_pattern("input")
    source_pattern = r"\$\{(?P<source>(?:slot|output|step|case)\.[^{}]+)\}"
    result: dict[str, str] = {}
    source_patterns = [
        rf"{param_pattern}\s*(?:<-|=|из|from)\s*{source_pattern}",
        rf"{source_pattern}\s*(?:->|=>|в|to)\s*{param_pattern}",
    ]
    for pattern in source_patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            if react_call and match.group("call") != react_call:
                continue
            binding = _binding_from_template_ref(match.group("source"))
            if binding:
                result[match.group("name")] = binding

    for match in re.finditer(param_pattern, text, flags=re.IGNORECASE):
        if react_call and match.group("call") != react_call:
            continue
        value_start = _input_value_start(text, match.end())
        if value_start is None:
            continue
        template_ref = _template_ref_at(text, value_start)
        if template_ref:
            binding = _binding_from_template_ref(template_ref[0])
        else:
            value_end = _input_value_end(text, value_start)
            binding = _constant_binding_from_raw(text[value_start:value_end])
        if binding:
            result[match.group("name")] = binding
    return result


def _template_source_for_parameter(parameter: str, instruction: str, react_call: str | None = None) -> str | None:
    return _template_input_bindings(instruction, react_call).get(parameter)


def _operation_schema_fields(schema: dict[str, Any] | None) -> list[dict[str, Any]]:
    properties = schema_properties(schema or {})
    required = set(schema_required(schema or {}))
    result: list[dict[str, Any]] = []
    for field_id, property_schema in properties.items():
        result.append({
            "field_id": field_id,
            "display_name": property_schema.get("title") or _humanize(field_id),
            "field_type": _schema_type(property_schema),
            "description": property_schema.get("description", ""),
            "required": field_id in required,
        })
        nested_properties = schema_properties(property_schema)
        nested_required = set(schema_required(property_schema))
        for nested_id, nested_schema in nested_properties.items():
            nested_field_id = f"{field_id}.{nested_id}"
            result.append({
                "field_id": nested_field_id,
                "display_name": nested_schema.get("title") or _humanize(nested_field_id),
                "field_type": _schema_type(nested_schema),
                "description": nested_schema.get("description", ""),
                "required": field_id in required and nested_id in nested_required,
            })
    return result


def _endpoint_by_id(integration_endpoints: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    return {
        str(endpoint.get("endpoint_id") or ""): endpoint
        for endpoint in integration_endpoints or []
        if endpoint.get("endpoint_id")
    }


def _operation_for_tool(
    tool: dict[str, Any] | None,
    integration_endpoints: list[dict[str, Any]] | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    binding = select_tool_binding(tool)
    endpoint = _endpoint_by_id(integration_endpoints).get((binding or {}).get("endpoint_id") or "")
    operation = (endpoint or {}).get("operations", {}).get((binding or {}).get("operation_id") or "")
    return binding, operation if isinstance(operation, dict) else None


def _external_event_completion_policy(
    operation: dict[str, Any] | None,
) -> dict[str, Any] | None:
    contracts = (operation or {}).get("async_event_contracts") or {}
    event_types = [event_type for event_type in contracts if event_type]
    if len(event_types) != 1:
        return None
    result_delivery = ((operation or {}).get("extensions") or {}).get("result_delivery") or {}
    policy = {
        "mode": "external_event",
        "max_wait_seconds": 86400,
        "timeout_action": "escalate_operator",
        "expected_event_type": event_types[0],
        "result_transport": result_delivery.get("default_transport") or "kafka_event",
    }
    result_topic = result_delivery.get("default_result_topic")
    if result_topic:
        policy["result_topic"] = result_topic
    return policy


def _result_schema_for_tool(
    tool: dict[str, Any] | None,
    integration_endpoints: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    binding, operation = _operation_for_tool(tool, integration_endpoints)
    completion_policy = _external_event_completion_policy(operation)
    if not binding or not operation or not completion_policy:
        return (tool or {}).get("result_schema")
    step = {
        "react_call": (tool or {}).get("tool_name"),
        "endpoint_id": binding.get("endpoint_id"),
        "operation_id": binding.get("operation_id"),
        "completion_policy": completion_policy,
    }
    result_schema, _tool, _operation = enrichment_step_result_schema(
        step,
        tool_by_name={str((tool or {}).get("tool_name") or ""): tool or {}},
        endpoint_by_id=_endpoint_by_id(integration_endpoints),
    )
    return result_schema or (tool or {}).get("result_schema")


def _schema_type(schema: dict[str, Any] | None) -> str:
    value = (schema or {}).get("type")
    if isinstance(value, list):
        value = next((item for item in value if item != "null"), None)
    if value == "integer":
        return "number"
    return value if value in {"string", "number", "boolean", "object", "array"} else "unknown"


def _humanize(value: str) -> str:
    return str(value or "").replace("_", " ").replace("-", " ").strip().capitalize() or "Значение"


def _tool_by_name(tools: list[dict[str, Any]], react_call: str | None, instruction: str) -> dict[str, Any] | None:
    instruction_calls = _instruction_react_calls(instruction)
    for template_call in instruction_calls:
        tool = _find_by_id(tools, "tool_name", template_call)
        if tool:
            return tool
    if instruction_calls:
        return None
    if react_call:
        return _find_by_id(tools, "tool_name", react_call)
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
    slot_target_pattern = (
        r"(?:\$\{slot\.(?P<slot>[A-Za-z][A-Za-z0-9_.-]*)\}"
        r"|(?P<plain_slot>[A-Za-z][A-Za-z0-9_.-]*))"
    )
    for pattern in [
        rf"{slot_target_pattern}\s*(?:<-|=|из|from)\s*{output_pattern}",
        rf"{output_pattern}\s*(?:->|=>|в|to)\s*{slot_target_pattern}",
    ]:
        for match in re.finditer(pattern, instruction or "", flags=re.IGNORECASE):
            if react_call and match.group("call") != react_call:
                continue
            target = match.group("slot") or match.group("plain_slot")
            if target:
                hints.append({"target": target, "field": match.group("name")})
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


def _template_reference_errors(
    *,
    instruction: str,
    slots: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    tool: dict[str, Any] | None = None,
    previous_steps: list[dict[str, Any]] | None = None,
    integration_endpoints: list[dict[str, Any]] | None = None,
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
                input_names = set(schema_properties(_react_parameter_schema(ref_tool)).keys())
                if input_names and name not in input_names:
                    errors.append(f"Ссылка ${{{ref}}} указывает на неизвестный входной параметр ReAct-вызова {ref_tool_name}: {name}.")
            elif kind == "output":
                result_schema = _result_schema_for_tool(ref_tool, integration_endpoints)
                output_names = set(field["field_id"] for field in _operation_schema_fields(result_schema or {}))
                if output_names and not schema_declares_path(
                    result_schema or {},
                    name,
                    allow_nested_additional=True,
                ):
                    errors.append(f"Ссылка ${{{ref}}} указывает на неизвестное поле результата ReAct-вызова {ref_tool_name}: {name}.")
        elif parts[0] == "entity":
            errors.append(
                f"Ссылка ${{{ref}}} использует устаревший тип entity. "
                "Используйте ${step.<step_id>.react.<react_call>.output.<field>}."
            )
        elif parts[0] == "channel":
            if len(parts) < 3:
                errors.append(f"Ссылка ${{{ref}}} должна иметь формат ${{channel.<channel_id>.<parameter>}}.")
        elif parts[0] == "case":
            if len(parts) < 2:
                errors.append(f"Ссылка ${{{ref}}} должна иметь формат ${{case.<field>}}.")
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
                input_names = set(schema_properties(_react_parameter_schema(ref_tool)).keys())
                if input_names and parsed_step["name"] not in input_names:
                    errors.append(
                        f"Ссылка ${{{ref}}} указывает на неизвестный входной параметр "
                        f"ReAct-вызова {parsed_step['call']}: {parsed_step['name']}."
                    )
            elif ref_tool and parsed_step["kind"] == "output":
                ref_result_schema, _, _ = enrichment_step_result_schema(
                    ref_step,
                    tool_by_name=tools_by_name,
                    endpoint_by_id=_endpoint_by_id(integration_endpoints),
                )
                output_names = set(field["field_id"] for field in _operation_schema_fields(ref_result_schema or ref_tool.get("result_schema", {})))
                output_name = parsed_step["name"].split(".")[-1]
                if output_names and not schema_declares_path(
                    ref_result_schema or ref_tool.get("result_schema", {}),
                    parsed_step["name"],
                    allow_nested_additional=True,
                ) and output_name not in output_names:
                    errors.append(
                        f"Ссылка ${{{ref}}} указывает на неизвестное поле результата "
                        f"ReAct-вызова {parsed_step['call']}: {parsed_step['name']}."
                    )
        else:
            errors.append(f"Неизвестный тип ссылки ${{{ref}}}.")
    return errors


def compile_attribute_resolution_step(
    *,
    instruction: str,
    slot_schema: dict[str, Any],
    tools: list[dict[str, Any]],
    react_call: str | None = None,
    step_name: str | None = None,
    previous_steps: list[dict[str, Any]] | None = None,
    integration_endpoints: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []
    slots = slot_schema.get("slots", [])
    instruction_calls = _instruction_react_calls(instruction)
    if len(instruction_calls) > 1:
        errors.append(
            "Один шаг разрешения атрибута может использовать только один ReAct-вызов. "
            f"Найдены: {', '.join(instruction_calls)}."
        )
    requested_react_call = instruction_calls[0] if instruction_calls else react_call
    tool = _tool_by_name(tools, requested_react_call, instruction)
    if not tool:
        errors.append("Не найден ReAct-вызов для шага разрешения атрибута.")
        tool = {}
    errors.extend(_template_reference_errors(
        instruction=instruction,
        slots=slots,
        tools=tools,
        tool=tool,
        previous_steps=previous_steps,
        integration_endpoints=integration_endpoints,
    ))
    parameter_schema = _react_parameter_schema(tool)
    parameters = list(schema_properties(parameter_schema).keys())
    required_groups = schema_required_parameter_groups(parameter_schema)
    required_parameters = {parameter for group in required_groups for parameter in group}
    parameter_mapping: dict[str, str] = {}
    selected_react_call = tool.get("tool_name") or requested_react_call
    explicit_input_bindings = _template_input_bindings(instruction, selected_react_call)
    referenced_input_parameters = _template_input_parameter_names(instruction, selected_react_call)
    if re.search(r"\bentity:", instruction or "", flags=re.IGNORECASE):
        errors.append(
            "Ссылки entity:<name> устарели. Используйте step:<step_id>.react.<react_call>.output.<field>."
        )
    for parameter in parameters:
        explicit_source = explicit_input_bindings.get(parameter)
        if explicit_source:
            parameter_mapping[parameter] = explicit_source
            continue
        explicit = re.search(
            rf"(?:параметр\s+)?{re.escape(parameter)}\s+(?:передай|заполни|=|<-)\s+"
            r"((?:slot|output|step|case|constant|secret):[A-Za-z0-9_.:-]+)",
            instruction or "",
            flags=re.IGNORECASE,
        )
        if explicit:
            parameter_mapping[parameter] = explicit.group(1).rstrip(".,;")
            continue
        explicit_constant = re.search(
            rf"(?:параметр\s+)?{re.escape(parameter)}\s*(?:<-|=|из|from)\s*([^\n.]+)",
            instruction or "",
            flags=re.IGNORECASE,
        )
        if explicit_constant:
            binding = _constant_binding_from_raw(explicit_constant.group(1))
            if binding:
                parameter_mapping[parameter] = binding
                continue
        slot = _slot_for_parameter(parameter, slots, instruction, selected_react_call)
        if slot:
            parameter_mapping[parameter] = f"slot:{slot['slot_id']}"
            continue
        has_default, default_value = schema_parameter_default(parameter_schema, parameter)
        if has_default:
            parameter_mapping[parameter] = constant_source_ref(default_value)
            continue
        if parameter not in required_parameters and parameter in referenced_input_parameters:
            warnings.append(f"Не удалось подобрать источник для необязательного параметра шага: {parameter}.")

    for required_group in required_groups:
        if any(parameter in parameter_mapping for parameter in required_group):
            continue
        errors.append(
            "Не удалось подобрать источник для обязательного параметра шага: "
            f"{format_required_parameter_group(required_group)}."
        )

    binding, operation = _operation_for_tool(tool, integration_endpoints)
    completion_policy = _external_event_completion_policy(operation)
    result_schema = _result_schema_for_tool(tool, integration_endpoints)
    result_fields = [
        {
            "field_id": field["field_id"],
            "display_name": field["display_name"],
            "field_type": field["field_type"],
            "description": field.get("description", ""),
        }
        for field in _operation_schema_fields(result_schema or {})
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
        "react_call": selected_react_call or "",
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
    if binding and operation:
        structure["endpoint_id"] = binding.get("endpoint_id") or ""
        structure["operation_id"] = binding.get("operation_id") or ""
    if completion_policy:
        structure["completion_policy"] = completion_policy
    output_mapping_hints = _output_mapping_hints(instruction, selected_react_call)
    for hint in output_mapping_hints:
        hint["source_ref"] = (
            f"${{step.{structure['step_id']}.react.{structure['react_call']}.output.{hint['field']}}}"
        )
    return {
        "schema_version": "1.0",
        "structure": structure,
        "references": {
            "slot_schema_id": slot_schema.get("slot_schema_id"),
            "react_call": structure["react_call"],
            "input_parameters": parameters,
            "result_fields": [field["field_id"] for field in result_fields],
            "output_mapping_hints": output_mapping_hints,
        },
        "warnings": warnings,
        "validation_errors": errors,
    }
