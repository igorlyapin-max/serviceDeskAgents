from __future__ import annotations

import unittest

from apps.orchestrator.app.execution_context import (
    build_execution_reference_context,
    build_simulation_variable_context,
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


def capabilities() -> list[dict]:
    return [
        {
            "capability_id": "get_user_login",
            "input_schema": {
                "type": "object",
                "properties": {"user_fio": {"type": "string"}},
            },
            "output_schema": {
                "type": "object",
                "properties": {"user_login": {"type": "string"}},
            },
        },
        {
            "capability_id": "get_manager_email",
            "input_schema": {
                "type": "object",
                "properties": {"login": {"type": "string"}},
            },
            "output_schema": {
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
            capabilities=capabilities(),
            steps=[{"step_id": "step1", "capability_id": "get_user_login"}],
            channels=[
                {
                    "channel_id": "service_desk",
                    "display_name": "Сервисдеск",
                    "mode": "offline_interactive",
                    "technical_profile": {
                        "transport": "kafka",
                        "task_topic": "public.ittask.serviceDeskL1.task",
                    },
                    "channel_parameters": [
                        {"parameter_id": "task_key", "display_name": "Ключ задачи"},
                    ],
                }
            ],
        )

        errors = validate_template_refs(
            (
                "Слот ${slot.user_fio}; "
                "первый результат ${step.step1.capability.get_user_login.output.0.user_login}; "
                "результат ${step.step1.capability.get_user_login.output.user_login}; "
                "case ${case.scenario_id}; wait ${wait.correlation_id}; "
                "канал ${channel.service_desk.task_topic}; ключ ${channel.service_desk.task_key}; "
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
            capabilities=capabilities(),
            steps=[
                {"step_id": "step1", "capability_id": "get_user_login"},
                {"step_id": "step2", "capability_id": "get_manager_email"},
            ],
            allowed_steps=[{"step_id": "step1", "capability_id": "get_user_login"}],
        )

        errors = validate_template_refs(
            (
                "legacy ${entity.users.login}; "
                "future ${step.step2.capability.get_manager_email.output.manager_email}"
            ),
            context,
            label="profile.step",
        )

        self.assertTrue(any("entity" in error for error in errors))
        self.assertTrue(any("недоступный предыдущий шаг" in error for error in errors))

    def test_validate_refs_rejects_unknown_contract_namespaces(self) -> None:
        context = build_execution_reference_context(
            slot_schema=slot_schema(),
            output_slots=["user_login"],
            capabilities=capabilities(),
            steps=[{"step_id": "step1", "capability_id": "get_user_login"}],
        )

        errors = validate_template_refs(
            "${OldContract.get_user_login} ${paramOld.get_user_login.output.user_login} "
            "${step.step1.operation.get_user_login.output.user_login}",
            context,
            label="profile.step",
        )

        self.assertGreaterEqual(len(errors), 3)

    def test_render_template_uses_public_runtime_values(self) -> None:
        rendered = render_template(
            "Логин ${slot.user_login}; секрет ${case.api_token}; итог ${stage.5.final_decision}",
            {
                "slot": {"user_login": {"value": "ivanov", "status": "filled"}},
                "case": {"api_token": "secret-token"},
                "stage": {"5": {"final_decision": "ready_for_capability"}},
            },
        )

        self.assertEqual(rendered, "Логин ivanov; секрет ; итог ready_for_capability")

    def test_render_template_uses_channel_values(self) -> None:
        rendered = render_template(
            "Topic ${channel.service_desk.task_topic}; key ${channel.service_desk.task_key}",
            {
                "channel": {
                    "service_desk": {
                        "task_topic": "public.ittask.serviceDeskL1.task",
                        "task_key": "IT-42",
                    }
                }
            },
        )

        self.assertEqual(rendered, "Topic public.ittask.serviceDeskL1.task; key IT-42")

    def test_simulation_context_exposes_channel_parameters(self) -> None:
        context = build_simulation_variable_context(
            scenario_id="password_reset",
            input_text="Сбросить пароль Иванову.",
            slot_values={},
            resolution_state={},
            classification={"priority": "P3"},
            ready_tool_launches=[],
            blocked_tool_launches=[],
            planned_waits=[{"correlation_id": "OPERU-42"}],
            final_decision="waiting_external_event",
            interaction_channel={
                "channel_id": "service_desk",
                "display_name": "Сервисдеск",
                "mode": "offline_interactive",
                "technical_profile": {
                    "transport": "kafka",
                    "task_topic": "public.ittask.serviceDeskL1.task",
                    "result_topic": "public.ittask.result",
                    "api_token": "secret-token",
                },
                "channel_parameters": [
                    {
                        "parameter_id": "task_topic",
                        "source": "technical_profile.task_topic",
                    },
                    {
                        "parameter_id": "task_key",
                        "source": "kafka.message_key",
                    },
                    {
                        "parameter_id": "hidden_token",
                        "source": "technical_profile.api_token",
                        "secret": True,
                    },
                ],
            },
        )

        rendered = render_template(
            (
                "Topic ${channel.service_desk.task_topic}; "
                "key ${channel.service_desk.task_key}; "
                "token ${channel.service_desk.hidden_token}; "
                "api ${channel.service_desk.api_token}"
            ),
            context,
        )

        self.assertEqual(rendered, "Topic public.ittask.serviceDeskL1.task; key OPERU-42; token ; api ")

    def test_simulation_context_applies_channel_parameter_overrides(self) -> None:
        context = build_simulation_variable_context(
            scenario_id="password_reset",
            input_text="Сбросить пароль Иванову.",
            slot_values={},
            resolution_state={},
            classification={"priority": "P3"},
            ready_tool_launches=[],
            blocked_tool_launches=[],
            planned_waits=[{"correlation_id": "OPERU-42"}],
            final_decision="waiting_external_event",
            interaction_channel={
                "channel_id": "service_desk",
                "display_name": "Сервисдеск",
                "mode": "offline_interactive",
                "technical_profile": {
                    "transport": "kafka",
                    "task_topic": "public.ittask.serviceDeskL1.task",
                    "result_topic": "public.ittask.result",
                    "api_token": "secret-token",
                },
                "channel_parameters": [
                    {"parameter_id": "task_key", "source": "kafka.message_key"},
                    {"parameter_id": "task_number", "source": "kafka.message_key"},
                    {"parameter_id": "result_message", "source": "TaskResultMessage"},
                    {"parameter_id": "api_token", "source": "technical_profile.api_token", "secret": True},
                ],
            },
            channel_parameter_values={
                "task_key": "OPERU-99",
                "result_message": "Выполнено в ServiceDesk",
                "api_token": "must-not-render",
            },
        )

        rendered = render_template(
            (
                "key ${channel.service_desk.task_key}; "
                "number ${channel.service_desk.task_number}; "
                "result ${channel.service_desk.result_message}; "
                "api ${channel.service_desk.api_token}"
            ),
            context,
        )

        self.assertEqual(
            rendered,
            "key OPERU-99; number OPERU-99; result Выполнено в ServiceDesk; api ",
        )


if __name__ == "__main__":
    unittest.main()
