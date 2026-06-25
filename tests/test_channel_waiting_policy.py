from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from apps.orchestrator.app.config_registry import (
    ConfigRegistryError,
    ConfigStore,
    client_waiting_defaults_from_legacy_escalation,
    default_classification_routes,
    default_escalation_policies,
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
            self.assertNotIn("question_delivery", channel)
            self.assertNotIn("incomplete_discussion_action", channel)
            self.assertNotIn("escalation_action", channel)
            self.assertNotIn("action_profiles", channel)

    def test_major_incident_is_not_part_of_default_configuration(self) -> None:
        routes = default_classification_routes()["routes"]
        policies = default_escalation_policies()["policies"]

        self.assertNotIn("major_incident", {route["route"] for route in routes})
        for policy in policies:
            self.assertNotIn("major_incident", policy)
            self.assertNotIn("affected_users_threshold", policy["handoff_conditions"])

    def test_major_incident_route_is_not_normalized_or_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            payload = default_classification_routes()
            payload["routes"][0]["route"] = "major_incident"

            validation = store.validate_payload("classification_routes", payload)

        self.assertEqual(validation["status"], "invalid")
        self.assertTrue(any("major_incident" in error for error in validation["errors"]), validation["errors"])

    def test_orchestration_graph_defaults_to_active_scenario_and_stage_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")

            overview = store.scenario_overview()
            graph = store.orchestration_graph(view="scenario")

        self.assertEqual(graph["scenario_id"], overview["scenarios"][0]["scenario_id"])
        titles = {node["title"] for node in graph["nodes"]}
        self.assertIn("Этапы сценария", titles)
        self.assertIn("Профили разрешения", titles)
        self.assertNotIn("0. Планирование этапов", titles)
        self.assertNotIn("0. Слоты", titles)

    def test_classification_reports_configured_and_selected_routes_separately(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            configured_route = store.scenario_detail("password_reset")["route"]

            classification = store.classify_text(
                "Нужен запрос доступа в группу поддержки",
                configured_route,
            )

        self.assertEqual(classification["configured_route_id"], "route.password_reset")
        self.assertEqual(classification["route_id"], "route.access_request")
        self.assertFalse(classification["matches_configured_route"])
        self.assertTrue(classification["positive_hits"])

    def test_debug_channel_behavior_is_system_managed(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            payload = store.active_payload("interaction_channels")
            debug = next(channel for channel in payload["channels"] if channel["channel_id"] == "debug")
            debug["capabilities"]["supports_async_result"] = True

            validation = store.validate_payload("interaction_channels", payload)

        self.assertEqual(validation["status"], "invalid")
        self.assertTrue(any("debug.capabilities" in error for error in validation["errors"]))

    def test_legacy_channel_action_fields_are_normalized_out(self) -> None:
        legacy_payload = default_interaction_channels()
        channel = legacy_payload["channels"][0]
        channel["question_delivery"] = {"action_type": "ask_end_user", "message_template": "{question}"}
        channel["incomplete_discussion_action"] = {"action_type": "create_draft"}
        channel["escalation_action"] = {"action_type": "call_specialist"}
        channel["action_profiles"] = [
            {
                "profile_id": "legacy",
                "display_name": "Legacy",
                "event_type": "standard_handoff",
                "action": {"action_type": "call_specialist"},
            }
        ]
        with tempfile.TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")

            normalized = store._normalize_payload("interaction_channels", legacy_payload)
            validation = store.validate_payload("interaction_channels", legacy_payload)

        normalized_channel = normalized["channels"][0]
        self.assertNotIn("question_delivery", normalized_channel)
        self.assertNotIn("incomplete_discussion_action", normalized_channel)
        self.assertNotIn("escalation_action", normalized_channel)
        self.assertNotIn("action_profiles", normalized_channel)
        self.assertEqual(validation["status"], "valid", validation["errors"])

    def test_simulation_can_debug_real_channel_behavior_and_parameters(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")

            simulation = store.simulate_scenario(
                "password_reset",
                text="Иванов Иван не может войти в доменную учетную запись",
                channel_id="service_desk",
            )

        self.assertEqual(simulation["interaction_channel"]["channel_id"], "service_desk")
        self.assertEqual(simulation["escalation_action"]["action_type"], "create_work_order")
        self.assertEqual(
            simulation["channel_variables"]["service_desk"]["task_topic"],
            "public.ittask.serviceDeskDefault.task",
        )
        self.assertEqual(
            simulation["channel_variables"]["service_desk"]["result_topic"],
            "public.ittask.result",
        )
        parameter_state = {
            parameter["parameter_id"]: parameter["status"]
            for parameter in simulation["channel_parameter_state"]
        }
        self.assertEqual(parameter_state["task_topic"], "resolved")
        self.assertEqual(parameter_state["task_key"], "missing")

    def test_simulation_accepts_service_desk_channel_parameter_values(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")

            simulation = store.simulate_scenario(
                "password_reset",
                text="Иванов Иван не может войти в доменную учетную запись",
                channel_id="service_desk",
                channel_parameter_values={
                    "task_key": "OPERU-123",
                    "result_message": "Пароль сброшен в ОперуИТ",
                    "api_token": "must-not-leak",
                },
            )

        service_desk = simulation["channel_variables"]["service_desk"]
        self.assertEqual(service_desk["task_key"], "OPERU-123")
        self.assertEqual(service_desk["task_number"], "OPERU-123")
        self.assertEqual(service_desk["result_message"], "Пароль сброшен в ОперуИТ")
        self.assertNotIn("api_token", service_desk)
        parameter_state = {
            parameter["parameter_id"]: parameter["status"]
            for parameter in simulation["channel_parameter_state"]
        }
        self.assertEqual(parameter_state["task_key"], "resolved")
        self.assertEqual(parameter_state["result_message"], "resolved")

    def test_simulation_rejects_channel_outside_scenario_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")

            with self.assertRaises(ConfigRegistryError):
                store.simulate_scenario(
                    "password_reset",
                    text="Иванов Иван не может войти в доменную учетную запись",
                    channel_id="missing_channel",
                )

    def test_default_slot_schemas_do_not_define_waiting_timeouts(self) -> None:
        for slot_schema in default_slot_schemas()["slot_schemas"]:
            self.assertNotIn("timeouts", slot_schema)

    def test_default_slot_schemas_define_planning_stages(self) -> None:
        for slot_schema in default_slot_schemas()["slot_schemas"]:
            self.assertIn("stages", slot_schema)
            self.assertGreaterEqual(len(slot_schema["stages"]), 1)
            self.assertEqual(
                slot_schema["slots"],
                [
                    slot
                    for stage in sorted(slot_schema["stages"], key=lambda item: item["order"])
                    for slot in stage["slots"]
                ],
            )

    def test_duplicate_channel_parameters_are_rejected_before_normalization(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            payload = store.active_payload("interaction_channels")
            channel = next(item for item in payload["channels"] if item["channel_id"] == "service_desk")
            existing = channel["channel_parameters"][0]
            channel["channel_parameters"].append(
                {
                    **existing,
                    "display_name": "Дубль параметра",
                }
            )

            validation = store.validate_payload("interaction_channels", payload)

        self.assertEqual(validation["status"], "invalid")
        self.assertTrue(
            any("дублирующийся параметр канала" in error for error in validation["errors"]),
            validation["errors"],
        )

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

    def test_empty_stage_requires_slots_or_resolution_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            payload = store.active_payload("slot_schemas")
            schema = payload["slot_schemas"][0]
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

    def test_empty_stage_with_resolution_profile_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            payload = store.active_payload("slot_schemas")
            schema = payload["slot_schemas"][0]
            schema["stages"].append(
                {
                    "stage_id": "stage.profile_only",
                    "display_name": "Профиль без локальных слотов",
                    "order": 99,
                    "resolution_profile_id": "profile.password_reset.login_from_ad",
                    "slots": [],
                }
            )

            validation = store.validate_payload("slot_schemas", payload)

        self.assertEqual(validation["status"], "valid", validation["errors"])


if __name__ == "__main__":
    unittest.main()
