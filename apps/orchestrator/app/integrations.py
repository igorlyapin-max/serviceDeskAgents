from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from jsonschema import Draft202012Validator

from .contracts import ContractRegistry, ContractValidationError


RISK_ORDER = ["low", "medium", "high", "critical"]


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

    def resolve(self, tool_name: str) -> EndpointBinding:
        tool = self.tools_by_name.get(tool_name)
        if not tool:
            raise ContractValidationError("tool_catalog", [f"unknown tool_name: {tool_name}"])

        binding = self._select_binding(tool)
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
    ) -> dict[str, Any]:
        self.contracts.require_valid("proposed_action", action)
        self.contracts.require_valid("execution_policy_result", policy_result)

        binding = self.resolve(action["tool_name"])
        self._validate_action_against_tool(action, binding.tool)
        operation_parameters = self._build_operation_parameters(
            action["parameters"],
            binding.binding,
        )
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

    def _select_binding(self, tool: dict[str, Any]) -> dict[str, Any]:
        if not tool["endpoint_bindings"]:
            raise ContractValidationError(
                "tool_catalog",
                [f"{tool['tool_name']} не содержит привязку endpoint/operation"],
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

        validator = Draft202012Validator(tool["parameters_schema"])
        for error in sorted(
            validator.iter_errors(action.get("parameters", {})),
            key=lambda item: list(item.path),
        ):
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

    @classmethod
    def _validate_operation_parameters(
        cls,
        tool_name: str,
        operation: dict[str, Any],
        operation_parameters: dict[str, Any],
    ) -> None:
        validator = Draft202012Validator(operation["request_schema"])
        errors = [
            cls._format_jsonschema_error(error, prefix="operation_parameters")
            for error in sorted(
                validator.iter_errors(operation_parameters),
                key=lambda item: list(item.path),
            )
        ]
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
        self.adapters: dict[str, IntegrationAdapter] = {
            "mock": MockAdapter(),
            "n8n_webhook": N8nWebhookAdapter(),
            "direct_http": DirectHttpAdapter(),
        }

    def dispatch(self, invocation: dict[str, Any]) -> dict[str, Any]:
        self.contracts.require_valid("tool_invocation", invocation)
        binding = self.registry.resolve(invocation["tool_name"])
        binding_error = self._binding_gate(invocation, binding)
        if binding_error:
            return self._require_result(binding_error)

        policy_result = self._policy_gate(invocation)
        if policy_result:
            return self._require_result(policy_result)

        endpoint_result = self._endpoint_gate(invocation, binding.endpoint)
        if endpoint_result:
            return self._require_result(endpoint_result)

        adapter = self.adapters.get(invocation["adapter_type"])
        if not adapter:
            return self._require_result(
                self._base_result(
                    invocation,
                    "error",
                    error={
                        "code": "adapter_not_supported",
                        "message": f"adapter_type не поддерживается: {invocation['adapter_type']}",
                    },
                )
            )

        result = self._invoke_with_retry(adapter, invocation, binding)
        return self._require_result(result)

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

    def _require_result(self, result: dict[str, Any]) -> dict[str, Any]:
        self.contracts.require_valid("tool_result", result)
        self.registry.validate_result(result)
        return result

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
        if extensions is not None:
            result["extensions"] = extensions
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
        auth_error = self._apply_auth(headers, endpoint.get("auth"))
        if auth_error:
            return IntegrationDispatcher._base_result(invocation, "error", error=auth_error)

        payload = {
            "schema_version": "1.0",
            "invocation": invocation,
            "parameters": invocation["operation_parameters"],
            "react_parameters": invocation["parameters"],
        }
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method=operation["method"],
        )

        try:
            with urlopen(request, timeout=operation["timeout_seconds"]) as response:
                raw_body = response.read().decode("utf-8")
                output = json.loads(raw_body) if raw_body else {}
        except HTTPError as error:
            return IntegrationDispatcher._base_result(
                invocation,
                "error",
                error={
                    "code": f"http_{error.code}",
                    "message": error.reason or "n8n webhook вернул HTTP-ошибку.",
                },
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
            extensions={
                "mock": False,
                "endpoint_url": url,
            },
        )

    @staticmethod
    def _operation_url(endpoint: dict[str, Any], operation: dict[str, Any]) -> str:
        base_url = os.getenv(endpoint.get("base_url_env", "")) or endpoint["base_url"]
        return f"{base_url.rstrip('/')}/{operation['path'].lstrip('/')}"

    @staticmethod
    def _apply_auth(
        headers: dict[str, str],
        auth: dict[str, Any] | None,
    ) -> dict[str, str] | None:
        if not auth or auth["type"] == "none":
            return None

        token = os.getenv(auth.get("token_env", ""))
        if not token:
            return {
                "code": "auth_token_missing",
                "message": f"Не задана переменная окружения с auth token: {auth.get('token_env')}",
            }

        if auth["type"] == "header_token":
            headers[auth["header_name"]] = token
            return None

        if auth["type"] == "bearer_token":
            headers["Authorization"] = f"Bearer {token}"
            return None

        return {
            "code": "auth_type_not_supported",
            "message": f"Неподдерживаемый auth type: {auth['type']}",
        }
