from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from apps.orchestrator.app.config_assistant import build_capability_step_assist_prompt, compile_attribute_resolution_step
from apps.orchestrator.app.config_registry import ConfigStore
from apps.orchestrator.app.contracts import ContractRegistry


def slot_schema() -> dict:
    return {
        "slot_schema_id": "slot.provider_channel_repair",
        "slots": [
            {
                "slot_id": "problem_url",
                "display_name": "Ссылка на проблему",
                "description": "URL исходной проблемы мониторинга.",
            },
            {
                "slot_id": "zabbix_url",
                "display_name": "Ссылка Zabbix",
                "description": "URL события Zabbix из письма мониторинга.",
                "extraction_instruction": "Извлеки Original problem URL.",
                "examples": ["Original problem: http://zabbix/tr_events.php?eventid=1"],
            },
            {"slot_id": "host", "display_name": "Хост", "description": "Имя проблемного роутера."},
            {"slot_id": "provider_mail_body", "display_name": "Тело письма провайдера"},
        ],
    }


def capability() -> dict:
    return {
        "capability_id": "provider_channel_repair_monitor",
        "display_name": "Мониторинг ремонта канала провайдера",
        "status": "active",
        "description": "Запускает внешний MCP исполнитель и возвращает результат провайдера.",
        "contract_version": "1.0",
        "execution_modes": ["async"],
        "input_schema": {
            "type": "object",
            "required": ["problem_url", "service_request"],
            "properties": {
                "problem_url": {"type": "string", "description": "URL проблемы в Zabbix."},
                "service_request": {"type": "string", "description": "Номер обращения ServiceDesk."},
                "problem_host": {"type": "string", "description": "Host/router identifier."},
                "from": {"type": "string"},
                "reply_to": {"type": "string"},
                "poll_interval_minutes": {"type": "integer", "default": 1, "minimum": 1},
                "timeout_minutes": {"type": "integer", "default": 20, "minimum": 1},
            },
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "provider_mail_body": {"type": "string"},
                "provider_mail_subject": {"type": "string"},
                "provider_ticket_number": {"type": "string"},
                "polling_diagnostic": {"type": "object"},
                "zabbix_status": {"type": "string"},
            },
        },
        "async_event_contracts": {
            "provider_channel_repair_monitor.completed": {
                "statuses": ["success", "error", "timeout", "cancelled", "progress"],
                "result_schema": {
                    "type": "object",
                    "properties": {
                        "provider_mail_body": {"type": "string"},
                    },
                },
            }
        },
        "default_completion_policy": {
            "mode": "external_event",
            "expected_event_type": "provider_channel_repair_monitor.completed",
            "timeout_action": "escalate_operator",
            "max_wait_seconds": 3600,
        },
    }


def binding() -> dict:
    return {
        "binding_id": "binding.provider_channel_repair_monitor.mcp_provider_ops",
        "capability_id": "provider_channel_repair_monitor",
        "environment_id": "mcp.provider_ops",
        "status": "active",
        "execution_mode": "async",
        "mcp_tool_name": "provider.channel.repair.monitor",
        "input_mapping": {
            "problem_url": "problem_url",
            "service_request": "service_request",
            "problem_host": "problem_host",
            "from": "from",
            "reply_to": "reply_to",
            "poll_interval_minutes": "poll_interval_minutes",
            "timeout_minutes": "timeout_minutes",
        },
        "output_mapping": {
            "provider_mail_body": "provider_mail_body",
        },
    }


def zabbix_wait_capability() -> dict:
    return {
        "capability_id": "zabbix_problem_status_wait",
        "display_name": "Ожидание восстановления проблемы Zabbix",
        "status": "active",
        "description": "Ожидает восстановления проблемы Zabbix.",
        "contract_version": "1.0",
        "execution_modes": ["async"],
        "input_schema": {
            "type": "object",
            "required": ["problem_url", "poll_interval_minutes", "timeout_minutes"],
            "properties": {
                "problem_url": {"type": "string", "description": "URL проблемы Zabbix."},
                "poll_interval_minutes": {"type": "integer", "default": 1},
                "timeout_minutes": {"type": "integer", "default": 20},
            },
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
            },
        },
        "async_event_contracts": {
            "zabbix_problem_status_wait.completed": {
                "display_name": "Результат ожидания восстановления Zabbix",
                "statuses": ["progress", "success", "error", "timeout", "cancelled"],
                "result_schema": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"},
                    },
                },
            },
        },
        "default_completion_policy": {
            "mode": "external_event",
            "expected_event_type": "zabbix_problem_status_wait.completed",
            "timeout_action": "escalate_operator",
            "max_wait_seconds": 86400,
        },
    }


def zabbix_wait_binding() -> dict:
    return {
        "binding_id": "binding.zabbix_problem_status_wait.mcp_provider_ops",
        "capability_id": "zabbix_problem_status_wait",
        "environment_id": "mcp.provider_ops",
        "status": "active",
        "execution_mode": "async",
        "mcp_tool_name": "zabbix.problem.status.wait",
        "input_mapping": {
            "problem_url": "problem_url",
            "poll_interval_minutes": "poll_interval_minutes",
            "timeout_minutes": "timeout_minutes",
        },
        "output_mapping": {
            "status": "status",
        },
    }


def zabbix_update_capability() -> dict:
    return {
        "capability_id": "zabbix_problem_update",
        "display_name": "Обновить проблему Zabbix",
        "status": "active",
        "description": "Добавляет комментарий в проблему Zabbix.",
        "contract_version": "1.0",
        "execution_modes": ["sync"],
        "input_schema": {
            "type": "object",
            "required": ["problem_url", "message"],
            "properties": {
                "problem_url": {"type": "string", "description": "URL проблемы Zabbix."},
                "message": {
                    "type": "string",
                    "description": "Текст комментария, который нужно записать в проблему Zabbix.",
                },
            },
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Статус выполнения обновления."},
                "message": {"type": "string", "description": "Сообщение, переданное в Zabbix."},
            },
        },
    }


def zabbix_update_binding() -> dict:
    return {
        "binding_id": "binding.zabbix_problem_update.mcp_provider_ops",
        "capability_id": "zabbix_problem_update",
        "environment_id": "mcp.provider_ops",
        "status": "active",
        "execution_mode": "sync",
        "mcp_tool_name": "zabbix.problem.update",
        "input_mapping": {
            "problem_url": "problem_url",
            "message": "message",
        },
        "output_mapping": {
            "status": "status",
            "message": "message",
        },
    }


class ConfigAssistantMcpOnlyTest(unittest.TestCase):
    def test_compiles_capability_step(self) -> None:
        result = compile_attribute_resolution_step(
            instruction=(
                "Выполни ${Capability.provider_channel_repair_monitor}. "
                "${paramCapability.provider_channel_repair_monitor.input.problem_url}<-${slot.problem_url} "
                "${paramCapability.provider_channel_repair_monitor.input.service_request}<-${case.ticket_id} "
                "${paramCapability.provider_channel_repair_monitor.input.from}<-monitor@example.test "
                "результат ${paramCapability.provider_channel_repair_monitor.output.provider_mail_body}->provider_mail_body"
            ),
            slot_schema=slot_schema(),
            tools=[],
            capabilities=[capability()],
            capability_bindings=[binding()],
        )

        self.assertEqual(result["validation_errors"], [])
        structure = result["structure"]
        self.assertEqual(structure["capability_id"], "provider_channel_repair_monitor")
        self.assertNotIn("tool_name", structure)
        self.assertEqual(structure["mcp_environment_id"], "mcp.provider_ops")
        self.assertEqual(structure["input_mapping"]["problem_url"], "slot:problem_url")
        self.assertEqual(structure["output_mapping"]["provider_mail_body"], "provider_mail_body")

    def test_llm_assist_compiles_natural_language_capability_step(self) -> None:
        def fake_llm_assist(**_: object) -> dict:
            return {
                "status": "success",
                "provider": "fake",
                "model": "fake-model",
                "duration_ms": 7,
                "redaction": {"redacted": False, "markers": []},
                "draft": {
                    "capability_id": "provider_channel_repair_monitor",
                    "step_name": "Отправить письмо провайдеру",
                    "input_mapping": {
                        "service_request": "case:ticket_id",
                        "problem_host": "slot:host",
                        "problem_url": "slot:zabbix_url",
                        "from": "constant:automation-test@local.test",
                        "reply_to": "constant:automation-test@local.test",
                        "poll_interval_minutes": "constant:1",
                        "timeout_minutes": "constant:20",
                    },
                    "output_mapping": {
                        "provider_mail_body": "provider_mail_body",
                    },
                },
            }

        instruction = (
            "возьми capability по отправке почты провайдера, заполни соответствующими "
            "входными данными, используй частоту опроса 1 минуту и таймаут 20, "
            "результат запиши в соответствующий слот"
        )
        result = compile_attribute_resolution_step(
            instruction=instruction,
            slot_schema=slot_schema(),
            tools=[],
            capabilities=[capability()],
            capability_bindings=[binding()],
            llm_assist_invoker=fake_llm_assist,
        )

        self.assertEqual(result["validation_errors"], [])
        structure = result["structure"]
        self.assertEqual(structure["capability_id"], "provider_channel_repair_monitor")
        self.assertEqual(structure["step_name"], "Отправить письмо провайдеру")
        self.assertEqual(structure["configuration_instruction"], instruction)
        self.assertEqual(structure["input_mapping"]["service_request"], "case:ticket_id")
        self.assertEqual(structure["input_mapping"]["problem_host"], "slot:host")
        self.assertEqual(structure["input_mapping"]["problem_url"], "slot:zabbix_url")
        self.assertEqual(structure["input_mapping"]["from"], "constant:automation-test@local.test")
        self.assertEqual(structure["input_mapping"]["reply_to"], "constant:automation-test@local.test")
        self.assertEqual(structure["input_mapping"]["poll_interval_minutes"], "constant:1")
        self.assertEqual(structure["input_mapping"]["timeout_minutes"], "constant:20")
        self.assertEqual(structure["output_mapping"]["provider_mail_body"], "provider_mail_body")
        self.assertEqual(structure["generated_structure_metadata"]["mode"], "llm_assist")
        self.assertIn("llm_assist", result["references"])

    def test_llm_assist_runs_when_capability_is_preselected(self) -> None:
        captured: dict[str, object] = {}

        def fake_llm_assist(**kwargs: object) -> dict:
            captured.update(kwargs)
            return {
                "status": "success",
                "draft": {
                    "capability_id": "provider_channel_repair_monitor",
                    "input_mapping": {
                        "service_request": "case:ticket_id",
                        "problem_url": "slot:zabbix_url",
                    },
                    "output_mapping": {"provider_mail_body": "provider_mail_body"},
                },
            }

        result = compile_attribute_resolution_step(
            instruction="заполни соответствующими входными данными",
            slot_schema=slot_schema(),
            tools=[],
            capabilities=[capability()],
            capability_id="provider_channel_repair_monitor",
            capability_bindings=[binding()],
            llm_assist_invoker=fake_llm_assist,
        )

        self.assertEqual(result["validation_errors"], [])
        self.assertEqual(captured["capability_id"], "provider_channel_repair_monitor")
        self.assertEqual(result["structure"]["generated_structure_metadata"]["mode"], "llm_assist")

    def test_llm_assist_filters_outputs_not_selected_by_profile(self) -> None:
        def fake_llm_assist(**_: object) -> dict:
            return {
                "status": "success",
                "draft": {
                    "capability_id": "provider_channel_repair_monitor",
                    "input_mapping": {
                        "service_request": "case:ticket_id",
                        "problem_url": "slot:zabbix_url",
                    },
                    "output_mapping": {
                        "provider_mail_body": "provider_mail_body",
                        "provider_mail_subject": "provider_mail_subject",
                        "provider_ticket_number": "provider_ticket_number",
                    },
                },
            }

        result = compile_attribute_resolution_step(
            instruction="результат запиши в соответствующий слот профиля",
            slot_schema=slot_schema(),
            tools=[],
            capabilities=[capability()],
            capability_id="provider_channel_repair_monitor",
            capability_bindings=[binding()],
            profile_context={
                "target_slot_id": "provider_mail_body",
                "output_slot_ids": ["provider_mail_body"],
                "output_slots_order": [{"slot_id": "provider_mail_body", "order": 1}],
            },
            llm_assist_invoker=fake_llm_assist,
        )

        self.assertEqual(result["validation_errors"], [])
        self.assertEqual(result["structure"]["output_mapping"], {"provider_mail_body": "provider_mail_body"})
        self.assertTrue(
            any("provider_mail_subject" in warning and "не записано в слот" in warning for warning in result["warnings"]),
            result["warnings"],
        )

    def test_explicit_output_mapping_to_missing_profile_slot_fails(self) -> None:
        def fake_llm_assist(**_: object) -> dict:
            return {
                "status": "success",
                "draft": {
                    "capability_id": "provider_channel_repair_monitor",
                    "input_mapping": {
                        "service_request": "case:ticket_id",
                        "problem_url": "slot:zabbix_url",
                    },
                    "output_mapping": {"provider_mail_body": "provider_mail_body"},
                },
            }

        result = compile_attribute_resolution_step(
            instruction=(
                "Выполни ${Capability.provider_channel_repair_monitor}. "
                "результат ${paramCapability.provider_channel_repair_monitor.output.provider_mail_subject}->provider_mail_subject"
            ),
            slot_schema=slot_schema(),
            tools=[],
            capabilities=[capability()],
            capability_id="provider_channel_repair_monitor",
            capability_bindings=[binding()],
            profile_context={
                "target_slot_id": "provider_mail_body",
                "output_slot_ids": ["provider_mail_body"],
                "output_slots_order": [{"slot_id": "provider_mail_body", "order": 1}],
            },
            llm_assist_invoker=fake_llm_assist,
        )

        self.assertEqual(result["structure"], {})
        self.assertTrue(
            any("provider_mail_subject" in error and "не найден" in error for error in result["validation_errors"]),
            result["validation_errors"],
        )

    def test_llm_assist_does_not_override_preselected_capability(self) -> None:
        def fake_llm_assist(**_: object) -> dict:
            return {
                "status": "success",
                "draft": {
                    "capability_id": "zabbix_problem_status_wait",
                    "input_mapping": {
                        "service_request": "case:ticket_id",
                        "problem_url": "slot:zabbix_url",
                    },
                    "output_mapping": {"provider_mail_body": "provider_mail_body"},
                },
            }

        result = compile_attribute_resolution_step(
            instruction="возьми capability по отправке почты провайдера и заполни соответствующими входными данными",
            slot_schema=slot_schema(),
            tools=[],
            capabilities=[capability(), zabbix_wait_capability()],
            capability_id="provider_channel_repair_monitor",
            capability_bindings=[binding(), zabbix_wait_binding()],
            llm_assist_invoker=fake_llm_assist,
        )

        self.assertEqual(result["validation_errors"], [])
        self.assertEqual(result["structure"]["capability_id"], "provider_channel_repair_monitor")
        self.assertTrue(
            any("zabbix_problem_status_wait" in warning for warning in result["warnings"]),
            result["warnings"],
        )

    def test_capability_step_prompt_filters_to_preselected_capability(self) -> None:
        messages = build_capability_step_assist_prompt(
            instruction="заполни соответствующими входными данными",
            slot_schema=slot_schema(),
            capabilities=[capability(), zabbix_wait_capability()],
            capability_bindings=[binding(), zabbix_wait_binding()],
            previous_steps=[],
            capability_id="provider_channel_repair_monitor",
            profile_context={"capability_id": "provider_channel_repair_monitor"},
        )
        payload = json.loads(messages[1]["content"])

        self.assertEqual(payload["constraints"]["selected_capability_id"], "provider_channel_repair_monitor")
        self.assertEqual([item["capability_id"] for item in payload["capabilities"]], ["provider_channel_repair_monitor"])

    def test_compiles_action_only_zabbix_wait_step_with_completion_policy(self) -> None:
        result = compile_attribute_resolution_step(
            instruction=(
                "Выполни ${Capability.zabbix_problem_status_wait}. "
                "${paramCapability.zabbix_problem_status_wait.input.problem_url}<-${slot.zabbix_url} "
                "${paramCapability.zabbix_problem_status_wait.input.poll_interval_minutes}<-1 "
                "${paramCapability.zabbix_problem_status_wait.input.timeout_minutes}<-10"
            ),
            slot_schema=slot_schema(),
            tools=[],
            capabilities=[zabbix_wait_capability()],
            capability_bindings=[zabbix_wait_binding()],
            profile_context={
                "target_slot_id": "",
                "output_slot_ids": [],
                "output_slots_order": [],
            },
        )

        self.assertEqual(result["validation_errors"], [])
        structure = result["structure"]
        self.assertEqual(structure["capability_id"], "zabbix_problem_status_wait")
        self.assertEqual(structure["output_mapping"], {})
        self.assertEqual(structure["completion_policy"]["mode"], "external_event")
        self.assertEqual(
            structure["completion_policy"]["expected_event_type"],
            "zabbix_problem_status_wait.completed",
        )
        self.assertEqual(structure["completion_policy"]["max_wait_seconds"], 86400)

    def test_capability_step_prompt_marks_selected_output_slots(self) -> None:
        messages = build_capability_step_assist_prompt(
            instruction="заполни соответствующими входными данными",
            slot_schema=slot_schema(),
            capabilities=[capability()],
            capability_bindings=[binding()],
            previous_steps=[],
            capability_id="provider_channel_repair_monitor",
            profile_context={
                "capability_id": "provider_channel_repair_monitor",
                "target_slot_id": "provider_mail_body",
                "output_slot_ids": ["provider_mail_body"],
                "output_slots_order": [{"slot_id": "provider_mail_body", "order": 1}],
            },
        )
        payload = json.loads(messages[1]["content"])

        self.assertTrue(payload["constraints"]["requires_output_mapping"])
        self.assertEqual(payload["constraints"]["selected_output_slot_ids"], ["provider_mail_body"])
        self.assertEqual(
            [slot["slot_id"] for slot in payload["selected_output_slots"]],
            ["provider_mail_body"],
        )
        self.assertEqual(
            payload["response_schema"]["output_mapping"],
            {"<selected_target_slot_id>": "<capability_output_field>"},
        )

    def test_llm_assist_allows_action_only_profile_without_output_warning(self) -> None:
        def fake_llm_assist(**_: object) -> dict:
            return {
                "status": "success",
                "draft": {
                    "capability_id": "zabbix_problem_update",
                    "step_name": "Обновить Zabbix",
                    "input_mapping": {
                        "problem_url": "slot:zabbix_url",
                        "message": "slot:provider_mail_body",
                    },
                },
            }

        result = compile_attribute_resolution_step(
            instruction="добавь комментарий в Zabbix из письма провайдера",
            slot_schema=slot_schema(),
            tools=[],
            capabilities=[zabbix_update_capability()],
            capability_id="zabbix_problem_update",
            capability_bindings=[zabbix_update_binding()],
            profile_context={
                "profile_id": "profile.zabbix_update",
                "target_slot_id": None,
                "output_slot_ids": [],
                "output_slots_order": [],
            },
            llm_assist_invoker=fake_llm_assist,
        )

        self.assertEqual(result["validation_errors"], [])
        self.assertEqual(result["structure"]["output_mapping"], {})
        self.assertFalse(
            any("не вернул output_mapping" in warning for warning in result["warnings"]),
            result["warnings"],
        )
        self.assertFalse(result["references"]["llm_assist"]["requires_output_mapping"])
        self.assertTrue(
            any("outputs: none" in assumption for assumption in result["references"]["llm_assist"]["assumptions"]),
            result["references"]["llm_assist"]["assumptions"],
        )

    def test_llm_assist_preserves_explicit_refs_as_constraints(self) -> None:
        def fake_llm_assist(**_: object) -> dict:
            return {
                "status": "success",
                "draft": {
                    "capability_id": "provider_channel_repair_monitor",
                    "input_mapping": {
                        "service_request": "slot:host",
                        "problem_url": "slot:problem_url",
                    },
                    "output_mapping": {"provider_mail_body": "provider_mail_body"},
                },
            }

        result = compile_attribute_resolution_step(
            instruction=(
                "Выполни ${Capability.provider_channel_repair_monitor}. "
                "${paramCapability.provider_channel_repair_monitor.input.service_request}<-${case.ticket_id} "
                "${paramCapability.provider_channel_repair_monitor.input.problem_url}<-${slot.zabbix_url} "
                "результат ${paramCapability.provider_channel_repair_monitor.output.provider_mail_body}->provider_mail_body"
            ),
            slot_schema=slot_schema(),
            tools=[],
            capabilities=[capability()],
            capability_bindings=[binding()],
            llm_assist_invoker=fake_llm_assist,
        )

        self.assertEqual(result["validation_errors"], [])
        self.assertEqual(result["structure"]["input_mapping"]["service_request"], "case:ticket_id")
        self.assertEqual(result["structure"]["input_mapping"]["problem_url"], "slot:zabbix_url")

    def test_llm_assist_unavailable_does_not_fall_back_to_deterministic_success(self) -> None:
        def failed_llm_assist(**_: object) -> dict:
            return {"status": "error", "error": {"message": "model unavailable"}}

        result = compile_attribute_resolution_step(
            instruction=(
                "Выполни ${Capability.provider_channel_repair_monitor}. "
                "${paramCapability.provider_channel_repair_monitor.input.problem_url}<-${slot.zabbix_url} "
                "${paramCapability.provider_channel_repair_monitor.input.service_request}<-${case.ticket_id}"
            ),
            slot_schema=slot_schema(),
            tools=[],
            capabilities=[capability()],
            capability_bindings=[binding()],
            llm_assist_invoker=failed_llm_assist,
        )

        self.assertEqual(result["structure"], {})
        self.assertTrue(any("LLM assist" in error for error in result["validation_errors"]))

    def test_capability_step_prompt_contains_rich_slot_and_field_metadata(self) -> None:
        messages = build_capability_step_assist_prompt(
            instruction="заполни соответствующими входными данными",
            slot_schema=slot_schema(),
            capabilities=[capability()],
            capability_bindings=[binding()],
            previous_steps=[],
            capability_id="provider_channel_repair_monitor",
            profile_context={"description": "Получить письмо регистрации от провайдера."},
            system_prompt_template="custom assist prompt",
        )
        self.assertEqual(messages[0]["content"], "custom assist prompt")
        payload = json.loads(messages[1]["content"])
        zabbix_slot = next(slot for slot in payload["slots"] if slot["slot_id"] == "zabbix_url")
        self.assertIn("Original problem URL", zabbix_slot["extraction_instruction"])
        provider_capability = payload["capabilities"][0]
        problem_url = next(field for field in provider_capability["input_fields"] if field["field_id"] == "problem_url")
        self.assertIn("Zabbix", problem_url["description"])
        poll_interval = next(field for field in provider_capability["input_fields"] if field["field_id"] == "poll_interval_minutes")
        self.assertEqual(poll_interval["default"], 1)
        self.assertEqual(payload["constraints"]["selected_capability_id"], "provider_channel_repair_monitor")
        self.assertTrue(payload["constraints"]["requires_output_mapping"])
        self.assertTrue(
            any(
                item["capability_id"] == "provider_channel_repair_monitor"
                and item["section"] == "input"
                and item["field_id"] == "from"
                for item in payload["metadata_quality"]["missing_capability_field_descriptions"]
            )
        )

    def test_llm_assist_rejects_unknown_output_field(self) -> None:
        def fake_llm_assist(**_: object) -> dict:
            return {
                "status": "success",
                "draft": {
                    "capability_id": "provider_channel_repair_monitor",
                    "input_mapping": {
                        "service_request": "case:ticket_id",
                        "problem_url": "slot:zabbix_url",
                    },
                    "output_mapping": {
                        "provider_mail_body": "unknown_output",
                    },
                },
            }

        result = compile_attribute_resolution_step(
            instruction="возьми capability по отправке почты провайдера и результат запиши в соответствующий слот",
            slot_schema=slot_schema(),
            tools=[],
            capabilities=[capability()],
            capability_bindings=[binding()],
            llm_assist_invoker=fake_llm_assist,
        )

        self.assertEqual(result["structure"], {})
        self.assertTrue(any("unknown_output" in error for error in result["validation_errors"]))

    def test_rejects_step_without_capability_reference(self) -> None:
        result = compile_attribute_resolution_step(
            instruction=(
                "Вызови внешнюю endpoint-операцию wait_for_email_by_ticket. "
                "ticket_number <- ${case.ticket_id}"
            ),
            slot_schema=slot_schema(),
            tools=[],
            capabilities=[capability()],
            capability_bindings=[binding()],
        )

        self.assertEqual(result["structure"], {})
        self.assertTrue(any("должен ссылаться на Capability" in error for error in result["validation_errors"]))

    def test_service_scenario_rejects_unknown_execution_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            store = ConfigStore(ContractRegistry(), db_path=Path(tempdir) / "state.sqlite")
            payload = copy.deepcopy(store.active_payload("service_scenarios"))
            payload["scenarios"][0]["legacy_call_names"] = ["wait_for_email_by_ticket"]
            validation = store.validate_payload("service_scenarios", payload)

        self.assertEqual(validation["status"], "invalid")
        self.assertTrue(any("legacy_call_names" in error for error in validation["errors"]))


if __name__ == "__main__":
    unittest.main()
