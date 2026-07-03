from __future__ import annotations

import copy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from apps.orchestrator.app.config_registry import ConfigStore, new_version_id, utc_now
from apps.orchestrator.app.contracts import ContractRegistry


def force_active_payload(store: ConfigStore, domain: str, payload: dict) -> None:
    activated_at = utc_now()
    normalized_payload = store._normalize_payload(domain, copy.deepcopy(payload))
    version = {
        "schema_version": "1.0",
        "version_id": new_version_id(),
        "domain": domain,
        "payload": normalized_payload,
        "source_draft_id": "test-force-active",
        "activated_by": "test",
        "activated_at": activated_at,
        "validation": {"schema_version": "1.0", "status": "forced"},
        "regression": {"schema_version": "1.0", "status": "skipped"},
    }
    with store._connect() as connection:
        connection.execute(
            """
            insert into config_versions (
                version_id,
                domain,
                version_json,
                source_draft_id,
                activated_by,
                activated_at
            )
            values (?, ?, ?, ?, ?, ?)
            """,
            (
                version["version_id"],
                domain,
                store._to_json(version),
                version["source_draft_id"],
                version["activated_by"],
                version["activated_at"],
            ),
        )
        connection.execute(
            """
            insert or replace into config_active (
                domain,
                version_id,
                activated_at
            )
            values (?, ?, ?)
            """,
            (domain, version["version_id"], activated_at),
        )


def slot_payload() -> dict:
    return {
        "schema_version": "1.0",
        "slot_schemas": [
            {
                "slot_schema_id": "slot.custom_copy",
                "display_name": "Слоты копирования атрибута",
                "stages": [
                    {
                        "stage_id": "stage.identity",
                        "display_name": "Идентификация",
                        "order": 1,
                        "slots": [
                            {
                                "slot_id": "incident_number",
                                "display_name": "Номер инцидента",
                                "priority_group": "what",
                                "required": True,
                                "fill_method": "resolution_profile",
                                "resolution_profile_id": "profile.used",
                            }
                        ],
                    }
                ],
            }
        ],
    }


def profile(profile_id: str, display_name: str) -> dict:
    return {
        "profile_id": profile_id,
        "display_name": display_name,
        "status": "active",
        "description": "Проверочный профиль разрешения.",
        "slot_schema_id": "slot.custom_copy",
        "target_slot_id": "incident_number",
        "use_llm_after_steps": True,
        "enrichment_steps": [],
        "output_slots_order": [
            {
                "slot_id": "incident_number",
                "order": 1,
                "required_for_success": True,
                "source_hint": "incident_number",
                "fallback": "ask_clarification",
            }
        ],
        "llm_resolution_script": {
            "script_text": "Заполни номер инцидента.",
            "response_contract": {
                "decision": "fill",
                "filled_slots": {},
                "confidence": 1,
                "next_question": "",
                "reason": "",
            },
        },
        "human_resolution_policy": {
            "action": "ask_client",
            "message_template": "Уточните номер инцидента.",
        },
        "max_attempts": 1,
    }


class ResolutionProfileUsageTest(unittest.TestCase):
    def test_usage_marks_only_explicitly_referenced_profile_as_participating(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            force_active_payload(store, "slot_schemas", slot_payload())
            force_active_payload(
                store,
                "attribute_resolution_profiles",
                {
                    "schema_version": "1.0",
                    "profiles": [
                        profile("profile.used", "Используемый профиль"),
                        profile("profile.unused", "Неиспользуемый профиль"),
                    ],
                },
            )
            scenario = copy.deepcopy(store.default_config("service_scenarios")["scenarios"][0])
            scenario["scenario_id"] = "custom_scenario"
            scenario["display_name"] = "Проверочный сценарий"
            scenario["slot_schema_id"] = "slot.custom_copy"
            force_active_payload(
                store,
                "service_scenarios",
                {"schema_version": "1.0", "scenarios": [scenario]},
            )

            usage = {
                item["profile_id"]: item
                for item in store.resolution_profile_usage()["profiles"]
            }
            self.assertTrue(usage["profile.used"]["participates"])
            self.assertFalse(usage["profile.used"]["delete_allowed"])
            self.assertEqual(usage["profile.used"]["used_by"][0]["scenario_id"], "custom_scenario")
            self.assertFalse(usage["profile.unused"]["participates"])
            self.assertTrue(usage["profile.unused"]["unused"])
            self.assertTrue(usage["profile.unused"]["delete_allowed"])

            detail = store.scenario_detail("custom_scenario")
            self.assertEqual(
                [item["profile_id"] for item in detail["attribute_resolution_profiles"]],
                ["profile.used"],
            )


if __name__ == "__main__":
    unittest.main()
