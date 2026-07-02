from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request

from jsonschema import Draft202012Validator

from .config_registry import (
    apply_schema_parameter_defaults,
    format_required_parameter_group,
    missing_required_parameter_groups,
)
from .contracts import ContractRegistry, ContractValidationError
from .http_client import urlopen_with_retry


RISK_ORDER = ["low", "medium", "high", "critical"]
SYSTEM_OPERATION_PARAMETERS = {"invocation"}
SENSITIVE_TRACE_KEYWORDS = (
    "token",
    "password",
    "passwd",
    "pwd",
    "secret",
    "key",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "session",
    "токен",
    "пароль",
    "секрет",
    "ключ",
)
N8N_ACK_BODY_DIAGNOSTIC_MAX_LENGTH = 2000
N8N_ACK_BODY_ALLOWED_KEYS = {
    "accepted",
    "action_id",
    "async_delivery",
    "correlation_id",
    "event_type",
    "invocation_id",
    "result_topic",
    "result_transport",
    "runbook_status",
    "source",
    "status",
    "wait_id",
}
TRACE_SOURCE_EXTENSION_KEYS = (
    "source_profile_id",
    "source_step_id",
    "debug_launch_id",
)


def copy_invocation(value: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(value, ensure_ascii=False))


def trace_source_extensions(invocation: dict[str, Any]) -> dict[str, Any]:
    extensions = invocation.get("extensions") if isinstance(invocation.get("extensions"), dict) else {}
    return {
        key: copy_invocation(value)
        for key in TRACE_SOURCE_EXTENSION_KEYS
        if (value := extensions.get(key)) not in (None, "", {}, [])
    }


def value_at_path(value: Any, path: str | None) -> Any:
    if not path:
        return None
    current = value
    for part in str(path).replace("[]", "").split("."):
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


@dataclass(frozen=True)
class EndpointBinding:
    tool: dict[str, Any]
    binding: dict[str, Any]
    endpoint: dict[str, Any]
    operation_id: str
    operation: dict[str, Any]


class IntegrationAdapter(Protocol):
    def invoke(
        self,
        invocation: dict[str, Any],
        endpoint: dict[str, Any],
        operation: dict[str, Any],
    ) -> dict[str, Any]:
        """Invoke an integration endpoint and return a normalized tool_result."""
        ...


class EndpointCaptureRecorder(Protocol):
    def record_endpoint_call(
        self,
        *,
        invocation: dict[str, Any],
        endpoint: dict[str, Any],
        operation: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        """Persist a real endpoint invocation for debug mock generation."""
        ...


class ToolRegistry:
    def __init__(
        self,
        contracts: ContractRegistry,
        profile: str | None = None,
    ):
        self.contracts = contracts
        self.tools_by_name = {
            tool["tool_name"]: tool
            for tool in self.contracts.tool_catalog["tools"]
        }
        self.endpoints_by_id = {
            endpoint["endpoint_id"]: endpoint
            for endpoint in self.contracts.integration_endpoint_catalog["endpoints"]
        }

    def resolve(
        self,
        tool_name: str,
        *,
        endpoint_id: str | None = None,
        operation_id: str | None = None,
    ) -> EndpointBinding:
        tool = self.tools_by_name.get(tool_name)
        if not tool:
            raise ContractValidationError("tool_catalog", [f"unknown tool_name: {tool_name}"])

        binding = self._select_binding(tool, endpoint_id=endpoint_id, operation_id=operation_id)
        endpoint = self.endpoints_by_id[binding["endpoint_id"]]
        operation = endpoint["operations"][binding["operation_id"]]
        return EndpointBinding(
            tool=tool,
            binding=binding,
            endpoint=endpoint,
            operation_id=binding["operation_id"],
            operation=operation,
        )

    def build_invocation(
        self,
        action: dict[str, Any],
        policy_result: dict[str, Any],
        *,
        case_id: str | None = None,
        ticket_id: str | None = None,
        approved_by_operator: bool = False,
        operator_id: str | None = None,
        endpoint_id: str | None = None,
        operation_id: str | None = None,
    ) -> dict[str, Any]:
        action = copy_invocation(action)
        self.contracts.require_valid("proposed_action", action)
        self.contracts.require_valid("execution_policy_result", policy_result)

        binding = self.resolve(action["tool_name"], endpoint_id=endpoint_id, operation_id=operation_id)
        action["parameters"], applied_react_defaults = apply_schema_parameter_defaults(
            binding.tool["parameters_schema"],
            action.get("parameters", {}),
        )
        self._validate_action_against_tool(action, binding.tool)
        operation_parameters = self._build_operation_parameters(
            action["parameters"],
            binding.binding,
        )
        operation_parameters, applied_operation_defaults = apply_schema_parameter_defaults(
            self._operation_parameters_validation_schema(binding.operation),
            operation_parameters,
        )
        secret_operation_parameters = self._secret_operation_parameters(binding.binding)
        self._validate_operation_parameters(
            action["tool_name"],
            binding.operation,
            operation_parameters,
        )

        invocation = {
            "schema_version": "1.0",
            "invocation_id": f"inv-{uuid.uuid4().hex[:12]}",
            "action_id": action["action_id"],
            "tool_name": action["tool_name"],
            "action_type": action["action_type"],
            "endpoint_id": binding.endpoint["endpoint_id"],
            "adapter_type": binding.endpoint["adapter_type"],
            "operation_id": binding.operation_id,
            "parameters": action["parameters"],
            "operation_parameters": operation_parameters,
            "execution_mode": policy_result["execution_mode"],
            "allowed": policy_result["allowed"],
            "approval_required": policy_result["approval_required"],
            "approved_by_operator": approved_by_operator,
            "policy_rule_id": policy_result["policy_rule_id"],
            "timeout_seconds": binding.operation.get(
                "timeout_seconds",
                binding.tool["policy"]["default_timeout_seconds"],
            ),
            "retry_policy": binding.tool["policy"]["retry"],
        }
        action_extensions = action.get("extensions") if isinstance(action.get("extensions"), dict) else {}
        source_extensions = {
            key: copy_invocation(value)
            for key in TRACE_SOURCE_EXTENSION_KEYS
            if (value := action_extensions.get(key)) not in (None, "", {}, [])
        }
        if source_extensions:
            invocation.setdefault("extensions", {}).update(source_extensions)
        applied_defaults = {
            **{
                f"react.{parameter}": value
                for parameter, value in applied_react_defaults.items()
            },
            **{
                f"operation.{parameter}": value
                for parameter, value in applied_operation_defaults.items()
            },
        }
        if applied_defaults:
            invocation.setdefault("extensions", {})["applied_parameter_defaults"] = applied_defaults
        if secret_operation_parameters:
            invocation.setdefault("extensions", {})["secret_operation_parameters"] = secret_operation_parameters
        if case_id:
            invocation["case_id"] = case_id
        if ticket_id:
            invocation["ticket_id"] = ticket_id
        if operator_id:
            invocation["operator_id"] = operator_id

        self.contracts.require_valid("tool_invocation", invocation)
        return invocation

    def validate_result(self, result: dict[str, Any]) -> None:
        if result["status"] not in {"success", "dry_run_completed"}:
            return
        output = result.get("output", {})
        if isinstance(output, dict) and output.get("async_delivery") is True:
            runbook_status = str(output.get("runbook_status") or "").lower()
            if runbook_status == "accepted" and (
                output.get("wait_id")
                or output.get("correlation_id")
                or result.get("extensions", {}).get("async_wait")
            ):
                return

        tool = self.tools_by_name[result["tool_name"]]
        validator = Draft202012Validator(tool["result_schema"])
        errors = [
            self._format_jsonschema_error(error)
            for error in sorted(
                validator.iter_errors(result.get("output", {})),
                key=lambda item: list(item.path),
            )
        ]
        if errors:
            raise ContractValidationError("tool_result", errors)

    def _select_binding(
        self,
        tool: dict[str, Any],
        *,
        endpoint_id: str | None = None,
        operation_id: str | None = None,
    ) -> dict[str, Any]:
        if not tool["endpoint_bindings"]:
            raise ContractValidationError(
                "tool_catalog",
                [f"{tool['tool_name']} не содержит привязку endpoint/operation"],
            )
        if endpoint_id or operation_id:
            for binding in tool["endpoint_bindings"]:
                if endpoint_id and binding.get("endpoint_id") != endpoint_id:
                    continue
                if operation_id and binding.get("operation_id") != operation_id:
                    continue
                return binding
            raise ContractValidationError(
                "tool_catalog",
                [
                    f"{tool['tool_name']} не содержит binding endpoint_id={endpoint_id} "
                    f"operation_id={operation_id}"
                ],
            )
        return tool["endpoint_bindings"][0]

    @staticmethod
    def _validate_action_against_tool(
        action: dict[str, Any],
        tool: dict[str, Any],
    ) -> None:
        errors = []
        if action["action_type"] != tool["action_type"]:
            errors.append(
                f"{action['tool_name']} action_type {action['action_type']} "
                f"не совпадает с action_type в каталоге {tool['action_type']}"
            )

        missing_groups = missing_required_parameter_groups(
            tool["parameters_schema"],
            action.get("parameters", {}),
        )
        for group in missing_groups:
            errors.append(
                "parameters: не заполнен обязательный параметр: "
                f"{format_required_parameter_group(group)}"
            )

        validator = Draft202012Validator(tool["parameters_schema"])
        for error in sorted(
            validator.iter_errors(action.get("parameters", {})),
            key=lambda item: list(item.path),
        ):
            if missing_groups and error.validator in {"required", "anyOf", "oneOf", "allOf"}:
                continue
            path = ".".join(str(part) for part in error.path)
            prefix = f"parameters.{path}" if path else "parameters"
            errors.append(f"{prefix}: {error.message}")

        max_risk_level = tool["policy"]["max_risk_level"]
        risk_level = action.get("risk_level")
        if (
            risk_level in RISK_ORDER
            and RISK_ORDER.index(risk_level) > RISK_ORDER.index(max_risk_level)
        ):
            errors.append(
                f"risk_level {risk_level} превышает catalog max_risk_level {max_risk_level}"
            )

        if errors:
            raise ContractValidationError("tool_invocation", errors)

    @staticmethod
    def _build_operation_parameters(
        react_parameters: dict[str, Any],
        binding: dict[str, Any],
    ) -> dict[str, Any]:
        result = {}
        for operation_parameter, source_ref in (binding.get("parameter_mapping") or {}).items():
            source, separator, source_value = str(source_ref).partition(":")
            if separator != ":" or not source_value:
                continue
            if source == "react":
                if source_value in react_parameters:
                    result[operation_parameter] = react_parameters[source_value]
            elif source == "constant":
                result[operation_parameter] = source_value
            elif source == "secret":
                secret_value = os.getenv(source_value, "")
                if secret_value:
                    result[operation_parameter] = secret_value
        return result

    @staticmethod
    def _secret_operation_parameters(binding: dict[str, Any]) -> dict[str, str]:
        result = {}
        for operation_parameter, source_ref in (binding.get("parameter_mapping") or {}).items():
            source, separator, source_value = str(source_ref).partition(":")
            if separator == ":" and source == "secret" and source_value:
                result[operation_parameter] = source_value
        return result

    @classmethod
    def _operation_parameters_validation_schema(cls, operation: dict[str, Any]) -> dict[str, Any]:
        schema = copy_invocation(operation["request_schema"])
        properties = schema.get("properties")
        if isinstance(properties, dict):
            for parameter in SYSTEM_OPERATION_PARAMETERS:
                properties.pop(parameter, None)
        required = schema.get("required")
        if isinstance(required, list):
            schema["required"] = [
                parameter
                for parameter in required
                if parameter not in SYSTEM_OPERATION_PARAMETERS
            ]
        return schema

    @classmethod
    def _validate_operation_parameters(
        cls,
        tool_name: str,
        operation: dict[str, Any],
        operation_parameters: dict[str, Any],
    ) -> None:
        validation_schema = cls._operation_parameters_validation_schema(operation)
        missing_groups = missing_required_parameter_groups(validation_schema, operation_parameters)
        errors = [
            cls._format_jsonschema_error(error, prefix="operation_parameters")
            for error in sorted(
                Draft202012Validator(validation_schema).iter_errors(operation_parameters),
                key=lambda item: list(item.path),
            )
            if not (missing_groups and error.validator in {"required", "anyOf", "oneOf", "allOf"})
        ]
        for group in missing_groups:
            errors.insert(
                0,
                "operation_parameters: не заполнен обязательный параметр: "
                f"{format_required_parameter_group(group)}",
            )
        if errors:
            raise ContractValidationError(
                "tool_invocation",
                [f"{tool_name}: {error}" for error in errors],
            )

    @staticmethod
    def _format_jsonschema_error(error: Any, prefix: str = "output") -> str:
        path = ".".join(str(part) for part in error.path)
        location = f"{prefix}.{path}" if path else prefix
        return f"{location}: {error.message}"


class IntegrationDispatcher:
    def __init__(self, contracts: ContractRegistry, registry: ToolRegistry):
        self.contracts = contracts
        self.registry = registry
        self.capture_recorder: EndpointCaptureRecorder | None = None
        self.adapters: dict[str, IntegrationAdapter] = {
            "mock": MockAdapter(),
            "n8n_webhook": N8nWebhookAdapter(),
            "direct_http": DirectHttpAdapter(),
        }

    def dispatch(self, invocation: dict[str, Any]) -> dict[str, Any]:
        binding, preflight_result = self._preflight(invocation)
        if preflight_result:
            return preflight_result

        adapter = self.adapters.get(invocation["adapter_type"])
        if not adapter:
            return self._require_result(
                self._with_trace(
                    self._base_result(
                        invocation,
                        "error",
                        error={
                            "code": "adapter_not_supported",
                            "message": f"adapter_type не поддерживается: {invocation['adapter_type']}",
                        },
                    ),
                    invocation,
                    binding,
                )
            )

        result = self._invoke_with_retry(adapter, invocation, binding)
        result = self._normalize_result_output(result, binding)
        result = self._with_trace(result, invocation, binding)
        self._record_capture(invocation, binding, result)
        return self._require_result(result)

    def preflight(self, invocation: dict[str, Any]) -> dict[str, Any] | None:
        _, result = self._preflight(invocation)
        return result

    def _preflight(self, invocation: dict[str, Any]) -> tuple[EndpointBinding, dict[str, Any] | None]:
        self.contracts.require_valid("tool_invocation", invocation)
        binding = self.registry.resolve(
            invocation["tool_name"],
            endpoint_id=invocation["endpoint_id"],
            operation_id=invocation["operation_id"],
        )
        binding_error = self._binding_gate(invocation, binding)
        if binding_error:
            return binding, self._require_result(self._with_trace(binding_error, invocation, binding))

        policy_result = self._policy_gate(invocation)
        if policy_result:
            return binding, self._require_result(self._with_trace(policy_result, invocation, binding))

        endpoint_result = self._endpoint_gate(invocation, binding.endpoint)
        if endpoint_result:
            return binding, self._require_result(self._with_trace(endpoint_result, invocation, binding))

        return binding, None

    def _binding_gate(
        self,
        invocation: dict[str, Any],
        binding: EndpointBinding,
    ) -> dict[str, Any] | None:
        expected = {
            "endpoint_id": binding.endpoint["endpoint_id"],
            "adapter_type": binding.endpoint["adapter_type"],
            "operation_id": binding.operation_id,
        }
        mismatches = [
            f"{key} expected {value}, got {invocation[key]}"
            for key, value in expected.items()
            if invocation[key] != value
        ]
        if not mismatches:
            return None

        return self._base_result(
            invocation,
            "error",
            error={
                "code": "invocation_binding_mismatch",
                "message": "; ".join(mismatches),
            },
        )

    def _policy_gate(self, invocation: dict[str, Any]) -> dict[str, Any] | None:
        if not invocation["allowed"] or invocation["execution_mode"] == "blocked":
            return self._base_result(
                invocation,
                "blocked",
                error={
                    "code": "blocked_by_policy",
                    "message": "Политика выполнения заблокировала вызов инструмента.",
                },
            )

        if invocation["execution_mode"] == "manual_only":
            return self._base_result(
                invocation,
                "skipped",
                output={
                    "message": "Режим manual_only не отправляет вызовы в интеграции.",
                },
            )

        if invocation["approval_required"] and not invocation["approved_by_operator"]:
            return self._base_result(
                invocation,
                "pending_approval",
                output={
                    "message": "Перед вызовом интеграции требуется согласование оператора.",
                },
            )

        return None

    def _endpoint_gate(
        self,
        invocation: dict[str, Any],
        endpoint: dict[str, Any],
    ) -> dict[str, Any] | None:
        if endpoint["enabled"]:
            return None

        return self._base_result(
            invocation,
            "error",
            error={
                "code": "endpoint_disabled",
                "message": endpoint.get(
                    "disabled_reason",
                    f"Endpoint отключен: {endpoint['endpoint_id']}",
                ),
            },
        )

    def _invoke_with_retry(
        self,
        adapter: IntegrationAdapter,
        invocation: dict[str, Any],
        binding: EndpointBinding,
    ) -> dict[str, Any]:
        retry_policy = invocation["retry_policy"]
        max_attempts = retry_policy["max_attempts"]
        backoff_seconds = retry_policy["backoff_seconds"]
        started = time.perf_counter()
        result = self._base_result(
            invocation,
            "error",
            error={
                "code": "adapter_not_invoked",
                "message": "Адаптер не был вызван.",
            },
        )

        for attempt in range(1, max_attempts + 1):
            result = adapter.invoke(invocation, binding.endpoint, binding.operation)
            result["attempts"] = attempt
            result["duration_ms"] = int((time.perf_counter() - started) * 1000)

            if result["status"] != "error" or attempt == max_attempts:
                break

            if backoff_seconds:
                time.sleep(backoff_seconds)

        return result

    def _normalize_result_output(
        self,
        result: dict[str, Any],
        binding: EndpointBinding,
    ) -> dict[str, Any]:
        if result["status"] not in {"success", "dry_run_completed"}:
            return result
        output = result.get("output") or {}
        operation_validator = Draft202012Validator(binding.operation.get("response_schema", {"type": "object"}))
        operation_errors = [
            self.registry._format_jsonschema_error(error, prefix="endpoint_output")
            for error in sorted(operation_validator.iter_errors(output), key=lambda item: list(item.path))
        ]
        if operation_errors:
            return self._base_result(
                result,
                "error",
                error={
                    "code": "endpoint_response_contract_violation",
                    "message": "; ".join(operation_errors),
                },
            )
        mapping = binding.binding.get("result_mapping") or {}
        if not mapping:
            return result
        normalized_output = dict(output)
        for react_field, endpoint_path in mapping.items():
            mapped_value = value_at_path(output, endpoint_path)
            if mapped_value is not None:
                normalized_output[react_field] = mapped_value
        result["output"] = normalized_output
        return result

    def _require_result(self, result: dict[str, Any]) -> dict[str, Any]:
        self.contracts.require_valid("tool_result", result)
        self.registry.validate_result(result)
        return result

    @classmethod
    def _with_trace(
        cls,
        result: dict[str, Any],
        invocation: dict[str, Any],
        binding: EndpointBinding,
    ) -> dict[str, Any]:
        extensions = result.setdefault("extensions", {})
        parameter_mapping = copy_invocation(binding.binding.get("parameter_mapping") or {})
        operation_parameters = cls._redact_trace_parameters(
            invocation.get("operation_parameters") or {},
            parameter_mapping=parameter_mapping,
        )
        extensions["trace"] = {
            "react_parameters": cls._redact_trace_parameters(invocation.get("parameters") or {}),
            "operation_parameters": operation_parameters,
            "parameter_mapping": parameter_mapping,
            "endpoint_id": invocation.get("endpoint_id"),
            "operation_id": invocation.get("operation_id"),
            "execution_mode": invocation.get("execution_mode"),
            "approved_by_operator": invocation.get("approved_by_operator"),
            **trace_source_extensions(invocation),
        }
        return result

    @classmethod
    def _redact_trace_parameters(
        cls,
        parameters: dict[str, Any],
        *,
        parameter_mapping: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        secret_targets = {
            parameter
            for parameter, source_ref in (parameter_mapping or {}).items()
            if str(source_ref).startswith("secret:")
        }
        result = copy_invocation(parameters)
        for key in list(result):
            normalized_key = str(key).lower()
            if key in secret_targets or any(keyword in normalized_key for keyword in SENSITIVE_TRACE_KEYWORDS):
                result[key] = "параметр скрыт"
        return result

    def _record_capture(
        self,
        invocation: dict[str, Any],
        binding: EndpointBinding,
        result: dict[str, Any],
    ) -> None:
        if not self.capture_recorder:
            return
        if invocation.get("adapter_type") == "mock":
            return
        try:
            self.capture_recorder.record_endpoint_call(
                invocation=copy_invocation(invocation),
                endpoint=binding.endpoint,
                operation=binding.operation,
                result=result,
            )
        except Exception:
            return

    @staticmethod
    def _base_result(
        invocation: dict[str, Any],
        status: str,
        *,
        output: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
        extensions: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = {
            "schema_version": "1.0",
            "invocation_id": invocation["invocation_id"],
            "action_id": invocation["action_id"],
            "tool_name": invocation["tool_name"],
            "endpoint_id": invocation["endpoint_id"],
            "adapter_type": invocation["adapter_type"],
            "operation_id": invocation["operation_id"],
            "status": status,
        }
        if output is not None:
            result["output"] = output
        if error is not None:
            result["error"] = error
        result_extensions = copy_invocation(extensions or {})
        result_extensions.update(trace_source_extensions(invocation))
        if result_extensions:
            result["extensions"] = result_extensions
        result["policy_rule_id"] = invocation["policy_rule_id"]
        result["duration_ms"] = 0
        result["attempts"] = 0
        return result


class MockAdapter:
    def invoke(
        self,
        invocation: dict[str, Any],
        endpoint: dict[str, Any],
        operation: dict[str, Any],
    ) -> dict[str, Any]:
        status = "success"
        if invocation["execution_mode"] == "dry_run":
            status = "dry_run_completed"

        return IntegrationDispatcher._base_result(
            invocation,
            status,
            output={
                **operation.get("mock_output", {}),
                "parameters": invocation["parameters"],
            },
            extensions={
                "mock": True,
                "endpoint_path": operation["path"],
                "endpoint_enabled": endpoint["enabled"],
            },
        )


class DirectHttpAdapter:
    def invoke(
        self,
        invocation: dict[str, Any],
        endpoint: dict[str, Any],
        operation: dict[str, Any],
    ) -> dict[str, Any]:
        return IntegrationDispatcher._base_result(
            invocation,
            "error",
            error={
                "code": "direct_http_not_implemented",
                "message": "Адаптер Direct HTTP пока является каркасом этапа 5 и не вызывает реальные системы.",
            },
            extensions={
                "endpoint_id": endpoint["endpoint_id"],
                "endpoint_path": operation["path"],
            },
        )


class N8nWebhookAdapter:
    def invoke(
        self,
        invocation: dict[str, Any],
        endpoint: dict[str, Any],
        operation: dict[str, Any],
    ) -> dict[str, Any]:
        if not endpoint["enabled"]:
            return IntegrationDispatcher._base_result(
                invocation,
                "error",
                error={
                    "code": "endpoint_disabled",
                    "message": f"Endpoint отключен: {endpoint['endpoint_id']}",
                },
            )

        url = self._operation_url(endpoint, operation)
        headers = {
            "Content-Type": "application/json",
        }
        auth_error = self._apply_auth(
            headers,
            endpoint.get("auth"),
            endpoint_id=endpoint.get("endpoint_id"),
            operation_id=invocation.get("operation_id"),
        )
        if auth_error:
            return IntegrationDispatcher._base_result(invocation, "error", error=auth_error)

        payload = self._request_payload(invocation, operation)
        request = Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method=operation["method"],
        )

        extensions = {
            "mock": False,
            "endpoint_url": url,
        }
        try:
            raw_body = urlopen_with_retry(
                request,
                timeout=operation["timeout_seconds"],
                operation_name=f"{endpoint['endpoint_id']}/{invocation['operation_id']}",
            ).decode("utf-8")
            async_callback = self._async_callback(invocation)
            if raw_body:
                try:
                    webhook_output = json.loads(raw_body)
                except json.JSONDecodeError as error:
                    if not async_callback:
                        raise error
                    webhook_output = raw_body
            else:
                webhook_output = {}
            if async_callback:
                output = self._accepted_async_output(invocation)
                ack_body = self._ack_body_diagnostic(webhook_output)
                if ack_body is not None:
                    extensions["n8n_ack_body"] = ack_body
            else:
                output = webhook_output
        except HTTPError as error:
            return IntegrationDispatcher._base_result(
                invocation,
                "error",
                error=self._http_error(error),
            )
        except (URLError, TimeoutError) as error:
            return IntegrationDispatcher._base_result(
                invocation,
                "error",
                error={
                    "code": "webhook_unreachable",
                    "message": str(error),
                },
            )
        except json.JSONDecodeError as error:
            return IntegrationDispatcher._base_result(
                invocation,
                "error",
                error={
                    "code": "invalid_webhook_json",
                    "message": str(error),
                },
            )

        return IntegrationDispatcher._base_result(
            invocation,
            "success",
            output=output,
            extensions=extensions,
        )

    @staticmethod
    def _request_payload(invocation: dict[str, Any], operation: dict[str, Any]) -> dict[str, Any]:
        operation_parameters = copy_invocation(invocation.get("operation_parameters") or {})
        external_invocation = N8nWebhookAdapter._external_invocation(invocation)
        payload = {
            **operation_parameters,
            "invocation": external_invocation,
        }
        request_schema = operation.get("request_schema") if isinstance(operation.get("request_schema"), dict) else {}
        properties = request_schema.get("properties") if isinstance(request_schema.get("properties"), dict) else {}
        if "parameters" in properties:
            payload["parameters"] = operation_parameters
        if "react_parameters" in properties:
            payload["react_parameters"] = copy_invocation(invocation.get("parameters") or {})
        if "schema_version" in properties:
            payload["schema_version"] = "1.0"
        return payload

    @staticmethod
    def _async_callback(invocation: dict[str, Any]) -> dict[str, Any]:
        extensions = invocation.get("extensions") if isinstance(invocation.get("extensions"), dict) else {}
        async_callback = extensions.get("async_callback") if isinstance(extensions.get("async_callback"), dict) else {}
        return async_callback

    @classmethod
    def _accepted_async_output(cls, invocation: dict[str, Any]) -> dict[str, Any]:
        async_callback = cls._async_callback(invocation)
        return {
            "runbook_status": "accepted",
            "message": "n8n webhook принял асинхронный вызов; результат ожидается external event.",
            "invocation_id": invocation.get("invocation_id"),
            "action_id": invocation.get("operation_id") or invocation.get("action_id"),
            "accepted_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "async_delivery": True,
            "correlation_id": async_callback.get("correlation_id"),
            "wait_id": async_callback.get("wait_id"),
            "result_transport": async_callback.get("result_transport"),
            "result_topic": async_callback.get("result_topic"),
            "has_callback_url": bool(async_callback.get("callback_url")),
        }

    @classmethod
    def _ack_body_diagnostic(cls, value: Any) -> Any | None:
        if value in (None, "", {}, []):
            return None
        if not isinstance(value, (dict, list)):
            return {
                "type": type(value).__name__,
                "length": len(str(value)),
                "content_redacted": True,
            }

        redacted = cls._redact_ack_body(value)
        serialized = json.dumps(redacted, ensure_ascii=False, sort_keys=True)
        if len(serialized) <= N8N_ACK_BODY_DIAGNOSTIC_MAX_LENGTH:
            return redacted
        return {
            "truncated": True,
            "length": len(serialized),
            "preview": serialized[:N8N_ACK_BODY_DIAGNOSTIC_MAX_LENGTH],
        }

    @classmethod
    def _redact_ack_body(cls, value: Any) -> Any:
        if isinstance(value, dict):
            result: dict[str, Any] = {}
            for key, item in value.items():
                normalized_key = str(key).lower()
                if any(keyword in normalized_key for keyword in SENSITIVE_TRACE_KEYWORDS):
                    result[str(key)] = "параметр скрыт"
                elif normalized_key in N8N_ACK_BODY_ALLOWED_KEYS:
                    result[str(key)] = cls._redact_ack_body(item)
                else:
                    result[str(key)] = cls._redacted_ack_value_summary(item)
            return result
        if isinstance(value, list):
            return {
                "type": "list",
                "length": len(value),
                "content_redacted": True,
            }
        if isinstance(value, str):
            if len(value) <= 160:
                return value
            return {
                "type": "str",
                "length": len(value),
                "content_redacted": True,
            }
        return value

    @staticmethod
    def _redacted_ack_value_summary(value: Any) -> Any:
        if value in (None, "", {}, []):
            return value
        if isinstance(value, (bool, int, float)):
            return value
        if isinstance(value, dict):
            return {
                "type": "object",
                "keys": sorted(str(key) for key in value.keys())[:20],
                "content_redacted": True,
            }
        if isinstance(value, list):
            return {
                "type": "list",
                "length": len(value),
                "content_redacted": True,
            }
        return {
            "type": type(value).__name__,
            "length": len(str(value)),
            "content_redacted": True,
        }

    @staticmethod
    def _external_invocation(invocation: dict[str, Any]) -> dict[str, Any]:
        external = copy_invocation(invocation)
        operation_id = external.get("operation_id")
        action_id = external.get("action_id")
        if operation_id and action_id != operation_id:
            external["action_id"] = operation_id
            external.setdefault("extensions", {})["platform_action_id"] = action_id
        return external

    @staticmethod
    def _http_error(error: HTTPError) -> dict[str, Any]:
        fallback = {
            "code": f"http_{error.code}",
            "message": error.reason or "n8n webhook вернул HTTP-ошибку.",
        }
        try:
            raw_body = error.read().decode("utf-8", errors="replace")
        except Exception:
            return fallback
        if not raw_body.strip():
            return fallback
        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError:
            return fallback
        if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
            payload = payload["error"]
        if not isinstance(payload, dict):
            return fallback
        code = payload.get("code") if isinstance(payload.get("code"), str) else fallback["code"]
        message = payload.get("message") if isinstance(payload.get("message"), str) else fallback["message"]
        return {
            "code": code,
            "message": message,
        }

    @staticmethod
    def _operation_url(endpoint: dict[str, Any], operation: dict[str, Any]) -> str:
        base_url = os.getenv(endpoint.get("base_url_env", "")) or endpoint["base_url"]
        base = base_url.rstrip("/")
        path = str(operation["path"])
        if base.endswith("/webhook") and path.startswith("/webhook/"):
            path = path.removeprefix("/webhook")
        return f"{base}/{path.lstrip('/')}"

    @staticmethod
    def _apply_auth(
        headers: dict[str, str],
        auth: dict[str, Any] | None,
        *,
        endpoint_id: str | None = None,
        operation_id: str | None = None,
    ) -> dict[str, str] | None:
        if not auth or auth["type"] == "none":
            return None

        token_env = str(auth.get("token_env") or "").strip()
        header_name = str(auth.get("header_name") or "Authorization").strip()
        token = os.getenv(token_env)
        if not token:
            location = []
            if endpoint_id:
                location.append(f"endpoint {endpoint_id}")
            if operation_id:
                location.append(f"operation {operation_id}")
            prefix = f"Для {' / '.join(location)} требуется " if location else "Требуется "
            return {
                "code": "auth_token_missing",
                "message": (
                    f"{prefix}{token_env or 'token_env'} для заголовка {header_name}; "
                    "переменная не задана в runtime orchestrator/async worker."
                ),
            }

        if auth["type"] == "header_token":
            headers[header_name] = token
            return None

        if auth["type"] == "bearer_token":
            headers["Authorization"] = f"Bearer {token}"
            return None

        return {
            "code": "auth_type_not_supported",
            "message": f"Неподдерживаемый auth type: {auth['type']}",
        }
