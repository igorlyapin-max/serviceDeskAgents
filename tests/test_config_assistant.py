from __future__ import annotations

import unittest

from apps.orchestrator.app.config_assistant import (
    compile_attribute_resolution_step,
    compile_slot_autofill_profile,
)


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

    def test_attribute_resolution_step_compiles_entity_and_result_contract(self) -> None:
        result = compile_attribute_resolution_step(
            instruction=(
                'Шаг: Найти пользователя в AD. Вызови get_user_login. '
                'В параметр user_fio передай слот "Фамилия Имя Отчество". '
                "Результат сохрани как users. Если ошибка, эскалируй оператору."
            ),
            slot_schema=password_slot_schema(),
            tools=[get_user_login_tool()],
            react_call="get_user_login",
        )

        structure = result["structure"]
        self.assertEqual(result["validation_errors"], [])
        self.assertEqual(structure["step_name"], "Найти пользователя в AD")
        self.assertEqual(structure["parameter_mapping"], {"user_fio": "slot:user_fio"})
        self.assertEqual(structure["result_entity_name"], "users")
        self.assertEqual(structure["on_error"], "escalate_operator")
        self.assertEqual(structure["result_fields"][0]["field_id"], "user_login")

    def test_attribute_resolution_step_uses_previous_entity_reference(self) -> None:
        result = compile_attribute_resolution_step(
            instruction=(
                "Вызови get_manager_email. "
                "В параметр login передай entity:users.0.user_login. "
                "Результат сохрани как manager."
            ),
            slot_schema=password_slot_schema(),
            tools=[get_manager_email_tool()],
            react_call="get_manager_email",
            previous_steps=[{"result_entity_name": "users"}],
        )

        structure = result["structure"]
        self.assertEqual(result["validation_errors"], [])
        self.assertEqual(structure["parameter_mapping"], {"login": "entity:users.0.user_login"})
        self.assertEqual(structure["result_entity_name"], "manager")
        self.assertEqual(structure["result_fields"][0]["field_id"], "manager_email")

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


if __name__ == "__main__":
    unittest.main()
