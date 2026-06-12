from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from apps.orchestrator.app.config_assistant import (
    compile_attribute_resolution_step,
    compile_slot_autofill_profile,
)
from apps.orchestrator.app.config_registry import (
    ConfigStore,
    normalize_attribute_resolution_profile,
    operation_response_items,
)
from apps.orchestrator.app.contracts import ContractRegistry


def password_slot_schema() -> dict:
    return {
        "slot_schema_id": "slot.password_reset",
        "scenario_id": "password_reset",
        "slots": [
            {
                "slot_id": "user_fio",
                "display_name": "Фамилия Имя Отчество",
                "required": True,
            },
            {
                "slot_id": "user_login",
                "display_name": "Логин пользователя",
                "required": True,
            },
        ],
    }


def get_user_login_tool() -> dict:
    return {
        "tool_name": "get_user_login",
        "display_name": "Найти логин пользователя",
        "action_type": "read_only",
        "parameters_schema": {
            "type": "object",
            "required": ["user_fio"],
            "properties": {
                "user_fio": {
                    "type": "string",
                    "title": "ФИО пользователя",
                }
            },
        },
        "result_schema": {
            "type": "object",
            "required": ["user_login"],
            "properties": {
                "user_login": {
                    "type": "string",
                    "title": "Логин пользователя",
                }
            },
        },
    }


def get_manager_email_tool() -> dict:
    return {
        "tool_name": "get_manager_email",
        "display_name": "Найти email руководителя",
        "action_type": "read_only",
        "parameters_schema": {
            "type": "object",
            "required": ["login"],
            "properties": {
                "login": {
                    "type": "string",
                    "title": "Логин пользователя",
                }
            },
        },
        "result_schema": {
            "type": "object",
            "required": ["manager_email"],
            "properties": {
                "manager_email": {
                    "type": "string",
                    "title": "Email руководителя",
                }
            },
        },
    }


class ConfigAssistantTest(unittest.TestCase):
    def test_slot_autofill_compiles_input_and_output_mapping_from_instruction(self) -> None:
        result = compile_slot_autofill_profile(
            instruction=(
                'Вызови get_user_login. В параметр user_fio передай слот "Фамилия Имя Отчество". '
                'Если результат единственный, заполни слот "Логин пользователя" из поля результата user_login.'
            ),
            slot_schema=password_slot_schema(),
            tools=[get_user_login_tool()],
            react_call="get_user_login",
        )

        structure = result["structure"]
        self.assertEqual(result["validation_errors"], [])
        self.assertEqual(structure["react_call"], "get_user_login")
        self.assertEqual(structure["accept_policy"], "single_result")
        self.assertNotIn("run_order", structure)
        self.assertEqual(structure["input_mapping"], {"user_fio": "slot:user_fio"})
        self.assertEqual(
            structure["output_mapping"],
            [{"result_field": "user_login", "target_slot": "user_login", "required_for_success": True}],
        )

    def test_slot_autofill_reports_required_parameter_without_source(self) -> None:
        tool = get_user_login_tool()
        tool["parameters_schema"]["required"] = ["employee_number"]
        tool["parameters_schema"]["properties"] = {"employee_number": {"type": "string"}}

        result = compile_slot_autofill_profile(
            instruction='Вызови get_user_login и заполни слот "Логин пользователя" из user_login.',
            slot_schema=password_slot_schema(),
            tools=[tool],
            react_call="get_user_login",
        )

        self.assertTrue(
            any("employee_number" in error for error in result["validation_errors"]),
            result["validation_errors"],
        )

    def test_slot_autofill_compiles_failure_actions_from_scoped_clauses(self) -> None:
        result = compile_slot_autofill_profile(
            instruction=(
                "ReAct-вызов: get_user_login. Входы: user_fio <- slot:user_fio. "
                "Выходы: user_login <- user_login (обязательно). "
                "Нет результата: продолжить сценарий. "
                "Несколько результатов: эскалировать оператору."
            ),
            slot_schema=password_slot_schema(),
            tools=[get_user_login_tool()],
            react_call="get_user_login",
        )

        structure = result["structure"]
        self.assertEqual(result["validation_errors"], [])
        self.assertEqual(structure["input_mapping"], {"user_fio": "slot:user_fio"})
        self.assertEqual(
            structure["output_mapping"],
            [{"result_field": "user_login", "target_slot": "user_login", "required_for_success": True}],
        )
        self.assertEqual(structure["on_no_result"], "continue")
        self.assertEqual(structure["on_ambiguous_result"], "operator_handoff")

    def test_slot_autofill_compiles_template_reference_tokens(self) -> None:
        result = compile_slot_autofill_profile(
            instruction=(
                "Вызови ${ReAct.get_user_login}. "
                "Передай ${slot.user_fio} в ${paramReAct.get_user_login.input.user_fio}. "
                "Заполни ${slot.user_login} из ${paramReAct.get_user_login.output.user_login}. "
                "Если результат единственный, используй значение."
            ),
            slot_schema=password_slot_schema(),
            tools=[get_user_login_tool()],
        )

        structure = result["structure"]
        self.assertEqual(result["validation_errors"], [])
        self.assertEqual(structure["react_call"], "get_user_login")
        self.assertEqual(structure["input_mapping"], {"user_fio": "slot:user_fio"})
        self.assertEqual(
            structure["output_mapping"],
            [{"result_field": "user_login", "target_slot": "user_login", "required_for_success": True}],
        )

    def test_slot_autofill_reports_unknown_template_slot(self) -> None:
        result = compile_slot_autofill_profile(
            instruction=(
                "Вызови ${ReAct.get_user_login}. "
                "Передай ${slot.missing_user} в ${paramReAct.get_user_login.input.user_fio}. "
                "Заполни ${slot.user_login} из ${paramReAct.get_user_login.output.user_login}."
            ),
            slot_schema=password_slot_schema(),
            tools=[get_user_login_tool()],
        )

        self.assertTrue(any("missing_user" in error for error in result["validation_errors"]))

    def test_slot_autofill_rejects_short_template_parameter_reference(self) -> None:
        result = compile_slot_autofill_profile(
            instruction=(
                "Вызови ${ReAct.get_user_login}. "
                "Передай ${slot.user_fio} в ${paramReAct.input.user_fio}. "
                "Заполни ${slot.user_login} из ${paramReAct.output.user_login}."
            ),
            slot_schema=password_slot_schema(),
            tools=[get_user_login_tool()],
        )

        self.assertTrue(any("короткую форму" in error for error in result["validation_errors"]))

    def test_slot_autofill_compiles_no_result_operator_handoff(self) -> None:
        result = compile_slot_autofill_profile(
            instruction=(
                'Вызови get_user_login. В параметр user_fio передай слот "Фамилия Имя Отчество". '
                'Выходы: user_login <- user_login. Нет результата: эскалировать оператору.'
            ),
            slot_schema=password_slot_schema(),
            tools=[get_user_login_tool()],
            react_call="get_user_login",
        )

        self.assertEqual(result["validation_errors"], [])
        self.assertEqual(result["structure"]["on_no_result"], "operator_handoff")

    def test_slot_autofill_compiles_run_order_from_instruction(self) -> None:
        result = compile_slot_autofill_profile(
            instruction=(
                "ReAct-вызов: get_user_login. Порядок запуска 4. "
                "Входы: user_fio <- slot:user_fio. Выходы: user_login <- user_login."
            ),
            slot_schema=password_slot_schema(),
            tools=[get_user_login_tool()],
            react_call="get_user_login",
        )

        self.assertEqual(result["validation_errors"], [])
        self.assertEqual(result["warnings"], [])
        self.assertEqual(result["structure"]["run_order"], 4)

    def test_slot_autofill_rejects_run_order_outside_ui_range(self) -> None:
        result = compile_slot_autofill_profile(
            instruction=(
                "ReAct-вызов: get_user_login. run_order: 101. "
                "Входы: user_fio <- slot:user_fio. Выходы: user_login <- user_login."
            ),
            slot_schema=password_slot_schema(),
            tools=[get_user_login_tool()],
            react_call="get_user_login",
        )

        self.assertEqual(result["validation_errors"], [])
        self.assertNotIn("run_order", result["structure"])
        self.assertTrue(any("Порядок запуска 101 вне диапазона 1..100" in warning for warning in result["warnings"]))

    def test_attribute_resolution_step_compiles_step_and_result_contract(self) -> None:
        result = compile_attribute_resolution_step(
            instruction=(
                'Шаг: Найти пользователя в AD. Вызови get_user_login. '
                'В параметр user_fio передай слот "Фамилия Имя Отчество". '
                "Если ошибка, эскалируй оператору."
            ),
            slot_schema=password_slot_schema(),
            tools=[get_user_login_tool()],
            react_call="get_user_login",
        )

        structure = result["structure"]
        self.assertEqual(result["validation_errors"], [])
        self.assertEqual(structure["step_name"], "Найти пользователя в AD")
        self.assertEqual(structure["parameter_mapping"], {"user_fio": "slot:user_fio"})
        self.assertNotIn("result_entity_name", structure)
        self.assertEqual(structure["on_error"], "escalate_operator")
        self.assertEqual(structure["generated_structure_metadata"]["result_fields"][0]["field_id"], "user_login")
        self.assertNotIn("result_fields", structure)

    def test_attribute_resolution_step_rejects_legacy_entity_reference(self) -> None:
        result = compile_attribute_resolution_step(
            instruction=(
                "Вызови get_manager_email. "
                "В параметр login передай entity:users.0.user_login. "
                "Если ошибка, эскалируй оператору."
            ),
            slot_schema=password_slot_schema(),
            tools=[get_manager_email_tool()],
            react_call="get_manager_email",
            previous_steps=[{
                "step_id": "step1",
                "react_call": "get_user_login",
            }],
        )

        structure = result["structure"]
        self.assertTrue(any("entity:<name>" in error for error in result["validation_errors"]))
        self.assertFalse(any(value.startswith("entity:") for value in structure["parameter_mapping"].values()))
        self.assertNotIn("result_entity_name", structure)

    def test_attribute_resolution_profile_migrates_legacy_entity_references(self) -> None:
        profile = {
            "profile_id": "profile.password.login",
            "display_name": "Поиск логина",
            "status": "active",
            "description": "Тестовый профиль разрешения атрибута.",
            "slot_schema_id": "slot.password_reset",
            "target_slot_id": "manager_email",
            "enrichment_steps": [
                {
                    "step_id": "step1",
                    "step_name": "Найти пользователя",
                    "react_call": "get_user_login",
                    "parameter_mapping": {"user_fio": "slot:user_fio"},
                    "result_entity_name": "users",
                    "result_entity_description": "Пользователи AD.",
                    "on_error": "continue_to_llm",
                },
                {
                    "step_id": "step2",
                    "step_name": "Найти руководителя",
                    "react_call": "get_manager_email",
                    "parameter_mapping": {"login": "entity:users.0.user_login"},
                    "on_error": "continue_to_llm",
                },
            ],
            "output_slots_order": [
                {
                    "slot_id": "manager_email",
                    "order": 1,
                    "required_for_success": True,
                    "source_hint": "manager_email",
                    "fallback": "ask_clarification",
                }
            ],
            "llm_resolution_script": {
                "script_text": "Используй ${entity.users.0.user_login} и entity:users.user_id.",
                "response_contract": {
                    "decision": "fill",
                    "filled_slots": {},
                    "confidence": 1,
                    "next_question": "",
                    "reason": "",
                },
            },
            "human_resolution_policy": {
                "clarification_question": "Уточните пользователя.",
                "clarification_slots": ["user_fio"],
                "handoff_package": ["user_fio", "manager_email"],
                "handoff_action": "operator_handoff",
                "fallback_action": "operator_handoff",
            },
            "max_attempts": 1,
        }

        normalized = normalize_attribute_resolution_profile(profile)

        self.assertNotIn("result_entity_name", normalized["enrichment_steps"][0])
        self.assertEqual(
            normalized["enrichment_steps"][1]["parameter_mapping"],
            {"login": "step:step1.react.get_user_login.output.users.0.user_login"},
        )
        self.assertIn(
            "${step.step1.react.get_user_login.output.users.0.user_login}",
            normalized["llm_resolution_script"]["script_text"],
        )
        self.assertIn(
            "step:step1.react.get_user_login.output.users.user_id",
            normalized["llm_resolution_script"]["script_text"],
        )
        self.assertNotIn("entity:", normalized["llm_resolution_script"]["script_text"])

    def test_attribute_resolution_step_compiles_step_reference_token(self) -> None:
        result = compile_attribute_resolution_step(
            instruction=(
                "Шаг: Найти руководителя. Вызови ${ReAct.get_manager_email}. "
                "Передай ${step.step1.react.get_user_login.output.user_login} "
                "в ${paramReAct.get_manager_email.input.login}. "
                "Результат сохрани как manager."
            ),
            slot_schema=password_slot_schema(),
            tools=[get_user_login_tool(), get_manager_email_tool()],
            previous_steps=[{
                "step_id": "step1",
                "step_name": "Найти пользователя",
                "react_call": "get_user_login",
            }],
        )

        structure = result["structure"]
        self.assertEqual(result["validation_errors"], [])
        self.assertEqual(structure["step_id"], "step2")
        self.assertEqual(
            structure["parameter_mapping"],
            {"login": "step:step1.react.get_user_login.output.user_login"},
        )
        self.assertNotIn("result_entity_name", structure)

    def test_attribute_resolution_step_compiles_template_reference_tokens(self) -> None:
        result = compile_attribute_resolution_step(
            instruction=(
                "Шаг: Найти руководителя. Вызови ${ReAct.get_manager_email}. "
                "Передай ${step.step1.react.get_user_login.output.0.user_login} "
                "в ${paramReAct.get_manager_email.input.login}. "
                "Если ошибка, эскалируй оператору."
            ),
            slot_schema=password_slot_schema(),
            tools=[get_user_login_tool(), get_manager_email_tool()],
            previous_steps=[{
                "step_id": "step1",
                "react_call": "get_user_login",
            }],
        )

        structure = result["structure"]
        self.assertEqual(result["validation_errors"], [])
        self.assertEqual(structure["react_call"], "get_manager_email")
        self.assertEqual(structure["parameter_mapping"], {"login": "step:step1.react.get_user_login.output.0.user_login"})
        self.assertNotIn("result_entity_name", structure)

    def test_attribute_resolution_step_infers_react_call_from_parameter_reference(self) -> None:
        result = compile_attribute_resolution_step(
            instruction=(
                "Шаг: Найти руководителя. "
                "Передай ${step.step1.react.get_user_login.output.user_login} "
                "в ${paramReAct.get_manager_email.input.login}. "
                "Если ошибка, эскалируй оператору."
            ),
            slot_schema=password_slot_schema(),
            tools=[get_user_login_tool(), get_manager_email_tool()],
            previous_steps=[{"step_id": "step1", "react_call": "get_user_login"}],
        )

        structure = result["structure"]
        self.assertEqual(result["validation_errors"], [])
        self.assertEqual(structure["react_call"], "get_manager_email")
        self.assertEqual(structure["parameter_mapping"], {"login": "step:step1.react.get_user_login.output.user_login"})

    def test_attribute_resolution_step_rejects_parameter_reference_from_other_react_call(self) -> None:
        result = compile_attribute_resolution_step(
            instruction=(
                "Шаг: Найти руководителя. Вызови ${ReAct.get_manager_email}. "
                "Передай ${slot.user_fio} в ${paramReAct.get_user_login.input.user_fio}. "
                "Результат сохрани как manager."
            ),
            slot_schema=password_slot_schema(),
            tools=[get_user_login_tool(), get_manager_email_tool()],
        )

        self.assertTrue(any("текущий профиль/шаг использует get_manager_email" in error for error in result["validation_errors"]))

    def test_explicit_unknown_react_call_is_not_replaced_by_first_tool(self) -> None:
        result = compile_attribute_resolution_step(
            instruction="Вызови missing_call и сохрани результат как users.",
            slot_schema=password_slot_schema(),
            tools=[get_user_login_tool()],
            react_call="missing_call",
        )

        self.assertEqual(result["structure"]["react_call"], "missing_call")
        self.assertTrue(result["validation_errors"])
        self.assertEqual(result["references"]["input_parameters"], [])

    def test_config_store_rejects_unknown_step_output_field(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            payload = store.active_payload("attribute_resolution_profiles")
            profile = next(item for item in payload["profiles"] if item["profile_id"] == "profile.password_reset.login_from_ad")
            profile["enrichment_steps"].append(
                {
                    "step_id": "step2",
                    "step_name": "Повторный поиск",
                    "react_call": "search_ad_users",
                    "parameter_mapping": {
                        "login": "step:step1.react.search_ad_users.output.no_such_field"
                    },
                    "on_error": "continue_to_llm",
                }
            )

            validation = store.validate_payload("attribute_resolution_profiles", payload)

            self.assertEqual(validation["status"], "invalid")
            self.assertTrue(
                any("no_such_field" in error for error in validation["errors"]),
                validation["errors"],
            )

    def test_config_store_rejects_slot_from_other_schema(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            payload = store.active_payload("attribute_resolution_profiles")
            profile = next(item for item in payload["profiles"] if item["profile_id"] == "profile.password_reset.login_from_ad")
            profile["enrichment_steps"][0]["parameter_mapping"]["login"] = "slot:device_name"

            validation = store.validate_payload("attribute_resolution_profiles", payload)

            self.assertEqual(validation["status"], "invalid")
            self.assertTrue(
                any("device_name" in error and "выбранной схемы" in error for error in validation["errors"]),
                validation["errors"],
            )

    def test_operation_response_items_requires_selector_for_ambiguous_containers(self) -> None:
        response_schema = {
            "type": "object",
            "properties": {
                "users": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
                "groups": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            },
        }

        count, item, summary = operation_response_items(
            {"users": [{"login": "ivanov"}], "groups": [{"name": "admins"}]},
            response_schema,
            [{"slot_id": "user_login", "source_hint": "login"}],
        )

        self.assertEqual(count, -1)
        self.assertIsNone(item)
        self.assertEqual(summary["source_status"], "configuration_error")

    def test_operation_response_items_uses_source_hint_container(self) -> None:
        response_schema = {
            "type": "object",
            "properties": {
                "users": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
                "groups": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            },
        }

        count, item, summary = operation_response_items(
            {"users": [{"login": "ivanov"}], "groups": [{"name": "admins"}]},
            response_schema,
            [{"slot_id": "user_login", "source_hint": "users.login"}],
        )

        self.assertEqual(count, 1)
        self.assertEqual(item, {"login": "ivanov"})
        self.assertEqual(summary["result_path"], "users")


if __name__ == "__main__":
    unittest.main()
