from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from apps.orchestrator.app.config_registry import ConfigStore, new_version_id, utc_now
from apps.orchestrator.app.contracts import ContractRegistry


class LegacySlotCleanupTest(unittest.TestCase):
    def store(self, tempdir: str) -> ConfigStore:
        return ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")

    def force_active_payload(self, store: ConfigStore, domain: str, payload: dict) -> None:
        activated_at = utc_now()
        version = {
            "schema_version": "1.0",
            "version_id": new_version_id(),
            "domain": domain,
            "payload": copy.deepcopy(payload),
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

    def test_direct_slot_delete_still_rejects_profile_output_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            store = self.store(tempdir)
            payload = store.active_payload("slot_schemas")
            schema = next(item for item in payload["slot_schemas"] if item["slot_schema_id"] == "slot.password_reset")
            for stage in schema["stages"]:
                stage["slots"] = [slot for slot in stage["slots"] if slot["slot_id"] != "user_id"]

            validation = store.validate_payload("slot_schemas", payload)

        self.assertEqual(validation["status"], "invalid")
        self.assertTrue(any("profile.password_reset.login_from_ad" in error for error in validation["errors"]))

    def test_cleanup_profile_removes_linked_slots_and_profile_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            store = self.store(tempdir)

            preview = store.cleanup_legacy_slot_resolution(
                slot_schema_id="slot.password_reset",
                slot_ids=["user_login"],
                profile_ids=["profile.password_reset.login_from_ad"],
                operator_id="admin-test",
                dry_run=True,
            )

            self.assertEqual(preview["status"], "ready")
            self.assertEqual(
                {item["slot_id"] for item in preview["summary"]["slots_to_remove"]},
                {"user_login", "user_id"},
            )
            self.assertEqual(
                [item["profile_id"] for item in preview["summary"]["profiles_to_delete"]],
                ["profile.password_reset.login_from_ad"],
            )

            result = store.cleanup_legacy_slot_resolution(
                slot_schema_id="slot.password_reset",
                slot_ids=["user_login"],
                profile_ids=["profile.password_reset.login_from_ad"],
                operator_id="admin-test",
                dry_run=False,
            )

            self.assertEqual(result["status"], "applied")
            self.assertEqual(
                [version["domain"] for version in result["versions"]],
                ["slot_schemas", "attribute_resolution_profiles"],
            )
            slot_schema = next(
                item for item in store.active_payload("slot_schemas")["slot_schemas"]
                if item["slot_schema_id"] == "slot.password_reset"
            )
            self.assertNotIn("user_login", {slot["slot_id"] for slot in slot_schema["slots"]})
            self.assertNotIn("user_id", {slot["slot_id"] for slot in slot_schema["slots"]})
            profile_ids = {
                profile["profile_id"]
                for profile in store.active_payload("attribute_resolution_profiles")["profiles"]
            }
            self.assertNotIn("profile.password_reset.login_from_ad", profile_ids)
            self.assertEqual(store.validate_payload("slot_schemas", store.active_payload("slot_schemas"))["status"], "valid")
            self.assertEqual(
                store.validate_payload(
                    "attribute_resolution_profiles",
                    store.active_payload("attribute_resolution_profiles"),
                )["status"],
                "valid",
            )

    def test_cleanup_one_output_slot_keeps_profile_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            store = self.store(tempdir)

            result = store.cleanup_legacy_slot_resolution(
                slot_schema_id="slot.password_reset",
                slot_ids=["user_id"],
                profile_ids=[],
                operator_id="admin-test",
                dry_run=False,
            )

            self.assertEqual(result["status"], "applied")
            profile = next(
                item for item in store.active_payload("attribute_resolution_profiles")["profiles"]
                if item["profile_id"] == "profile.password_reset.login_from_ad"
            )
            self.assertEqual(profile["target_slot_id"], "user_login")
            self.assertEqual([item["slot_id"] for item in profile["output_slots_order"]], ["user_login"])
            self.assertTrue(profile["output_slots_order"][0]["required_for_success"])

    def test_legacy_flat_slots_are_read_compatible(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            store = self.store(tempdir)
            payload = store.active_payload("slot_schemas")
            schema = next(item for item in payload["slot_schemas"] if item["slot_schema_id"] == "slot.password_reset")
            legacy_slots = schema["slots"]
            schema.pop("stages", None)
            schema["slots"] = legacy_slots

            normalized = store._normalize_payload("slot_schemas", payload)

        normalized_schema = next(
            item for item in normalized["slot_schemas"]
            if item["slot_schema_id"] == "slot.password_reset"
        )
        self.assertEqual(normalized_schema["stages"][0]["stage_id"], "stage.default")
        self.assertEqual(
            [slot["slot_id"] for slot in normalized_schema["stages"][0]["slots"]],
            [slot["slot_id"] for slot in legacy_slots],
        )

    def test_repair_orphaned_resolution_profile_keeps_slot_as_operator_manual(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            store = self.store(tempdir)
            payload = store.active_payload("slot_schemas")
            schema = next(item for item in payload["slot_schemas"] if item["slot_schema_id"] == "slot.password_reset")
            for slot in schema["slots"]:
                if slot["slot_id"] == "user_login":
                    slot["resolution_profile_id"] = "profile.deleted.missing"
            for stage in schema["stages"]:
                for slot in stage["slots"]:
                    if slot["slot_id"] == "user_login":
                        slot["resolution_profile_id"] = "profile.deleted.missing"
            self.force_active_payload(store, "slot_schemas", payload)

            preview = store.repair_orphaned_resolution_profiles(
                slot_schema_id="slot.password_reset",
                operator_id="admin-test",
                dry_run=True,
            )

            self.assertEqual(preview["status"], "ready")
            self.assertEqual(
                [item["slot_id"] for item in preview["summary"]["orphan_slots_repaired"]],
                ["user_login"],
            )

            result = store.repair_orphaned_resolution_profiles(
                slot_schema_id="slot.password_reset",
                operator_id="admin-test",
                dry_run=False,
            )

            self.assertEqual(result["status"], "applied")
            repaired_schema = next(
                item for item in store.active_payload("slot_schemas")["slot_schemas"]
                if item["slot_schema_id"] == "slot.password_reset"
            )
            repaired_slot = next(item for item in repaired_schema["slots"] if item["slot_id"] == "user_login")
            self.assertEqual(repaired_slot["fill_method"], "operator_manual")
            self.assertNotIn("resolution_profile_id", repaired_slot)
            self.assertIn("operator_hint", repaired_slot)
            self.assertEqual(store.validate_payload("slot_schemas", store.active_payload("slot_schemas"))["status"], "valid")

    def test_profile_activation_guard_rejects_orphaning_active_slot_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            store = self.store(tempdir)
            payload = store.active_payload("attribute_resolution_profiles")
            payload["profiles"] = [
                profile
                for profile in payload["profiles"]
                if profile["profile_id"] != "profile.password_reset.login_from_ad"
            ]
            draft = store.create_draft(
                domain="attribute_resolution_profiles",
                payload=payload,
                created_by="admin-test",
            )
            draft["validation"] = {"schema_version": "1.0", "status": "valid", "errors": []}
            draft["regression"] = {"schema_version": "1.0", "status": "skipped"}
            store._save_draft(draft)

            with self.assertRaisesRegex(Exception, "slot_schemas"):
                store.activate_draft(draft["draft_id"], activated_by="admin-test")

    def test_stage_without_slots_requires_resolution_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            store = self.store(tempdir)
            payload = store.active_payload("slot_schemas")
            schema = next(item for item in payload["slot_schemas"] if item["slot_schema_id"] == "slot.password_reset")
            schema["stages"].append(
                {
                    "stage_id": "stage.empty",
                    "display_name": "Пустой этап",
                    "order": 99,
                    "slots": [],
                }
            )

            validation = store.validate_payload("slot_schemas", payload)

        self.assertEqual(validation["status"], "invalid")
        self.assertTrue(any("stage.empty" in error for error in validation["errors"]))

    def test_stage_with_resolution_profile_can_have_no_slots(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            store = self.store(tempdir)
            payload = store.active_payload("slot_schemas")
            schema = next(item for item in payload["slot_schemas"] if item["slot_schema_id"] == "slot.password_reset")
            schema["stages"].append(
                {
                    "stage_id": "stage.profile_only",
                    "display_name": "Разрешение профилем",
                    "order": 99,
                    "resolution_profile_id": "profile.password_reset.login_from_ad",
                    "slots": [],
                }
            )

            validation = store.validate_payload("slot_schemas", payload)

        self.assertEqual(validation["status"], "valid")


if __name__ == "__main__":
    unittest.main()
