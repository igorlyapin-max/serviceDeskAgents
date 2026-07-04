from __future__ import annotations

import os
import unittest
from unittest.mock import patch
from unittest.mock import Mock

from apps.orchestrator.app import runtime_guardrails
from apps.orchestrator.app.runtime_guardrails import (
    RuntimeConfigurationError,
    local_security_warnings,
    log_debug_event,
    metrics_client_allowed,
    readiness_http_status,
    security_headers,
    sanitize_log_value,
    validate_startup_environment,
)


class RuntimeGuardrailsTest(unittest.TestCase):
    def test_production_rejects_dev_auth_and_default_secrets(self) -> None:
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                "SECURITY_AUTH_MODE": "dev_header",
                "POSTGRES_PASSWORD": "servicedesk_dev_password",
                "LITELLM_MASTER_KEY": "sk-dev-litellm-master-key",
                "INTEGRATION_CALLBACK_TOKEN": "dev-callback-token",
                "MCP_PROVIDER_OPS_TOKEN": "change_me_mcp_provider_ops_token",
            },
            clear=False,
        ):
            with self.assertRaises(RuntimeConfigurationError):
                validate_startup_environment()

    def test_local_allows_dev_auth(self) -> None:
        with patch.dict(os.environ, {"APP_ENV": "local", "SECURITY_AUTH_MODE": "dev_header"}, clear=False):
            validate_startup_environment()

    def test_staging_rejects_dev_auth_and_stdout_only_logging(self) -> None:
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "staging",
                "SECURITY_AUTH_MODE": "dev_header",
                "SECURITY_CALLBACK_AUTH_MODE": "oidc_jwks",
                "CALLBACK_OIDC_ISSUER": "https://idp.example",
                "CALLBACK_OIDC_AUDIENCE": "servicedesk-callbacks",
                "CALLBACK_OIDC_ALLOWED_CLIENT_IDS": "mcp-provider-ops",
                "CALLBACK_OIDC_JWKS_URL": "https://idp.example/.well-known/jwks.json",
                "LOG_SINKS": "stdout",
            },
            clear=True,
        ):
            with self.assertRaises(RuntimeConfigurationError) as context:
                validate_startup_environment()

        self.assertIn("второй log sink", str(context.exception))
        self.assertIn("SECURITY_AUTH_MODE", str(context.exception))

    def test_staging_rejects_plaintext_kafka_external_events(self) -> None:
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "staging",
                "SECURITY_AUTH_MODE": "oidc",
                "SECURITY_CALLBACK_AUTH_MODE": "oidc_jwks",
                "CALLBACK_OIDC_ISSUER": "https://idp.example",
                "CALLBACK_OIDC_AUDIENCE": "servicedesk-callbacks",
                "CALLBACK_OIDC_ALLOWED_CLIENT_IDS": "mcp-provider-ops",
                "CALLBACK_OIDC_JWKS_URL": "https://idp.example/.well-known/jwks.json",
                "LOG_SINKS": "stdout,jsonl",
                "POSTGRES_PASSWORD": "strong-postgres-password",
                "LITELLM_MASTER_KEY": "strong-litellm-master-key",
                "MCP_PROVIDER_OPS_TOKEN": "strong-mcp-provider-token",
                "KAFKA_SECURITY_PROTOCOL": "PLAINTEXT",
            },
            clear=True,
        ):
            with self.assertRaises(RuntimeConfigurationError) as context:
                validate_startup_environment()

        self.assertIn("Kafka external.events", str(context.exception))

    def test_staging_rejects_source_token_callback_auth(self) -> None:
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "staging",
                "SECURITY_AUTH_MODE": "oidc",
                "SECURITY_CALLBACK_AUTH_MODE": "source_token",
                "LOG_SINKS": "stdout,jsonl",
                "POSTGRES_PASSWORD": "strong-postgres-password",
                "LITELLM_MASTER_KEY": "strong-litellm-master-key",
                "MCP_PROVIDER_OPS_TOKEN": "strong-mcp-provider-token",
                "INTEGRATION_CALLBACK_TOKEN__PROVIDER_OPS": "strong-callback-token",
                "KAFKA_SECURITY_PROTOCOL": "SASL_SSL",
            },
            clear=True,
        ):
            with self.assertRaises(RuntimeConfigurationError) as context:
                validate_startup_environment()

        self.assertIn("SECURITY_CALLBACK_AUTH_MODE=oidc_jwks/oidc_proxy_jwt", str(context.exception))

    def test_staging_rejects_oidc_jwks_without_jwks_url(self) -> None:
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "staging",
                "SECURITY_AUTH_MODE": "oidc",
                "SECURITY_CALLBACK_AUTH_MODE": "oidc_jwks",
                "CALLBACK_OIDC_ISSUER": "https://idp.example",
                "CALLBACK_OIDC_AUDIENCE": "servicedesk-callbacks",
                "CALLBACK_OIDC_ALLOWED_CLIENT_IDS": "mcp-provider-ops",
                "LOG_SINKS": "stdout,jsonl",
                "POSTGRES_PASSWORD": "strong-postgres-password",
                "LITELLM_MASTER_KEY": "strong-litellm-master-key",
                "MCP_PROVIDER_OPS_TOKEN": "strong-mcp-provider-token",
                "KAFKA_SECURITY_PROTOCOL": "SASL_SSL",
            },
            clear=True,
        ):
            with self.assertRaises(RuntimeConfigurationError) as context:
                validate_startup_environment()

        self.assertIn("CALLBACK_OIDC_JWKS_URL", str(context.exception))

    def test_staging_rejects_oidc_proxy_without_trust_proof(self) -> None:
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "staging",
                "SECURITY_AUTH_MODE": "oidc",
                "SECURITY_CALLBACK_AUTH_MODE": "oidc_proxy_jwt",
                "CALLBACK_OIDC_ISSUER": "https://idp.example",
                "CALLBACK_OIDC_AUDIENCE": "servicedesk-callbacks",
                "CALLBACK_OIDC_ALLOWED_CLIENT_IDS": "mcp-provider-ops",
                "LOG_SINKS": "stdout,jsonl",
                "POSTGRES_PASSWORD": "strong-postgres-password",
                "LITELLM_MASTER_KEY": "strong-litellm-master-key",
                "MCP_PROVIDER_OPS_TOKEN": "strong-mcp-provider-token",
                "KAFKA_SECURITY_PROTOCOL": "SASL_SSL",
            },
            clear=True,
        ):
            with self.assertRaises(RuntimeConfigurationError) as context:
                validate_startup_environment()

        self.assertIn("oidc_proxy_jwt требует", str(context.exception))

    def test_unknown_environment_is_rejected(self) -> None:
        with patch.dict(os.environ, {"APP_ENV": "sandbox"}, clear=True):
            with self.assertRaises(RuntimeConfigurationError) as context:
                validate_startup_environment()

        self.assertIn("APP_ENV=sandbox", str(context.exception))

    def test_local_reports_dev_auth_warning(self) -> None:
        with patch.dict(os.environ, {"APP_ENV": "local", "SECURITY_AUTH_MODE": "dev_header"}, clear=True):
            warnings = local_security_warnings()

        self.assertTrue(any("SECURITY_AUTH_MODE=dev_header" in item for item in warnings))

    def test_metrics_allowlist_accepts_loopback_and_cidr(self) -> None:
        self.assertTrue(metrics_client_allowed("127.0.0.1"))
        self.assertTrue(metrics_client_allowed("10.10.5.7", ["10.10.0.0/16"]))

    def test_metrics_allowlist_rejects_unknown_ip(self) -> None:
        self.assertFalse(metrics_client_allowed("192.0.2.10", ["127.0.0.1", "::1"]))
        self.assertFalse(metrics_client_allowed(None, ["127.0.0.1"]))

    def test_security_headers_include_static_ui_policy(self) -> None:
        headers = security_headers(https_enabled=True)
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertIn("Strict-Transport-Security", headers)
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])

    def test_readiness_http_status_supports_error_and_strict_degraded(self) -> None:
        self.assertEqual(readiness_http_status({"status": "ok"}), 200)
        self.assertEqual(readiness_http_status({"status": "error"}), 503)
        with patch.dict(os.environ, {"READYZ_STRICT": "true"}, clear=True):
            self.assertEqual(readiness_http_status({"status": "degraded"}), 503)
        with patch.dict(os.environ, {"READYZ_STRICT": "false"}, clear=True):
            self.assertEqual(readiness_http_status({"status": "degraded"}), 200)

    def test_log_sanitizer_masks_english_and_russian_secret_keys(self) -> None:
        sanitized = sanitize_log_value(
            "details",
            {
                "api_token": "secret-token",
                "пароль": "secret-password",
                "safe": "visible",
            },
        )

        self.assertEqual(sanitized["api_token"], "параметр скрыт")
        self.assertEqual(sanitized["пароль"], "параметр скрыт")
        self.assertEqual(sanitized["safe"], "visible")

    def test_log_sanitizer_masks_personal_values_inside_safe_keys(self) -> None:
        sanitized = sanitize_log_value(
            "ticket_input",
            {
                "description": "Связаться с ivan.petrov@example.org или +7 999 123-45-67.",
                "summary": "service host c2m-router-01",
            },
        )

        self.assertNotIn("ivan.petrov@example.org", sanitized["description"])
        self.assertNotIn("+7 999 123-45-67", sanitized["description"])
        self.assertIn("персональные данные скрыты", sanitized["description"])
        self.assertEqual(sanitized["summary"], "service host c2m-router-01")

    def test_debug_logging_event_respects_basic_and_verbose_levels(self) -> None:
        logger = Mock()
        with patch.dict(os.environ, {"DEBUG_LOGGING_ENABLED": "false"}, clear=True):
            self.assertFalse(log_debug_event(logger, "startup", safe="visible"))
            logger.log.assert_not_called()

        with patch.dict(os.environ, {"DEBUG_LOGGING_ENABLED": "true", "DEBUG_LOGGING_LEVEL": "Basic"}, clear=True):
            self.assertTrue(log_debug_event(logger, "startup", safe="visible", verbose_fields={"api_token": "secret"}))
            basic_message = logger.log.call_args.args[1]
            self.assertIn("diagnostic_startup", basic_message)
            self.assertIn("visible", basic_message)
            self.assertNotIn("secret", basic_message)

        logger.reset_mock()
        with patch.dict(os.environ, {"DEBUG_LOGGING_ENABLED": "true", "DEBUG_LOGGING_LEVEL": "Verbose"}, clear=True):
            self.assertTrue(log_debug_event(logger, "startup", safe="visible", verbose_fields={"api_token": "secret"}))
            verbose_message = logger.log.call_args.args[1]
            self.assertIn("diagnostic_startup", verbose_message)
            self.assertIn("параметр скрыт", verbose_message)
            self.assertNotIn("secret", verbose_message)

    def test_readiness_reports_async_runtime_error(self) -> None:
        config_store = Mock()
        config_store.active_payload.return_value = {"scenarios": []}
        workflow = Mock()
        workflow.model_config.return_value = {"status": "ok"}
        workflow.knowledge_status.return_value = {"status": "ok"}
        processing_store = Mock()
        processing_store.overview.return_value = {
            "schema_version": "1.0",
            "runtime": {
                "schema_version": "1.0",
                "status": "error",
                "issues": ["Outbox publisher не запускался или не записал heartbeat."],
                "required_components": [],
            },
        }

        with (
            patch.object(runtime_guardrails, "_state_db_check", return_value={"name": "state_db", "status": "ok"}),
            patch.object(runtime_guardrails, "_kafka_bootstrap_check", return_value={"name": "kafka_bootstrap", "status": "ok"}),
            patch.object(runtime_guardrails, "_model_gateway_check", return_value={"name": "model_gateway", "status": "ok"}),
            patch.object(runtime_guardrails, "_integration_auth_check", return_value={"name": "integration_auth", "status": "ok"}),
        ):
            report = runtime_guardrails.readiness_report(
                config_store=config_store,
                workflow=workflow,
                processing_store=processing_store,
            )

        self.assertEqual(report["status"], "error")
        async_check = next(check for check in report["checks"] if check["name"] == "async_runtime")
        self.assertEqual(async_check["status"], "error")
        self.assertIn("Outbox publisher", async_check["message"])

    def test_async_runtime_check_reports_recovery_attention_as_degraded(self) -> None:
        check = runtime_guardrails._async_runtime_check(
            {
                "schema_version": "1.0",
                "runtime": {
                    "schema_version": "1.0",
                    "status": "ok",
                    "issues": [],
                    "required_components": [],
                },
                "recovery": {
                    "schema_version": "1.0",
                    "status": "needs_attention",
                    "issues": ["Найдено зависших ExternalEvent idempotency receipts: 1"],
                },
            }
        )

        self.assertEqual(check["status"], "degraded")
        self.assertIn("ExternalEvent", check["message"])
        self.assertEqual(check["recovery"]["status"], "needs_attention")

    def test_model_gateway_check_uses_litellm_models_endpoint(self) -> None:
        class Response:
            status = 200

            def __enter__(self) -> "Response":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

        model_config = {
            "gateway": {"type": "litellm", "base_url": "http://litellm:4000/v1"},
            "routing": {"slot_resolution": "openai-primary"},
            "providers": {
                "openai": {
                    "model_alias": "openai-primary",
                    "base_url": "https://api.openai.com/v1",
                }
            },
        }

        with (
            patch.dict(os.environ, {"LITELLM_MASTER_KEY": "test-key"}, clear=True),
            patch.object(runtime_guardrails.urllib.request, "urlopen", return_value=Response()) as urlopen_mock,
        ):
            check = runtime_guardrails._model_gateway_check(model_config)

        self.assertEqual(check["status"], "ok")
        request = urlopen_mock.call_args.args[0]
        self.assertEqual(request.full_url, "http://litellm:4000/v1/models")
        self.assertEqual(request.headers["Authorization"], "Bearer test-key")

    def test_integration_auth_check_reports_missing_token_env(self) -> None:
        config_store = Mock()
        config_store.active_payload.return_value = {
            "environments": [
                {
                    "environment_id": "provider_ops",
                    "status": "active",
                    "auth_mode": "bearer_token",
                    "auth_ref": "env:MCP_PROVIDER_OPS_TOKEN",
                }
            ]
        }

        with patch.dict(os.environ, {}, clear=True):
            check = runtime_guardrails._integration_auth_check(config_store)

        self.assertEqual(check["status"], "error")
        self.assertIn("provider_ops", check["message"])
        self.assertIn("MCP_PROVIDER_OPS_TOKEN", check["message"])

    def test_integration_auth_check_accepts_configured_token_env(self) -> None:
        config_store = Mock()
        config_store.active_payload.return_value = {
            "environments": [
                {
                    "environment_id": "provider_ops",
                    "status": "active",
                    "auth_mode": "bearer_token",
                    "auth_ref": "env:MCP_PROVIDER_OPS_TOKEN",
                }
            ]
        }

        with patch.dict(os.environ, {"MCP_PROVIDER_OPS_TOKEN": "secret"}, clear=True):
            check = runtime_guardrails._integration_auth_check(config_store)

        self.assertEqual(check["status"], "ok")
        self.assertNotIn("secret", check["message"])

    def test_mcp_health_check_uses_origin_http_get(self) -> None:
        class Response:
            status = 200

            def __enter__(self) -> "Response":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

        config_store = Mock()
        config_store.active_payload.return_value = {
            "environments": [
                {
                    "environment_id": "provider_ops",
                    "status": "active",
                    "base_url": "http://127.0.0.1:9000/mcp",
                    "health_check": {"mode": "http_get", "path": "/health", "timeout_seconds": 2},
                }
            ]
        }

        with patch.object(runtime_guardrails.urllib.request, "urlopen", return_value=Response()) as urlopen_mock:
            check = runtime_guardrails._mcp_health_check(config_store)

        self.assertEqual(check["status"], "ok")
        request = urlopen_mock.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:9000/health")

    def test_mcp_health_check_degrades_on_unreachable_environment(self) -> None:
        config_store = Mock()
        config_store.active_payload.return_value = {
            "environments": [
                {
                    "environment_id": "provider_ops",
                    "status": "active",
                    "base_url": "http://127.0.0.1:9000/mcp",
                    "health_check": {"mode": "http_get", "path": "/health", "timeout_seconds": 2},
                }
            ]
        }

        with patch.object(runtime_guardrails.urllib.request, "urlopen", side_effect=OSError("connection refused")):
            check = runtime_guardrails._mcp_health_check(config_store)

        self.assertEqual(check["status"], "degraded")
        self.assertIn("provider_ops", check["message"])


if __name__ == "__main__":
    unittest.main()
