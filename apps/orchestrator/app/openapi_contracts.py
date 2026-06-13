from __future__ import annotations

import copy
import json
import os
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import Request

from jsonschema import Draft202012Validator, SchemaError

from .http_client import urlopen_with_retry


class OpenApiContractError(ValueError):
    pass


MAX_OPENAPI_CONTRACT_BYTES = 2 * 1024 * 1024
SUPPORTED_METHODS = {"GET", "POST"}
TRANSPORT_SECURITY_SELECTOR_KEYS = {"selected_transport", "result_transport"}


def safe_url_for_log(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def resolve_contract_source_url(endpoint: dict[str, Any], contract_source: dict[str, Any]) -> str:
    source_url = str(contract_source.get("url") or "").strip()
    if not source_url:
        raise OpenApiContractError("Укажите URL OpenAPI-контракта.")

    base_url = _endpoint_base_url(endpoint)
    parsed_source = urlparse(source_url)
    if parsed_source.scheme in {"http", "https"}:
        parsed_base = urlparse(base_url)
        if parsed_base.scheme not in {"http", "https"} or not parsed_base.netloc:
            raise OpenApiContractError("Базовый URL endpoint должен быть абсолютным http/https URL.")
        if parsed_source.scheme != parsed_base.scheme or parsed_source.netloc != parsed_base.netloc:
            raise OpenApiContractError("Абсолютный URL OpenAPI должен совпадать с host и scheme сохраненного endpoint.")
        return source_url
    if parsed_source.scheme:
        raise OpenApiContractError("OpenAPI-контракт можно получать только по http или https.")

    if not base_url:
        raise OpenApiContractError("Для относительного URL OpenAPI укажите базовый URL endpoint или env-переменную.")

    parsed_base = urlparse(base_url)
    if parsed_base.scheme not in {"http", "https"} or not parsed_base.netloc:
        raise OpenApiContractError("Базовый URL endpoint должен быть абсолютным http/https URL.")

    base_path = parsed_base.path.rstrip("/")
    source_path = parsed_source.path or source_url.strip()
    if source_path.startswith("/") and (
        not base_path or source_path == base_path or source_path.startswith(f"{base_path}/")
    ):
        resolved_path = source_path
    else:
        resolved_path = f"{base_path}/{source_path.lstrip('/')}" if base_path else f"/{source_path.lstrip('/')}"
    return urlunparse((parsed_base.scheme, parsed_base.netloc, resolved_path, "", parsed_source.query, ""))


def _endpoint_base_url(endpoint: dict[str, Any]) -> str:
    base_url = ""
    base_url_env = str(endpoint.get("base_url_env") or "").strip()
    if base_url_env:
        base_url = os.getenv(base_url_env, "").strip()
    if not base_url:
        base_url = str(endpoint.get("base_url") or "").strip()
    return base_url


def _auth_headers(endpoint: dict[str, Any]) -> dict[str, str]:
    auth = endpoint.get("auth") or {}
    auth_type = auth.get("type", "none")
    if auth_type == "none":
        return {}
    token_env = str(auth.get("token_env") or "").strip()
    token = os.getenv(token_env, "").strip() if token_env else ""
    if not token:
        return {}
    if auth_type == "bearer_token":
        return {"Authorization": f"Bearer {token}"}
    if auth_type == "header_token":
        header_name = str(auth.get("header_name") or "X-ServiceDesk-Token").strip()
        return {header_name: token}
    return {}


def fetch_openapi_contract(endpoint: dict[str, Any], contract_source: dict[str, Any]) -> tuple[dict[str, Any], str]:
    url = resolve_contract_source_url(endpoint, contract_source)
    headers = {"Accept": "application/json"}
    headers.update(_auth_headers(endpoint))
    request = Request(url, headers=headers, method=str(contract_source.get("method") or "GET").upper())
    operation_name = f"openapi_contract/{endpoint.get('endpoint_id', 'endpoint')}"
    try:
        body = urlopen_with_retry(request, timeout=10, operation_name=operation_name, attempts=2)
    except HTTPError as error:
        raise OpenApiContractError(f"OpenAPI endpoint вернул HTTP {error.code}: {safe_url_for_log(url)}") from error
    except (URLError, TimeoutError) as error:
        raise OpenApiContractError(f"Не удалось получить OpenAPI-контракт: {error}") from error
    if len(body) > MAX_OPENAPI_CONTRACT_BYTES:
        raise OpenApiContractError("OpenAPI-контракт слишком большой для импорта в UI.")
    try:
        document = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise OpenApiContractError("OpenAPI endpoint должен возвращать JSON-документ.") from error
    if not isinstance(document, dict):
        raise OpenApiContractError("OpenAPI endpoint вернул не объект JSON.")
    return document, url


def _contains_delivery_selector(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            key in TRANSPORT_SECURITY_SELECTOR_KEYS or _contains_delivery_selector(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_delivery_selector(item) for item in value)
    return False


def _string_list(value: Any, default: list[str]) -> list[str]:
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        return items or default
    if isinstance(value, str) and value.strip():
        return [item.strip() for item in value.split(",") if item.strip()] or default
    return default


def normalize_openapi_transport_security(document: dict[str, Any]) -> dict[str, Any] | None:
    raw = document.get("x-transport-security")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise OpenApiContractError("x-transport-security должен быть объектом.")
    if _contains_delivery_selector(raw):
        raise OpenApiContractError(
            "x-transport-security описывает защиту транспорта и не должен содержать "
            "selected_transport или result_transport."
        )

    result: dict[str, Any] = {}
    http = raw.get("http") or raw.get("http_callback")
    if isinstance(http, dict):
        http_result = {
            "policy": str(http.get("policy") or "admin_configured"),
            "production_recommended_scheme": str(
                http.get("production_recommended_scheme")
                or http.get("recommended_production_scheme")
                or "https"
            ),
        }
        for key in ("base_url_env", "callback_base_url_env", "token_header", "token_env"):
            if http.get(key):
                http_result[key] = str(http[key])
        result["http"] = http_result

    kafka = raw.get("kafka") or raw.get("kafka_event") or raw.get("queue")
    if isinstance(kafka, dict):
        kafka_result = {
            "policy": str(kafka.get("policy") or "admin_configured"),
            "bootstrap_servers_env": str(kafka.get("bootstrap_servers_env") or "KAFKA_BOOTSTRAP_SERVERS"),
            "security_protocol_env": str(kafka.get("security_protocol_env") or "KAFKA_SECURITY_PROTOCOL"),
            "supported_security_protocols": _string_list(
                kafka.get("supported_security_protocols"),
                ["SASL_SSL", "SSL"],
            ),
            "supported_auth": _string_list(kafka.get("supported_auth"), ["sasl", "mtls"]),
        }
        result["kafka"] = kafka_result

    if not result:
        raise OpenApiContractError("x-transport-security должен содержать http/http_callback или kafka/kafka_event.")
    return result


def normalize_operation_id(value: str | None, method: str, path: str) -> str:
    raw = value or f"{method.lower()}_{path.strip('/')}"
    raw = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", str(raw))
    raw = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", raw)
    normalized = re.sub(r"[^a-z0-9_]+", "_", str(raw).lower()).strip("_")
    normalized = re.sub(r"_+", "_", normalized)
    if not normalized:
        normalized = "operation"
    if not re.match(r"^[a-z]", normalized):
        normalized = f"op_{normalized}"
    return normalized


def normalize_react_call_name(endpoint_id: str, operation_id: str) -> str:
    raw = f"{endpoint_id}_{operation_id}"
    raw = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", raw)
    raw = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", raw)
    normalized = re.sub(r"[^a-z0-9_]+", "_", raw.lower()).strip("_")
    normalized = re.sub(r"_+", "_", normalized)
    if not normalized:
        normalized = "react_call"
    if not re.match(r"^[a-z]", normalized):
        normalized = f"call_{normalized}"
    return normalized


def schema_property_names(schema: dict[str, Any] | None) -> list[str]:
    if not isinstance(schema, dict):
        return []
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return []
    return [str(name) for name in properties]


def default_parameter_mapping(operation: dict[str, Any]) -> dict[str, str]:
    return {
        parameter_name: f"react:{parameter_name}"
        for parameter_name in schema_property_names(operation.get("request_schema"))
    }


def default_result_mapping(operation: dict[str, Any]) -> dict[str, str]:
    return {
        result_name: result_name
        for result_name in schema_property_names(operation.get("response_schema"))
    }


def default_react_policy(action_type: str, operation: dict[str, Any]) -> dict[str, Any]:
    read_only = action_type == "read_only"
    return {
        "default_timeout_seconds": int(operation.get("timeout_seconds") or 30),
        "retry": {
            "max_attempts": 1,
            "backoff_seconds": 0,
        },
        "approval_required_hint": not read_only,
        "auto_execution_eligible": read_only,
        "max_risk_level": "low" if read_only else "medium",
    }


def proposed_react_calls_for_operations(
    endpoint: dict[str, Any],
    operations: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    endpoint_id = str(endpoint.get("endpoint_id") or "endpoint")
    proposed_tools: dict[str, dict[str, Any]] = {}
    bindings: dict[str, dict[str, Any]] = {}
    for operation_id, operation in sorted(operations.items()):
        action_type = "read_only" if str(operation.get("method") or "").upper() == "GET" else "action"
        tool_name = normalize_react_call_name(endpoint_id, operation_id)
        binding = {
            "endpoint_id": endpoint_id,
            "operation_id": operation_id,
            "parameter_mapping": default_parameter_mapping(operation),
            "result_mapping": default_result_mapping(operation),
        }
        bindings[tool_name] = binding
        proposed_tools[tool_name] = {
            "tool_name": tool_name,
            "action_type": action_type,
            "description": operation.get("description")
            or operation.get("display_name")
            or f"ReAct-вызов ИИ для OpenAPI операции {operation_id}.",
            "endpoint_bindings": [binding],
            "parameters_schema": copy.deepcopy(operation.get("request_schema") or {"type": "object", "additionalProperties": True}),
            "result_schema": copy.deepcopy(operation.get("response_schema") or {"type": "object", "additionalProperties": True}),
            "contract_version": str(operation.get("contract_version") or "1.0"),
            "contract_status": str(operation.get("contract_status") or "draft"),
            "policy": default_react_policy(action_type, operation),
            "extensions": {
                "generated_from": "openapi_3_1",
                "endpoint_id": endpoint_id,
                "operation_id": operation_id,
            },
        }
    return {
        "tools": proposed_tools,
        "bindings": bindings,
    }


def _json_pointer(document: dict[str, Any], pointer: str) -> Any:
    current: Any = document
    for raw_part in pointer.lstrip("/").split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            raise OpenApiContractError(f"OpenAPI $ref не найден: #/{pointer.lstrip('/')}")
    return current


def resolve_schema_refs(schema: Any, document: dict[str, Any], warnings: list[str], seen: set[str] | None = None) -> Any:
    if seen is None:
        seen = set()
    if isinstance(schema, list):
        return [resolve_schema_refs(item, document, warnings, seen) for item in schema]
    if not isinstance(schema, dict):
        return schema
    ref = schema.get("$ref")
    if isinstance(ref, str):
        if not ref.startswith("#/"):
            warnings.append(f"Внешний $ref не поддерживается и заменен пустой схемой: {ref}")
            return {}
        if ref in seen:
            warnings.append(f"Циклический $ref заменен пустой схемой: {ref}")
            return {}
        try:
            target = copy.deepcopy(_json_pointer(document, ref[1:]))
        except OpenApiContractError as error:
            warnings.append(str(error))
            return {}
        return resolve_schema_refs(target, document, warnings, {*seen, ref})
    return {
        key: resolve_schema_refs(value, document, warnings, seen)
        for key, value in schema.items()
    }


def schema_or_default(schema: Any, document: dict[str, Any], warnings: list[str], *, context: str) -> dict[str, Any]:
    resolved = resolve_schema_refs(schema, document, warnings) if schema is not None else None
    if isinstance(resolved, bool):
        warnings.append(f"{context}: boolean JSON Schema заменена на свободный объект для UI.")
        return {"type": "object", "additionalProperties": True}
    if not isinstance(resolved, dict):
        warnings.append(f"{context}: схема отсутствует или не является объектом; использован свободный объект.")
        return {"type": "object", "additionalProperties": True}
    try:
        Draft202012Validator.check_schema(resolved)
    except SchemaError as error:
        warnings.append(f"{context}: JSON Schema невалидна ({error.message}); использован свободный объект.")
        return {"type": "object", "additionalProperties": True}
    return resolved


def _content_json_schema(content: dict[str, Any] | None) -> Any:
    if not isinstance(content, dict):
        return None
    for content_type in ("application/json", "application/problem+json"):
        item = content.get(content_type)
        if isinstance(item, dict) and "schema" in item:
            return item["schema"]
    for content_type, item in content.items():
        if "+json" in content_type and isinstance(item, dict) and "schema" in item:
            return item["schema"]
    return None


def _parameter_schema(parameter: dict[str, Any], document: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    schema = parameter.get("schema")
    if isinstance(schema, dict) and "schema" in schema:
        schema = schema["schema"]
    result = schema_or_default(schema or {"type": "string"}, document, warnings, context=f"parameter {parameter.get('name')}")
    if "description" not in result and parameter.get("description"):
        result = {**result, "description": parameter["description"]}
    return result


def request_schema_for_operation(
    path_item: dict[str, Any],
    operation: dict[str, Any],
    document: dict[str, Any],
    warnings: list[str],
    *,
    operation_id: str,
) -> dict[str, Any]:
    request_body = operation.get("requestBody")
    if isinstance(request_body, dict) and "$ref" in request_body:
        request_body = resolve_schema_refs(request_body, document, warnings)
    body_schema = None
    if isinstance(request_body, dict):
        body_schema = _content_json_schema(request_body.get("content"))
    request_schema = schema_or_default(
        body_schema or {"type": "object", "additionalProperties": True},
        document,
        warnings,
        context=f"{operation_id} requestBody",
    )

    parameters: list[dict[str, Any]] = []
    for raw_parameter in [*(path_item.get("parameters") or []), *(operation.get("parameters") or [])]:
        parameter = resolve_schema_refs(raw_parameter, document, warnings)
        if isinstance(parameter, dict) and parameter.get("name"):
            parameters.append(parameter)
    if not parameters:
        return request_schema

    if request_schema.get("type") != "object":
        request_schema = {
            "type": "object",
            "properties": {"body": request_schema},
            "required": ["body"] if isinstance(request_body, dict) and request_body.get("required") else [],
        }
    request_schema = copy.deepcopy(request_schema)
    properties = request_schema.setdefault("properties", {})
    required = list(request_schema.get("required") or [])
    for parameter in parameters:
        name = str(parameter["name"])
        properties[name] = _parameter_schema(parameter, document, warnings)
        if parameter.get("required") and name not in required:
            required.append(name)
    if required:
        request_schema["required"] = required
    return request_schema


def response_schema_for_operation(
    operation: dict[str, Any],
    document: dict[str, Any],
    warnings: list[str],
    *,
    operation_id: str,
) -> dict[str, Any]:
    responses = operation.get("responses") or {}
    if not isinstance(responses, dict) or not responses:
        warnings.append(f"{operation_id}: responses отсутствует; использован свободный объект.")
        return {"type": "object", "additionalProperties": True}
    response_key = next((key for key in ("200", "201", "202") if key in responses), None)
    if not response_key:
        response_key = next((key for key in sorted(responses) if str(key).startswith("2")), None)
    if not response_key:
        warnings.append(f"{operation_id}: успешный 2xx response не найден; использован свободный объект.")
        return {"type": "object", "additionalProperties": True}
    response = resolve_schema_refs(responses[response_key], document, warnings)
    content = response.get("content") if isinstance(response, dict) else {}
    schema = _content_json_schema(content)
    if schema is None:
        warnings.append(f"{operation_id}: response {response_key} не содержит application/json schema.")
    return schema_or_default(
        schema or {"type": "object", "additionalProperties": True},
        document,
        warnings,
        context=f"{operation_id} response {response_key}",
    )


def import_openapi_operations(document: dict[str, Any]) -> dict[str, Any]:
    openapi_version = str(document.get("openapi") or "")
    if not openapi_version:
        raise OpenApiContractError("Документ не похож на OpenAPI: отсутствует поле openapi.")
    warnings: list[str] = []
    if not openapi_version.startswith("3.1"):
        warnings.append(f"Версия OpenAPI {openapi_version}; ожидается 3.1, импорт выполнен в совместимом режиме.")
    paths = document.get("paths")
    if not isinstance(paths, dict) or not paths:
        raise OpenApiContractError("OpenAPI-документ не содержит paths.")

    info = document.get("info") if isinstance(document.get("info"), dict) else {}
    contract_version = str(info.get("version") or openapi_version or "1.0")
    operations: dict[str, dict[str, Any]] = {}
    used_ids: set[str] = set()
    for path, path_item in sorted(paths.items()):
        if not isinstance(path_item, dict):
            continue
        for raw_method, operation in sorted(path_item.items()):
            method = str(raw_method).upper()
            if method not in SUPPORTED_METHODS:
                continue
            if not isinstance(operation, dict):
                continue
            base_operation_id = normalize_operation_id(operation.get("operationId"), method, str(path))
            operation_id = base_operation_id
            duplicate_index = 2
            while operation_id in used_ids:
                operation_id = f"{base_operation_id}_{duplicate_index}"
                duplicate_index += 1
            if operation_id != base_operation_id:
                warnings.append(f"Дублируется operationId {base_operation_id}; импортировано как {operation_id}.")
            used_ids.add(operation_id)

            operation_warnings: list[str] = []
            request_schema = request_schema_for_operation(
                path_item,
                operation,
                document,
                operation_warnings,
                operation_id=operation_id,
            )
            response_schema = response_schema_for_operation(
                operation,
                document,
                operation_warnings,
                operation_id=operation_id,
            )
            warnings.extend(operation_warnings)
            display_name = str(operation.get("summary") or operation.get("operationId") or operation_id)
            description = str(operation.get("description") or operation.get("summary") or f"OpenAPI операция {operation_id}.")
            operations[operation_id] = {
                "display_name": display_name,
                "description": description,
                "method": method,
                "path": str(path),
                "request_schema": request_schema,
                "response_schema": response_schema,
                "async_event_contracts": {},
                "contract_version": contract_version,
                "contract_status": "draft" if operation_warnings else "valid",
                "timeout_seconds": 30,
                "extensions": {
                    "contract_source": "openapi_3_1",
                    "openapi_path": str(path),
                    "openapi_operation_id": operation.get("operationId") or operation_id,
                },
            }

    if not operations:
        raise OpenApiContractError("В OpenAPI-документе не найдены операции GET/POST для импорта.")
    result = {
        "schema_version": "1.0",
        "openapi_version": openapi_version,
        "info_version": contract_version,
        "operations": operations,
        "warnings": warnings,
    }
    transport_security = normalize_openapi_transport_security(document)
    if transport_security:
        result["transport_security"] = transport_security
    return result


def preview_openapi_contract(endpoint: dict[str, Any], contract_source: dict[str, Any]) -> dict[str, Any]:
    if str(endpoint.get("adapter_type") or "") != "n8n_webhook":
        raise OpenApiContractError("Импорт OpenAPI сейчас доступен только для endpoint n8n_webhook.")
    source = copy.deepcopy(contract_source or endpoint.get("contract_source") or {})
    if source.get("type") not in {"openapi_3_1", None}:
        raise OpenApiContractError("Поддерживается только contract_source.type=openapi_3_1.")
    source.setdefault("method", "GET")
    document, resolved_url = fetch_openapi_contract(endpoint, source)
    result = import_openapi_operations(document)
    result["proposed_react_calls"] = proposed_react_calls_for_operations(endpoint, result["operations"])
    result["source_url"] = safe_url_for_log(resolved_url)
    return result
