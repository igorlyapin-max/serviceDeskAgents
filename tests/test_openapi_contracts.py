from __future__ import annotations

import unittest

from apps.orchestrator.app.openapi_contracts import (
    OpenApiContractError,
    import_openapi_operations,
    resolve_contract_source_url,
)


class OpenApiContractsTest(unittest.TestCase):
    def test_resolves_relative_n8n_contract_url_under_webhook_base_path(self) -> None:
        endpoint = {
            "endpoint_id": "n8n",
            "adapter_type": "n8n_webhook",
            "base_url": "http://127.0.0.1:5678/webhook",
        }

        self.assertEqual(
            resolve_contract_source_url(endpoint, {"url": "contracts/openapi.json"}),
            "http://127.0.0.1:5678/webhook/contracts/openapi.json",
        )
        self.assertEqual(
            resolve_contract_source_url(endpoint, {"url": "/webhook/contracts/openapi.json"}),
            "http://127.0.0.1:5678/webhook/contracts/openapi.json",
        )

    def test_absolute_contract_url_must_match_endpoint_host(self) -> None:
        endpoint = {
            "endpoint_id": "n8n",
            "adapter_type": "n8n_webhook",
            "base_url": "http://127.0.0.1:5678/webhook",
        }

        self.assertEqual(
            resolve_contract_source_url(endpoint, {"url": "http://127.0.0.1:5678/webhook/contracts/openapi.json"}),
            "http://127.0.0.1:5678/webhook/contracts/openapi.json",
        )
        with self.assertRaises(OpenApiContractError):
            resolve_contract_source_url(endpoint, {"url": "http://169.254.169.254/latest/meta-data"})

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
        operation = result["operations"]["findaduser"]

        self.assertEqual(operation["display_name"], "Найти пользователя в AD")
        self.assertEqual(operation["method"], "POST")
        self.assertEqual(operation["path"], "/webhook/find-user")
        self.assertEqual(operation["contract_version"], "2026.06")
        self.assertEqual(operation["request_schema"]["required"], ["full_name"])
        self.assertIn("manager_email", operation["response_schema"]["properties"])

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
