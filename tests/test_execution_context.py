from __future__ import annotations

import unittest

from apps.orchestrator.app.execution_context import (
    build_execution_reference_context,
    render_template,
    validate_template_refs,
)


def slot_schema() -> dict:
    return {
        "slots": [
            {"slot_id": "user_fio", "display_name": "ФИО"},
            {"slot_id": "user_login", "display_name": "Логин"},
        ]
    }


def react_tools() -> list[dict]:
    return [
        {
            "tool_name": "get_user_login",
            "parameters_schema": {
                "type": "object",
                "properties": {"user_fio": {"type": "string"}},
            },
            "result_schema": {
                "type": "object",
                "properties": {"user_login": {"type": "string"}},
            },
        },
        {
            "tool_name": "get_manager_email",
            "parameters_schema": {
                "type": "object",
                "properties": {"login": {"type": "string"}},
            },
            "result_schema": {
                "type": "object",
                "properties": {"manager_email": {"type": "string"}},
            },
        },
    ]


class ExecutionContextTest(unittest.TestCase):
    def test_validate_refs_accepts_runtime_namespaces(self) -> None:
        context = build_execution_reference_context(
            slot_schema=slot_schema(),
            output_slots=["user_login"],
            tools=react_tools(),
            steps=[{"step_id": "step1", "react_call": "get_user_login"}],
        )

        errors = validate_template_refs(
            (
                "Слот ${slot.user_fio}; "
                "первый результат ${step.step1.react.get_user_login.output.0.user_login}; "
                "результат ${step.step1.react.get_user_login.output.user_login}; "
                "case ${case.scenario_id}; wait ${wait.correlation_id}; "
                "этап ${stage.5.final_decision}."
            ),
            context,
            label="test",
        )

        self.assertEqual(errors, [])

    def test_validate_refs_rejects_legacy_entity_and_future_step(self) -> None:
        context = build_execution_reference_context(
            slot_schema=slot_schema(),
            output_slots=["user_login"],
            tools=react_tools(),
            steps=[
                {"step_id": "step1", "react_call": "get_user_login"},
                {"step_id": "step2", "react_call": "get_manager_email"},
            ],
            allowed_steps=[{"step_id": "step1", "react_call": "get_user_login"}],
        )

        errors = validate_template_refs(
            (
                "legacy ${entity.users.login}; "
                "future ${step.step2.react.get_manager_email.output.manager_email}"
            ),
            context,
            label="profile.step",
        )

        self.assertTrue(any("entity" in error for error in errors))
        self.assertTrue(any("недоступный предыдущий шаг" in error for error in errors))

    def test_render_template_uses_public_runtime_values(self) -> None:
        rendered = render_template(
            "Логин ${slot.user_login}; секрет ${case.api_token}; итог ${stage.5.final_decision}",
            {
                "slot": {"user_login": {"value": "ivanov", "status": "filled"}},
                "case": {"api_token": "secret-token"},
                "stage": {"5": {"final_decision": "ready_for_react"}},
            },
        )

        self.assertEqual(rendered, "Логин ivanov; секрет ; итог ready_for_react")


if __name__ == "__main__":
    unittest.main()
