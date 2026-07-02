from __future__ import annotations

import unittest

from apps.orchestrator.app.config_registry import build_agent_outcome_from_simulation, next_slot_question


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

    def test_pending_live_resolution_waits_for_external_event_not_client_question(self) -> None:
        outcome = build_agent_outcome_from_simulation(
            {
                "slot_values": {},
                "missing_slots": ["provider_mail_body"],
                "execution_trace": [],
                "attribute_resolution": [
                    {
                        "profile_id": "profile.provider.mail",
                        "status": "pending_live_execution",
                        "decision": "execute_react_call",
                    }
                ],
            }
        )

        self.assertEqual(outcome["status"], "waiting_external_event")
        self.assertEqual(outcome["label"], "Ожидает n8n")

    def test_resolution_profile_escalation_does_not_create_client_question(self) -> None:
        question = next_slot_question(
            {
                "slot_id": "provider_mail_body",
                "fill_method": "resolution_profile",
                "resolution_profile_id": "profile.provider.mail",
                "fallback_question": "Уточните тело письма.",
            },
            {
                "profile.provider.mail": {
                    "profile_id": "profile.provider.mail",
                    "human_resolution_policy": {
                        "action": "escalate_operator",
                        "message_template": "Передайте оператору.",
                    },
                }
            },
        )

        self.assertIsNone(question)


if __name__ == "__main__":
    unittest.main()
