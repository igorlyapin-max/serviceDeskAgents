from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from apps.orchestrator.app.config_registry import ConfigStore
from apps.orchestrator.app.contracts import ContractRegistry


def activate_bundle(store: ConfigStore, draft_ids: list[str], operator_id: str = "admin-1") -> dict:
    validated = store.validate_draft_bundle(draft_ids)
    if validated["status"] != "valid":
        raise AssertionError(validated["validations"])
    for draft in validated["drafts"]:
        store.save_regression(
            draft["draft_id"],
            {
                "schema_version": "1.0",
                "domain": draft["domain"],
                "status": "skipped",
                "run_at": "2026-06-25T00:00:00Z",
                "gates": [],
            },
        )
    return store.activate_draft_bundle(draft_ids, activated_by=operator_id)


def create_current_draft(
    store: ConfigStore,
    *,
    domain: str,
    payload: dict,
    created_by: str = "admin-1",
) -> dict:
    return store.create_draft(
        domain=domain,
        payload=payload,
        created_by=created_by,
        base_version_id=store.active_version_id(domain),
    )


def mark_draft_ready(store: ConfigStore, draft_id: str) -> dict:
    validated = store.validate_draft(draft_id)
    if validated["validation"]["status"] != "valid":
        raise AssertionError(validated["validation"]["errors"])
    return store.save_regression(
        draft_id,
        {
            "schema_version": "1.0",
            "domain": validated["domain"],
            "status": "skipped",
            "run_at": "2026-06-25T00:00:00Z",
            "gates": [],
        },
    )


def custom_slot_payload(profile_id: str = "profile.custom.attribute_copy") -> dict:
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
                                "resolution_profile_id": profile_id,
                            }
                        ],
                    }
                ],
            }
        ],
    }


def custom_multi_slot_payload(profile_id: str = "profile.custom.attribute_copy") -> dict:
    return {
        "schema_version": "1.0",
        "slot_schemas": [
            {
                "slot_schema_id": "slot.custom_copy",
                "display_name": "Слоты копирования атрибутов",
                "stages": [
                    {
                        "stage_id": "stage.provider",
                        "display_name": "Данные провайдера",
                        "order": 1,
                        "slots": [
                            {
                                "slot_id": "provider_mail_body",
                                "display_name": "Тело письма провайдера",
                                "priority_group": "what",
                                "required": True,
                                "fill_method": "resolution_profile",
                                "resolution_profile_id": profile_id,
                            },
                            {
                                "slot_id": "provider_mail_subject",
                                "display_name": "Тема письма провайдера",
                                "priority_group": "what",
                                "required": False,
                                "fill_method": "resolution_profile",
                                "resolution_profile_id": profile_id,
                            },
                        ],
                    }
                ],
            }
        ],
    }


def custom_profile_payload(*, output_slot_id: str = "incident_number") -> dict:
    return {
        "schema_version": "1.0",
        "profiles": [
            {
                "profile_id": "profile.custom.attribute_copy",
                "display_name": "Копирование атрибута",
                "status": "draft",
                "description": "Проверочный профиль для заполнения номера инцидента.",
                "slot_schema_id": "slot.custom_copy",
                "target_slot_id": output_slot_id,
                "use_llm_after_steps": True,
                "enrichment_steps": [],
                "output_slots_order": [
                    {
                        "slot_id": output_slot_id,
                        "order": 1,
                        "required_for_success": True,
                        "source_hint": output_slot_id,
                        "fallback": "ask_clarification",
                    }
                ],
                "llm_resolution_script": {
                    "script_text": "Заполни выходной слот по данным обращения.",
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
                "fallback": {
                    "action": "ask_user",
                    "question": "Уточните номер инцидента.",
                },
                "max_attempts": 1,
            }
        ],
    }


def custom_multi_output_profile_payload(profile_id: str = "profile.custom.attribute_copy") -> dict:
    return {
        "schema_version": "1.0",
        "profiles": [
            {
                "profile_id": profile_id,
                "display_name": "Копирование атрибутов",
                "status": "draft",
                "description": "Проверочный профиль для заполнения нескольких атрибутов.",
                "slot_schema_id": "slot.custom_copy",
                "target_slot_id": "provider_mail_body",
                "use_llm_after_steps": True,
                "enrichment_steps": [],
                "output_slots_order": [
                    {
                        "slot_id": "provider_mail_body",
                        "order": 1,
                        "required_for_success": True,
                        "source_hint": "provider_mail_body",
                        "fallback": "ask_clarification",
                    },
                    {
                        "slot_id": "provider_mail_subject",
                        "order": 2,
                        "required_for_success": False,
                        "source_hint": "provider_mail_subject",
                        "fallback": "ask_clarification",
                    },
                ],
                "llm_resolution_script": {
                    "script_text": "Заполни выходные слоты по данным обращения.",
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
                    "message_template": "Уточните данные письма провайдера.",
                },
                "fallback": {
                    "action": "ask_user",
                    "question": "Уточните данные письма провайдера.",
                },
                "max_attempts": 1,
            }
        ],
    }


def llm_slot_payload(*, extraction_instruction: str) -> dict:
    return {
        "schema_version": "1.0",
        "slot_schemas": [
            {
                "slot_schema_id": "slot.llm_extraction",
                "display_name": "Слоты LLM-извлечения",
                "stages": [
                    {
                        "stage_id": "stage.identity",
                        "display_name": "Идентификация",
                        "order": 1,
                        "slots": [
                            {
                                "slot_id": "user_fio",
                                "display_name": "ФИО пользователя",
                                "priority_group": "who",
                                "required": True,
                                "fill_method": "user_question",
                                "user_question": "Уточните ФИО пользователя.",
                            },
                            {
                                "slot_id": "user_login",
                                "display_name": "Логин пользователя",
                                "priority_group": "who",
                                "required": True,
                                "fill_method": "llm_extraction",
                                "extraction_instruction": extraction_instruction,
                            },
                        ],
                    }
                ],
            }
        ],
    }


class ConfigDraftValidationTest(unittest.TestCase):
    def test_scoped_profile_draft_ignores_invalid_sibling_and_activates_only_selected_profile(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            slot_draft = store.create_draft(
                domain="slot_schemas",
                payload=custom_slot_payload(),
                created_by="admin-1",
            )
            profile_draft = store.create_draft(
                domain="attribute_resolution_profiles",
                payload=custom_profile_payload(),
                created_by="admin-1",
            )
            activate_bundle(store, [slot_draft["draft_id"], profile_draft["draft_id"]])

            payload = custom_profile_payload()
            payload["profiles"][0]["description"] = "Изменено только в выбранном профиле."
            invalid_sibling = {
                **payload["profiles"][0],
                "profile_id": "profile.custom.invalid_sibling",
                "display_name": "Невалидный соседний профиль",
                "description": "",
            }
            payload["profiles"].append(invalid_sibling)
            scoped_draft = store.create_draft(
                domain="attribute_resolution_profiles",
                payload=payload,
                created_by="admin-1",
                base_version_id=store.active_version_id("attribute_resolution_profiles"),
                scope={
                    "type": "collection_item",
                    "collection": "profiles",
                    "id_key": "profile_id",
                    "id": "profile.custom.attribute_copy",
                    "action": "upsert",
                },
            )

            validated = store.validate_draft(scoped_draft["draft_id"])
            self.assertEqual(validated["validation"]["status"], "valid", validated["validation"]["errors"])
            store.save_regression(
                scoped_draft["draft_id"],
                {
                    "schema_version": "1.0",
                    "domain": "attribute_resolution_profiles",
                    "status": "skipped",
                    "run_at": "2026-06-25T00:00:00Z",
                    "gates": [],
                },
            )
            store.activate_draft(scoped_draft["draft_id"], activated_by="admin-1")

            active_profiles = store.active_payload("attribute_resolution_profiles")["profiles"]
            self.assertEqual([profile["profile_id"] for profile in active_profiles], ["profile.custom.attribute_copy"])
            self.assertEqual(active_profiles[0]["description"], "Изменено только в выбранном профиле.")

    def test_scoped_profile_draft_preserves_invalid_payload_and_requires_bundle_for_new_slots(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            slot_draft = store.create_draft(
                domain="slot_schemas",
                payload=custom_slot_payload(),
                created_by="admin-1",
            )
            profile_draft = store.create_draft(
                domain="attribute_resolution_profiles",
                payload=custom_profile_payload(),
                created_by="admin-1",
            )
            activate_bundle(store, [slot_draft["draft_id"], profile_draft["draft_id"]])

            payload = custom_profile_payload(output_slot_id="new_provider_ticket")
            scoped_draft = store.create_draft(
                domain="attribute_resolution_profiles",
                payload=payload,
                created_by="admin-1",
                base_version_id=store.active_version_id("attribute_resolution_profiles"),
                scope={
                    "type": "collection_item",
                    "collection": "profiles",
                    "id_key": "profile_id",
                    "id": "profile.custom.attribute_copy",
                    "action": "upsert",
                },
            )

            validated = store.validate_draft(scoped_draft["draft_id"])

            self.assertEqual(validated["status"], "invalid")
            self.assertIn("Используйте «Активировать пакет»", "; ".join(validated["validation"]["errors"]))
            saved = store.require_draft(scoped_draft["draft_id"])
            self.assertEqual(saved["payload"]["profiles"][0]["target_slot_id"], "new_provider_ticket")

    def test_slot_schema_draft_can_reference_profile_draft_from_same_operator(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            create_current_draft(
                store,
                domain="attribute_resolution_profiles",
                payload=custom_profile_payload(),
                created_by="admin-1",
            )
            slot_draft = create_current_draft(
                store,
                domain="slot_schemas",
                payload=custom_slot_payload(),
                created_by="admin-1",
            )

            validated = store.validate_draft(slot_draft["draft_id"])

            self.assertEqual(validated["validation"]["status"], "valid", validated["validation"]["errors"])

    def test_attribute_resolution_profile_draft_can_reference_slot_schema_draft_from_same_operator(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            create_current_draft(
                store,
                domain="slot_schemas",
                payload=custom_slot_payload(),
                created_by="admin-1",
            )
            profile_draft = create_current_draft(
                store,
                domain="attribute_resolution_profiles",
                payload=custom_profile_payload(),
                created_by="admin-1",
            )

            validated = store.validate_draft(profile_draft["draft_id"])

            self.assertEqual(validated["validation"]["status"], "valid", validated["validation"]["errors"])

    def test_invalid_related_draft_is_not_used_as_working_config(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            profile_draft = store.create_draft(
                domain="attribute_resolution_profiles",
                payload=custom_profile_payload(),
                created_by="admin-1",
            )
            slot_draft = store.create_draft(
                domain="slot_schemas",
                payload=custom_slot_payload(),
                created_by="admin-1",
            )
            activate_bundle(store, [slot_draft["draft_id"], profile_draft["draft_id"]])

            invalid_profile_payload = custom_profile_payload()
            invalid_profile_payload["profiles"][0]["description"] = ""
            invalid_profile_draft = create_current_draft(
                store,
                domain="attribute_resolution_profiles",
                payload=invalid_profile_payload,
                created_by="admin-1",
            )
            invalid_profile_draft = store.validate_draft(invalid_profile_draft["draft_id"])
            self.assertEqual(invalid_profile_draft["status"], "invalid")

            next_slot_draft = create_current_draft(
                store,
                domain="slot_schemas",
                payload=custom_slot_payload(),
                created_by="admin-1",
            )

            validated = store.validate_draft(next_slot_draft["draft_id"])

            self.assertEqual(validated["validation"]["status"], "valid", validated["validation"]["errors"])

    def test_stale_related_profile_draft_from_previous_active_version_is_ignored(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            previous_profile_version = store.active_version_id("attribute_resolution_profiles")
            profile_draft = create_current_draft(
                store,
                domain="attribute_resolution_profiles",
                payload=custom_profile_payload(),
                created_by="admin-1",
            )
            slot_draft = create_current_draft(
                store,
                domain="slot_schemas",
                payload=custom_slot_payload(),
                created_by="admin-1",
            )
            activate_bundle(store, [slot_draft["draft_id"], profile_draft["draft_id"]])

            store.create_draft(
                domain="attribute_resolution_profiles",
                payload=custom_profile_payload(output_slot_id="other_slot"),
                created_by="admin-1",
                base_version_id=previous_profile_version,
            )
            next_slot_draft = create_current_draft(
                store,
                domain="slot_schemas",
                payload=custom_slot_payload(),
                created_by="admin-1",
            )

            validated = store.validate_draft(next_slot_draft["draft_id"])

            self.assertEqual(validated["validation"]["status"], "valid", validated["validation"]["errors"])

    def test_slot_schema_draft_can_reference_multi_output_profile_from_same_operator(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            create_current_draft(
                store,
                domain="attribute_resolution_profiles",
                payload=custom_multi_output_profile_payload(),
                created_by="admin-1",
            )
            slot_draft = create_current_draft(
                store,
                domain="slot_schemas",
                payload=custom_multi_slot_payload(),
                created_by="admin-1",
            )

            validated = store.validate_draft(slot_draft["draft_id"])

            self.assertEqual(validated["validation"]["status"], "valid", validated["validation"]["errors"])

    def test_draft_bundle_validation_accepts_multi_output_profile_missing_from_active_config(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            profile_draft = store.create_draft(
                domain="attribute_resolution_profiles",
                payload=custom_multi_output_profile_payload(),
                created_by="admin-1",
            )
            slot_draft = store.create_draft(
                domain="slot_schemas",
                payload=custom_multi_slot_payload(),
                created_by="admin-1",
            )

            result = store.validate_draft_bundle([slot_draft["draft_id"], profile_draft["draft_id"]])

            self.assertEqual(result["status"], "valid", result["validations"])
            self.assertEqual(result["validations"]["slot_schemas"]["status"], "valid")
            self.assertEqual(result["validations"]["attribute_resolution_profiles"]["status"], "valid")

    def test_draft_bundle_validation_reports_invalid_profile_not_unknown_profile_id(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            profile_payload = custom_multi_output_profile_payload()
            profile_payload["profiles"][0]["human_resolution_policy"]["message_template"] = (
                "Уточните ${slot.unknown_slot}."
            )
            profile_draft = store.create_draft(
                domain="attribute_resolution_profiles",
                payload=profile_payload,
                created_by="admin-1",
            )
            slot_draft = store.create_draft(
                domain="slot_schemas",
                payload=custom_multi_slot_payload(),
                created_by="admin-1",
            )

            result = store.validate_draft_bundle([slot_draft["draft_id"], profile_draft["draft_id"]])

            self.assertEqual(result["status"], "invalid")
            self.assertEqual(result["validations"]["slot_schemas"]["status"], "valid")
            profile_errors = result["validations"]["attribute_resolution_profiles"]["errors"]
            self.assertTrue(
                any("неизвестный слот: unknown_slot" in error for error in profile_errors),
                profile_errors,
            )
            self.assertFalse(
                any("ссылается на неизвестный profile_id" in error for error in result["validations"]["slot_schemas"]["errors"]),
                result["validations"]["slot_schemas"]["errors"],
            )

    def test_slot_schema_llm_extraction_can_reference_slot_from_same_draft_schema(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            slot_draft = store.create_draft(
                domain="slot_schemas",
                payload=llm_slot_payload(
                    extraction_instruction="Извлеки логин с учетом ${slot.user_fio}."
                ),
                created_by="admin-1",
            )

            validated = store.validate_draft(slot_draft["draft_id"])

            self.assertEqual(validated["validation"]["status"], "valid", validated["validation"]["errors"])

    def test_slot_schema_llm_extraction_rejects_unknown_slot_reference(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            slot_draft = store.create_draft(
                domain="slot_schemas",
                payload=llm_slot_payload(
                    extraction_instruction="Извлеки логин с учетом ${slot.unknown_slot}."
                ),
                created_by="admin-1",
            )

            validated = store.validate_draft(slot_draft["draft_id"])

            self.assertEqual(validated["validation"]["status"], "invalid")
            self.assertTrue(
                any("неизвестный слот: unknown_slot" in error for error in validated["validation"]["errors"]),
                validated["validation"]["errors"],
            )

    def test_attribute_resolution_profile_template_can_reference_new_slot_schema_draft_slot(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            create_current_draft(
                store,
                domain="slot_schemas",
                payload=custom_slot_payload(),
                created_by="admin-1",
            )
            profile_payload = custom_profile_payload()
            profile_payload["profiles"][0]["human_resolution_policy"]["message_template"] = (
                "Уточните данные для ${slot.incident_number}."
            )
            profile_payload["profiles"][0]["llm_resolution_script"]["script_text"] = (
                "Заполни ${slot.incident_number} из результата последнего шага."
            )
            profile_draft = create_current_draft(
                store,
                domain="attribute_resolution_profiles",
                payload=profile_payload,
                created_by="admin-1",
            )

            validated = store.validate_draft(profile_draft["draft_id"])

            self.assertEqual(validated["validation"]["status"], "valid", validated["validation"]["errors"])

    def test_attribute_resolution_profile_step_instruction_can_reference_new_slot_schema_draft_slot(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            create_current_draft(
                store,
                domain="slot_schemas",
                payload=custom_slot_payload(),
                created_by="admin-1",
            )
            profile_payload = custom_profile_payload()
            profile_payload["profiles"][0]["output_slots_order"][0]["source_hint"] = "provider_ticket_number"
            profile_payload["profiles"][0]["enrichment_steps"] = [
                {
                    "step_id": "step1",
                    "step_name": "Проверить статус",
                    "capability_id": "provider_channel_repair_monitor",
                    "mcp_environment_id": "env.provider_ops",
                    "input_mapping": {
                        "problem_url": "constant:http://zabbix/problem",
                        "service_request": "slot:incident_number",
                    },
                    "output_mapping": {"incident_number": "provider_ticket_number"},
                    "on_error": "continue_to_llm",
                    "configuration_instruction": (
                        "Используй ${slot.incident_number} как вход "
                        "${paramCapability.provider_channel_repair_monitor.input.service_request}."
                    ),
                }
            ]
            profile_draft = create_current_draft(
                store,
                domain="attribute_resolution_profiles",
                payload=profile_payload,
                created_by="admin-1",
            )

            validated = store.validate_draft(profile_draft["draft_id"])

            self.assertEqual(validated["validation"]["status"], "valid", validated["validation"]["errors"])

    def test_attribute_resolution_step_output_mapping_is_limited_to_selected_output_slots(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            create_current_draft(
                store,
                domain="slot_schemas",
                payload=custom_multi_slot_payload(),
                created_by="admin-1",
            )
            profile_payload = custom_multi_output_profile_payload()
            profile = profile_payload["profiles"][0]
            profile["output_slots_order"] = [profile["output_slots_order"][0]]
            profile["enrichment_steps"] = [
                {
                    "step_id": "step1",
                    "step_name": "Получить ответ провайдера",
                    "capability_id": "provider_channel_repair_monitor",
                    "mcp_environment_id": "env.provider_ops",
                    "input_mapping": {
                        "problem_url": "constant:http://zabbix/problem",
                        "service_request": "constant:SR-1",
                    },
                    "output_mapping": {
                        "provider_mail_body": "provider_mail_body",
                        "provider_mail_subject": "provider_mail_subject",
                        "provider_ticket_number": "provider_ticket_number",
                        "polling_diagnostic": "polling_diagnostic",
                        "zabbix_status": "zabbix_status",
                    },
                    "on_error": "continue_to_llm",
                }
            ]
            profile_draft = create_current_draft(
                store,
                domain="attribute_resolution_profiles",
                payload=profile_payload,
                created_by="admin-1",
            )

            validated = store.validate_draft(profile_draft["draft_id"])

            self.assertEqual(
                profile_draft["payload"]["profiles"][0]["enrichment_steps"][0]["output_mapping"],
                {"provider_mail_body": "provider_mail_body"},
            )
            self.assertEqual(validated["validation"]["status"], "valid", validated["validation"]["errors"])
            validated["payload"]["profiles"][0]["enrichment_steps"][0]["output_mapping"] = {
                "provider_mail_body": "provider_mail_body",
                "provider_mail_subject": "provider_mail_subject",
                "provider_ticket_number": "provider_ticket_number",
                "polling_diagnostic": "polling_diagnostic",
                "zabbix_status": "zabbix_status",
            }
            store._save_draft(validated)

            repaired = store.validate_draft(profile_draft["draft_id"])

            self.assertEqual(repaired["validation"]["status"], "valid", repaired["validation"]["errors"])
            self.assertEqual(
                repaired["payload"]["profiles"][0]["enrichment_steps"][0]["output_mapping"],
                {"provider_mail_body": "provider_mail_body"},
            )

    def test_attribute_resolution_profile_normalizes_legacy_parameter_mapping(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            create_current_draft(
                store,
                domain="slot_schemas",
                payload=custom_slot_payload(),
                created_by="admin-1",
            )
            profile_payload = custom_profile_payload()
            profile_payload["profiles"][0]["output_slots_order"][0]["source_hint"] = "provider_ticket_number"
            profile_payload["profiles"][0]["enrichment_steps"] = [
                {
                    "step_id": "step1",
                    "step_name": "Проверить статус",
                    "capability_id": "provider_channel_repair_monitor",
                    "mcp_environment_id": "env.provider_ops",
                    "input_mapping": {
                        "problem_url": "constant:http://zabbix/problem",
                        "service_request": "slot:incident_number",
                    },
                    "output_mapping": {"incident_number": "provider_ticket_number"},
                    "on_error": "continue_to_llm",
                    "parameter_mapping": {},
                }
            ]

            profile_draft = create_current_draft(
                store,
                domain="attribute_resolution_profiles",
                payload=profile_payload,
                created_by="admin-1",
            )
            validated = store.validate_draft(profile_draft["draft_id"])
            normalized = store._normalize_payload("attribute_resolution_profiles", profile_payload)

            self.assertEqual(validated["validation"]["status"], "valid", validated["validation"]["errors"])
            self.assertNotIn(
                "parameter_mapping",
                normalized["profiles"][0]["enrichment_steps"][0],
            )

    def test_attribute_resolution_profile_draft_still_rejects_unknown_slot_template_ref(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            create_current_draft(
                store,
                domain="slot_schemas",
                payload=custom_slot_payload(),
                created_by="admin-1",
            )
            profile_payload = custom_profile_payload()
            profile_payload["profiles"][0]["human_resolution_policy"]["message_template"] = (
                "Уточните данные для ${slot.unknown_slot}."
            )
            profile_draft = create_current_draft(
                store,
                domain="attribute_resolution_profiles",
                payload=profile_payload,
                created_by="admin-1",
            )

            validated = store.validate_draft(profile_draft["draft_id"])

            self.assertEqual(validated["validation"]["status"], "invalid")
            self.assertTrue(
                any("неизвестный слот: unknown_slot" in error for error in validated["validation"]["errors"]),
                validated["validation"]["errors"],
            )

    def test_draft_bundle_validation_accepts_cross_referenced_slot_and_profile(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            slot_draft = store.create_draft(
                domain="slot_schemas",
                payload=custom_slot_payload(),
                created_by="admin-1",
            )
            profile_draft = store.create_draft(
                domain="attribute_resolution_profiles",
                payload=custom_profile_payload(),
                created_by="admin-1",
            )

            result = store.validate_draft_bundle([slot_draft["draft_id"], profile_draft["draft_id"]])

            self.assertEqual(result["status"], "valid", result["validations"])
            self.assertEqual(
                set(result["domains"]),
                {"slot_schemas", "attribute_resolution_profiles"},
            )

    def test_active_payload_overrides_are_context_scoped(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            original = store.active_payload("slot_schemas")
            candidate = custom_slot_payload()

            with store.active_payload_overrides({"slot_schemas": candidate}):
                self.assertEqual(
                    store.active_payload("slot_schemas")["slot_schemas"][0]["slot_schema_id"],
                    "slot.custom_copy",
                )

            self.assertEqual(store.active_payload("slot_schemas"), original)

    def test_normalized_draft_bundle_payloads_returns_candidate_payloads(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            slot_draft = store.create_draft(
                domain="slot_schemas",
                payload=custom_slot_payload(),
                created_by="admin-1",
            )
            profile_draft = store.create_draft(
                domain="attribute_resolution_profiles",
                payload=custom_profile_payload(),
                created_by="admin-1",
            )

            payloads = store.normalized_draft_bundle_payloads([slot_draft["draft_id"], profile_draft["draft_id"]])

            self.assertEqual(set(payloads), {"slot_schemas", "attribute_resolution_profiles"})
            self.assertEqual(payloads["slot_schemas"]["slot_schemas"][0]["slot_schema_id"], "slot.custom_copy")
            self.assertEqual(
                payloads["attribute_resolution_profiles"]["profiles"][0]["profile_id"],
                "profile.custom.attribute_copy",
            )

    def test_draft_bundle_activation_activates_cross_referenced_slot_and_profile(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            slot_draft = store.create_draft(
                domain="slot_schemas",
                payload=custom_slot_payload(),
                created_by="admin-1",
            )
            profile_draft = store.create_draft(
                domain="attribute_resolution_profiles",
                payload=custom_profile_payload(),
                created_by="admin-1",
            )
            validated = store.validate_draft_bundle([slot_draft["draft_id"], profile_draft["draft_id"]])
            for draft in validated["drafts"]:
                store.save_regression(
                    draft["draft_id"],
                    {
                        "schema_version": "1.0",
                        "domain": draft["domain"],
                        "status": "skipped",
                        "run_at": "2026-06-22T00:00:00Z",
                        "gates": [],
                    },
                )

            result = store.activate_draft_bundle(
                [slot_draft["draft_id"], profile_draft["draft_id"]],
                activated_by="admin-1",
            )

            self.assertEqual(result["status"], "activated")
            self.assertEqual(
                {
                    store.active_payload("slot_schemas")["slot_schemas"][0]["slots"][0]["slot_id"],
                    store.active_payload("attribute_resolution_profiles")["profiles"][0]["output_slots_order"][0]["slot_id"],
                },
                {"incident_number"},
            )

    def test_attribute_resolution_profile_without_target_slot_can_use_output_slots(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            profile_payload = custom_profile_payload()
            profile_payload["profiles"][0].pop("target_slot_id")
            profile_payload["profiles"][0]["output_slots_order"][0]["required_for_success"] = True
            create_current_draft(
                store,
                domain="slot_schemas",
                payload=custom_slot_payload(),
                created_by="admin-1",
            )
            profile_draft = create_current_draft(
                store,
                domain="attribute_resolution_profiles",
                payload=profile_payload,
                created_by="admin-1",
            )

            validated = store.validate_draft(profile_draft["draft_id"])

            self.assertEqual(validated["validation"]["status"], "valid", validated["validation"]["errors"])

    def test_attribute_resolution_profile_can_activate_with_empty_output_slots(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            slot_payload = custom_slot_payload()
            slot = slot_payload["slot_schemas"][0]["stages"][0]["slots"][0]
            slot["fill_method"] = "operator_manual"
            slot["operator_hint"] = "Заполните номер инцидента вручную."
            slot.pop("resolution_profile_id", None)

            profile_payload = custom_profile_payload()
            profile = profile_payload["profiles"][0]
            profile.pop("target_slot_id")
            profile["output_slots_order"] = []

            slot_draft = store.create_draft(
                domain="slot_schemas",
                payload=slot_payload,
                created_by="admin-1",
            )
            profile_draft = store.create_draft(
                domain="attribute_resolution_profiles",
                payload=profile_payload,
                created_by="admin-1",
            )

            validated = store.validate_draft_bundle([slot_draft["draft_id"], profile_draft["draft_id"]])
            self.assertEqual(validated["status"], "valid", validated.get("errors", []))
            for draft in validated["drafts"]:
                store.save_regression(
                    draft["draft_id"],
                    {
                        "schema_version": "1.0",
                        "domain": draft["domain"],
                        "status": "skipped",
                        "run_at": "2026-06-25T00:00:00Z",
                        "gates": [],
                    },
                )

            result = store.activate_draft_bundle(
                [slot_draft["draft_id"], profile_draft["draft_id"]],
                activated_by="admin-1",
            )

            active_profile = store.active_payload("attribute_resolution_profiles")["profiles"][0]
            self.assertEqual(result["status"], "activated")
            self.assertNotIn("target_slot_id", active_profile)
            self.assertEqual(active_profile["output_slots_order"], [])

    def test_attribute_resolution_profile_with_enrichment_steps_can_skip_output_slots(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            profile_payload = store.active_payload("attribute_resolution_profiles")
            profile = next(
                item
                for item in profile_payload["profiles"]
                if item["profile_id"] == "profile.password_reset.login_from_ad"
            )
            profile.pop("target_slot_id", None)
            profile["output_slots_order"] = []

            validated = store.validate_payload("attribute_resolution_profiles", profile_payload)

            self.assertEqual(validated["status"], "valid", validated["errors"])

    def test_attribute_resolution_profile_empty_completion_policy_uses_capability_default(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            create_current_draft(
                store,
                domain="slot_schemas",
                payload=custom_slot_payload(),
                created_by="admin-1",
            )
            profile_payload = custom_profile_payload()
            profile = profile_payload["profiles"][0]
            profile.pop("target_slot_id", None)
            profile["use_llm_after_steps"] = False
            profile["output_slots_order"] = []
            profile["enrichment_steps"] = [
                {
                    "step_id": "step1",
                    "step_name": "Ждать восстановления Zabbix",
                    "capability_id": "zabbix_problem_status_wait",
                    "mcp_environment_id": "mcp.provider_ops",
                    "completion_policy": {},
                    "input_mapping": {
                        "problem_url": "constant:http://zabbix/tr_events.php?eventid=1",
                        "poll_interval_minutes": "constant:1",
                        "timeout_minutes": "constant:10",
                    },
                    "output_mapping": {},
                    "on_error": "continue_to_llm",
                }
            ]
            profile_draft = create_current_draft(
                store,
                domain="attribute_resolution_profiles",
                payload=profile_payload,
                created_by="admin-1",
            )

            normalized_step = profile_draft["payload"]["profiles"][0]["enrichment_steps"][0]
            self.assertEqual(normalized_step["completion_policy"]["mode"], "external_event")
            self.assertEqual(
                normalized_step["completion_policy"]["expected_event_type"],
                "zabbix_problem_status_wait.completed",
            )

            validated = store.validate_draft(profile_draft["draft_id"])

            self.assertEqual(validated["validation"]["status"], "valid", validated["validation"]["errors"])

    def test_activate_draft_deletes_working_drafts_for_same_domain_operator(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            domain = "attribute_resolution_profiles"
            payload = store.active_payload(domain)
            old_working = create_current_draft(
                store,
                domain=domain,
                payload=payload,
                created_by="admin-1",
            )
            other_operator = create_current_draft(
                store,
                domain=domain,
                payload=payload,
                created_by="other-admin",
            )
            invalid_same_operator = create_current_draft(
                store,
                domain=domain,
                payload=payload,
                created_by="admin-1",
            )
            invalid_draft = store.require_draft(invalid_same_operator["draft_id"])
            invalid_draft["status"] = "invalid"
            invalid_draft["validation"] = {
                "schema_version": "1.0",
                "status": "invalid",
                "errors": ["test"],
                "gates": [],
            }
            store._save_draft(invalid_draft)
            activating = create_current_draft(
                store,
                domain=domain,
                payload=payload,
                created_by="admin-1",
            )
            mark_draft_ready(store, activating["draft_id"])

            version = store.activate_draft(activating["draft_id"], activated_by="admin-1")

            self.assertEqual(version["source_draft_id"], activating["draft_id"])
            self.assertIsNone(store.get_draft(old_working["draft_id"]))
            self.assertEqual(store.require_draft(activating["draft_id"])["status"], "activated")
            self.assertIsNotNone(store.get_draft(other_operator["draft_id"]))
            self.assertIsNotNone(store.get_draft(invalid_same_operator["draft_id"]))

    def test_activate_draft_bundle_deletes_working_drafts_for_activated_domains(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            old_profile = create_current_draft(
                store,
                domain="attribute_resolution_profiles",
                payload=store.active_payload("attribute_resolution_profiles"),
                created_by="admin-1",
            )
            old_slot_schema = create_current_draft(
                store,
                domain="slot_schemas",
                payload=store.active_payload("slot_schemas"),
                created_by="admin-1",
            )
            profile_draft = create_current_draft(
                store,
                domain="attribute_resolution_profiles",
                payload=store.active_payload("attribute_resolution_profiles"),
                created_by="admin-1",
            )
            slot_draft = create_current_draft(
                store,
                domain="slot_schemas",
                payload=store.active_payload("slot_schemas"),
                created_by="admin-1",
            )

            result = activate_bundle(store, [slot_draft["draft_id"], profile_draft["draft_id"]])

            self.assertEqual(result["status"], "activated")
            self.assertIsNone(store.get_draft(old_profile["draft_id"]))
            self.assertIsNone(store.get_draft(old_slot_schema["draft_id"]))
            self.assertEqual(store.require_draft(profile_draft["draft_id"])["status"], "activated")
            self.assertEqual(store.require_draft(slot_draft["draft_id"])["status"], "activated")

    def test_delete_invalid_drafts_removes_only_current_operator_domain(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            invalid_current = store.create_draft(
                domain="attribute_resolution_profiles",
                payload=custom_profile_payload(),
                created_by="admin-1",
            )
            valid_current = store.create_draft(
                domain="attribute_resolution_profiles",
                payload=custom_profile_payload(output_slot_id="other_slot"),
                created_by="admin-1",
            )
            invalid_other_operator = store.create_draft(
                domain="attribute_resolution_profiles",
                payload=custom_profile_payload(),
                created_by="other-admin",
            )
            invalid_other_domain = store.create_draft(
                domain="slot_schemas",
                payload=custom_slot_payload(),
                created_by="admin-1",
            )

            for draft_id in (
                invalid_current["draft_id"],
                invalid_other_operator["draft_id"],
                invalid_other_domain["draft_id"],
            ):
                draft = store.require_draft(draft_id)
                draft["status"] = "invalid"
                draft["validation"] = {
                    "schema_version": "1.0",
                    "status": "invalid",
                    "errors": ["test"],
                    "gates": [],
                }
                store._save_draft(draft)

            result = store.delete_invalid_drafts(
                domain="attribute_resolution_profiles",
                operator_id="admin-1",
            )

            self.assertEqual(result["deleted_count"], 1)
            self.assertEqual(result["deleted_draft_ids"], [invalid_current["draft_id"]])
            self.assertIsNone(store.get_draft(invalid_current["draft_id"]))
            self.assertIsNotNone(store.get_draft(valid_current["draft_id"]))
            self.assertIsNotNone(store.get_draft(invalid_other_operator["draft_id"]))
            self.assertIsNotNone(store.get_draft(invalid_other_domain["draft_id"]))

    def test_slot_schema_draft_still_rejects_unknown_profile_id(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            slot_draft = store.create_draft(
                domain="slot_schemas",
                payload=custom_slot_payload(profile_id="profile.custom.missing"),
                created_by="admin-1",
            )

            validated = store.validate_draft(slot_draft["draft_id"])

            self.assertEqual(validated["validation"]["status"], "invalid")
            self.assertTrue(
                any("profile.custom.missing" in error for error in validated["validation"]["errors"]),
                validated["validation"]["errors"],
            )

    def test_slot_schema_draft_rejects_profile_draft_without_output_slot(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            profile_payload = custom_profile_payload(output_slot_id="other_slot")
            create_current_draft(
                store,
                domain="attribute_resolution_profiles",
                payload=profile_payload,
                created_by="admin-1",
            )
            slot_draft = create_current_draft(
                store,
                domain="slot_schemas",
                payload=custom_slot_payload(),
                created_by="admin-1",
            )

            validated = store.validate_draft(slot_draft["draft_id"])

            self.assertEqual(validated["validation"]["status"], "invalid")
            self.assertTrue(
                any("output_slots_order" in error for error in validated["validation"]["errors"]),
                validated["validation"]["errors"],
            )

    def test_slot_schema_draft_ignores_profile_draft_from_other_operator(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            create_current_draft(
                store,
                domain="attribute_resolution_profiles",
                payload=custom_profile_payload(),
                created_by="other-admin",
            )
            slot_draft = create_current_draft(
                store,
                domain="slot_schemas",
                payload=custom_slot_payload(),
                created_by="admin-1",
            )

            validated = store.validate_draft(slot_draft["draft_id"])

            self.assertEqual(validated["validation"]["status"], "invalid")
            self.assertTrue(
                any("profile.custom.attribute_copy" in error for error in validated["validation"]["errors"]),
                validated["validation"]["errors"],
            )


if __name__ == "__main__":
    unittest.main()
