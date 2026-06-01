from __future__ import annotations

import unittest

from apps.orchestrator.app.config_registry import build_agent_outcome_from_simulation


class AgentOutcomeTest(unittest.TestCase):
    def test_missing_required_slot_means_question_to_customer(self) -> None:
        outcome = build_agent_outcome_from_simulation(
            {
                "slot_values": {},
                "missing_slots": ["user_login"],
                "execution_trace": [],
            }
        )

        self.assertEqual(outcome["status"], "waiting")
        self.assertEqual(outcome["label"], "Вопрос клиенту")

    def test_low_confidence_means_escalation_not_review(self) -> None:
        outcome = build_agent_outcome_from_simulation(
            {
                "slot_values": {
                    "user_login": {
                        "value": "ivanov",
                        "status": "candidate_below_threshold",
                    }
                },
                "missing_slots": [],
                "execution_trace": [],
            }
        )

        self.assertEqual(outcome["status"], "escalated")
        self.assertEqual(outcome["label"], "Требуется эскалация")

    def test_complete_path_means_automatic_completion(self) -> None:
        outcome = build_agent_outcome_from_simulation(
            {
                "slot_values": {
                    "user_login": {
                        "value": "ivanov",
                        "status": "filled",
                    }
                },
                "missing_slots": [],
                "execution_trace": [],
            }
        )

        self.assertEqual(outcome["status"], "success")
        self.assertEqual(outcome["label"], "Завершено автоматически")


if __name__ == "__main__":
    unittest.main()
