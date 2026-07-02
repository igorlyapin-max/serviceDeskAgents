from __future__ import annotations

import copy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from apps.orchestrator.app.config_assistant import (
    compile_attribute_resolution_step,
)
from apps.orchestrator.app.config_registry import (
    ConfigStore,
    apply_schema_parameter_defaults,
    new_version_id,
    normalize_attribute_resolution_profile,
    operation_response_items,
    resolved_dry_run_parameters,
    utc_now,
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


def wait_for_email_by_ticket_tool() -> dict:
    return {
        "tool_name": "n8n_wait_for_email_by_ticket",
        "display_name": "Дождаться письма по номеру заявки",
        "action_type": "read_only",
        "parameters_schema": {
            "type": "object",
            "required": ["ticket_number"],
            "properties": {
                "ticket_number": {"type": "string", "title": "Номер заявки"},
                "poll_interval_minutes": {"type": "integer", "title": "Интервал опроса"},
                "timeout_minutes": {"type": "integer", "title": "Таймаут"},
            },
        },
        "result_schema": {
            "type": "object",
            "required": ["ticket_number"],
            "properties": {
                "ticket_number": {"type": "string", "title": "Номер заявки"},
                "body": {"type": "string", "title": "Тело письма"},
                "subject": {"type": "string", "title": "Тема письма"},
                "status": {"type": "string", "title": "Статус"},
            },
        },
    }


def wait_for_email_by_ticket_openapi_tool() -> dict:
    tool = copy.deepcopy(wait_for_email_by_ticket_tool())
    tool["parameters_schema"] = {
        "type": "object",
        "required": ["ticket_number", "poll_interval_minutes", "timeout_minutes"],
        "additionalProperties": True,
        "properties": {
            "invocation": {
                "type": "object",
                "additionalProperties": True,
                "title": "invocation",
            },
            "ticket_number": {
                "type": "string",
                "title": "ticket number",
            },
            "ticketNumber": {
                "type": "string",
                "title": "ticketNumber",
                "description": "Alias, принимаемый workflow для ticket_number.",
            },
            "poll_interval_minutes": {
                "type": "integer",
                "title": "poll interval minutes",
            },
            "pollIntervalMinutes": {
                "type": "integer",
                "title": "pollIntervalMinutes",
                "description": "Alias accepted by the workflow for poll_interval_minutes.",
            },
            "timeout_minutes": {
                "type": "integer",
                "title": "timeout minutes",
            },
            "timeoutMinutes": {
                "type": "integer",
                "title": "timeoutMinutes",
                "description": "Alias, принимаемый workflow для timeout_minutes.",
            },
        },
    }
    tool["result_schema"] = {
        "oneOf": [
            {
                "type": "object",
                "required": ["runbook_status", "message", "async_delivery"],
                "properties": {
                    "runbook_status": {"type": "string", "title": "runbook status"},
                    "message": {"type": "string", "title": "message"},
                    "async_delivery": {"type": "boolean", "title": "async delivery"},
                },
            },
            {
                "type": "object",
                "required": ["status", "ticket_number", "match_count"],
                "properties": {
                    "status": {"type": "string", "title": "status"},
                    "ticket_number": {"type": "string", "title": "ticket number"},
                    "body": {"type": ["string", "null"], "title": "body"},
                    "subject": {"type": ["string", "null"], "title": "subject"},
                    "match_count": {"type": "integer", "title": "match count"},
                },
            },
        ]
    }
    return tool


def provider_mail_slot_payload() -> dict:
    return {
        "schema_version": "1.0",
        "slot_schemas": [
            {
                "slot_schema_id": "slot.provider_mail",
                "display_name": "Слоты письма провайдера",
                "stages": [
                    {
                        "stage_id": "stage.provider",
                        "display_name": "Провайдер",
                        "order": 1,
                        "slots": [
                            {
                                "slot_id": "provider_mail_body",
                                "display_name": "Тело письма провайдера",
                                "priority_group": "what",
                                "required": True,
                                "fill_method": "resolution_profile",
                                "resolution_profile_id": "profile.provider_mail",
                            },
                            {
                                "slot_id": "provider_mail_subject",
                                "display_name": "Тема письма провайдера",
                                "priority_group": "what",
                                "required": False,
                                "fill_method": "resolution_profile",
                                "resolution_profile_id": "profile.provider_mail",
                            },
                        ],
                    }
                ],
            }
        ],
    }


def provider_mail_endpoint_payload() -> dict:
    return {
        "schema_version": "1.0",
        "endpoints": [
            {
                "endpoint_id": "mock",
                "display_name": "Mock",
                "adapter_type": "mock",
                "enabled": True,
                "auth": {"type": "none"},
                "operations": {
                    "wait_for_email_by_ticket": {
                        "operation_id": "wait_for_email_by_ticket",
                        "display_name": "Ждать письмо",
                        "method": "POST",
                        "path": "/mock/wait",
                        "timeout_seconds": 30,
                        "contract_status": "valid",
                        "request_schema": {
                            "type": "object",
                            "properties": {
                                "ticket_number": {"type": "string"},
                            },
                            "required": ["ticket_number"],
                            "additionalProperties": True,
                        },
                        "response_schema": wait_for_email_by_ticket_tool()["result_schema"],
                        "mock_output": {
                            "ticket_number": "T-1",
                            "body": "Тело письма",
                            "subject": "Тема письма",
                            "status": "OK",
                        },
                    },
                    "monitor_provider_channel_repair": {
                        "operation_id": "monitor_provider_channel_repair",
                        "display_name": "Мониторить ремонт",
                        "method": "POST",
                        "path": "/mock/monitor",
                        "timeout_seconds": 30,
                        "contract_status": "valid",
                        "request_schema": {
                            "type": "object",
                            "properties": {
                                "host": {"type": "string"},
                            },
                            "required": ["host"],
                            "additionalProperties": True,
                        },
                        "response_schema": {
                            "type": "object",
                            "required": ["runbook_status", "message", "async_delivery"],
                            "properties": {
                                "runbook_status": {"type": "string"},
                                "message": {"type": "string"},
                                "async_delivery": {"type": "boolean"},
                            },
                            "additionalProperties": True,
                        },
                        "mock_output": {
                            "runbook_status": "accepted",
                            "message": "Принято",
                            "async_delivery": True,
                        },
                    },
                },
            }
        ],
    }


def provider_mail_tool_payload() -> dict:
    wait_tool = wait_for_email_by_ticket_tool()
    wait_tool["endpoint_bindings"] = [
        {
            "endpoint_id": "mock",
            "operation_id": "wait_for_email_by_ticket",
            "parameter_mapping": {"ticket_number": "react:ticket_number"},
            "result_mapping": {
                "ticket_number": "ticket_number",
                "body": "body",
                "subject": "subject",
                "status": "status",
            },
        }
    ]
    monitor_tool = {
        "tool_name": "n8n_monitor_provider_channel_repair",
        "display_name": "Мониторить ремонт канала",
        "description": "Тестовый мониторинг ремонта канала.",
        "action_type": "read_only",
        "parameters_schema": {
            "type": "object",
            "required": ["host"],
            "properties": {"host": {"type": "string"}},
            "additionalProperties": True,
        },
        "result_schema": provider_mail_endpoint_payload()["endpoints"][0]["operations"]["monitor_provider_channel_repair"]["response_schema"],
        "endpoint_bindings": [
            {
                "endpoint_id": "mock",
                "operation_id": "monitor_provider_channel_repair",
                "parameter_mapping": {"host": "react:host"},
                "result_mapping": {
                    "runbook_status": "runbook_status",
                    "message": "message",
                    "async_delivery": "async_delivery",
                },
            }
        ],
    }
    return {"schema_version": "1.0", "tools": [wait_tool, monitor_tool]}


def provider_mail_resolution_profile(body_hint: str, subject_hint: str) -> dict:
    return {
        "profile_id": "profile.provider_mail",
        "display_name": "Получить письмо провайдера",
        "status": "active",
        "description": "Проверочный многошаговый профиль.",
        "slot_schema_id": "slot.provider_mail",
        "target_slot_id": "provider_mail_body",
        "use_llm_after_steps": False,
        "enrichment_steps": [
            {
                "step_id": "step1",
                "step_name": "Дождаться письма",
                "react_call": "n8n_wait_for_email_by_ticket",
                "endpoint_id": "mock",
                "operation_id": "wait_for_email_by_ticket",
                "parameter_mapping": {"ticket_number": "constant:T-1"},
                "configuration_instruction": "Дождись письма провайдера.",
                "on_error": "continue_to_llm",
            },
            {
                "step_id": "step2",
                "step_name": "Мониторить ремонт",
                "react_call": "n8n_monitor_provider_channel_repair",
                "endpoint_id": "mock",
                "operation_id": "monitor_provider_channel_repair",
                "parameter_mapping": {"host": "constant:router-1"},
                "configuration_instruction": "Мониторь ремонт канала.",
                "on_error": "continue_to_llm",
            },
        ],
        "output_slots_order": [
            {
                "slot_id": "provider_mail_body",
                "order": 1,
                "required_for_success": True,
                "source_hint": body_hint,
                "fallback": "operator_handoff",
            },
            {
                "slot_id": "provider_mail_subject",
                "order": 2,
                "required_for_success": False,
                "source_hint": subject_hint,
                "fallback": "leave_empty",
            },
        ],
        "llm_resolution_script": {
            "script_text": "Заполни выходные слоты.",
            "response_contract": {
                "decision": "fill",
                "filled_slots": {},
                "confidence": 1,
                "next_question": "",
                "reason": "",
            },
        },
        "human_resolution_policy": {
            "action": "escalate_operator",
            "message_template": "Передайте обращение оператору.",
        },
        "max_attempts": 1,
    }


class ConfigAssistantTest(unittest.TestCase):
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
                "action": "ask_client",
                "message_template": "Уточните пользователя.",
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

    def test_attribute_resolution_profile_normalizes_template_source_hints(self) -> None:
        profile = {
            "profile_id": "profile.custom.attribute_copy",
            "display_name": "Получить письмо провайдера",
            "status": "active",
            "description": "Тест нормализации полей результата.",
            "slot_schema_id": "slot.provider_case",
            "target_slot_id": "provider_mail_body",
            "use_llm_after_steps": False,
            "enrichment_steps": [
                {
                    "step_id": "step1",
                    "step_name": "Дождаться письма",
                    "react_call": "n8n_wait_for_email_by_ticket",
                    "parameter_mapping": {"ticket_number": "case:ticket_id"},
                    "configuration_instruction": (
                        "результат ${paramReAct.n8n_wait_for_email_by_ticket.output.body}-> provider_mail_body "
                        "${paramReAct.n8n_wait_for_email_by_ticket.output.subject} ->provider_mail_subject"
                    ),
                    "on_error": "continue_to_llm",
                }
            ],
            "output_slots_order": [
                {
                    "slot_id": "provider_mail_body",
                    "order": 1,
                    "required_for_success": True,
                    "source_hint": "${paramReAct.n8n_wait_for_email_by_ticket.output.ticket_number}",
                    "fallback": "operator_handoff",
                },
                {
                    "slot_id": "provider_mail_subject",
                    "order": 2,
                    "required_for_success": False,
                    "source_hint": "${step.step1.react.n8n_wait_for_email_by_ticket.output.subject}",
                    "fallback": "leave_empty",
                },
            ],
            "llm_resolution_script": {
                "script_text": "Заполни выходные слоты.",
                "response_contract": {
                    "decision": "fill",
                    "filled_slots": {},
                    "confidence": 1,
                    "next_question": "",
                    "reason": "",
                },
            },
            "human_resolution_policy": {
                "action": "escalate_operator",
                "message_template": "Передайте обращение оператору.",
            },
            "max_attempts": 1,
        }

        normalized = normalize_attribute_resolution_profile(profile)

        self.assertEqual(normalized["output_slots_order"][0]["source_hint"], "body")
        self.assertEqual(normalized["output_slots_order"][1]["source_hint"], "subject")

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

    def test_attribute_resolution_step_explicit_react_overrides_current_and_parses_case_and_constants(self) -> None:
        result = compile_attribute_resolution_step(
            instruction=(
                "Вызови ${ReAct.n8n_wait_for_email_by_ticket}. "
                "${paramReAct.n8n_wait_for_email_by_ticket.input.ticket_number}<-${case.ticket_id}\n"
                "${paramReAct.n8n_wait_for_email_by_ticket.input.poll_interval_minutes}<-1\n"
                "${paramReAct.n8n_wait_for_email_by_ticket.input.timeout_minutes}<-15\n"
                "Результат ${paramReAct.n8n_wait_for_email_by_ticket.output.ticket_number}->${slot.user_login}."
            ),
            slot_schema=password_slot_schema(),
            tools=[get_manager_email_tool(), wait_for_email_by_ticket_tool()],
            react_call="get_manager_email",
        )

        structure = result["structure"]
        self.assertEqual(result["validation_errors"], [])
        self.assertEqual(structure["react_call"], "n8n_wait_for_email_by_ticket")
        self.assertEqual(
            structure["parameter_mapping"],
            {
                "ticket_number": "case:ticket_id",
                "poll_interval_minutes": "constant:1",
                "timeout_minutes": "constant:15",
            },
        )

    def test_attribute_resolution_step_returns_output_mapping_hints_for_plain_slot_targets(self) -> None:
        slot_schema = {
            "slot_schema_id": "slot.provider_case",
            "slots": [
                {"slot_id": "provider_mail_body", "display_name": "Тело письма провайдера"},
                {"slot_id": "provider_mail_subject", "display_name": "Тема письма провайдера"},
            ],
        }

        result = compile_attribute_resolution_step(
            instruction=(
                "Вызови ${ReAct.n8n_wait_for_email_by_ticket}. "
                "${paramReAct.n8n_wait_for_email_by_ticket.input.ticket_number}<-${case.ticket_id}\n"
                "${paramReAct.n8n_wait_for_email_by_ticket.input.poll_interval_minutes}<-1\n"
                "${paramReAct.n8n_wait_for_email_by_ticket.input.timeout_minutes}<-15\n"
                "результат ${paramReAct.n8n_wait_for_email_by_ticket.output.body}-> provider_mail_body "
                "${paramReAct.n8n_wait_for_email_by_ticket.output.subject} ->provider_mail_subject"
            ),
            slot_schema=slot_schema,
            tools=[wait_for_email_by_ticket_tool()],
        )

        self.assertEqual(result["validation_errors"], [])
        self.assertEqual(
            result["references"]["output_mapping_hints"],
            [
                {
                    "target": "provider_mail_body",
                    "field": "body",
                    "source_ref": "${step.step1.react.n8n_wait_for_email_by_ticket.output.body}",
                },
                {
                    "target": "provider_mail_subject",
                    "field": "subject",
                    "source_ref": "${step.step1.react.n8n_wait_for_email_by_ticket.output.subject}",
                },
            ],
        )

    def test_attribute_resolution_step_uses_canonical_react_parameters_and_reads_oneof_result_schema(self) -> None:
        result = compile_attribute_resolution_step(
            instruction=(
                "Вызови ${ReAct.n8n_wait_for_email_by_ticket}. "
                "${paramReAct.n8n_wait_for_email_by_ticket.input.ticket_number}<-${case.ticket_id}\n"
                "${paramReAct.n8n_wait_for_email_by_ticket.input.poll_interval_minutes}<-1\n"
                "${paramReAct.n8n_wait_for_email_by_ticket.input.timeout_minutes}<-15\n"
                "Результат ${paramReAct.n8n_wait_for_email_by_ticket.output.ticket_number}."
            ),
            slot_schema=password_slot_schema(),
            tools=[wait_for_email_by_ticket_openapi_tool()],
        )

        structure = result["structure"]
        result_field_ids = [
            field["field_id"]
            for field in structure["generated_structure_metadata"]["result_fields"]
        ]
        self.assertEqual(result["validation_errors"], [])
        self.assertEqual(
            structure["parameter_mapping"],
            {
                "ticket_number": "case:ticket_id",
                "poll_interval_minutes": "constant:1",
                "timeout_minutes": "constant:15",
            },
        )
        self.assertIn("ticket_number", result_field_ids)
        self.assertIn("status", result_field_ids)
        self.assertIn("runbook_status", result_field_ids)
        self.assertEqual(result["references"]["output_mapping_hints"], [])
        self.assertNotIn("value", result_field_ids)
        self.assertFalse(
            any("Контракт результата ReAct-вызова пустой" in warning for warning in result["warnings"]),
            result["warnings"],
        )
        self.assertFalse(any("invocation" in warning for warning in result["warnings"]), result["warnings"])
        self.assertFalse(any("ticketNumber" in warning for warning in result["warnings"]), result["warnings"])
        self.assertFalse(any("pollIntervalMinutes" in warning for warning in result["warnings"]), result["warnings"])
        self.assertFalse(any("timeoutMinutes" in warning for warning in result["warnings"]), result["warnings"])

    def test_config_store_normalizes_n8n_wait_react_contract_without_endpoint_alias_loss(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            polluted_tool = wait_for_email_by_ticket_openapi_tool()

            endpoints_payload = store.active_payload("integration_endpoints")
            n8n_endpoint = next(item for item in endpoints_payload["endpoints"] if item["endpoint_id"] == "n8n")
            n8n_endpoint["operations"]["wait_for_email_by_ticket"] = {
                "display_name": "Дождаться письма по номеру заявки",
                "description": "Тестовая endpoint-операция с alias-полями OpenAPI.",
                "method": "POST",
                "path": "/webhook/email/wait",
                "request_schema": copy.deepcopy(polluted_tool["parameters_schema"]),
                "response_schema": copy.deepcopy(polluted_tool["result_schema"]),
                "async_event_contracts": {},
                "contract_version": "1.0",
                "contract_status": "valid",
                "timeout_seconds": 30,
            }
            self.force_active_payload(store, "integration_endpoints", endpoints_payload)

            tools_payload = store.active_payload("tools")
            polluted_tool.update(
                {
                    "action_type": "read_only",
                    "endpoint_bindings": [
                        {
                            "endpoint_id": "n8n",
                            "operation_id": "wait_for_email_by_ticket",
                            "parameter_mapping": {
                                "invocation": "react:invocation",
                                "ticket_number": "react:ticket_number",
                                "ticketNumber": "react:ticketNumber",
                                "poll_interval_minutes": "react:poll_interval_minutes",
                                "pollIntervalMinutes": "react:pollIntervalMinutes",
                                "timeout_minutes": "react:timeout_minutes",
                                "timeoutMinutes": "react:timeoutMinutes",
                            },
                            "result_mapping": {
                                "ticket_number": "ticket_number",
                                "status": "status",
                            },
                        }
                    ],
                    "policy": copy.deepcopy(tools_payload["tools"][0]["policy"]),
                    "contract_version": "1.0",
                    "contract_status": "valid",
                }
            )
            tools_payload["tools"].append(polluted_tool)
            self.force_active_payload(store, "tools", tools_payload)

            normalized_tool = next(
                item
                for item in store.active_payload("tools")["tools"]
                if item["tool_name"] == "n8n_wait_for_email_by_ticket"
            )
            normalized_properties = set(normalized_tool["parameters_schema"]["properties"])
            normalized_mapping = normalized_tool["endpoint_bindings"][0]["parameter_mapping"]
            endpoint_operation = next(
                item
                for item in store.active_payload("integration_endpoints")["endpoints"]
                if item["endpoint_id"] == "n8n"
            )["operations"]["wait_for_email_by_ticket"]

        self.assertEqual(
            normalized_properties,
            {"ticket_number", "poll_interval_minutes", "timeout_minutes"},
        )
        self.assertEqual(
            normalized_mapping,
            {
                "ticket_number": "react:ticket_number",
                "poll_interval_minutes": "react:poll_interval_minutes",
                "timeout_minutes": "react:timeout_minutes",
            },
        )
        self.assertIn("ticketNumber", endpoint_operation["request_schema"]["properties"])
        self.assertIn("pollIntervalMinutes", endpoint_operation["request_schema"]["properties"])

    def test_attribute_resolution_step_rejects_multiple_react_calls_in_one_step(self) -> None:
        result = compile_attribute_resolution_step(
            instruction=(
                "Вызови ${ReAct.get_user_login}. "
                "Передай ${slot.user_fio} в ${paramReAct.get_manager_email.input.login}."
            ),
            slot_schema=password_slot_schema(),
            tools=[get_user_login_tool(), get_manager_email_tool()],
        )

        self.assertTrue(
            any("только один ReAct-вызов" in error for error in result["validation_errors"]),
            result["validation_errors"],
        )

    def test_attribute_resolution_step_does_not_create_unknown_output_slot(self) -> None:
        result = compile_attribute_resolution_step(
            instruction=(
                "Вызови ${ReAct.n8n_wait_for_email_by_ticket}. "
                "${paramReAct.n8n_wait_for_email_by_ticket.input.ticket_number}<-${case.ticket_id}. "
                "Результат ${paramReAct.n8n_wait_for_email_by_ticket.output.ticket_number}->${slot.incident_number}."
            ),
            slot_schema=password_slot_schema(),
            tools=[wait_for_email_by_ticket_tool()],
        )

        self.assertTrue(
            any("неизвестный слот: incident_number" in error for error in result["validation_errors"]),
            result["validation_errors"],
        )
        self.assertNotIn("incident_number", [slot["slot_id"] for slot in password_slot_schema()["slots"]])

    def test_resolved_dry_run_parameters_reads_case_fields(self) -> None:
        parameters = resolved_dry_run_parameters(
            {
                "ticket_number": "case:ticket_id",
                "poll_interval_minutes": "constant:1",
            },
            provided={"ticket_id": "SR-42"},
            slot_values={},
            enrichment_step_results={},
        )

        self.assertEqual(parameters["ticket_number"], "SR-42")
        self.assertEqual(parameters["poll_interval_minutes"], "1")

    def test_schema_parameter_defaults_coerce_numeric_constants(self) -> None:
        parameters, applied_defaults = apply_schema_parameter_defaults(
            {
                "type": "object",
                "required": ["poll_interval_minutes", "timeout_minutes"],
                "properties": {
                    "poll_interval_minutes": {"type": "integer"},
                    "timeout_minutes": {"type": "integer", "default": 15},
                },
            },
            {"poll_interval_minutes": "1"},
        )

        self.assertEqual(parameters["poll_interval_minutes"], 1)
        self.assertEqual(parameters["timeout_minutes"], 15)
        self.assertEqual(applied_defaults, {"timeout_minutes": 15})

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

    def test_config_store_accepts_output_hint_from_non_last_step(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            self.force_active_payload(store, "slot_schemas", provider_mail_slot_payload())
            self.force_active_payload(store, "tools", provider_mail_tool_payload())
            self.force_active_payload(store, "integration_endpoints", provider_mail_endpoint_payload())
            profile = provider_mail_resolution_profile(
                body_hint="${step.step1.react.n8n_wait_for_email_by_ticket.output.body}",
                subject_hint="${step.step1.react.n8n_wait_for_email_by_ticket.output.subject}",
            )

            validation = store.validate_payload(
                "attribute_resolution_profiles",
                {"schema_version": "1.0", "profiles": [profile]},
            )

            self.assertEqual(validation["status"], "valid", validation["errors"])

    def test_config_store_rejects_resolution_step_missing_required_react_parameter(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            self.force_active_payload(store, "slot_schemas", provider_mail_slot_payload())
            tools = provider_mail_tool_payload()
            monitor_tool = next(item for item in tools["tools"] if item["tool_name"] == "n8n_monitor_provider_channel_repair")
            monitor_tool["parameters_schema"]["required"] = [
                "host",
                "poll_interval_minutes",
                "timeout_minutes",
            ]
            monitor_tool["parameters_schema"]["properties"]["poll_interval_minutes"] = {"type": "integer"}
            monitor_tool["parameters_schema"]["properties"]["timeout_minutes"] = {"type": "integer"}
            self.force_active_payload(store, "tools", tools)
            self.force_active_payload(store, "integration_endpoints", provider_mail_endpoint_payload())
            profile = provider_mail_resolution_profile(
                body_hint="${step.step1.react.n8n_wait_for_email_by_ticket.output.body}",
                subject_hint="${step.step1.react.n8n_wait_for_email_by_ticket.output.subject}",
            )

            validation = store.validate_payload(
                "attribute_resolution_profiles",
                {"schema_version": "1.0", "profiles": [profile]},
            )

            self.assertEqual(validation["status"], "invalid")
            self.assertTrue(
                any("poll_interval_minutes" in error for error in validation["errors"])
                and any("timeout_minutes" in error for error in validation["errors"]),
                validation["errors"],
            )

    def test_config_store_accepts_resolution_step_required_react_defaults(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            self.force_active_payload(store, "slot_schemas", provider_mail_slot_payload())
            tools = provider_mail_tool_payload()
            monitor_tool = next(item for item in tools["tools"] if item["tool_name"] == "n8n_monitor_provider_channel_repair")
            monitor_tool["parameters_schema"]["required"] = [
                "host",
                "poll_interval_minutes",
                "timeout_minutes",
            ]
            monitor_tool["parameters_schema"]["properties"]["poll_interval_minutes"] = {"type": "integer", "default": 1}
            monitor_tool["parameters_schema"]["properties"]["timeout_minutes"] = {"type": "integer", "default": 15}
            self.force_active_payload(store, "tools", tools)
            self.force_active_payload(store, "integration_endpoints", provider_mail_endpoint_payload())
            profile = provider_mail_resolution_profile(
                body_hint="${step.step1.react.n8n_wait_for_email_by_ticket.output.body}",
                subject_hint="${step.step1.react.n8n_wait_for_email_by_ticket.output.subject}",
            )

            validation = store.validate_payload(
                "attribute_resolution_profiles",
                {"schema_version": "1.0", "profiles": [profile]},
            )
            launch = store._profile_step_launch(
                profile=profile,
                step=profile["enrichment_steps"][1],
                tool_by_name={item["tool_name"]: item for item in tools["tools"]},
                endpoint_by_id={item["endpoint_id"]: item for item in provider_mail_endpoint_payload()["endpoints"]},
                delivery_defaults={},
            )

            self.assertEqual(validation["status"], "valid", validation["errors"])
            self.assertEqual(launch["parameter_bindings"]["poll_interval_minutes"], "constant:1")
            self.assertEqual(launch["parameter_bindings"]["timeout_minutes"], "constant:15")

    def test_config_store_rejects_plain_output_hint_from_wrong_last_step(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            self.force_active_payload(store, "slot_schemas", provider_mail_slot_payload())
            self.force_active_payload(store, "tools", provider_mail_tool_payload())
            self.force_active_payload(store, "integration_endpoints", provider_mail_endpoint_payload())
            profile = provider_mail_resolution_profile(body_hint="ticket_number", subject_hint="subject")

            validation = store.validate_payload(
                "attribute_resolution_profiles",
                {"schema_version": "1.0", "profiles": [profile]},
            )

            self.assertEqual(validation["status"], "invalid")
            output_error = next(
                (
                    error
                    for error in validation["errors"]
                    if "Тема письма провайдера" in error and "subject" in error
                ),
                "",
            )
            self.assertIn('Профиль "Получить письмо провайдера" (profile.provider_mail)', output_error)
            self.assertIn("Выходные слоты и порядок заполнения -> строка 2", output_error)
            self.assertIn('"Тема письма провайдера" (provider_mail_subject)', output_error)
            self.assertIn('шаг 2 "Мониторить ремонт" (step2)', output_error)
            self.assertIn(
                'ReAct-вызов "Мониторить ремонт канала" (n8n_monitor_provider_channel_repair)',
                output_error,
            )
            self.assertIn("Доступные поля результата: async_delivery, message, runbook_status", output_error)

    def test_config_store_validates_output_hint_against_endpoint_response_contract(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            self.force_active_payload(store, "slot_schemas", provider_mail_slot_payload())
            self.force_active_payload(store, "tools", provider_mail_tool_payload())
            endpoints = provider_mail_endpoint_payload()
            endpoints["endpoints"][0]["operations"]["wait_for_email_by_ticket"]["response_schema"] = {
                "type": "object",
                "properties": {},
                "additionalProperties": True,
            }
            self.force_active_payload(store, "integration_endpoints", endpoints)
            profile = provider_mail_resolution_profile(
                body_hint="${step.step1.react.n8n_wait_for_email_by_ticket.output.body}",
                subject_hint="${step.step1.react.n8n_wait_for_email_by_ticket.output.subject}",
            )

            validation = store.validate_payload(
                "attribute_resolution_profiles",
                {"schema_version": "1.0", "profiles": [profile]},
            )

            self.assertEqual(validation["status"], "invalid")
            output_error = next(
                (
                    error
                    for error in validation["errors"]
                    if "Тело письма провайдера" in error and "body" in error
                ),
                "",
            )
            self.assertIn('Профиль "Получить письмо провайдера" (profile.provider_mail)', output_error)
            self.assertIn('шаг 1 "Дождаться письма" (step1)', output_error)
            self.assertIn("контракт не содержит именованных полей", output_error)

    def test_config_store_validates_external_event_output_hint_against_async_contract(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            self.force_active_payload(store, "slot_schemas", provider_mail_slot_payload())
            self.force_active_payload(store, "tools", provider_mail_tool_payload())
            endpoints = provider_mail_endpoint_payload()
            operation = endpoints["endpoints"][0]["operations"]["wait_for_email_by_ticket"]
            operation["response_schema"] = {
                "type": "object",
                "required": ["runbook_status", "async_delivery"],
                "properties": {
                    "runbook_status": {"const": "accepted"},
                    "async_delivery": {"const": True},
                },
                "additionalProperties": True,
            }
            operation["mock_output"] = {
                "runbook_status": "accepted",
                "async_delivery": True,
            }
            operation["async_event_contracts"] = {
                "wait_for_email_by_ticket_completed": {
                    "display_name": "Письмо найдено",
                    "description": "Финальный результат ожидания письма.",
                    "statuses": ["progress", "success", "error", "timeout", "cancelled"],
                    "result_schema": wait_for_email_by_ticket_tool()["result_schema"],
                    "contract_version": "1.0",
                    "contract_status": "valid",
                }
            }
            self.force_active_payload(store, "integration_endpoints", endpoints)
            profile = provider_mail_resolution_profile(
                body_hint="${step.step1.react.n8n_wait_for_email_by_ticket.output.body}",
                subject_hint="${step.step1.react.n8n_wait_for_email_by_ticket.output.subject}",
            )
            profile["enrichment_steps"][0]["completion_policy"] = {
                "mode": "external_event",
                "expected_event_type": "wait_for_email_by_ticket_completed",
                "max_wait_seconds": 900,
                "timeout_action": "escalate_operator",
                "result_transport": "kafka_event",
            }

            validation = store.validate_payload(
                "attribute_resolution_profiles",
                {"schema_version": "1.0", "profiles": [profile]},
            )

            self.assertEqual(validation["status"], "valid", validation["errors"])

    def test_config_store_rejects_external_event_contract_from_other_operation(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            self.force_active_payload(store, "slot_schemas", provider_mail_slot_payload())
            self.force_active_payload(store, "tools", provider_mail_tool_payload())
            endpoints = provider_mail_endpoint_payload()
            endpoints["endpoints"][0]["operations"]["wait_for_email_by_ticket"]["async_event_contracts"] = {
                "wait_for_email_by_ticket_completed": {
                    "display_name": "Письмо найдено",
                    "statuses": ["success", "error", "timeout"],
                    "result_schema": wait_for_email_by_ticket_tool()["result_schema"],
                    "contract_version": "1.0",
                    "contract_status": "valid",
                }
            }
            self.force_active_payload(store, "integration_endpoints", endpoints)
            profile = provider_mail_resolution_profile(
                body_hint="${step.step1.react.n8n_wait_for_email_by_ticket.output.body}",
                subject_hint="${step.step1.react.n8n_wait_for_email_by_ticket.output.subject}",
            )
            profile["enrichment_steps"][1]["completion_policy"] = {
                "mode": "external_event",
                "expected_event_type": "wait_for_email_by_ticket_completed",
                "max_wait_seconds": 900,
                "timeout_action": "escalate_operator",
                "result_transport": "kafka_event",
            }

            validation = store.validate_payload(
                "attribute_resolution_profiles",
                {"schema_version": "1.0", "profiles": [profile]},
            )

            self.assertEqual(validation["status"], "invalid")
            error = next(
                (
                    item
                    for item in validation["errors"]
                    if "wait_for_email_by_ticket_completed" in item
                    and "mock/monitor_provider_channel_repair" in item
                ),
                "",
            )
            self.assertIn("endpoint-операция mock/monitor_provider_channel_repair", error)
            self.assertIn("не содержит async_event_contracts", error)

    def test_attribute_resolution_direct_mapping_reads_output_from_referenced_step(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            self.force_active_payload(store, "slot_schemas", provider_mail_slot_payload())
            self.force_active_payload(store, "tools", provider_mail_tool_payload())
            self.force_active_payload(store, "integration_endpoints", provider_mail_endpoint_payload())
            profile = provider_mail_resolution_profile(
                body_hint="${step.step1.react.n8n_wait_for_email_by_ticket.output.body}",
                subject_hint="${step.step1.react.n8n_wait_for_email_by_ticket.output.subject}",
            )

            result = store.simulate_attribute_resolution_profile(
                profile=profile,
                slot_schema=provider_mail_slot_payload()["slot_schemas"][0],
                provided={},
                simulation_options={
                    "allow_llm": False,
                    "allow_readonly_integrations": True,
                    "allow_mock_integrations": True,
                },
                effective_thresholds={
                    "auto_accept_confidence": 0.85,
                    "clarification_confidence": 0.70,
                    "operator_handoff_confidence": 0.50,
                    "min_extraction_confidence": 0.70,
                },
                execution_trace=[],
                slot_values={},
            )

            self.assertEqual(result["status"], "filled", result)
            self.assertEqual(result["output_values"]["provider_mail_body"], "Тело письма")
            self.assertEqual(result["output_values"]["provider_mail_subject"], "Тема письма")

    def test_attribute_resolution_can_fill_directly_without_llm(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            profile = copy.deepcopy(
                next(
                    item
                    for item in store.active_payload("attribute_resolution_profiles")["profiles"]
                    if item["profile_id"] == "profile.password_reset.login_from_ad"
                )
            )
            profile["use_llm_after_steps"] = False
            slot_schema = next(
                item
                for item in store.active_payload("slot_schemas")["slot_schemas"]
                if item["slot_schema_id"] == "slot.password_reset"
            )
            trace: list[dict] = []

            result = store.simulate_attribute_resolution_profile(
                profile=profile,
                slot_schema=slot_schema,
                provided={},
                simulation_options={
                    "allow_llm": False,
                    "allow_readonly_integrations": True,
                    "allow_mock_integrations": True,
                },
                effective_thresholds={
                    "auto_accept_confidence": 0.85,
                    "clarification_confidence": 0.70,
                    "operator_handoff_confidence": 0.50,
                    "min_extraction_confidence": 0.70,
                },
                execution_trace=trace,
                slot_values={},
            )

            self.assertEqual(result["resolution_mode"], "direct_mapping")
            self.assertIsNone(result["llm_decision"])
            self.assertEqual(result["status"], "filled")
            self.assertEqual(result["output_values"]["user_login"], "ivanov")
            self.assertEqual(result["output_values"]["user_id"], "u-1001")

    def test_attribute_resolution_direct_mapping_can_continue_without_value(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            profile = copy.deepcopy(
                next(
                    item
                    for item in store.active_payload("attribute_resolution_profiles")["profiles"]
                    if item["profile_id"] == "profile.password_reset.login_from_ad"
                )
            )
            profile["use_llm_after_steps"] = False
            profile["output_slots_order"] = [
                {
                    "slot_id": "user_login",
                    "order": 1,
                    "required_for_success": True,
                    "source_hint": "missing_field",
                    "fallback": "leave_empty",
                }
            ]
            slot_schema = next(
                item
                for item in store.active_payload("slot_schemas")["slot_schemas"]
                if item["slot_schema_id"] == "slot.password_reset"
            )

            result = store.simulate_attribute_resolution_profile(
                profile=profile,
                slot_schema=slot_schema,
                provided={},
                simulation_options={
                    "allow_llm": False,
                    "allow_readonly_integrations": True,
                    "allow_mock_integrations": True,
                },
                effective_thresholds={
                    "auto_accept_confidence": 0.85,
                    "clarification_confidence": 0.70,
                    "operator_handoff_confidence": 0.50,
                    "min_extraction_confidence": 0.70,
                },
                execution_trace=[],
                slot_values={},
            )

            self.assertEqual(result["resolution_mode"], "direct_mapping")
            self.assertEqual(result["decision"], "leave_empty")
            self.assertEqual(result["status"], "skipped")
            self.assertEqual(result["output_values"], {})

    def test_attribute_resolution_can_escalate_operator_without_value(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            profile = copy.deepcopy(
                next(
                    item
                    for item in store.active_payload("attribute_resolution_profiles")["profiles"]
                    if item["profile_id"] == "profile.password_reset.login_from_ad"
                )
            )
            profile["use_llm_after_steps"] = False
            profile["human_resolution_policy"] = {
                "action": "escalate_operator",
                "message_template": "Передайте обращение оператору: ${slot.user_fio}.",
            }
            profile["output_slots_order"] = [
                {
                    "slot_id": "user_login",
                    "order": 1,
                    "required_for_success": True,
                    "source_hint": "missing_field",
                    "fallback": "ask_clarification",
                }
            ]
            slot_schema = next(
                item
                for item in store.active_payload("slot_schemas")["slot_schemas"]
                if item["slot_schema_id"] == "slot.password_reset"
            )

            result = store.simulate_attribute_resolution_profile(
                profile=profile,
                slot_schema=slot_schema,
                provided={},
                simulation_options={
                    "allow_llm": False,
                    "allow_readonly_integrations": True,
                    "allow_mock_integrations": True,
                },
                effective_thresholds={
                    "auto_accept_confidence": 0.85,
                    "clarification_confidence": 0.70,
                    "operator_handoff_confidence": 0.50,
                    "min_extraction_confidence": 0.70,
                },
                execution_trace=[],
                slot_values={},
            )

            self.assertEqual(result["decision"], "handoff")
            self.assertEqual(result["status"], "operator_handoff")
            self.assertEqual(result["pending_question"], None)
            self.assertEqual(
                result["resolution_decision"]["handoff_message"],
                "Передайте обращение оператору: ${slot.user_fio}.",
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

    def test_operation_response_items_keeps_root_source_hint_for_top_level_field(self) -> None:
        response_schema = {
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "router_candidates": {
                    "type": "array",
                    "items": {"type": "object", "additionalProperties": True},
                },
                "email_result": {
                    "type": "object",
                    "properties": {"body": {"type": "string"}},
                },
            },
        }

        count, item, summary = operation_response_items(
            {
                "message": "Письмо провайдеру отправлено.",
                "router_candidates": [],
                "email_result": {"body": "ok"},
            },
            response_schema,
            [{"slot_id": "provider_mail_body", "source_hint": "message"}],
        )

        self.assertEqual(count, 1)
        self.assertEqual(item["message"], "Письмо провайдеру отправлено.")
        self.assertEqual(summary["result_path"], "")

    def test_service_scenario_accepts_known_react_call_scope(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            payload = copy.deepcopy(store.active_payload("service_scenarios"))
            tool_name = store.active_payload("tools")["tools"][0]["tool_name"]
            scenario = next(item for item in payload["scenarios"] if item["scenario_id"] == "password_reset")
            scenario["allowed_react_call_names"] = [tool_name]

            validation = store.validate_payload("service_scenarios", payload)

            self.assertEqual(validation["status"], "valid", validation["errors"])

    def test_service_scenario_rejects_unknown_react_call_scope(self) -> None:
        with TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            payload = copy.deepcopy(store.active_payload("service_scenarios"))
            scenario = next(item for item in payload["scenarios"] if item["scenario_id"] == "password_reset")
            scenario["allowed_react_call_names"] = ["missing_react_call"]

            validation = store.validate_payload("service_scenarios", payload)

            self.assertEqual(validation["status"], "invalid")
            self.assertTrue(
                any("missing_react_call" in error and "ReAct-вызов" in error for error in validation["errors"]),
                validation["errors"],
            )


if __name__ == "__main__":
    unittest.main()
