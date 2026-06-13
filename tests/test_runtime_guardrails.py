from __future__ import annotations

import os
import unittest
from unittest.mock import patch
from unittest.mock import Mock

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
                "N8N_DB_PASSWORD": "n8n_dev_password",
                "N8N_ENCRYPTION_KEY": "replace_with_32_plus_chars_dev_key",
                "N8N_WEBHOOK_TOKEN": "replace_with_dev_webhook_token",
                "LITELLM_MASTER_KEY": "sk-dev-litellm-master-key",
                "INTEGRATION_CALLBACK_TOKEN": "dev-callback-token",
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
                "LOG_SINKS": "stdout",
            },
            clear=True,
        ):
            with self.assertRaises(RuntimeConfigurationError) as context:
                validate_startup_environment()

        self.assertIn("второй log sink", str(context.exception))
        self.assertIn("SECURITY_AUTH_MODE", str(context.exception))

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


if __name__ == "__main__":
    unittest.main()
