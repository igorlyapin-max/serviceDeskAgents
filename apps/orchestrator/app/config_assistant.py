from __future__ import annotations

import copy
import json
import os
import re
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request

from .config_registry import (
    DEFAULT_CAPABILITY_STEP_ASSIST_PROMPT_TEMPLATE,
    constant_source_ref,
    format_required_parameter_group,
    parse_json_object,
    schema_at_path,
    schema_declares_path,
    schema_properties,
    schema_parameter_default,
    schema_required,
    schema_required_parameter_groups,
    select_model_provider,
)
from .http_client import urlopen_with_retry
from .privacy import redact_for_llm


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


def _template_capability_ids(instruction: str) -> list[str]:
    capability_ids = []
    for ref in _template_refs(instruction):
        parts = _template_ref_parts(ref)
        if len(parts) == 2 and parts[0] == "Capability":
            capability_ids.append(parts[1])
            continue
        parsed = _template_capability_param_ref(ref)
        if parsed:
            capability_ids.append(parsed["capability_id"])
    result: list[str] = []
    seen: set[str] = set()
    for capability_id in capability_ids:
        if capability_id and capability_id not in seen:
            seen.add(capability_id)
            result.append(capability_id)
    return result


def _template_slot_ids(instruction: str) -> list[str]:
    slot_ids = []
    for ref in _template_refs(instruction):
        parts = _template_ref_parts(ref)
        if len(parts) == 2 and parts[0] == "slot":
            slot_ids.append(parts[1])
    return slot_ids


def _template_capability_ref_pattern(kind: str) -> str:
    return (
        r"\$\{paramCapability\."
        r"(?P<capability_id>[A-Za-z][A-Za-z0-9_.-]*)\."
        rf"{kind}\."
        r"(?P<name>[A-Za-z][A-Za-z0-9_.-]*)\}"
    )


def _template_capability_param_ref(ref: str) -> dict[str, str] | None:
    match = re.match(
        r"^paramCapability\.(?P<capability_id>[A-Za-z][A-Za-z0-9_.-]*)\.(?P<kind>input|output)\.(?P<name>[A-Za-z][A-Za-z0-9_.-]*)$",
        ref or "",
    )
    return match.groupdict() if match else None


def _template_step_ref(ref: str) -> dict[str, str] | None:
    capability_match = re.match(
        r"^step\.(?P<step_id>step[1-9][0-9]*)\.capability\."
        r"(?P<capability_id>[A-Za-z][A-Za-z0-9_.-]*)\."
        r"(?P<kind>input|output)\."
        r"(?P<name>[A-Za-z0-9_][A-Za-z0-9_.-]*)$",
        ref or "",
    )
    if capability_match:
        result = capability_match.groupdict()
        result["owner_type"] = "capability"
        return result
    return None


def _binding_from_template_ref(ref: str) -> str | None:
    step_ref = _template_step_ref(ref)
    if step_ref:
        return (
            f"step:{step_ref['step_id']}.capability.{step_ref['capability_id']}."
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
        r"\s+\$\{paramCapability\.",
        r"\s+\$\{(?:slot|output|step|case)\.",
        r"\s+результат\b",
        r"\s+если\b",
        r"\n",
    ):
        match = re.search(pattern, value[position:], flags=re.IGNORECASE)
        if match:
            boundaries.append(position + match.start())
    return min(boundaries)


def _template_capability_input_parameter_names(instruction: str, capability_id: str | None = None) -> set[str]:
    result: set[str] = set()
    for ref in _template_refs(instruction):
        parsed = _template_capability_param_ref(ref)
        if not parsed or parsed["kind"] != "input":
            continue
        if capability_id and parsed["capability_id"] != capability_id:
            continue
        result.add(parsed["name"])
    return result


def _template_capability_input_bindings(instruction: str, capability_id: str | None = None) -> dict[str, str]:
    text = instruction or ""
    param_pattern = _template_capability_ref_pattern("input")
    source_pattern = r"\$\{(?P<source>(?:slot|output|step|case)\.[^{}]+)\}"
    result: dict[str, str] = {}
    source_patterns = [
        rf"{param_pattern}\s*(?:<-|=|из|from)\s*{source_pattern}",
        rf"{source_pattern}\s*(?:->|=>|в|to)\s*{param_pattern}",
    ]
    for pattern in source_patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            if capability_id and match.group("capability_id") != capability_id:
                continue
            binding = _binding_from_template_ref(match.group("source"))
            if binding:
                result[match.group("name")] = binding

    for match in re.finditer(param_pattern, text, flags=re.IGNORECASE):
        if capability_id and match.group("capability_id") != capability_id:
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


def _schema_type(schema: dict[str, Any] | None) -> str:
    value = (schema or {}).get("type")
    if isinstance(value, list):
        value = next((item for item in value if item != "null"), None)
    if value == "integer":
        return "number"
    return value if value in {"string", "number", "boolean", "object", "array"} else "unknown"


def _humanize(value: str) -> str:
    return str(value or "").replace("_", " ").replace("-", " ").strip().capitalize() or "Значение"


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
) -> dict[str, Any] | None:
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


def _capability_output_mapping_hints(instruction: str, capability_id: str | None = None) -> list[dict[str, str]]:
    hints: list[dict[str, str]] = []
    output_pattern = _template_capability_ref_pattern("output")
    slot_target_pattern = (
        r"(?:\$\{slot\.(?P<slot>[A-Za-z][A-Za-z0-9_.-]*)\}"
        r"|(?P<plain_slot>[A-Za-z][A-Za-z0-9_.-]*))"
    )
    for pattern in [
        rf"{slot_target_pattern}\s*(?:<-|=|из|from)\s*{output_pattern}",
        rf"{output_pattern}\s*(?:->|=>|в|to)\s*{slot_target_pattern}",
    ]:
        for match in re.finditer(pattern, instruction or "", flags=re.IGNORECASE):
            if capability_id and match.group("capability_id") != capability_id:
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
    for hint in _capability_output_mapping_hints(instruction):
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
    capabilities: list[dict[str, Any]] | None = None,
    tool: dict[str, Any] | None = None,
    capability: dict[str, Any] | None = None,
    previous_steps: list[dict[str, Any]] | None = None,
    integration_endpoints: list[dict[str, Any]] | None = None,
) -> list[str]:
    void_args = (tools, tool, integration_endpoints)
    del void_args
    errors: list[str] = []
    slot_ids = {str(slot.get("slot_id") or "") for slot in slots}
    capability_ids = {str(item.get("capability_id") or "") for item in capabilities or []}
    selected_capability = capability or {}
    selected_capability_id = str(selected_capability.get("capability_id") or "")
    capabilities_by_id = {
        str(item.get("capability_id") or ""): item
        for item in capabilities or []
        if item.get("capability_id")
    }
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
        elif parts[0] == "Capability":
            capability_id = ".".join(parts[1:])
            if capability_id not in capability_ids:
                errors.append(f"Ссылка ${{{ref}}} указывает на неизвестную capability: {capability_id}.")
        elif parts[0] == "paramCapability":
            parsed_param = _template_capability_param_ref(ref)
            if not parsed_param:
                errors.append(
                    f"Ссылка ${{{ref}}} должна иметь формат "
                    "${paramCapability.<capability_id>.input.<parameter>} или "
                    "${paramCapability.<capability_id>.output.<field>}."
                )
                continue
            ref_capability_id = parsed_param["capability_id"]
            ref_capability = capabilities_by_id.get(ref_capability_id)
            if not ref_capability:
                errors.append(f"Ссылка ${{{ref}}} указывает на неизвестную capability: {ref_capability_id}.")
                continue
            if selected_capability_id and ref_capability_id != selected_capability_id:
                errors.append(
                    f"Ссылка ${{{ref}}} относится к capability {ref_capability_id}, "
                    f"но текущий профиль/шаг использует {selected_capability_id}."
                )
                continue
            kind = parsed_param["kind"]
            name = parsed_param["name"]
            schema = ref_capability.get("input_schema" if kind == "input" else "output_schema", {})
            if schema_properties(schema) and not schema_declares_path(
                schema,
                name,
                allow_nested_additional=True,
            ):
                human_kind = "входной параметр" if kind == "input" else "поле результата"
                errors.append(
                    f"Ссылка ${{{ref}}} указывает на неизвестный {human_kind} "
                    f"capability {ref_capability_id}: {name}."
                )
        elif parts[0] == "entity":
            errors.append(
                f"Ссылка ${{{ref}}} использует устаревший тип entity. "
                "Используйте ${step.<step_id>.capability.<capability_id>.output.<field>}."
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
                    "${step.<step_id>.capability.<capability_id>.input|output.<field>}."
                )
                continue
            ref_step = previous_steps_by_id.get(parsed_step["step_id"])
            if not ref_step:
                errors.append(f"Ссылка ${{{ref}}} указывает на неизвестный предыдущий шаг: {parsed_step['step_id']}.")
                continue
            if ref_step.get("capability_id") != parsed_step["capability_id"]:
                errors.append(
                    f"Ссылка ${{{ref}}} ожидает capability {parsed_step['capability_id']} "
                    f"в {parsed_step['step_id']}, но там настроена {ref_step.get('capability_id')}."
                )
                continue
            ref_capability = capabilities_by_id.get(parsed_step["capability_id"])
            if ref_capability:
                schema = ref_capability.get("input_schema" if parsed_step["kind"] == "input" else "output_schema", {})
                if schema_properties(schema) and not schema_declares_path(
                    schema,
                    parsed_step["name"],
                    allow_nested_additional=True,
                ):
                    human_kind = "входной параметр" if parsed_step["kind"] == "input" else "поле результата"
                    errors.append(
                        f"Ссылка ${{{ref}}} указывает на неизвестный {human_kind} "
                        f"capability {parsed_step['capability_id']}: {parsed_step['name']}."
                    )
        else:
            errors.append(f"Неизвестный тип ссылки ${{{ref}}}.")
    return errors


def _capability_by_id(
    capabilities: list[dict[str, Any]],
    capability_id: str | None,
    instruction: str,
) -> dict[str, Any] | None:
    instruction_capabilities = _template_capability_ids(instruction)
    for template_capability_id in instruction_capabilities:
        capability = _find_by_id(capabilities, "capability_id", template_capability_id)
        if capability:
            return capability
    if instruction_capabilities:
        return None
    if capability_id:
        return _find_by_id(capabilities, "capability_id", capability_id)
    normalized_instruction = _normalize_text(instruction)
    for capability in capabilities:
        candidate_id = _normalize_text(capability.get("capability_id"))
        display_name = _normalize_text(capability.get("display_name"))
        if (candidate_id and candidate_id in normalized_instruction) or (
            display_name and display_name in normalized_instruction
        ):
            return capability
    return capabilities[0] if capabilities else None


def _active_capability_binding(
    capability_id: str,
    capability_bindings: list[dict[str, Any]] | None,
) -> dict[str, Any] | None:
    candidates = [
        binding
        for binding in capability_bindings or []
        if binding.get("capability_id") == capability_id and binding.get("status") == "active"
    ]
    return candidates[0] if candidates else None


def _case_source_fields() -> list[str]:
    return [
        "case_id",
        "ticket_id",
        "description",
        "input_text",
        "scenario_id",
        "channel_id",
        "priority",
        "user",
    ]


def _source_ref_to_instruction_value(
    source_ref: str,
    *,
    slots: list[dict[str, Any]],
    previous_steps: list[dict[str, Any]] | None,
) -> tuple[str | None, str | None]:
    value = str(source_ref or "").strip()
    if not value:
        return None, "пустой source ref"
    if value.startswith("slot:"):
        slot_id = value.removeprefix("slot:").strip()
        if not _find_by_id(slots, "slot_id", slot_id):
            return None, f"неизвестный слот {slot_id}"
        return f"${{slot.{slot_id}}}", None
    if value.startswith("case:"):
        field = value.removeprefix("case:").strip()
        if not re.match(r"^[A-Za-z][A-Za-z0-9_.-]*$", field):
            return None, f"некорректное поле case {field}"
        return f"${{case.{field}}}", None
    if value.startswith("output:"):
        field = value.removeprefix("output:").strip()
        if not re.match(r"^[A-Za-z][A-Za-z0-9_.-]*$", field):
            return None, f"некорректное поле output {field}"
        return f"${{output.{field}}}", None
    if value.startswith("step:"):
        step_ref = value.removeprefix("step:").strip()
        template_step_ref = step_ref if step_ref.startswith("step.") else f"step.{step_ref}"
        parsed = _template_step_ref(template_step_ref)
        previous_step_ids = {
            str(step.get("step_id") or f"step{index}")
            for index, step in enumerate(previous_steps or [], start=1)
        }
        if not parsed:
            return None, f"некорректная ссылка на step {step_ref}"
        if parsed["step_id"] not in previous_step_ids:
            return None, f"неизвестный предыдущий шаг {parsed['step_id']}"
        return f"${{{template_step_ref}}}", None
    if value.startswith("constant:"):
        constant = value.removeprefix("constant:")
        if not constant.strip():
            return None, "пустая константа"
        if "${" in constant or "\n" in constant or "\r" in constant:
            return None, "константа содержит недопустимый template или перенос строки"
        return constant.strip(), None
    return None, f"неподдерживаемый source ref {value}"


def _normalize_llm_output_mapping(
    *,
    raw_mapping: Any,
    slots: list[dict[str, Any]],
    output_schema: dict[str, Any],
    allowed_slot_ids: set[str] | None = None,
) -> tuple[dict[str, str], list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []
    result: dict[str, str] = {}
    if raw_mapping in (None, ""):
        return result, warnings, errors
    if not isinstance(raw_mapping, dict):
        return result, warnings, ["LLM assist вернул output_mapping не объектом."]
    slot_ids = {str(slot.get("slot_id") or "") for slot in slots}
    output_fields = {field["field_id"] for field in _operation_schema_fields(output_schema)}
    effective_allowed_slot_ids = slot_ids if allowed_slot_ids is None else slot_ids & allowed_slot_ids
    for raw_target, raw_field in raw_mapping.items():
        target = str(raw_target or "").strip()
        field = str(raw_field or "").strip()
        if not target or not field:
            errors.append("LLM assist вернул пустой target/output field в output_mapping.")
            continue
        if target in slot_ids and target not in effective_allowed_slot_ids:
            warnings.append(
                f"Поле результата capability {field} не записано в слот {target}: "
                "слот не выбран как выходной слот профиля."
            )
            continue
        if target in slot_ids:
            if field in output_fields or schema_declares_path(output_schema, field, allow_nested_additional=True):
                result[target] = field
            else:
                errors.append(f"LLM assist output_mapping указывает неизвестное поле результата: {target} / {field}.")
            continue
        if field in slot_ids and field not in effective_allowed_slot_ids:
            warnings.append(
                f"Поле результата capability {target} не записано в слот {field}: "
                "слот не выбран как выходной слот профиля."
            )
            continue
        if field in slot_ids:
            if target in output_fields or schema_declares_path(output_schema, target, allow_nested_additional=True):
                result[field] = target
                warnings.append(
                    f"LLM assist вернул output_mapping в обратном порядке; нормализовано {field} <- {target}."
                )
            else:
                errors.append(f"LLM assist output_mapping указывает неизвестное поле результата: {target} / {field}.")
            continue
        if target in output_fields or schema_declares_path(output_schema, target, allow_nested_additional=True):
            warnings.append(
                f"Поле результата capability {target} доступно через ссылку step output, "
                "но не записано в слот: такой выходной слот не выбран в профиле."
            )
            continue
        if field in output_fields or schema_declares_path(output_schema, field, allow_nested_additional=True):
            warnings.append(
                f"Поле результата capability {field} доступно через ссылку step output, "
                "но не записано в слот: такой выходной слот не выбран в профиле."
            )
            continue
        if target not in slot_ids and field not in slot_ids:
            errors.append(f"LLM assist output_mapping не указывает известный слот: {target} / {field}.")
        else:
            errors.append(f"LLM assist output_mapping указывает неизвестное поле результата: {target} / {field}.")
    return result, warnings, errors


def _allowed_output_slot_ids_from_profile_context(
    profile_context: dict[str, Any] | None,
) -> set[str] | None:
    if profile_context is None:
        return None
    if not any(key in profile_context for key in ("output_slot_ids", "output_slots_order", "target_slot_id")):
        return None
    result: set[str] = set()
    for slot_id in profile_context.get("output_slot_ids") or []:
        normalized = str(slot_id or "").strip()
        if normalized:
            result.add(normalized)
    for rule in profile_context.get("output_slots_order") or []:
        if not isinstance(rule, dict):
            continue
        normalized = str(rule.get("slot_id") or "").strip()
        if normalized:
            result.add(normalized)
    target_slot_id = str(profile_context.get("target_slot_id") or "").strip()
    if target_slot_id:
        result.add(target_slot_id)
    return result


def _slot_specs_for_prompt(slots: list[dict[str, Any]], slot_ids: set[str] | None = None) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for slot in slots:
        slot_id = str(slot.get("slot_id") or "").strip()
        if not slot_id:
            continue
        if slot_ids is not None and slot_id not in slot_ids:
            continue
        selected.append({
            "slot_id": slot_id,
            "display_name": slot.get("display_name", slot_id),
            "description": slot.get("description", ""),
            "extraction_instruction": slot.get("extraction_instruction", ""),
            "examples": slot.get("examples", []),
            "fill_method": slot.get("fill_method", ""),
            "priority_group": slot.get("priority_group", ""),
            "resolution_profile_id": slot.get("resolution_profile_id", ""),
            "required": slot.get("required", False),
        })
    return selected


def _missing_capability_field_descriptions(capability_specs: list[dict[str, Any]]) -> list[dict[str, str]]:
    missing: list[dict[str, str]] = []
    for capability in capability_specs:
        capability_id = str(capability.get("capability_id") or "")
        for section, fields_key in (("input", "input_fields"), ("output", "output_fields")):
            for field in capability.get(fields_key) or []:
                field_id = str(field.get("field_id") or "").strip()
                if field_id and not str(field.get("description") or "").strip():
                    missing.append({
                        "capability_id": capability_id,
                        "section": section,
                        "field_id": field_id,
                    })
    return missing


def _canonical_instruction_from_llm_draft(
    *,
    original_instruction: str,
    draft: dict[str, Any],
    slot_schema: dict[str, Any],
    capabilities: list[dict[str, Any]],
    capability_id: str | None,
    previous_steps: list[dict[str, Any]] | None,
    allowed_output_slot_ids: set[str] | None = None,
) -> tuple[str | None, str | None, list[str], list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []
    assumptions: list[str] = []
    slots = slot_schema.get("slots", [])
    explicit_capability_ids = _template_capability_ids(original_instruction)
    if len(explicit_capability_ids) > 1:
        errors.append(
            "Один шаг разрешения атрибута может использовать только одну capability. "
            f"Найдены: {', '.join(explicit_capability_ids)}."
        )
    requested_capability_id = str(capability_id or "").strip()
    explicit_capability_id = str(explicit_capability_ids[0] if explicit_capability_ids else "").strip()
    draft_capability_id = str(draft.get("capability_id") or "").strip()
    if requested_capability_id and explicit_capability_id and requested_capability_id != explicit_capability_id:
        errors.append(
            "Явная ссылка Capability в инструкции конфликтует с выбранной capability профиля: "
            f"{explicit_capability_id} != {requested_capability_id}."
        )
    selected_capability_id = requested_capability_id or explicit_capability_id or draft_capability_id
    if errors:
        return None, selected_capability_id or None, assumptions, warnings, errors
    if selected_capability_id and draft_capability_id and draft_capability_id != selected_capability_id:
        warnings.append(
            "LLM assist выбрал capability "
            f"{draft_capability_id}, но использована выбранная capability {selected_capability_id}."
        )
    capability = _find_by_id(capabilities, "capability_id", selected_capability_id)
    if not capability:
        errors.append(f"LLM assist выбрал неизвестную capability: {selected_capability_id or 'не указана'}.")
        return None, selected_capability_id or None, assumptions, warnings, errors

    input_schema = capability.get("input_schema") or {}
    output_schema = capability.get("output_schema") or {}
    input_mapping = draft.get("input_mapping") or {}
    if not isinstance(input_mapping, dict):
        errors.append("LLM assist вернул input_mapping не объектом.")
        input_mapping = {}
    input_mapping = {
        str(parameter): str(source_ref)
        for parameter, source_ref in input_mapping.items()
        if str(parameter or "").strip()
    }
    explicit_input_bindings = _template_capability_input_bindings(original_instruction, selected_capability_id)
    if explicit_input_bindings:
        input_mapping.update(explicit_input_bindings)

    lines = [f"Выполни ${{Capability.{selected_capability_id}}}."]
    input_assumptions: list[str] = []
    for raw_parameter, raw_source_ref in input_mapping.items():
        parameter = str(raw_parameter or "").strip()
        if not parameter:
            errors.append("LLM assist вернул пустой input parameter.")
            continue
        if not schema_declares_path(input_schema, parameter, allow_nested_additional=True):
            errors.append(f"LLM assist указал неизвестный входной параметр capability {selected_capability_id}: {parameter}.")
            continue
        instruction_value, error = _source_ref_to_instruction_value(
            str(raw_source_ref or ""),
            slots=slots,
            previous_steps=previous_steps,
        )
        if error or not instruction_value:
            errors.append(f"LLM assist невалидно заполнил {parameter}: {error}.")
            continue
        lines.append(f"${{paramCapability.{selected_capability_id}.input.{parameter}}}<-{instruction_value}")
        input_assumptions.append(f"{parameter}<-{raw_source_ref}")

    output_mapping, output_warnings, output_errors = _normalize_llm_output_mapping(
        raw_mapping=draft.get("output_mapping"),
        slots=slots,
        output_schema=output_schema,
        allowed_slot_ids=allowed_output_slot_ids,
    )
    warnings.extend(output_warnings)
    errors.extend(output_errors)
    for hint in _capability_output_mapping_hints(original_instruction, selected_capability_id):
        slot = _slot_by_label(slots, hint["target"])
        if not slot:
            errors.append(
                f"Выходной слот {hint['target']} не найден в выбранном сценарии профиля. "
                "Добавьте слот в сценарий и в список выходных слотов профиля либо удалите mapping из инструкции."
            )
            continue
        slot_id = str(slot.get("slot_id") or "")
        if allowed_output_slot_ids is not None and slot_id not in allowed_output_slot_ids:
            errors.append(
                f"Выходной слот {slot_id} не выбран как выходной слот профиля. "
                "Добавьте его в блок \"Выходные слоты и порядок заполнения\" либо удалите mapping из инструкции."
            )
            continue
        if schema_declares_path(output_schema, hint["field"], allow_nested_additional=True):
            output_mapping[slot_id] = hint["field"]
    output_assumptions: list[str] = []
    for slot_id, field in output_mapping.items():
        lines.append(f"результат ${{paramCapability.{selected_capability_id}.output.{field}}}->{slot_id}")
        output_assumptions.append(f"{slot_id}<-{field}")

    assumptions.append(f"capability={selected_capability_id}")
    if input_assumptions:
        assumptions.append(f"inputs: {', '.join(input_assumptions)}")
    if output_assumptions:
        assumptions.append(f"outputs: {', '.join(output_assumptions)}")
    if not input_assumptions:
        warnings.append("LLM assist не вернул input_mapping; источники будут подбираться deterministic compiler.")
    if not output_assumptions:
        if allowed_output_slot_ids is not None and not allowed_output_slot_ids:
            assumptions.append("outputs: none (profile has no selected output slots)")
        else:
            warnings.append("LLM assist не вернул output_mapping; выходы будут подбираться deterministic compiler.")

    canonical_instruction = "\n".join(lines)
    if len(canonical_instruction) > 4000:
        errors.append("LLM assist сформировал слишком длинную canonical instruction.")
    return canonical_instruction, selected_capability_id, assumptions, warnings, errors


def _capability_field_specs(schema: dict[str, Any] | None) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    for field in _operation_schema_fields(schema or {}):
        field_schema = schema_at_path(schema or {}, field["field_id"]) or {}
        spec = {
            "field_id": field["field_id"],
            "display_name": field["display_name"],
            "title": field_schema.get("title") or field["display_name"],
            "type": field["field_type"],
            "description": field_schema.get("description") or field.get("description", ""),
            "required": field.get("required", False),
        }
        for key in ("default", "enum", "minimum", "maximum", "minLength", "maxLength", "pattern"):
            if key in field_schema:
                spec[key] = field_schema[key]
        fields.append(spec)
    return fields


def _llm_assist_constraints(
    *,
    instruction: str,
    capability_id: str | None,
    selected_capability_id: str | None,
) -> dict[str, Any]:
    constraint_capability_ids = _template_capability_ids(instruction)
    target_capability_id = constraint_capability_ids[0] if len(constraint_capability_ids) == 1 else capability_id
    return {
        "selected_capability_id": capability_id or selected_capability_id,
        "explicit_capability_refs": constraint_capability_ids,
        "explicit_input_mapping": _template_capability_input_bindings(instruction, target_capability_id),
        "explicit_output_mapping": _capability_output_mapping_hints(instruction, target_capability_id),
    }


def build_capability_step_assist_prompt(
    *,
    instruction: str,
    slot_schema: dict[str, Any],
    capabilities: list[dict[str, Any]],
    capability_bindings: list[dict[str, Any]] | None,
    previous_steps: list[dict[str, Any]] | None,
    capability_id: str | None = None,
    profile_context: dict[str, Any] | None = None,
    system_prompt_template: str | None = None,
) -> list[dict[str, str]]:
    active_binding_capability_ids = {
        str(binding.get("capability_id") or "")
        for binding in capability_bindings or []
        if binding.get("status") == "active"
    }
    selected_capability_id = str(capability_id or (profile_context or {}).get("capability_id") or "").strip()
    capability_specs = []
    for capability in capabilities:
        capability_ref_id = str(capability.get("capability_id") or "")
        if selected_capability_id and capability_ref_id != selected_capability_id:
            continue
        if active_binding_capability_ids and capability_ref_id not in active_binding_capability_ids:
            continue
        capability_specs.append({
            "capability_id": capability_ref_id,
            "display_name": capability.get("display_name") or capability_ref_id,
            "description": capability.get("description") or "",
            "input_fields": _capability_field_specs(capability.get("input_schema") or {}),
            "output_fields": _capability_field_specs(capability.get("output_schema") or {}),
        })
    raw_slots = slot_schema.get("slots", [])
    slots = _slot_specs_for_prompt(raw_slots)
    allowed_output_slot_ids = _allowed_output_slot_ids_from_profile_context(profile_context)
    selected_output_slots = _slot_specs_for_prompt(raw_slots, allowed_output_slot_ids)
    previous_step_specs = [
        {
            "step_id": step.get("step_id") or f"step{index}",
            "capability_id": step.get("capability_id"),
            "output_mapping": step.get("output_mapping") or {},
        }
        for index, step in enumerate(previous_steps or [], start=1)
    ]
    constraints = _llm_assist_constraints(
        instruction=instruction,
        capability_id=capability_id,
        selected_capability_id=selected_capability_id,
    )
    requires_output_mapping = allowed_output_slot_ids is None or bool(allowed_output_slot_ids)
    constraints["requires_output_mapping"] = requires_output_mapping
    constraints["selected_output_slot_ids"] = sorted(allowed_output_slot_ids) if allowed_output_slot_ids is not None else []
    return [
        {
            "role": "system",
            "content": (system_prompt_template or DEFAULT_CAPABILITY_STEP_ASSIST_PROMPT_TEMPLATE).strip()
            or DEFAULT_CAPABILITY_STEP_ASSIST_PROMPT_TEMPLATE,
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "instruction": instruction,
                    "slot_schema_id": slot_schema.get("slot_schema_id"),
                    "profile_context": profile_context or {},
                    "slots": slots,
                    "selected_output_slots": selected_output_slots,
                    "case_fields": _case_source_fields(),
                    "previous_steps": previous_step_specs,
                    "capabilities": capability_specs,
                    "constraints": constraints,
                    "metadata_quality": {
                        "missing_capability_field_descriptions": _missing_capability_field_descriptions(capability_specs),
                    },
                    "source_ref_format": {
                        "slot": "slot:<slot_id>",
                        "case": "case:<field>",
                        "previous_step_output": "step:<step_id>.capability.<capability_id>.output.<field>",
                        "constant": "constant:<literal>",
                    },
                    "response_schema": {
                        "capability_id": "<capability_id>",
                        "step_name": "short russian name",
                        "input_mapping": {"<capability_input>": "slot:<slot_id>|case:<field>|step:<...>|constant:<literal>"},
                        "output_mapping": (
                            {"<selected_target_slot_id>": "<capability_output_field>"}
                            if requires_output_mapping
                            else {}
                        ),
                        "reason": "short russian explanation",
                    },
                },
                ensure_ascii=False,
            ),
        },
    ]


def invoke_capability_step_assist_model(
    *,
    model_config: dict[str, Any],
    instruction: str,
    slot_schema: dict[str, Any],
    capabilities: list[dict[str, Any]],
    capability_bindings: list[dict[str, Any]] | None,
    previous_steps: list[dict[str, Any]] | None,
    capability_id: str | None = None,
    profile_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    alias = model_config.get("routing", {}).get("capability_selection") or model_config.get("default_model_alias")
    provider = select_model_provider(model_config, alias)
    if not provider:
        return {
            "status": "error",
            "error": {
                "code": "model_provider_not_configured",
                "message": "Не найдено включенное подключение модели для capability_selection.",
            },
        }
    gateway = model_config.get("gateway", {})
    base_url = gateway.get("base_url") or provider.get("base_url")
    if not base_url:
        return {
            "status": "error",
            "provider": provider.get("display_name"),
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

    redaction = redact_for_llm(instruction)
    system_prompts = model_config.get("settings", {}).get("system_prompts", {})
    if not isinstance(system_prompts, dict):
        system_prompts = {}
    capability_step_assist_prompt = str(
        system_prompts.get("capability_step_assist") or DEFAULT_CAPABILITY_STEP_ASSIST_PROMPT_TEMPLATE
    ).strip()
    payload = {
        "model": model_name,
        "messages": build_capability_step_assist_prompt(
            instruction=redaction.text,
            slot_schema=slot_schema,
            capabilities=capabilities,
            capability_bindings=capability_bindings,
            previous_steps=previous_steps,
            capability_id=capability_id,
            profile_context=profile_context,
            system_prompt_template=capability_step_assist_prompt,
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
        content = (
            body.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        draft = parse_json_object(content)
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
    except (json.JSONDecodeError, TypeError) as error:
        return {
            "status": "error",
            "provider": provider.get("display_name"),
            "model": model_name,
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "redaction": redaction.as_dict(),
            "error": {
                "code": "capability_step_assist_json_invalid",
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
        "draft": draft,
    }


def _compile_llm_assisted_capability_resolution_step(
    *,
    instruction: str,
    slot_schema: dict[str, Any],
    capabilities: list[dict[str, Any]],
    capability_id: str | None = None,
    step_name: str | None = None,
    previous_steps: list[dict[str, Any]] | None = None,
    capability_bindings: list[dict[str, Any]] | None = None,
    model_config: dict[str, Any] | None = None,
    llm_assist_invoker: Callable[..., dict[str, Any]] | None = None,
    profile_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not model_config and not llm_assist_invoker:
        return {
            "schema_version": "1.0",
            "structure": {},
            "references": {"slot_schema_id": slot_schema.get("slot_schema_id")},
            "warnings": [],
            "validation_errors": ["Шаг разрешения атрибута должен ссылаться на Capability."],
        }
    model_result = (
        llm_assist_invoker(
            instruction=instruction,
            slot_schema=slot_schema,
            capabilities=capabilities,
            capability_bindings=capability_bindings,
            previous_steps=previous_steps,
            capability_id=capability_id,
            profile_context=profile_context,
        )
        if llm_assist_invoker
        else invoke_capability_step_assist_model(
            model_config=model_config or {},
            instruction=instruction,
            slot_schema=slot_schema,
            capabilities=capabilities,
            capability_bindings=capability_bindings,
            previous_steps=previous_steps,
            capability_id=capability_id,
            profile_context=profile_context,
        )
    )
    if model_result.get("status") != "success":
        error = model_result.get("error") or {}
        return {
            "schema_version": "1.0",
            "structure": {},
            "references": {
                "slot_schema_id": slot_schema.get("slot_schema_id"),
                "llm_assist": {
                    "status": model_result.get("status", "error"),
                    "provider": model_result.get("provider"),
                    "model": model_result.get("model"),
                    "redaction": model_result.get("redaction", {}),
                },
            },
            "warnings": [],
            "validation_errors": [
                f"LLM assist не сформировал структуру: {error.get('message') or error.get('code') or 'unknown error'}."
            ],
        }
    draft = model_result.get("draft") or {}
    if not isinstance(draft, dict):
        draft = {}
    allowed_output_slot_ids = _allowed_output_slot_ids_from_profile_context(profile_context)
    selected_output_slots = _slot_specs_for_prompt(slot_schema.get("slots", []), allowed_output_slot_ids)
    requires_output_mapping = allowed_output_slot_ids is None or bool(allowed_output_slot_ids)
    canonical_instruction, selected_capability_id, assumptions, warnings, errors = _canonical_instruction_from_llm_draft(
        original_instruction=instruction,
        draft=draft,
        slot_schema=slot_schema,
        capabilities=capabilities,
        capability_id=capability_id,
        previous_steps=previous_steps,
        allowed_output_slot_ids=allowed_output_slot_ids,
    )
    llm_reference = {
        "status": "success",
        "provider": model_result.get("provider"),
        "model": model_result.get("model"),
        "duration_ms": model_result.get("duration_ms"),
        "redaction": model_result.get("redaction", {}),
        "capability_id": selected_capability_id,
        "assumptions": assumptions,
        "requires_output_mapping": requires_output_mapping,
        "selected_output_slots": selected_output_slots,
    }
    if errors or not canonical_instruction:
        return {
            "schema_version": "1.0",
            "structure": {},
            "references": {
                "slot_schema_id": slot_schema.get("slot_schema_id"),
                "llm_assist": llm_reference,
            },
            "warnings": warnings,
            "validation_errors": errors or ["LLM assist не сформировал canonical instruction."],
        }

    compiled = _compile_capability_resolution_step(
        instruction=canonical_instruction,
        slot_schema=slot_schema,
        capabilities=capabilities,
        capability_id=selected_capability_id,
        step_name=str(draft.get("step_name") or step_name or "").strip() or step_name,
        previous_steps=previous_steps,
        capability_bindings=capability_bindings,
        allowed_output_slot_ids=allowed_output_slot_ids,
    )
    compiled["warnings"] = warnings + compiled.get("warnings", [])
    compiled["references"]["llm_assist"] = {
        **llm_reference,
        "canonical_instruction": canonical_instruction,
    }
    if compiled.get("structure"):
        compiled["structure"]["configuration_instruction"] = instruction
        metadata = compiled["structure"].setdefault("generated_structure_metadata", {})
        metadata["mode"] = "llm_assist"
        metadata["llm_assist"] = {
            "provider": model_result.get("provider"),
            "model": model_result.get("model"),
            "duration_ms": model_result.get("duration_ms"),
            "redaction": model_result.get("redaction", {}),
            "canonical_instruction": canonical_instruction,
            "assumptions": assumptions,
            "requires_output_mapping": requires_output_mapping,
            "selected_output_slots": selected_output_slots,
        }
    return compiled


def _compile_capability_resolution_step(
    *,
    instruction: str,
    slot_schema: dict[str, Any],
    capabilities: list[dict[str, Any]],
    capability_id: str | None = None,
    step_name: str | None = None,
    previous_steps: list[dict[str, Any]] | None = None,
    capability_bindings: list[dict[str, Any]] | None = None,
    allowed_output_slot_ids: set[str] | None = None,
) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []
    slots = slot_schema.get("slots", [])
    instruction_capabilities = _template_capability_ids(instruction)
    if len(instruction_capabilities) > 1:
        errors.append(
            "Один шаг разрешения атрибута может использовать только одну capability. "
            f"Найдены: {', '.join(instruction_capabilities)}."
        )
    requested_capability_id = instruction_capabilities[0] if instruction_capabilities else capability_id
    capability = _capability_by_id(capabilities, requested_capability_id, instruction)
    if not capability:
        errors.append("Не найдена capability для шага разрешения атрибута.")
        capability = {}
    selected_capability_id = capability.get("capability_id") or requested_capability_id or ""
    errors.extend(_template_reference_errors(
        instruction=instruction,
        slots=slots,
        tools=[],
        capabilities=capabilities,
        capability=capability,
        previous_steps=previous_steps,
    ))
    input_schema = capability.get("input_schema") or {}
    output_schema = capability.get("output_schema") or {}
    parameters = list(schema_properties(input_schema).keys())
    required_groups = schema_required_parameter_groups(input_schema)
    required_parameters = {parameter for group in required_groups for parameter in group}
    input_mapping: dict[str, str] = {}
    explicit_input_bindings = _template_capability_input_bindings(instruction, selected_capability_id)
    referenced_input_parameters = _template_capability_input_parameter_names(instruction, selected_capability_id)

    for parameter in parameters:
        explicit_source = explicit_input_bindings.get(parameter)
        if explicit_source:
            input_mapping[parameter] = explicit_source
            continue
        explicit = re.search(
            rf"(?:параметр\s+)?{re.escape(parameter)}\s+(?:передай|заполни|=|<-)\s+"
            r"((?:slot|output|step|case|constant|secret):[A-Za-z0-9_.:-]+)",
            instruction or "",
            flags=re.IGNORECASE,
        )
        if explicit:
            input_mapping[parameter] = explicit.group(1).rstrip(".,;")
            continue
        explicit_constant = re.search(
            rf"(?:параметр\s+)?{re.escape(parameter)}\s*(?:<-|=|из|from)\s*([^\n.]+)",
            instruction or "",
            flags=re.IGNORECASE,
        )
        if explicit_constant:
            binding = _constant_binding_from_raw(explicit_constant.group(1))
            if binding:
                input_mapping[parameter] = binding
                continue
        slot = _slot_for_parameter(parameter, slots, instruction)
        if slot:
            input_mapping[parameter] = f"slot:{slot['slot_id']}"
            continue
        has_default, default_value = schema_parameter_default(input_schema, parameter)
        if has_default:
            input_mapping[parameter] = constant_source_ref(default_value)
            continue
        if parameter not in required_parameters and parameter in referenced_input_parameters:
            warnings.append(f"Не удалось подобрать источник для необязательного параметра capability: {parameter}.")

    for required_group in required_groups:
        if any(parameter in input_mapping for parameter in required_group):
            continue
        errors.append(
            "Не удалось подобрать источник для обязательного параметра capability: "
            f"{format_required_parameter_group(required_group)}."
        )

    result_fields = [
        {
            "field_id": field["field_id"],
            "display_name": field["display_name"],
            "field_type": field["field_type"],
            "description": field.get("description", ""),
        }
        for field in _operation_schema_fields(output_schema)
    ]
    if not result_fields:
        result_fields = [{"field_id": "value", "display_name": "Значение", "field_type": "unknown", "description": ""}]
        warnings.append("Контракт результата capability пустой; добавлено поле value.")

    output_mapping: dict[str, str] = {}
    output_mapping_hints = _capability_output_mapping_hints(instruction, selected_capability_id)
    applied_output_mapping_hints: list[dict[str, str]] = []
    for hint in output_mapping_hints:
        slot = _slot_by_label(slots, hint["target"])
        if not slot:
            errors.append(
                f"Выходной слот {hint['target']} не найден в выбранном сценарии профиля. "
                "Добавьте слот в сценарий и в список выходных слотов профиля либо удалите mapping из инструкции."
            )
            continue
        slot_id = str(slot.get("slot_id") or "")
        if allowed_output_slot_ids is not None and slot_id not in allowed_output_slot_ids:
            errors.append(
                f"Выходной слот {slot_id} не выбран как выходной слот профиля. "
                "Добавьте его в блок \"Выходные слоты и порядок заполнения\" либо удалите mapping из инструкции."
            )
            continue
        output_mapping[slot_id] = hint["field"]
        applied_output_mapping_hints.append(dict(hint))
    if not output_mapping:
        field_ids = {field["field_id"] for field in result_fields}
        for slot in slots:
            slot_id = str(slot.get("slot_id") or "")
            if allowed_output_slot_ids is not None and slot_id not in allowed_output_slot_ids:
                continue
            if slot_id in field_ids:
                output_mapping[slot_id] = slot_id

    resolved_step_name = step_name or ""
    if not resolved_step_name:
        match = re.search(r"шаг\s*[:.-]\s*([^\n.]+)", instruction or "", flags=re.IGNORECASE)
        call_label = capability.get("display_name") or selected_capability_id or "capability"
        resolved_step_name = (match.group(1).strip() if match else "") or f"Выполнить {_humanize(call_label)}"

    binding = _active_capability_binding(selected_capability_id, capability_bindings)
    completion_policy = copy.deepcopy(capability.get("default_completion_policy") or {})
    if binding and binding.get("execution_mode") == "sync" and not completion_policy:
        completion_policy = {"mode": "sync", "max_wait_seconds": 0, "timeout_action": "resume_agent"}
    structure = {
        "step_id": f"step{len(previous_steps or []) + 1}",
        "step_name": resolved_step_name[:240],
        "capability_id": selected_capability_id,
        "input_mapping": input_mapping,
        "output_mapping": output_mapping,
        "on_error": _on_error_from_instruction(instruction),
        "configuration_instruction": instruction,
        "generated_structure_metadata": {
            "generator": "config_assistant",
            "mode": "deterministic",
            "source": "attribute_resolution_step_instruction",
            "result_fields": result_fields,
        },
    }
    if binding:
        structure["mcp_environment_id"] = binding.get("environment_id") or ""
    if completion_policy:
        structure["completion_policy"] = completion_policy
    for hint in applied_output_mapping_hints:
        hint["source_ref"] = (
            f"${{step.{structure['step_id']}.capability.{structure['capability_id']}.output.{hint['field']}}}"
        )
    return {
        "schema_version": "1.0",
        "structure": structure,
        "references": {
            "slot_schema_id": slot_schema.get("slot_schema_id"),
            "capability_id": structure["capability_id"],
            "input_parameters": parameters,
            "result_fields": [field["field_id"] for field in result_fields],
            "output_mapping_hints": applied_output_mapping_hints,
        },
        "warnings": warnings,
        "validation_errors": errors,
    }


def compile_attribute_resolution_step(
    *,
    instruction: str,
    slot_schema: dict[str, Any],
    tools: list[dict[str, Any]],
    capabilities: list[dict[str, Any]] | None = None,
    capability_id: str | None = None,
    step_name: str | None = None,
    previous_steps: list[dict[str, Any]] | None = None,
    integration_endpoints: list[dict[str, Any]] | None = None,
    capability_bindings: list[dict[str, Any]] | None = None,
    model_config: dict[str, Any] | None = None,
    llm_assist_invoker: Callable[..., dict[str, Any]] | None = None,
    profile_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    del tools, integration_endpoints
    warnings: list[str] = []
    errors: list[str] = []
    instruction_capabilities = _template_capability_ids(instruction)
    if model_config or llm_assist_invoker:
        return _compile_llm_assisted_capability_resolution_step(
            instruction=instruction,
            slot_schema=slot_schema,
            capabilities=capabilities or [],
            capability_id=capability_id,
            step_name=step_name,
            previous_steps=previous_steps,
            capability_bindings=capability_bindings,
            model_config=model_config,
            llm_assist_invoker=llm_assist_invoker,
            profile_context=profile_context,
        )
    if instruction_capabilities or capability_id:
        return _compile_capability_resolution_step(
            instruction=instruction,
            slot_schema=slot_schema,
            capabilities=capabilities or [],
            capability_id=capability_id,
            step_name=step_name,
            previous_steps=previous_steps,
            capability_bindings=capability_bindings,
            allowed_output_slot_ids=_allowed_output_slot_ids_from_profile_context(profile_context),
        )
    return {
        "schema_version": "1.0",
        "structure": {},
        "references": {"slot_schema_id": slot_schema.get("slot_schema_id")},
        "warnings": warnings,
        "validation_errors": errors or ["Шаг разрешения атрибута должен ссылаться на Capability."],
    }
