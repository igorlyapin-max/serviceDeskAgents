from __future__ import annotations

import unittest

from apps.orchestrator.app.privacy import redact_for_llm


class PrivacyRedactionTest(unittest.TestCase):
    def test_redacts_email_phone_and_secrets(self) -> None:
        result = redact_for_llm(
            "email user@example.com phone +7 999 123-45-67 password: qwerty token=sk_secret_1234567890abcd"
        )
        self.assertTrue(result.redacted)
        self.assertIn("[REDACTED_EMAIL]", result.text)
        self.assertIn("[REDACTED_PHONE]", result.text)
        self.assertIn("[REDACTED_SECRET]", result.text)
        self.assertNotIn("user@example.com", result.text)
        self.assertNotIn("qwerty", result.text)

    def test_preserves_plain_ticket_text(self) -> None:
        result = redact_for_llm("Сбросьте пароль Иванову Ивану Ивановичу")
        self.assertFalse(result.redacted)
        self.assertEqual(result.text, "Сбросьте пароль Иванову Ивану Ивановичу")


if __name__ == "__main__":
    unittest.main()
