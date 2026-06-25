from __future__ import annotations

import unittest

from pydantic import ValidationError

from apps.orchestrator.app.main import TicketAnalyzeRequest


class PublicTicketAnalyzeRequestTest(unittest.TestCase):
    def test_rejects_debug_bypass_fields(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
