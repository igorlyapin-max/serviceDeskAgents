from __future__ import annotations

import copy
import json
import os
import re
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request

from jsonschema import Draft202012Validator

from .http_client import urlopen_with_retry


class McpExecutionError(ValueError):
    """Raised when an MCP execution contract is invalid."""


SecretResolver = Callable[[str], str | None]


REQUIRED_ASYNC_CONTEXT_FIELDS = {
    "case_id",
    "run_id",
    "wait_id",
    "correlation_id",
    "capability_id",
    "contract_version",
    "expected_event_type",
    "idempotency_key_base",
}
SERVICE_DESK_METADATA_KEYS = ("servicedesk", "serviceDesk", "service_desk")
ASYNC_EVENT_STATUSES = {"progress", "success", "error", "timeout", "cancelled"}
PROD_MCP_AUTH_MODES = {"oidc_client_credentials", "oidc_workload_identity"}


def _schema_type_set(schema: dict[str, Any]) -> set[str]:
    value = schema.get("type")
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        return {str(item) for item in value if isinstance(item, str)}
    return set()


def _coerce_value_for_schema(value: Any, schema: dict[str, Any]) -> Any:
    if not isinstance(schema, dict):
        return value
    schema_types = _schema_type_set(schema)
    if isinstance(value, dict) and ("object" in schema_types or schema.get("properties")):
        properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        return {
            key: _coerce_value_for_schema(item, properties.get(key, {}))
            for key, item in value.items()
        }
    if isinstance(value, list) and "array" in schema_types:
        item_schema = schema.get("items") if isinstance(schema.get("items"), dict) else {}
        return [_coerce_value_for_schema(item, item_schema) for item in value]
    if not isinstance(value, str):
        return value

    stripped = value.strip()
    if "integer" in schema_types and re.fullmatch(r"[+-]?\d+", stripped):
        return int(stripped)
    if "number" in schema_types and re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", stripped):
        return float(stripped)
    if "boolean" in schema_types and stripped.lower() in {"true", "false"}:
        return stripped.lower() == "true"
    if "object" in schema_types and stripped.startswith("{") and stripped.endswith("}"):
        try:
            decoded = json.loads(stripped)
        except json.JSONDecodeError:
            return value
        if isinstance(decoded, dict):
            return _coerce_value_for_schema(decoded, schema)
    if "array" in schema_types and stripped.startswith("[") and stripped.endswith("]"):
        try:
            decoded = json.loads(stripped)
        except json.JSONDecodeError:
            return value
        if isinstance(decoded, list):
            return _coerce_value_for_schema(decoded, schema)
    return value


def coerce_inputs_for_schema(inputs: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(_coerce_value_for_schema(inputs, schema))


def select_capability_binding(
    *,
    capability_id: str,
    execution_mode: str,
    bindings: list[dict[str, Any]],
    environment_id: str | None = None,
) -> dict[str, Any]:
    candidates = [
        binding
        for binding in bindings
        if binding.get("capability_id") == capability_id
        and binding.get("execution_mode") == execution_mode
        and binding.get("status") == "active"
        and (not environment_id or binding.get("environment_id") == environment_id)
    ]
    if not candidates:
        target = f"{capability_id}/{execution_mode}"
        if environment_id:
            target = f"{target}/{environment_id}"
        raise McpExecutionError(f"Не найдена active MCP binding для {target}.")
    if len(candidates) > 1:
        raise McpExecutionError(f"Найдено несколько active MCP bindings для {capability_id}/{execution_mode}.")
    return candidates[0]


def build_async_context(
    *,
    case_id: str,
    run_id: str,
    wait_id: str,
    correlation_id: str,
    capability: dict[str, Any],
    expected_event_type: str,
    idempotency_key_base: str,
    result_transport: str,
    callback_url: str | None = None,
    result_topic: str | None = None,
) -> dict[str, Any]:
    context = {
        "case_id": case_id,
        "run_id": run_id,
        "wait_id": wait_id,
        "correlation_id": correlation_id,
        "capability_id": capability.get("capability_id"),
        "contract_version": capability.get("contract_version"),
        "expected_event_type": expected_event_type,
        "idempotency_key_base": idempotency_key_base,
        "result_transport": result_transport,
    }
    if callback_url:
        context["callback_url"] = callback_url
    if result_topic:
        context["result_topic"] = result_topic
    validate_async_context(context)
    return context


def validate_async_context(context: dict[str, Any]) -> None:
    missing = sorted(field for field in REQUIRED_ASYNC_CONTEXT_FIELDS if not context.get(field))
    if missing:
        raise McpExecutionError(f"async_context missing required fields: {', '.join(missing)}.")
    result_transport = context.get("result_transport")
    if result_transport in {"http_callback", "both"} and not context.get("callback_url"):
        raise McpExecutionError("async_context requires callback_url for http_callback/both transport.")
    if result_transport in {"kafka_event", "both"} and not context.get("result_topic"):
        raise McpExecutionError("async_context requires result_topic for kafka_event/both transport.")


def build_mcp_tool_request(
    *,
    capability: dict[str, Any],
    environment: dict[str, Any],
    binding: dict[str, Any],
    inputs: dict[str, Any],
    async_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    execution_mode = binding.get("execution_mode")
    if execution_mode not in {"sync", "async"}:
        raise McpExecutionError(f"Unsupported MCP execution_mode: {execution_mode}.")
    input_schema = capability.get("input_schema") or {}
    normalized_inputs = coerce_inputs_for_schema(inputs, input_schema)
    Draft202012Validator(input_schema).validate(normalized_inputs)
    if execution_mode == "async":
        if not async_context:
            raise McpExecutionError("async MCP execution requires async_context.")
        validate_async_context(async_context)
    return {
        "schema_version": "1.0",
        "environment_id": environment.get("environment_id"),
        "capability_id": capability.get("capability_id"),
        "contract_version": capability.get("contract_version"),
        "mcp_tool_name": binding.get("mcp_tool_name"),
        "execution_mode": execution_mode,
        "inputs": normalized_inputs,
        "async_context": async_context if execution_mode == "async" else None,
    }


def mcp_auth_headers(
    environment: dict[str, Any],
    *,
    secret_resolver: SecretResolver | None = None,
    oidc_token: str | None = None,
) -> dict[str, str]:
    auth_mode = environment.get("auth_mode")
    if auth_mode == "dev_bearer_token":
        token = resolve_secret_ref(environment.get("auth_ref"), secret_resolver=secret_resolver)
        if not token:
            raise McpExecutionError(f"MCP environment {environment.get('environment_id')} has empty dev token.")
        return {"Authorization": f"Bearer {token}"}
    if auth_mode in {"oidc_client_credentials", "oidc_workload_identity"}:
        if not oidc_token:
            oidc_token = resolve_secret_ref(environment.get("auth_ref"), secret_resolver=secret_resolver)
        if not oidc_token:
            raise McpExecutionError("OIDC MCP auth requires a resolved oidc_token.")
        return {"Authorization": f"Bearer {oidc_token}"}
    if auth_mode == "signed_event":
        return {}
    raise McpExecutionError(f"Unsupported MCP auth_mode: {auth_mode}.")


def resolve_secret_ref(ref: str | None, *, secret_resolver: SecretResolver | None = None) -> str | None:
    if not ref:
        return None
    prefix, separator, value = str(ref).partition(":")
    if separator != ":" or not value:
        return None
    resolver = secret_resolver or os.getenv
    if prefix == "env":
        return resolver(value)
    if prefix == "secret":
        return resolver(ref)
    return None


def validate_async_ack(ack: dict[str, Any], *, correlation_id: str) -> None:
    if ack.get("status") != "accepted":
        raise McpExecutionError("Async MCP ack must contain status=accepted.")
    if not ack.get("external_execution_id"):
        raise McpExecutionError("Async MCP ack must contain external_execution_id.")
    if ack.get("correlation_id") != correlation_id:
        raise McpExecutionError("Async MCP ack correlation_id does not match request.")


def validate_sync_result(result: dict[str, Any], capability: dict[str, Any]) -> None:
    if result.get("status") != "success":
        raise McpExecutionError("Sync MCP result must contain status=success.")
    if "result" not in result:
        raise McpExecutionError("Sync MCP result must contain result payload.")
    Draft202012Validator(capability.get("output_schema") or {}).validate(result["result"])


def build_mcp_jsonrpc_tool_call(mcp_request: dict[str, Any], *, request_id: str) -> dict[str, Any]:
    arguments = {
        "inputs": mcp_request.get("inputs") or {},
    }
    if mcp_request.get("async_context") is not None:
        arguments["async_context"] = mcp_request["async_context"]
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {
            "name": mcp_request.get("mcp_tool_name"),
            "arguments": arguments,
        },
    }


def build_mcp_jsonrpc_request(method: str, *, request_id: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    request = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
    }
    if params is not None:
        request["params"] = params
    return request


def invoke_mcp_tool_request(
    *,
    environment: dict[str, Any],
    mcp_request: dict[str, Any],
    secret_resolver: SecretResolver | None = None,
    oidc_token: str | None = None,
    request_id: str | None = None,
    timeout_seconds: int | float = 30,
    attempts: int = 2,
) -> dict[str, Any]:
    result = invoke_mcp_jsonrpc_method(
        environment=environment,
        method="tools/call",
        params={
            "name": mcp_request.get("mcp_tool_name"),
            "arguments": {
                "inputs": mcp_request.get("inputs") or {},
                **(
                    {"async_context": mcp_request["async_context"]}
                    if mcp_request.get("async_context") is not None
                    else {}
                ),
            },
        },
        secret_resolver=secret_resolver,
        oidc_token=oidc_token,
        request_id=request_id,
        timeout_seconds=timeout_seconds,
        attempts=attempts,
    )
    return normalize_mcp_tool_result(result)


def invoke_mcp_tools_list(
    *,
    environment: dict[str, Any],
    secret_resolver: SecretResolver | None = None,
    oidc_token: str | None = None,
    request_id: str | None = None,
    timeout_seconds: int | float = 30,
    attempts: int = 2,
) -> list[dict[str, Any]]:
    result = invoke_mcp_jsonrpc_method(
        environment=environment,
        method="tools/list",
        params={},
        secret_resolver=secret_resolver,
        oidc_token=oidc_token,
        request_id=request_id or f"{environment.get('environment_id') or 'mcp'}.tools.list",
        timeout_seconds=timeout_seconds,
        attempts=attempts,
    )
    tools = result.get("tools") if isinstance(result, dict) else None
    if not isinstance(tools, list):
        raise McpExecutionError("MCP tools/list result must contain tools array.")
    normalized: list[dict[str, Any]] = []
    for tool in tools:
        if not isinstance(tool, dict):
            raise McpExecutionError("MCP tools/list tool descriptor must be object.")
        normalized.append(tool)
    return normalized


def invoke_mcp_jsonrpc_method(
    *,
    environment: dict[str, Any],
    method: str,
    params: dict[str, Any] | None,
    secret_resolver: SecretResolver | None = None,
    oidc_token: str | None = None,
    request_id: str | None = None,
    timeout_seconds: int | float = 30,
    attempts: int = 2,
) -> dict[str, Any]:
    transport = environment.get("transport")
    if transport not in {"streamable_http", "http_sse"}:
        raise McpExecutionError(f"MCP transport {transport} не поддерживается command worker.")
    base_url = str(environment.get("base_url") or "").strip()
    if not base_url:
        raise McpExecutionError(f"MCP environment {environment.get('environment_id')} has empty base_url.")
    request_id = request_id or str(environment.get("environment_id") or "mcp-call")
    body = json.dumps(
        build_mcp_jsonrpc_request(method, request_id=request_id, params=params),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        **mcp_auth_headers(environment, secret_resolver=secret_resolver, oidc_token=oidc_token),
    }
    request = Request(base_url, data=body, headers=headers, method="POST")
    try:
        raw_body = urlopen_with_retry(
            request,
            timeout=timeout_seconds,
            operation_name=f"mcp.{environment.get('environment_id')}.{method}.{request_id}",
            attempts=attempts,
        )
    except HTTPError as error:
        raise McpExecutionError(f"MCP HTTP error {error.code}.") from error
    except (URLError, TimeoutError, OSError) as error:
        raise McpExecutionError(f"MCP network error: {type(error).__name__}.") from error
    try:
        response = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise McpExecutionError("MCP response must be UTF-8 JSON.") from error
    if not isinstance(response, dict):
        raise McpExecutionError("MCP response must be JSON object.")
    if response.get("jsonrpc") == "2.0":
        if response.get("error"):
            error = response["error"] if isinstance(response["error"], dict) else {}
            code = error.get("code", "jsonrpc_error")
            message = error.get("message", "MCP JSON-RPC error.")
            raise McpExecutionError(f"MCP JSON-RPC error {code}: {message}")
        response_id = response.get("id")
        if response_id != request_id:
            raise McpExecutionError("MCP JSON-RPC response id does not match request.")
        result = response.get("result")
        if not isinstance(result, dict):
            raise McpExecutionError("MCP JSON-RPC result must be object.")
        return result
    return response


def normalize_mcp_tool_result(result: dict[str, Any]) -> dict[str, Any]:
    if "status" in result:
        return result
    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        return structured
    content = result.get("content")
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "text":
                continue
            text = item.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict) and "status" in parsed:
                return parsed
    raise McpExecutionError("MCP tool result must contain canonical status.")


def discover_mcp_capability_candidates(
    *,
    environment: dict[str, Any],
    tools: list[dict[str, Any]] | None = None,
    secret_resolver: SecretResolver | None = None,
    oidc_token: str | None = None,
    timeout_seconds: int | float = 30,
    attempts: int = 2,
) -> dict[str, Any]:
    if environment.get("environment_tier") == "prod" and environment.get("auth_mode") not in PROD_MCP_AUTH_MODES:
        raise McpExecutionError("prod MCP discovery requires OIDC auth mode.")
    discovered_tools = tools if tools is not None else invoke_mcp_tools_list(
        environment=environment,
        secret_resolver=secret_resolver,
        oidc_token=oidc_token,
        timeout_seconds=timeout_seconds,
        attempts=attempts,
    )
    candidates: list[dict[str, Any]] = []
    ignored_tools: list[dict[str, Any]] = []
    for tool in discovered_tools:
        metadata = extract_service_desk_tool_metadata(tool)
        tool_name = str(tool.get("name") or "").strip()
        if metadata is None:
            ignored_tools.append({"tool_name": tool_name, "reason": "servicedesk metadata missing"})
            continue
        candidates.append(
            service_desk_tool_to_capability_candidate(
                environment=environment,
                tool=tool,
                metadata=metadata,
            )
        )
    return {
        "schema_version": "1.0",
        "environment_id": environment.get("environment_id"),
        "tools_checked": len(discovered_tools),
        "capability_candidates": candidates,
        "ignored_tools": ignored_tools,
    }


def build_discovery_import_payloads(
    *,
    active_capabilities: dict[str, Any],
    active_environments: dict[str, Any],
    active_bindings: dict[str, Any],
    environment_id: str,
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    if not candidates:
        raise McpExecutionError("No MCP discovery candidates selected for import.")
    capabilities_payload = copy.deepcopy(active_capabilities)
    environments_payload = copy.deepcopy(active_environments)
    bindings_payload = copy.deepcopy(active_bindings)
    imported_capability_ids: list[str] = []
    imported_binding_ids: list[str] = []
    for candidate in candidates:
        capability = copy.deepcopy(candidate.get("capability"))
        binding = copy.deepcopy(candidate.get("binding"))
        if not isinstance(capability, dict) or not isinstance(binding, dict):
            raise McpExecutionError("Discovery candidate must contain capability and binding objects.")
        capability_id = _required_text(capability, "capability_id", "Discovery candidate capability")
        binding_id = _required_text(binding, "binding_id", "Discovery candidate binding")
        if binding.get("capability_id") != capability_id:
            raise McpExecutionError(f"Discovery candidate binding {binding_id} capability_id mismatch.")
        if binding.get("environment_id") != environment_id:
            raise McpExecutionError(f"Discovery candidate binding {binding_id} environment_id mismatch.")
        _upsert_by_key(capabilities_payload.setdefault("capabilities", []), "capability_id", capability)
        _upsert_by_key(bindings_payload.setdefault("bindings", []), "binding_id", binding)
        imported_capability_ids.append(capability_id)
        imported_binding_ids.append(binding_id)
    environment = next(
        (
            item
            for item in environments_payload.setdefault("environments", [])
            if item.get("environment_id") == environment_id
        ),
        None,
    )
    if not environment:
        raise McpExecutionError(f"MCP environment not found for import: {environment_id}.")
    allowed = list(environment.get("allowed_capabilities") or [])
    for capability_id in imported_capability_ids:
        if capability_id not in allowed:
            allowed.append(capability_id)
    environment["allowed_capabilities"] = allowed
    return {
        "schema_version": "1.0",
        "imported_capability_ids": imported_capability_ids,
        "imported_binding_ids": imported_binding_ids,
        "payloads": {
            "capabilities": capabilities_payload,
            "mcp_environments": environments_payload,
            "capability_bindings": bindings_payload,
        },
    }


def extract_service_desk_tool_metadata(tool: dict[str, Any]) -> dict[str, Any] | None:
    for container in (
        tool,
        tool.get("_meta") if isinstance(tool.get("_meta"), dict) else None,
        tool.get("metadata") if isinstance(tool.get("metadata"), dict) else None,
        tool.get("annotations") if isinstance(tool.get("annotations"), dict) else None,
    ):
        if not isinstance(container, dict):
            continue
        for key in SERVICE_DESK_METADATA_KEYS:
            value = container.get(key)
            if isinstance(value, dict):
                return value
    return None


def service_desk_tool_to_capability_candidate(
    *,
    environment: dict[str, Any],
    tool: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    tool_name = _required_text(tool, "name", "MCP tool")
    capability_id = str(metadata.get("capability_id") or tool_name).strip()
    _validate_identifier(capability_id, "capability_id")
    execution_modes = _metadata_execution_modes(metadata)
    input_schema = metadata.get("input_schema") or tool.get("inputSchema")
    output_schema = metadata.get("output_schema")
    diagnostic_schema = metadata.get("diagnostic_schema") or {"type": "object", "additionalProperties": True}
    contract_version = _required_text(metadata, "contract_version", f"ServiceDesk metadata for {tool_name}")
    async_event_contracts = metadata.get("async_event_contracts") or {}
    default_completion_policy = metadata.get("default_completion_policy") or _default_completion_policy(
        execution_modes,
        async_event_contracts,
    )
    _validate_json_schema(input_schema, f"{tool_name}.input_schema")
    _validate_json_schema(output_schema, f"{tool_name}.output_schema")
    _validate_json_schema(diagnostic_schema, f"{tool_name}.diagnostic_schema")
    accepted_ack_schema = metadata.get("accepted_ack_schema")
    if "async" in execution_modes:
        _validate_async_discovery_metadata(
            tool_name=tool_name,
            async_event_contracts=async_event_contracts,
            default_completion_policy=default_completion_policy,
            accepted_ack_schema=accepted_ack_schema,
        )
    capability = {
        "capability_id": capability_id,
        "display_name": str(metadata.get("display_name") or tool.get("title") or tool_name),
        "status": str(metadata.get("status") or "draft"),
        "description": str(metadata.get("description") or tool.get("description") or tool_name),
        "contract_version": contract_version,
        "execution_modes": execution_modes,
        "input_schema": input_schema,
        "output_schema": output_schema,
        "async_event_contracts": async_event_contracts,
        "default_completion_policy": default_completion_policy,
        "diagnostic_schema": diagnostic_schema,
    }
    binding = {
        "binding_id": _binding_id(environment.get("environment_id"), capability_id),
        "capability_id": capability_id,
        "environment_id": environment.get("environment_id"),
        "mcp_tool_name": tool_name,
        "execution_mode": "async" if "async" in execution_modes else "sync",
        "status": "draft",
        "input_mapping": {
            field: f"input.{field}"
            for field in (input_schema.get("properties") or {})
        },
        "output_mapping": {
            field: f"result.{field}"
            for field in (output_schema.get("properties") or {})
        },
        "async_context_mapping": _default_async_context_mapping() if "async" in execution_modes else {},
    }
    return {
        "source_tool_name": tool_name,
        "capability": capability,
        "binding": binding,
        "accepted_ack_schema": accepted_ack_schema,
    }


def _metadata_execution_modes(metadata: dict[str, Any]) -> list[str]:
    raw = metadata.get("execution_modes")
    if raw is None and metadata.get("execution_mode"):
        raw = [metadata["execution_mode"]]
    if not isinstance(raw, list) or not raw:
        raise McpExecutionError("ServiceDesk metadata must contain non-empty execution_modes.")
    modes: list[str] = []
    for item in raw:
        mode = str(item).strip()
        if mode not in {"sync", "async"}:
            raise McpExecutionError(f"Unsupported ServiceDesk execution_mode: {mode}.")
        if mode not in modes:
            modes.append(mode)
    return modes


def _validate_async_discovery_metadata(
    *,
    tool_name: str,
    async_event_contracts: Any,
    default_completion_policy: Any,
    accepted_ack_schema: Any,
) -> None:
    if not isinstance(async_event_contracts, dict) or not async_event_contracts:
        raise McpExecutionError(f"{tool_name} async discovery metadata must contain async_event_contracts.")
    if not isinstance(default_completion_policy, dict):
        raise McpExecutionError(f"{tool_name} async discovery metadata must contain default_completion_policy.")
    if default_completion_policy.get("mode") != "external_event":
        raise McpExecutionError(f"{tool_name} async default_completion_policy.mode must be external_event.")
    expected_event_type = default_completion_policy.get("expected_event_type")
    if expected_event_type not in async_event_contracts:
        raise McpExecutionError(f"{tool_name} expected_event_type is not present in async_event_contracts.")
    _validate_accepted_ack_schema(accepted_ack_schema, tool_name)
    for event_type, contract in async_event_contracts.items():
        _validate_identifier(str(event_type), f"{tool_name}.event_type")
        if not isinstance(contract, dict):
            raise McpExecutionError(f"{tool_name} async event contract {event_type} must be object.")
        statuses = contract.get("statuses")
        if not isinstance(statuses, list) or not statuses:
            raise McpExecutionError(f"{tool_name} async event contract {event_type} must contain statuses.")
        unsupported = sorted(str(status) for status in statuses if status not in ASYNC_EVENT_STATUSES)
        if unsupported:
            raise McpExecutionError(f"{tool_name} async event contract {event_type} has unsupported statuses: {', '.join(unsupported)}.")
        _validate_json_schema(contract.get("result_schema"), f"{tool_name}.{event_type}.result_schema")
        if contract.get("progress_schema") is not None:
            _validate_json_schema(contract.get("progress_schema"), f"{tool_name}.{event_type}.progress_schema")
        if contract.get("error_schema") is not None:
            _validate_json_schema(contract.get("error_schema"), f"{tool_name}.{event_type}.error_schema")


def _validate_accepted_ack_schema(schema: Any, tool_name: str) -> None:
    _validate_json_schema(schema, f"{tool_name}.accepted_ack_schema")
    required = set(schema.get("required") or [])
    missing_required = {"status", "external_execution_id", "correlation_id"} - required
    if missing_required:
        raise McpExecutionError(
            f"{tool_name} accepted_ack_schema misses required fields: {', '.join(sorted(missing_required))}."
        )
    status_schema = (schema.get("properties") or {}).get("status") or {}
    if status_schema.get("const") != "accepted":
        raise McpExecutionError(f"{tool_name} accepted_ack_schema.status must const accepted.")


def _default_completion_policy(execution_modes: list[str], async_event_contracts: dict[str, Any]) -> dict[str, Any]:
    if "async" not in execution_modes:
        return {"mode": "sync", "max_wait_seconds": 0, "timeout_action": "mark_failed"}
    event_type = next(iter(async_event_contracts), "")
    return {
        "mode": "external_event",
        "max_wait_seconds": 3600,
        "expected_event_type": event_type,
        "timeout_action": "escalate_operator",
    }


def _default_async_context_mapping() -> dict[str, str]:
    return {field: f"async_context.{field}" for field in sorted(REQUIRED_ASYNC_CONTEXT_FIELDS)}


def _required_text(payload: dict[str, Any], field: str, owner: str) -> str:
    value = str(payload.get(field) or "").strip()
    if not value:
        raise McpExecutionError(f"{owner} must contain {field}.")
    return value


def _validate_json_schema(schema: Any, label: str) -> None:
    if not isinstance(schema, dict) or not schema:
        raise McpExecutionError(f"{label} must be non-empty JSON schema object.")
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as error:  # noqa: BLE001 - jsonschema exposes several schema error types
        raise McpExecutionError(f"{label} is not a valid JSON schema: {error}") from error


def _validate_identifier(value: str, label: str) -> None:
    if not value or not all(char.islower() or char.isdigit() or char in "_.-" for char in value) or not value[0].islower():
        raise McpExecutionError(f"{label} must match ServiceDesk identifier format.")


def _binding_id(environment_id: Any, capability_id: str) -> str:
    environment = str(environment_id or "environment").replace("mcp.", "")
    raw = f"binding.{capability_id}.{environment}"
    return "".join(char if char.islower() or char.isdigit() or char in "_.-" else "-" for char in raw)


def _upsert_by_key(items: list[dict[str, Any]], key: str, value: dict[str, Any]) -> None:
    target = value.get(key)
    for index, item in enumerate(items):
        if item.get(key) == target:
            items[index] = value
            return
    items.append(value)
