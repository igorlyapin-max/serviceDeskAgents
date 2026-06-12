from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from apps.orchestrator.app.contracts import ContractRegistry
from apps.orchestrator.app.security import CallbackTokenInvalid, SecurityManager


class SecurityCallbackTokenTest(unittest.TestCase):
    def test_local_callback_uses_global_token_fallback(self) -> None:
        manager = SecurityManager(ContractRegistry())
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "local",
                "INTEGRATION_CALLBACK_TOKEN": "global-token",
            },
            clear=True,
        ):
            context = manager.callback_context(
                {"x-servicedesk-callback-token": "global-token"},
                endpoint_id="n8n",
            )

        self.assertEqual(context.actor_id, "endpoint:n8n")

    def test_shared_callback_requires_source_specific_token(self) -> None:
        manager = SecurityManager(ContractRegistry())
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "shared",
                "INTEGRATION_CALLBACK_TOKEN": "global-token",
            },
            clear=True,
        ):
            with self.assertRaises(CallbackTokenInvalid):
                manager.callback_context(
                    {"x-servicedesk-callback-token": "global-token"},
                    endpoint_id="n8n",
                )

    def test_source_specific_callback_token_is_accepted(self) -> None:
        manager = SecurityManager(ContractRegistry())
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "shared",
                "INTEGRATION_CALLBACK_TOKEN__N8N": "source-token",
            },
            clear=True,
        ):
            context = manager.callback_context(
                {"x-servicedesk-callback-token": "source-token"},
                endpoint_id="n8n",
            )

        self.assertEqual(context.actor_id, "endpoint:n8n")


if __name__ == "__main__":
    unittest.main()
