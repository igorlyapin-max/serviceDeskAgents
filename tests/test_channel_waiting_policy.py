from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from apps.orchestrator.app.config_registry import (
    ConfigStore,
    client_waiting_defaults_from_legacy_escalation,
    default_interaction_channels,
    default_slot_schemas,
    normalize_channel_waiting_policy,
)
from apps.orchestrator.app.contracts import ContractRegistry


class ChannelWaitingPolicyTest(unittest.TestCase):
    def test_legacy_escalation_waiting_values_fill_missing_channel_fields(self) -> None:
        legacy_payload = {
            "policies": [
                {
                    "policy_id": "escalation.password_reset",
                    "auto_close": {
                        "requires_tool_success": True,
                        "requires_user_confirmation": False,
                    },
                    "waiting": {
                        "pause_sla": False,
                        "auto_close_after_hours": 48,
                    },
                }
            ]
        }

        defaults = client_waiting_defaults_from_legacy_escalation(legacy_payload)
        waiting = normalize_channel_waiting_policy(
            {
                "first_reminder_after_seconds": 180,
                "discussion_timeout_seconds": 480,
                "sla_elapsed_percent_threshold": 0,
                "on_no_answer": "create_draft",
            },
            defaults,
        )

        self.assertFalse(waiting["auto_close_requires_client_confirmation"])
        self.assertFalse(waiting["pause_sla_on_client_wait"])
        self.assertEqual(waiting["client_wait_auto_close_after_hours"], 48)

    def test_default_channels_define_client_waiting_fields(self) -> None:
        for channel in default_interaction_channels()["channels"]:
            waiting = channel["waiting_policy"]
            self.assertIn("auto_close_requires_client_confirmation", waiting)
            self.assertIn("pause_sla_on_client_wait", waiting)
            self.assertIn("client_wait_auto_close_after_hours", waiting)

    def test_default_slot_schemas_do_not_define_waiting_timeouts(self) -> None:
        for slot_schema in default_slot_schemas()["slot_schemas"]:
            self.assertNotIn("timeouts", slot_schema)

    def test_legacy_slot_schema_timeouts_are_normalized_out(self) -> None:
        legacy_payload = default_slot_schemas()
        legacy_payload["slot_schemas"][0]["timeouts"] = {
            "reminder_after_seconds": 180,
            "draft_after_seconds": 480,
        }
        with tempfile.TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")

            normalized = store._normalize_payload("slot_schemas", legacy_payload)

        self.assertNotIn("timeouts", normalized["slot_schemas"][0])


if __name__ == "__main__":
    unittest.main()
