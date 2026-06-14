from __future__ import annotations

import json
import unittest
from pathlib import Path

from apps.orchestrator.app import openapi_contracts
from apps.orchestrator.app.openapi_contracts import (
    OpenApiContractError,
    import_openapi_operations,
    openapi_contract_localization_diagnostics,
    openapi_operation_language_warnings,
    proposed_react_calls_for_operations,
    resolve_contract_source_url,
)


class OpenApiContractsTest(unittest.TestCase):
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
