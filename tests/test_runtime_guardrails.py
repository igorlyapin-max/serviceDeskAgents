from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from apps.orchestrator.app.runtime_guardrails import (
    RuntimeConfigurationError,
    security_headers,
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

    def test_security_headers_include_static_ui_policy(self) -> None:
        headers = security_headers(https_enabled=True)
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertIn("Strict-Transport-Security", headers)
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])


if __name__ == "__main__":
    unittest.main()
