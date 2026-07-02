from __future__ import annotations

import json
import io
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from apps.orchestrator.app import openapi_contracts
from apps.orchestrator.app.contracts import ContractRegistry, ContractValidationError
from apps.orchestrator.app.integrations import IntegrationDispatcher, N8nWebhookAdapter, ToolRegistry
from apps.orchestrator.app.openapi_contracts import (
    OpenApiContractError,
    import_openapi_operations,
    openapi_contract_localization_diagnostics,
    openapi_operation_language_warnings,
    proposed_react_calls_for_operations,
    resolve_contract_source_url,
)


class OpenApiContractsTest(unittest.TestCase):
    def _n8n_ack_contracts(self) -> ContractRegistry:
        contracts = ContractRegistry()
        contracts.tool_catalog = {
            "schema_version": "1.0",
            "tools": [
                {
                    "tool_name": "n8n_wait_for_email_by_ticket",
                    "description": "Дождаться письма.",
                    "action_type": "read_only",
                    "parameters_schema": {
                        "type": "object",
                        "required": ["ticket_number"],
                        "properties": {
                            "ticket_number": {"type": "string"},
                        },
                        "additionalProperties": True,
                    },
                    "result_schema": {
                        "type": "object",
                        "required": ["runbook_status", "message"],
                        "properties": {
                            "runbook_status": {"type": "string"},
                            "message": {"type": "string"},
                            "async_delivery": {"type": "boolean"},
                        },
                        "additionalProperties": True,
                    },
                    "endpoint_bindings": [
                        {
                            "endpoint_id": "n8n",
                            "operation_id": "wait_for_email_by_ticket",
                            "parameter_mapping": {"ticket_number": "react:ticket_number"},
                            "result_mapping": {},
                        }
                    ],
                    "policy": {
                        "default_timeout_seconds": 30,
                        "retry": {"max_attempts": 1, "backoff_seconds": 0},
                        "approval_required_hint": False,
                        "auto_execution_eligible": True,
                        "max_risk_level": "low",
                    },
                    "contract_version": "1.0",
                    "contract_status": "valid",
                }
            ],
        }
        contracts.integration_endpoint_catalog = {
            "schema_version": "1.0",
            "endpoints": [
                {
                    "endpoint_id": "n8n",
                    "display_name": "n8n",
                    "adapter_type": "n8n_webhook",
                    "enabled": True,
                    "base_url": "http://127.0.0.1:5678/webhook",
                    "base_url_env": "",
                    "auth": {"type": "none"},
                    "operations": {
                        "wait_for_email_by_ticket": {
                            "operation_id": "wait_for_email_by_ticket",
                            "display_name": "Дождаться письма",
                            "method": "POST",
                            "path": "/webhook/email/wait-for-ticket",
                            "timeout_seconds": 5,
                            "request_schema": {
                                "type": "object",
                                "properties": {"ticket_number": {"type": "string"}},
                                "additionalProperties": True,
                            },
                            "response_schema": {
                                "type": "object",
                                "required": ["runbook_status", "message"],
                                "properties": {
                                    "runbook_status": {"type": "string"},
                                    "message": {"type": "string"},
                                },
                                "additionalProperties": True,
                            },
                        }
                    },
                }
            ],
        }
        return contracts

    def _n8n_ack_invocation(self, registry: ToolRegistry) -> dict:
        return registry.build_invocation(
            {
                "tool_name": "n8n_wait_for_email_by_ticket",
                "action_id": "act-ack",
                "action_type": "read_only",
                "parameters": {"ticket_number": "SR-42"},
                "reason": "Проверка async ack.",
                "risk_level": "low",
                "expected_effect": "Дождаться письма.",
                "requires_state_change": False,
            },
            {
                "schema_version": "1.0",
                "action_id": "act-ack",
                "tool_name": "n8n_wait_for_email_by_ticket",
                "execution_mode": "auto_execute",
                "allowed": True,
                "approval_required": False,
                "policy_rule_id": "test",
                "reason": "Проверка async ack.",
            },
        )

    def test_tool_registry_allows_async_ack_before_terminal_result_schema(self) -> None:
        contracts = self._n8n_ack_contracts()
        contracts.tool_catalog["tools"][0]["result_schema"] = {
            "type": "object",
            "required": ["body"],
            "properties": {"body": {"type": "string"}},
            "additionalProperties": False,
        }
        registry = ToolRegistry(contracts)
        result = {
            "schema_version": "1.0",
            "invocation_id": "inv-async-ack",
            "action_id": "act-ack",
            "tool_name": "n8n_wait_for_email_by_ticket",
            "endpoint_id": "n8n",
            "adapter_type": "n8n_webhook",
            "operation_id": "wait_for_email_by_ticket",
            "status": "success",
            "policy_rule_id": "test",
            "duration_ms": 1,
            "attempts": 1,
            "output": {
                "runbook_status": "accepted",
                "message": "Accepted.",
                "async_delivery": True,
                "wait_id": "wait-1",
                "correlation_id": "corr-1",
            },
            "extensions": {"async_wait": {"wait_id": "wait-1"}},
        }

        registry.validate_result(result)

        result["output"] = {"runbook_status": "accepted", "message": "Accepted."}
        result["extensions"] = {}
        with self.assertRaises(ContractValidationError):
            registry.validate_result(result)

    def test_n8n_webhook_payload_puts_operation_parameters_at_top_level(self) -> None:
        endpoint = {
            "endpoint_id": "n8n",
            "enabled": True,
            "base_url": "http://127.0.0.1:5678/webhook",
            "base_url_env": "",
            "auth": {"type": "none"},
        }
        operation = {
            "method": "POST",
            "path": "/webhook/email/wait-for-ticket",
            "timeout_seconds": 5,
            "request_schema": {
                "type": "object",
                "additionalProperties": True,
                "required": ["ticket_number"],
                "properties": {
                    "ticket_number": {"type": "string"},
                    "invocation": {"type": "object"},
                },
            },
        }
        invocation = {
            "invocation_id": "inv-1",
            "action_id": "act-1",
            "tool_name": "n8n_wait_for_email_by_ticket",
            "endpoint_id": "n8n",
            "adapter_type": "n8n_webhook",
            "operation_id": "wait_for_email_by_ticket",
            "operation_parameters": {"ticket_number": "SR-42"},
            "parameters": {"ticket_number": "SR-42"},
            "policy_rule_id": "debug",
        }
        captured = {}

        def fake_urlopen(request, **_kwargs):
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return b'{"status":"OK","ticket_number":"SR-42"}'

        with patch("apps.orchestrator.app.integrations.urlopen_with_retry", fake_urlopen):
            result = N8nWebhookAdapter().invoke(invocation, endpoint, operation)

        self.assertEqual(result["status"], "success")
        self.assertEqual(captured["body"]["ticket_number"], "SR-42")
        self.assertEqual(captured["body"]["invocation"]["invocation_id"], "inv-1")
        self.assertEqual(captured["body"]["invocation"]["action_id"], "wait_for_email_by_ticket")
        self.assertEqual(captured["body"]["invocation"]["extensions"]["platform_action_id"], "act-1")
        self.assertNotIn("parameters", captured["body"])

    def test_n8n_webhook_payload_keeps_parameters_wrapper_when_contract_declares_it(self) -> None:
        endpoint = {
            "endpoint_id": "n8n",
            "enabled": True,
            "base_url": "http://127.0.0.1:5678/webhook",
            "base_url_env": "",
            "auth": {"type": "none"},
        }
        operation = {
            "method": "POST",
            "path": "/webhook/servicedesk/runbook/start",
            "timeout_seconds": 5,
            "request_schema": {
                "type": "object",
                "additionalProperties": True,
                "required": ["invocation"],
                "properties": {
                    "invocation": {"type": "object"},
                    "parameters": {"type": "object"},
                },
            },
        }
        invocation = {
            "invocation_id": "inv-1",
            "action_id": "act-1",
            "tool_name": "start_systemcenter_runbook",
            "endpoint_id": "n8n",
            "adapter_type": "n8n_webhook",
            "operation_id": "start_systemcenter_runbook",
            "operation_parameters": {"runbook_code": "password_reset"},
            "parameters": {"runbook_code": "password_reset"},
            "policy_rule_id": "debug",
        }
        captured = {}

        def fake_urlopen(request, **_kwargs):
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return b'{"runbook_status":"accepted"}'

        with patch("apps.orchestrator.app.integrations.urlopen_with_retry", fake_urlopen):
            result = N8nWebhookAdapter().invoke(invocation, endpoint, operation)

        self.assertEqual(result["status"], "success")
        self.assertEqual(captured["body"]["runbook_code"], "password_reset")
        self.assertEqual(captured["body"]["parameters"]["runbook_code"], "password_reset")
        self.assertEqual(captured["body"]["invocation"]["invocation_id"], "inv-1")
        self.assertEqual(captured["body"]["invocation"]["action_id"], "start_systemcenter_runbook")
        self.assertEqual(captured["body"]["invocation"]["extensions"]["platform_action_id"], "act-1")

    def test_tool_registry_applies_required_parameter_defaults_before_validation(self) -> None:
        contracts = ContractRegistry()
        contracts.tool_catalog = {
            "schema_version": "1.0",
            "tools": [
                {
                    "tool_name": "n8n_wait_for_email_by_ticket",
                    "description": "Дождаться письма.",
                    "action_type": "read_only",
                    "parameters_schema": {
                        "type": "object",
                        "required": ["ticket_number", "poll_interval_minutes", "timeout_minutes"],
                        "properties": {
                            "ticket_number": {"type": "string"},
                            "poll_interval_minutes": {"type": "integer", "default": 1},
                            "timeout_minutes": {"type": "integer", "default": 15},
                        },
                        "additionalProperties": True,
                    },
                    "result_schema": {"type": "object", "additionalProperties": True},
                    "endpoint_bindings": [
                        {
                            "endpoint_id": "n8n",
                            "operation_id": "wait_for_email_by_ticket",
                            "parameter_mapping": {
                                "ticket_number": "react:ticket_number",
                                "poll_interval_minutes": "react:poll_interval_minutes",
                                "timeout_minutes": "react:timeout_minutes",
                            },
                            "result_mapping": {},
                        }
                    ],
                    "policy": {
                        "default_timeout_seconds": 30,
                        "retry": {"max_attempts": 1, "backoff_seconds": 0},
                        "approval_required_hint": False,
                        "auto_execution_eligible": True,
                        "max_risk_level": "low",
                    },
                    "contract_version": "1.0",
                    "contract_status": "valid",
                }
            ],
        }
        contracts.integration_endpoint_catalog = {
            "schema_version": "1.0",
            "endpoints": [
                {
                    "endpoint_id": "n8n",
                    "display_name": "n8n",
                    "adapter_type": "n8n_webhook",
                    "enabled": True,
                    "auth": {"type": "none"},
                    "operations": {
                        "wait_for_email_by_ticket": {
                            "operation_id": "wait_for_email_by_ticket",
                            "display_name": "Дождаться письма",
                            "method": "POST",
                            "path": "/webhook/email/wait",
                            "timeout_seconds": 30,
                            "request_schema": {
                                "type": "object",
                                "required": ["ticket_number", "poll_interval_minutes", "timeout_minutes"],
                                "properties": {
                                    "ticket_number": {"type": "string"},
                                    "poll_interval_minutes": {"type": "integer"},
                                    "timeout_minutes": {"type": "integer"},
                                },
                                "additionalProperties": True,
                            },
                            "response_schema": {"type": "object", "additionalProperties": True},
                        }
                    },
                }
            ],
        }

        invocation = ToolRegistry(contracts).build_invocation(
            {
                "tool_name": "n8n_wait_for_email_by_ticket",
                "action_id": "act-1",
                "action_type": "read_only",
                "parameters": {"ticket_number": "SR-42"},
                "reason": "Проверка.",
                "risk_level": "low",
                "expected_effect": "Дождаться письма.",
                "requires_state_change": False,
            },
            {
                "schema_version": "1.0",
                "action_id": "act-1",
                "tool_name": "n8n_wait_for_email_by_ticket",
                "execution_mode": "auto_execute",
                "allowed": True,
                "approval_required": False,
                "policy_rule_id": "test",
                "reason": "Проверка.",
            },
        )

        self.assertEqual(invocation["parameters"]["poll_interval_minutes"], 1)
        self.assertEqual(invocation["parameters"]["timeout_minutes"], 15)
        self.assertEqual(invocation["operation_parameters"]["poll_interval_minutes"], 1)
        self.assertEqual(invocation["operation_parameters"]["timeout_minutes"], 15)
        self.assertEqual(invocation["extensions"]["applied_parameter_defaults"]["react.poll_interval_minutes"], 1)

    def test_tool_registry_reports_missing_required_parameter_group(self) -> None:
        contracts = ContractRegistry()
        contracts.tool_catalog = {
            "schema_version": "1.0",
            "tools": [
                {
                    "tool_name": "n8n_wait_for_email_by_ticket",
                    "description": "Дождаться письма.",
                    "action_type": "read_only",
                    "parameters_schema": {
                        "type": "object",
                        "properties": {
                            "ticket_number": {"type": "string"},
                            "poll_interval_minutes": {"type": "integer"},
                            "timeout_minutes": {"type": "integer"},
                        },
                        "allOf": [
                            {"anyOf": [{"required": ["poll_interval_minutes"]}, {"required": ["pollIntervalMinutes"]}]},
                            {"anyOf": [{"required": ["timeout_minutes"]}, {"required": ["timeoutMinutes"]}]},
                        ],
                        "additionalProperties": True,
                    },
                    "result_schema": {"type": "object", "additionalProperties": True},
                    "endpoint_bindings": [
                        {
                            "endpoint_id": "n8n",
                            "operation_id": "wait_for_email_by_ticket",
                            "parameter_mapping": {"ticket_number": "react:ticket_number"},
                            "result_mapping": {},
                        }
                    ],
                    "policy": {
                        "default_timeout_seconds": 30,
                        "retry": {"max_attempts": 1, "backoff_seconds": 0},
                        "approval_required_hint": False,
                        "auto_execution_eligible": True,
                        "max_risk_level": "low",
                    },
                    "contract_version": "1.0",
                    "contract_status": "valid",
                }
            ],
        }
        contracts.integration_endpoint_catalog = {
            "schema_version": "1.0",
            "endpoints": [
                {
                    "endpoint_id": "n8n",
                    "display_name": "n8n",
                    "adapter_type": "n8n_webhook",
                    "enabled": True,
                    "auth": {"type": "none"},
                    "operations": {
                        "wait_for_email_by_ticket": {
                            "operation_id": "wait_for_email_by_ticket",
                            "display_name": "Дождаться письма",
                            "method": "POST",
                            "path": "/webhook/email/wait",
                            "timeout_seconds": 30,
                            "request_schema": {"type": "object", "additionalProperties": True},
                            "response_schema": {"type": "object", "additionalProperties": True},
                        }
                    },
                }
            ],
        }

        with self.assertRaises(ContractValidationError) as raised:
            ToolRegistry(contracts).build_invocation(
                {
                    "tool_name": "n8n_wait_for_email_by_ticket",
                    "action_id": "act-1",
                    "action_type": "read_only",
                    "parameters": {"ticket_number": "SR-42"},
                    "reason": "Проверка.",
                    "risk_level": "low",
                    "expected_effect": "Дождаться письма.",
                    "requires_state_change": False,
                },
                {
                    "schema_version": "1.0",
                    "action_id": "act-1",
                    "tool_name": "n8n_wait_for_email_by_ticket",
                    "execution_mode": "auto_execute",
                    "allowed": True,
                    "approval_required": False,
                    "policy_rule_id": "test",
                    "reason": "Проверка.",
                },
            )

        self.assertTrue(
            any("poll_interval_minutes или pollIntervalMinutes" in error for error in raised.exception.errors),
            raised.exception.errors,
        )

    def test_n8n_webhook_http_error_uses_n8n_error_payload(self) -> None:
        endpoint = {
            "endpoint_id": "n8n",
            "enabled": True,
            "base_url": "http://127.0.0.1:5678/webhook",
            "base_url_env": "",
            "auth": {"type": "none"},
        }
        operation = {
            "method": "POST",
            "path": "/webhook/email/wait-for-ticket",
            "timeout_seconds": 5,
            "request_schema": {
                "type": "object",
                "additionalProperties": True,
                "properties": {"ticket_number": {"type": "string"}},
            },
        }
        invocation = {
            "invocation_id": "inv-1",
            "action_id": "act-1",
            "tool_name": "n8n_wait_for_email_by_ticket",
            "endpoint_id": "n8n",
            "adapter_type": "n8n_webhook",
            "operation_id": "wait_for_email_by_ticket",
            "operation_parameters": {},
            "parameters": {},
            "policy_rule_id": "debug",
        }

        def fake_urlopen(_request, **_kwargs):
            error_body = json.dumps(
                {
                    "error": {
                        "code": "missing_ticket_number",
                        "message": "Поле ticket_number обязательно.",
                    }
                },
                ensure_ascii=False,
            ).encode("utf-8")
            raise HTTPError(
                url="http://127.0.0.1:5678/webhook/email/wait-for-ticket",
                code=400,
                msg="Bad Request",
                hdrs={},
                fp=io.BytesIO(error_body),
            )

        with patch("apps.orchestrator.app.integrations.urlopen_with_retry", fake_urlopen):
            result = N8nWebhookAdapter().invoke(invocation, endpoint, operation)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "missing_ticket_number")
        self.assertIn("ticket_number", result["error"]["message"])

    def test_n8n_webhook_empty_async_response_is_accepted_output(self) -> None:
        endpoint = {
            "endpoint_id": "n8n",
            "enabled": True,
            "base_url": "http://127.0.0.1:5678/webhook",
            "base_url_env": "",
            "auth": {"type": "none"},
        }
        operation = {
            "method": "POST",
            "path": "/webhook/email/wait-for-ticket",
            "timeout_seconds": 5,
            "request_schema": {
                "type": "object",
                "additionalProperties": True,
                "properties": {"ticket_number": {"type": "string"}},
            },
        }
        invocation = {
            "invocation_id": "inv-1",
            "action_id": "act-1",
            "tool_name": "n8n_wait_for_email_by_ticket",
            "endpoint_id": "n8n",
            "adapter_type": "n8n_webhook",
            "operation_id": "wait_for_email_by_ticket",
            "operation_parameters": {"ticket_number": "SR-42"},
            "parameters": {"ticket_number": "SR-42"},
            "policy_rule_id": "debug",
            "extensions": {
                "async_callback": {
                    "correlation_id": "case-1:tool_command:inv-1",
                    "wait_id": "wait-1",
                    "result_transport": "http_callback",
                    "result_topic": "external.events",
                    "callback_url": "http://hostmachine:18088/external-events/n8n",
                }
            },
        }

        with patch("apps.orchestrator.app.integrations.urlopen_with_retry", lambda *_args, **_kwargs: b""):
            result = N8nWebhookAdapter().invoke(invocation, endpoint, operation)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["output"]["runbook_status"], "accepted")
        self.assertTrue(result["output"]["async_delivery"])
        self.assertEqual(result["output"]["wait_id"], "wait-1")
        self.assertEqual(result["output"]["correlation_id"], "case-1:tool_command:inv-1")
        self.assertEqual(result["output"]["result_transport"], "http_callback")

    def test_n8n_webhook_nonempty_async_ack_is_accepted_output(self) -> None:
        contracts = self._n8n_ack_contracts()
        registry = ToolRegistry(contracts)
        invocation = self._n8n_ack_invocation(registry)
        invocation.setdefault("extensions", {})["async_callback"] = {
            "correlation_id": "case-1:tool_command:inv-ack",
            "wait_id": "wait-ack",
            "result_transport": "http_callback",
            "result_topic": "external.events",
            "callback_url": "http://hostmachine:18088/external-events/n8n",
        }

        def fake_urlopen(_request, **_kwargs):
            return json.dumps(
                {
                    "accepted": True,
                    "token": "secret-value",
                },
                ensure_ascii=False,
            ).encode("utf-8")

        with patch("apps.orchestrator.app.integrations.urlopen_with_retry", fake_urlopen):
            result = IntegrationDispatcher(contracts, registry).dispatch(invocation)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["output"]["runbook_status"], "accepted")
        self.assertTrue(result["output"]["async_delivery"])
        self.assertEqual(result["output"]["wait_id"], "wait-ack")
        self.assertEqual(result["output"]["correlation_id"], "case-1:tool_command:inv-ack")
        self.assertEqual(result["extensions"]["n8n_ack_body"]["accepted"], True)
        self.assertEqual(result["extensions"]["n8n_ack_body"]["token"], "параметр скрыт")
        self.assertNotIn("error", result)

    def test_n8n_webhook_reports_missing_auth_token_with_endpoint_context(self) -> None:
        contracts = self._n8n_ack_contracts()
        contracts.integration_endpoint_catalog["endpoints"][0]["auth"] = {
            "type": "header_token",
            "header_name": "X-ServiceDesk-Token",
            "token_env": "N8N_WEBHOOK_TOKEN",
        }
        registry = ToolRegistry(contracts)
        invocation = self._n8n_ack_invocation(registry)

        with patch.dict("os.environ", {}, clear=True):
            result = IntegrationDispatcher(contracts, registry).dispatch(invocation)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "auth_token_missing")
        self.assertIn("endpoint n8n", result["error"]["message"])
        self.assertIn("operation wait_for_email_by_ticket", result["error"]["message"])
        self.assertIn("N8N_WEBHOOK_TOKEN", result["error"]["message"])
        self.assertIn("X-ServiceDesk-Token", result["error"]["message"])

    def test_n8n_webhook_adds_configured_auth_header_without_leaking_token(self) -> None:
        contracts = self._n8n_ack_contracts()
        contracts.integration_endpoint_catalog["endpoints"][0]["auth"] = {
            "type": "header_token",
            "header_name": "X-ServiceDesk-Token",
            "token_env": "N8N_WEBHOOK_TOKEN",
        }
        registry = ToolRegistry(contracts)
        invocation = self._n8n_ack_invocation(registry)
        invocation.setdefault("extensions", {})["async_callback"] = {
            "correlation_id": "case-1:tool_command:inv-auth",
            "wait_id": "wait-auth",
            "result_transport": "http_callback",
            "result_topic": "external.events",
            "callback_url": "http://hostmachine:18088/external-events/n8n",
        }
        captured_headers: dict[str, str] = {}

        def fake_urlopen(request, **_kwargs):
            captured_headers.update(dict(request.headers))
            return b""

        with (
            patch.dict("os.environ", {"N8N_WEBHOOK_TOKEN": "secret-token"}, clear=True),
            patch("apps.orchestrator.app.integrations.urlopen_with_retry", fake_urlopen),
        ):
            result = IntegrationDispatcher(contracts, registry).dispatch(invocation)

        self.assertEqual(result["status"], "success")
        self.assertEqual(captured_headers["X-servicedesk-token"], "secret-token")
        self.assertNotIn("secret-token", json.dumps(result, ensure_ascii=False))

    def test_n8n_webhook_sync_ack_body_still_requires_response_schema(self) -> None:
        contracts = self._n8n_ack_contracts()
        registry = ToolRegistry(contracts)
        invocation = self._n8n_ack_invocation(registry)

        with patch(
            "apps.orchestrator.app.integrations.urlopen_with_retry",
            lambda *_args, **_kwargs: b'{"accepted": true}',
        ):
            result = IntegrationDispatcher(contracts, registry).dispatch(invocation)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "endpoint_response_contract_violation")
        self.assertIn("runbook_status", result["error"]["message"])
        self.assertIn("message", result["error"]["message"])

    def test_n8n_webhook_url_does_not_duplicate_webhook_prefix(self) -> None:
        endpoint = {
            "base_url": "http://127.0.0.1:5678/webhook",
            "base_url_env": "",
        }
        operation = {"path": "/webhook/email/wait-for-ticket"}

        self.assertEqual(
            N8nWebhookAdapter._operation_url(endpoint, operation),
            "http://127.0.0.1:5678/webhook/email/wait-for-ticket",
        )

    def test_n8n_endpoint_catalog_declares_transport_security_policy(self) -> None:
        catalog = json.loads(Path("contracts/integrations/integration-endpoint-catalog.json").read_text())
        endpoint = next(item for item in catalog["endpoints"] if item["endpoint_id"] == "n8n")
        transport = endpoint["extensions"]["transport_security"]

        self.assertEqual(transport["http"]["policy"], "admin_configured")
        self.assertEqual(transport["http"]["base_url_env"], "N8N_WEBHOOK_BASE_URL")
        self.assertEqual(transport["http"]["callback_base_url_env"], "ORCHESTRATOR_PUBLIC_URL")
        self.assertEqual(transport["http"]["production_recommended_scheme"], "https")
        self.assertNotIn("selected_transport", transport)
        self.assertNotIn("result_transport", transport)
        self.assertEqual(transport["kafka"]["policy"], "admin_configured")
        self.assertEqual(transport["kafka"]["security_protocol_env"], "KAFKA_SECURITY_PROTOCOL")
        self.assertEqual(transport["kafka"]["supported_security_protocols"], ["SASL_SSL", "SSL"])
        self.assertEqual(transport["kafka"]["supported_auth"], ["sasl", "mtls"])
        self.assertEqual(endpoint["contract_source"]["lang"], "ru")

    def test_imports_openapi_transport_security_without_delivery_choice(self) -> None:
        document = {
            "openapi": "3.1.0",
            "info": {"version": "2026.06"},
            "x-transport-security": {
                "http": {
                    "policy": "admin_configured",
                    "base_url_env": "N8N_WEBHOOK_BASE_URL",
                    "callback_base_url_env": "ORCHESTRATOR_PUBLIC_URL",
                    "production_recommended_scheme": "https",
                    "token_header": "X-ServiceDesk-Callback-Token",
                },
                "kafka": {
                    "policy": "admin_configured",
                    "bootstrap_servers_env": "KAFKA_BOOTSTRAP_SERVERS",
                    "security_protocol_env": "KAFKA_SECURITY_PROTOCOL",
                    "supported_security_protocols": ["SASL_SSL", "SSL"],
                    "supported_auth": ["sasl", "mtls"],
                },
            },
            "paths": {
                "/webhook/ping": {
                    "get": {
                        "operationId": "ping",
                        "responses": {"200": {"content": {"application/json": {"schema": {"type": "object"}}}}},
                    }
                }
            },
        }

        result = import_openapi_operations(document)
        transport = result["transport_security"]

        self.assertEqual(transport["http"]["policy"], "admin_configured")
        self.assertEqual(transport["http"]["production_recommended_scheme"], "https")
        self.assertEqual(transport["kafka"]["supported_security_protocols"], ["SASL_SSL", "SSL"])
        self.assertNotIn("result_transport", transport)
        self.assertNotIn("selected_transport", transport)

    def test_imports_openapi_credential_configured_transport_security(self) -> None:
        document = {
            "openapi": "3.1.0",
            "info": {"version": "2026.06"},
            "x-transport-security": {
                "http": {
                    "policy": "credential_configured",
                    "production_recommended_scheme": "https",
                    "token_header": "X-ServiceDesk-Callback-Token",
                    "token_env": "N8N_CALLBACK_TOKEN",
                },
                "kafka": {
                    "policy": "credential_configured",
                    "bootstrap_servers_env": "KAFKA_BOOTSTRAP_SERVERS",
                    "security_protocol_env": "KAFKA_SECURITY_PROTOCOL",
                    "supported_security_protocols": ["SASL_SSL", "SSL"],
                    "supported_auth": ["sasl", "mtls"],
                },
            },
            "paths": {
                "/webhook/ping": {
                    "get": {
                        "operationId": "ping",
                        "responses": {"200": {"content": {"application/json": {"schema": {"type": "object"}}}}},
                    }
                }
            },
        }

        result = import_openapi_operations(document)
        transport = result["transport_security"]

        self.assertEqual(transport["http"]["policy"], "credential_configured")
        self.assertEqual(transport["http"]["token_env"], "N8N_CALLBACK_TOKEN")
        self.assertEqual(transport["kafka"]["policy"], "credential_configured")
        self.assertNotIn("result_transport", transport)
        self.assertNotIn("selected_transport", transport)

    def test_imports_async_result_contract_from_oneof_accepted_and_result(self) -> None:
        document = {
            "openapi": "3.1.0",
            "info": {"version": "2026.06"},
            "paths": {
                "/webhook/email/wait-for-ticket": {
                    "post": {
                        "operationId": "waitForEmailByTicket",
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "oneOf": [
                                                {"$ref": "#/components/schemas/Accepted"},
                                                {"$ref": "#/components/schemas/EmailResult"},
                                            ]
                                        }
                                    }
                                }
                            }
                        },
                    }
                }
            },
            "components": {
                "schemas": {
                    "Accepted": {
                        "type": "object",
                        "required": ["runbook_status", "async_delivery"],
                        "properties": {
                            "runbook_status": {"const": "accepted"},
                            "async_delivery": {"const": True},
                            "wait_id": {"type": "string"},
                        },
                    },
                    "EmailResult": {
                        "type": "object",
                        "required": ["status", "ticket_number"],
                        "properties": {
                            "status": {"type": "string"},
                            "ticket_number": {"type": "string"},
                            "body": {"type": "string"},
                            "subject": {"type": "string"},
                        },
                    },
                }
            },
        }

        result = import_openapi_operations(document)
        operation = result["operations"]["wait_for_email_by_ticket"]
        async_contract = operation["async_event_contracts"]["wait_for_email_by_ticket_completed"]

        self.assertIn("oneOf", operation["response_schema"])
        self.assertEqual(async_contract["contract_status"], "valid")
        self.assertIn("body", async_contract["result_schema"]["properties"])
        self.assertIn("subject", async_contract["result_schema"]["properties"])

    def test_imports_async_result_contract_from_x_result_delivery(self) -> None:
        document = {
            "openapi": "3.1.0",
            "info": {"version": "2026.06"},
            "paths": {
                "/webhook/provider/channel-repair/monitor": {
                    "post": {
                        "operationId": "monitorProviderChannelRepair",
                        "x-result-delivery": {
                            "default_transport": "kafka_event",
                            "default_result_topic": "external.events",
                            "result_schema": "#/components/schemas/MonitorResult",
                            "supported_transports": ["http_callback", "kafka_event", "both"],
                        },
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "runbook_status": {"const": "accepted"},
                                                "async_delivery": {"const": True},
                                            },
                                        }
                                    }
                                }
                            }
                        },
                    }
                }
            },
            "components": {
                "schemas": {
                    "MonitorResult": {
                        "type": "object",
                        "required": ["status"],
                        "properties": {
                            "status": {"type": "string"},
                            "provider_status": {"type": "string"},
                        },
                    }
                }
            },
        }

        result = import_openapi_operations(document)
        operation = result["operations"]["monitor_provider_channel_repair"]
        async_contract = operation["async_event_contracts"]["monitor_provider_channel_repair_completed"]
        proposals = proposed_react_calls_for_operations(
            {"endpoint_id": "n8n", "adapter_type": "n8n_webhook"},
            result["operations"],
        )
        tool = proposals["tools"]["n8n_monitor_provider_channel_repair"]
        binding = proposals["bindings"]["n8n_monitor_provider_channel_repair"]

        self.assertIn("provider_status", async_contract["result_schema"]["properties"])
        self.assertEqual(operation["extensions"]["result_delivery"]["default_transport"], "kafka_event")
        self.assertEqual(operation["extensions"]["result_delivery"]["default_result_topic"], "external.events")
        self.assertIn("provider_status", tool["result_schema"]["properties"])
        self.assertEqual(tool["result_schema"]["required"], ["status"])
        self.assertEqual(binding["result_mapping"], {
            "status": "status",
            "provider_status": "provider_status",
        })

    def test_openapi_transport_security_rejects_delivery_choice(self) -> None:
        document = {
            "openapi": "3.1.0",
            "info": {"version": "2026.06"},
            "x-transport-security": {
                "selected_transport": "kafka_event",
                "http": {"policy": "admin_configured"},
            },
            "paths": {
                "/webhook/ping": {
                    "get": {
                        "operationId": "ping",
                        "responses": {"200": {"content": {"application/json": {"schema": {"type": "object"}}}}},
                    }
                }
            },
        }

        with self.assertRaises(OpenApiContractError):
            import_openapi_operations(document)

    def test_resolves_relative_n8n_contract_url_under_webhook_base_path(self) -> None:
        endpoint = {
            "endpoint_id": "n8n",
            "adapter_type": "n8n_webhook",
            "base_url": "http://127.0.0.1:5678/webhook",
        }

        self.assertEqual(
            resolve_contract_source_url(endpoint, {"url": "contracts/openapi.json"}),
            "http://127.0.0.1:5678/webhook/contracts/openapi.json?lang=ru",
        )
        self.assertEqual(
            resolve_contract_source_url(endpoint, {"url": "/webhook/contracts/openapi.json"}),
            "http://127.0.0.1:5678/webhook/contracts/openapi.json?lang=ru",
        )
        self.assertEqual(
            resolve_contract_source_url(endpoint, {"url": "contracts/openapi.json?version=1", "lang": "en"}),
            "http://127.0.0.1:5678/webhook/contracts/openapi.json?version=1&lang=en",
        )
        self.assertEqual(
            resolve_contract_source_url(endpoint, {"url": "contracts/openapi.json?lang=en"}),
            "http://127.0.0.1:5678/webhook/contracts/openapi.json?lang=en",
        )
        with self.assertRaises(OpenApiContractError):
            resolve_contract_source_url(endpoint, {"url": "contracts/openapi.json", "lang": "de"})

    def test_absolute_contract_url_must_match_endpoint_host(self) -> None:
        endpoint = {
            "endpoint_id": "n8n",
            "adapter_type": "n8n_webhook",
            "base_url": "http://127.0.0.1:5678/webhook",
        }

        self.assertEqual(
            resolve_contract_source_url(endpoint, {"url": "http://127.0.0.1:5678/webhook/contracts/openapi.json"}),
            "http://127.0.0.1:5678/webhook/contracts/openapi.json?lang=ru",
        )
        with self.assertRaises(OpenApiContractError):
            resolve_contract_source_url(endpoint, {"url": "http://169.254.169.254/latest/meta-data"})

    def test_openapi_localization_diagnostics_detects_stale_english_ru_contract(self) -> None:
        document = {
            "openapi": "3.1.0",
            "info": {
                "title": "n8n Integration Adapter API",
                "description": "Machine-readable contract for n8n webhooks.",
            },
            "paths": {
                "/webhook/contracts/openapi.json": {
                    "get": {
                        "summary": "Get the OpenAPI contract for n8n webhooks",
                        "responses": {"200": {"description": "OpenAPI contract"}},
                    }
                },
                "/webhook/email/send": {
                    "post": {
                        "summary": "Send a text email through n8n",
                        "responses": {"200": {"description": "OK"}},
                    }
                },
            },
        }

        diagnostics, warnings = openapi_contract_localization_diagnostics(document, "ru")

        self.assertFalse(diagnostics["has_x_localization"])
        self.assertEqual(diagnostics["requested_language"], "ru")
        self.assertIn("x-localization", warnings[0])
        self.assertTrue(any("англоязычной" in warning for warning in warnings))

    def test_preview_returns_localization_diagnostics(self) -> None:
        endpoint = {
            "endpoint_id": "n8n",
            "adapter_type": "n8n_webhook",
            "base_url": "http://127.0.0.1:5678/webhook",
        }
        document = {
            "openapi": "3.1.0",
            "info": {
                "title": "n8n Integration Adapter API",
                "version": "2026.06",
                "description": "Machine-readable contract for n8n webhooks.",
            },
            "paths": {
                "/webhook/email/send": {
                    "post": {
                        "operationId": "sendEmail",
                        "summary": "Send a text email through n8n",
                        "responses": {
                            "200": {
                                "description": "OK",
                                "content": {"application/json": {"schema": {"type": "object"}}},
                            }
                        },
                    }
                }
            },
        }
        original_fetch = openapi_contracts.fetch_openapi_contract
        try:
            openapi_contracts.fetch_openapi_contract = lambda _endpoint, _source: (
                document,
                "http://127.0.0.1:5678/webhook/contracts/openapi.json?lang=ru",
            )

            result = openapi_contracts.preview_openapi_contract(
                endpoint,
                {"url": "contracts/openapi.json", "lang": "ru"},
            )
        finally:
            openapi_contracts.fetch_openapi_contract = original_fetch

        localization = result["contract_diagnostics"]["localization"]
        self.assertEqual(localization["requested_language"], "ru")
        self.assertFalse(localization["has_x_localization"])
        self.assertTrue(any("англоязычной" in warning for warning in result["warnings"]))

    def test_preview_rejects_non_get_openapi_contract_method_before_fetch(self) -> None:
        endpoint = {
            "endpoint_id": "n8n",
            "adapter_type": "n8n_webhook",
            "base_url": "http://127.0.0.1:5678/webhook",
        }
        original_fetch = openapi_contracts.urlopen_with_retry
        try:
            openapi_contracts.urlopen_with_retry = lambda *_args, **_kwargs: self.fail("fetch should not be called")
            with self.assertRaisesRegex(OpenApiContractError, "GET"):
                openapi_contracts.preview_openapi_contract(
                    endpoint,
                    {"url": "contracts/openapi.json", "method": "POST", "lang": "ru"},
                )
        finally:
            openapi_contracts.urlopen_with_retry = original_fetch

    def test_operation_language_warning_detects_english_metadata_in_ru_import(self) -> None:
        result = {
            "operations": {
                "send_email": {
                    "display_name": "Send email",
                    "description": "Send an email through n8n.",
                }
            }
        }

        warnings = openapi_operation_language_warnings(result, "ru")

        self.assertTrue(any("metadata операций" in warning for warning in warnings))

    def test_operation_language_warning_accepts_russian_metadata_in_ru_import(self) -> None:
        result = {
            "operations": {
                "send_email": {
                    "display_name": "Отправить email",
                    "description": "Отправляет сообщение через n8n.",
                }
            }
        }

        self.assertEqual(openapi_operation_language_warnings(result, "ru"), [])

    def test_imports_openapi_operation_contracts(self) -> None:
        document = {
            "openapi": "3.1.0",
            "info": {"title": "n8n contracts", "version": "2026.06"},
            "components": {
                "schemas": {
                    "FindUserRequest": {
                        "type": "object",
                        "required": ["full_name"],
                        "properties": {
                            "full_name": {"type": "string", "description": "ФИО пользователя"}
                        },
                        "additionalProperties": False,
                    },
                    "FindUserResponse": {
                        "type": "object",
                        "required": ["user_login"],
                        "properties": {
                            "user_login": {"type": "string"},
                            "manager_email": {"type": "string"},
                        },
                        "additionalProperties": True,
                    },
                }
            },
            "paths": {
                "/webhook/find-user": {
                    "post": {
                        "operationId": "findAdUser",
                        "summary": "Найти пользователя в AD",
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/FindUserRequest"}
                                }
                            },
                        },
                        "responses": {
                            "200": {
                                "description": "OK",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/FindUserResponse"}
                                    }
                                },
                            }
                        },
                    }
                }
            },
        }

        result = import_openapi_operations(document)
        operation = result["operations"]["find_ad_user"]

        self.assertEqual(operation["display_name"], "Найти пользователя в AD")
        self.assertEqual(operation["method"], "POST")
        self.assertEqual(operation["path"], "/webhook/find-user")
        self.assertEqual(operation["contract_version"], "2026.06")
        self.assertEqual(operation["request_schema"]["required"], ["full_name"])
        self.assertIn("manager_email", operation["response_schema"]["properties"])
        self.assertEqual(operation["extensions"]["openapi_operation_id"], "findAdUser")

    def test_builds_prefixed_react_call_proposals_for_openapi_operations(self) -> None:
        operations = {
            "send_email": {
                "display_name": "Отправить email",
                "description": "Отправляет email через n8n.",
                "method": "POST",
                "path": "/webhook/email/send",
                "request_schema": {
                    "type": "object",
                    "required": ["to", "subject"],
                    "properties": {
                        "to": {"type": "string"},
                        "subject": {"type": "string"},
                        "body": {"type": "string"},
                    },
                },
                "response_schema": {
                    "type": "object",
                    "required": ["status"],
                    "properties": {
                        "status": {"type": "string"},
                        "message_id": {"type": "string"},
                    },
                },
                "contract_version": "2026.06",
                "contract_status": "valid",
                "timeout_seconds": 30,
            }
        }

        proposals = proposed_react_calls_for_operations(
            {"endpoint_id": "n8n", "adapter_type": "n8n_webhook"},
            operations,
        )
        tool = proposals["tools"]["n8n_send_email"]
        binding = proposals["bindings"]["n8n_send_email"]

        self.assertEqual(tool["tool_name"], "n8n_send_email")
        self.assertEqual(tool["action_type"], "action")
        self.assertEqual(tool["parameters_schema"]["required"], ["to", "subject"])
        self.assertEqual(tool["result_schema"]["required"], ["status"])
        self.assertEqual(binding["endpoint_id"], "n8n")
        self.assertEqual(binding["operation_id"], "send_email")
        self.assertEqual(binding["parameter_mapping"], {
            "to": "react:to",
            "subject": "react:subject",
            "body": "react:body",
        })
        self.assertEqual(binding["result_mapping"], {
            "status": "status",
            "message_id": "message_id",
        })

    def test_openapi_import_preserves_request_parameter_defaults_in_react_proposal(self) -> None:
        document = {
            "openapi": "3.1.0",
            "info": {"version": "2026.06"},
            "paths": {
                "/webhook/email/wait": {
                    "post": {
                        "operationId": "waitForEmailByTicket",
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "required": ["ticket_number", "poll_interval_minutes"],
                                        "properties": {
                                            "ticket_number": {"type": "string"},
                                            "poll_interval_minutes": {"type": "integer", "default": 1},
                                        },
                                    }
                                }
                            },
                        },
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {"type": "object", "additionalProperties": True}
                                    }
                                }
                            }
                        },
                    }
                }
            },
        }

        result = import_openapi_operations(document)
        operation = result["operations"]["wait_for_email_by_ticket"]
        proposals = proposed_react_calls_for_operations(
            {"endpoint_id": "n8n", "adapter_type": "n8n_webhook"},
            result["operations"],
        )
        proposal = proposals["tools"]["n8n_wait_for_email_by_ticket"]

        self.assertEqual(operation["request_schema"]["properties"]["poll_interval_minutes"]["default"], 1)
        self.assertEqual(proposal["parameters_schema"]["properties"]["poll_interval_minutes"]["default"], 1)

    def test_imports_duplicate_operation_ids_with_suffix(self) -> None:
        document = {
            "openapi": "3.1.0",
            "info": {"version": "1.0"},
            "paths": {
                "/a": {
                    "post": {
                        "operationId": "same",
                        "responses": {"200": {"content": {"application/json": {"schema": {"type": "object"}}}}},
                    }
                },
                "/b": {
                    "post": {
                        "operationId": "same",
                        "responses": {"200": {"content": {"application/json": {"schema": {"type": "object"}}}}},
                    }
                },
            },
        }

        result = import_openapi_operations(document)

        self.assertEqual(set(result["operations"]), {"same", "same_2"})
        self.assertTrue(any("Дублируется operationId" in warning for warning in result["warnings"]))

    def test_missing_response_schema_becomes_draft_with_warning(self) -> None:
        document = {
            "openapi": "3.1.0",
            "info": {"version": "1.0"},
            "paths": {
                "/ping": {
                    "get": {
                        "operationId": "ping",
                        "responses": {"204": {"description": "No content"}},
                    }
                }
            },
        }

        result = import_openapi_operations(document)
        operation = result["operations"]["ping"]

        self.assertEqual(operation["contract_status"], "draft")
        self.assertEqual(operation["response_schema"], {"type": "object", "additionalProperties": True})

    def test_invalid_openapi_document_is_rejected(self) -> None:
        with self.assertRaises(OpenApiContractError):
            import_openapi_operations({"info": {"version": "1.0"}, "paths": {}})


if __name__ == "__main__":
    unittest.main()
