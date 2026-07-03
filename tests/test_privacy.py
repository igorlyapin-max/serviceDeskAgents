from __future__ import annotations

import unittest

from apps.orchestrator.app.privacy import redact_for_llm


class PrivacyRedactionTest(unittest.TestCase):
    def test_redacts_only_tokens_passwords_and_secret_assignments(self) -> None:
        result = redact_for_llm(
            "email user@example.com phone +7 999 123-45-67 password: qwerty token=sk_secret_1234567890abcd"
        )
        self.assertTrue(result.redacted)
        self.assertIn("user@example.com", result.text)
        self.assertIn("+7 999 123-45-67", result.text)
        self.assertIn("[REDACTED_SECRET]", result.text)
        self.assertNotIn("qwerty", result.text)

    def test_preserves_plain_ticket_text(self) -> None:
        result = redact_for_llm("Сбросьте пароль Иванову Ивану Ивановичу")
        self.assertFalse(result.redacted)
        self.assertEqual(result.text, "Сбросьте пароль Иванову Ивану Ивановичу")

    def test_preserves_service_ticket_identifiers(self) -> None:
        text = "Ваша заявка зарегистрирована за номером МТС000000000000001, SR1234567890."
        result = redact_for_llm(text)

        self.assertFalse(result.redacted)
        self.assertEqual(result.text, text)

    def test_redacts_bearer_and_api_key_tokens(self) -> None:
        result = redact_for_llm("Bearer abcdefghijklmnopqrstuvwxyz012345 token_sk_secret_1234567890")

        self.assertTrue(result.redacted)
        self.assertIn("Bearer [REDACTED_TOKEN]", result.text)
        self.assertIn("[REDACTED_API_KEY]", result.text)


if __name__ == "__main__":
    unittest.main()
