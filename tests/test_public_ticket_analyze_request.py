from __future__ import annotations

import json
import unittest

from pydantic import ValidationError

from apps.orchestrator.app.main import TicketAnalyzeRequest, ticket_debug_shape


class TicketAnalyzeRequestTest(unittest.TestCase):
    def test_rejects_operator_debug_bypass_fields(self) -> None:
        with self.assertRaises(ValidationError) as context:
            TicketAnalyzeRequest(
                user="ivanov",
                service="billing-worker",
                description="Нужно восстановить сервис.",
                priority="p3",
                scenario="runbook",
                debug_run_mode="operator_full_debug",
                debug_bypass_policy_gates=True,
            )

        fields = {error["loc"][0] for error in context.exception.errors()}
        self.assertIn("debug_run_mode", fields)
        self.assertIn("debug_bypass_policy_gates", fields)

    def test_rejects_unknown_fields(self) -> None:
        with self.assertRaises(ValidationError) as context:
            TicketAnalyzeRequest(
                user="ivanov",
                service="billing-worker",
                description="Нужно восстановить сервис.",
                priority="p3",
                scenario="runbook",
                unknown_debug_override=True,
            )

        fields = {error["loc"][0] for error in context.exception.errors()}
        self.assertIn("unknown_debug_override", fields)

    def test_ticket_debug_shape_does_not_include_raw_ticket_text(self) -> None:
        shape = ticket_debug_shape(
            {
                "ticket_id": "T-1",
                "description": "Не работает сервис, password=secret-value",
                "original_problem": "http://example.invalid/problem",
                "channel_parameters": {"service_desk_request_id": "SR-1"},
            }
        )
        serialized = json.dumps(shape, ensure_ascii=False)

        self.assertTrue(shape["has_description"])
        self.assertGreater(shape["description_length"], 0)
        self.assertNotIn("secret-value", serialized)
        self.assertNotIn("Не работает сервис", serialized)


if __name__ == "__main__":
    unittest.main()
