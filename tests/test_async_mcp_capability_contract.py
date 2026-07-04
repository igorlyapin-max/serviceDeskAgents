from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import copy
import unittest

from apps.orchestrator.app.config_registry import ConfigStore, normalize_simulation_options
from apps.orchestrator.app.contracts import ContractRegistry
from apps.orchestrator.app.config_assistant import compile_attribute_resolution_step


def capability_payload() -> dict:
    return {
        "schema_version": "1.0",
        "capabilities": [
            {
                "capability_id": "provider_channel_repair_monitor",
                "display_name": "Мониторинг ремонта канала провайдера",
                "status": "active",
                "description": "Запускает внешнее MCP-окружение для контроля ремонта канала.",
                "contract_version": "1.0",
                "execution_modes": ["async"],
                "input_schema": {
                    "type": "object",
                    "required": ["problem_url", "service_request", "from", "reply_to"],
                    "properties": {
                        "problem_host": {"type": "string"},
                        "router_ref": {"type": "string"},
                        "problem_url": {"type": "string", "minLength": 1},
                        "service_request": {"type": "string", "minLength": 1},
                        "from": {"type": "string", "minLength": 1},
                        "reply_to": {"type": "string", "minLength": 1},
                        "poll_interval_minutes": {"type": "integer", "minimum": 1},
                        "timeout_minutes": {"type": "integer", "minimum": 1},
                    },
                    "additionalProperties": False,
                },
                "output_schema": {
                    "type": "object",
                    "required": ["provider_mail_body"],
                    "properties": {
                        "provider_mail_body": {"type": "string"},
                        "provider_mail_subject": {"type": "string"},
                        "provider_ticket_number": {"type": "string"},
                        "zabbix_status": {"type": "string"},
                        "polling_diagnostic": {"type": "object", "additionalProperties": True},
                    },
                    "additionalProperties": True,
                },
                "async_event_contracts": {
                    "provider_channel_repair_monitor.completed": {
                        "display_name": "Результат мониторинга канала",
                        "statuses": ["progress", "success", "error", "timeout", "cancelled"],
                        "result_schema": {
                            "type": "object",
                            "required": ["provider_mail_body"],
                            "properties": {
                                "provider_mail_body": {"type": "string"},
                                "provider_ticket_number": {"type": "string"},
                            },
                            "additionalProperties": True,
                        },
                        "progress_schema": {
                            "type": "object",
                            "properties": {
                                "polling_diagnostic": {"type": "object", "additionalProperties": True}
                            },
                            "additionalProperties": True,
                        },
                        "error_schema": {
                            "type": "object",
                            "required": ["message"],
                            "properties": {"message": {"type": "string"}},
                            "additionalProperties": True,
                        },
                        "contract_version": "1.0",
                        "contract_status": "valid",
                    }
                },
                "default_completion_policy": {
                    "mode": "external_event",
                    "max_wait_seconds": 3600,
                    "expected_event_type": "provider_channel_repair_monitor.completed",
                    "timeout_action": "escalate_operator",
                },
                "diagnostic_schema": {
                    "type": "object",
                    "additionalProperties": True,
                },
            }
        ],
    }


def environment_payload(*, tier: str = "dev", auth_mode: str = "dev_bearer_token") -> dict:
    environment = {
        "environment_id": "mcp.provider_ops",
        "display_name": "Provider ops MCP",
        "status": "active",
        "environment_tier": tier,
        "transport": "streamable_http",
        "base_url": "env:MCP_PROVIDER_OPS_URL",
        "auth_mode": auth_mode,
        "auth_ref": "env:MCP_PROVIDER_OPS_TOKEN",
        "allowed_capabilities": ["provider_channel_repair_monitor"],
        "health_check": {"mode": "mcp_ping", "timeout_seconds": 5},
        "discovery_policy": {"mode": "manual"},
    }
    if auth_mode.startswith("oidc_"):
        environment["oidc_audience"] = "servicedeskagents:mcp.provider_ops"
    return {"schema_version": "1.0", "environments": [environment]}


def binding_payload() -> dict:
    return {
        "schema_version": "1.0",
        "bindings": [
            {
                "binding_id": "binding.provider_channel_repair_monitor.primary",
                "capability_id": "provider_channel_repair_monitor",
                "environment_id": "mcp.provider_ops",
                "mcp_tool_name": "provider_channel_repair_monitor",
                "execution_mode": "async",
                "status": "active",
                "input_mapping": {
                    "problem_url": "input.problem_url",
                    "service_request": "input.service_request",
                    "from": "input.from",
                    "reply_to": "input.reply_to",
                },
                "output_mapping": {
                    "provider_mail_body": "result.provider_mail_body",
                },
                "async_context_mapping": {
                    "case_id": "async_context.case_id",
                    "run_id": "async_context.run_id",
                    "wait_id": "async_context.wait_id",
                    "correlation_id": "async_context.correlation_id",
                    "capability_id": "async_context.capability_id",
                    "contract_version": "async_context.contract_version",
                    "expected_event_type": "async_context.expected_event_type",
                    "idempotency_key_base": "async_context.idempotency_key_base",
                },
            }
        ],
    }


def capability_profile(*, with_mock_output: bool = False) -> dict:
    profile = {
        "profile_id": "profile.provider.capability_monitor",
        "display_name": "Мониторинг через capability",
        "status": "active",
        "description": "Заполняет тело письма провайдера через внешнее MCP-окружение.",
        "slot_schema_id": "slot.provider_channel_repair",
        "target_slot_id": "provider_mail_body",
        "use_llm_after_steps": False,
        "enrichment_steps": [
            {
                "step_id": "step1",
                "step_name": "Мониторить ремонт канала",
                "capability_id": "provider_channel_repair_monitor",
                "input_mapping": {
                    "problem_url": "slot:problem_url",
                    "service_request": "case:ticket_id",
                    "from": "constant:monitor@example.test",
                    "reply_to": "constant:monitor@example.test",
                },
                "output_mapping": {
                    "provider_mail_body": "provider_mail_body",
                },
                "completion_policy": {
                    "mode": "external_event",
                    "max_wait_seconds": 3600,
                    "expected_event_type": "provider_channel_repair_monitor.completed",
                    "timeout_action": "escalate_operator",
                },
                "configuration_instruction": "Выполни ${Capability.provider_channel_repair_monitor}.",
                "on_error": "escalate_operator",
            }
        ],
        "output_slots_order": [
            {
                "slot_id": "provider_mail_body",
                "order": 1,
                "required_for_success": True,
                "source_hint": "${step.step1.capability.provider_channel_repair_monitor.output.provider_mail_body}",
                "fallback": "operator_handoff",
            }
        ],
        "llm_resolution_script": {
            "script_text": "Заполни provider_mail_body из результата capability.",
            "response_contract": {
                "decision": "fill",
                "filled_slots": [],
                "confidence": 1,
                "next_question": "",
                "reason": "",
            },
        },
        "human_resolution_policy": {
            "action": "escalate_operator",
            "message_template": "Передайте ответ провайдера оператору.",
        },
        "max_attempts": 1,
    }
    if with_mock_output:
        profile["enrichment_steps"][0]["extensions"] = {"mock_output": {"provider_mail_body": "Body from MCP"}}
    return profile


class AsyncMcpCapabilityContractTest(unittest.TestCase):
    def make_store(self) -> ConfigStore:
        tempdir = TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        return ConfigStore(ContractRegistry(), db_path=Path(tempdir.name) / "state.sqlite")

    def test_valid_async_capability_environment_and_binding(self) -> None:
        store = self.make_store()
        capabilities = capability_payload()
        environments = environment_payload()
        bindings = binding_payload()
        overrides = {
            "capabilities": capabilities,
            "mcp_environments": environments,
            "capability_bindings": bindings,
        }

        for domain, payload in overrides.items():
            with self.subTest(domain=domain):
                validation = store.validate_payload(domain, payload, active_overrides=overrides)
                self.assertEqual(validation["status"], "valid", validation["errors"])

    def test_prod_mcp_environment_rejects_dev_token_auth(self) -> None:
        store = self.make_store()
        capabilities = capability_payload()
        environments = environment_payload(tier="prod", auth_mode="dev_bearer_token")

        validation = store.validate_payload(
            "mcp_environments",
            environments,
            active_overrides={"capabilities": capabilities, "mcp_environments": environments},
        )

        self.assertEqual(validation["status"], "invalid")
        self.assertTrue(any("prod MCP должен использовать OIDC" in error for error in validation["errors"]))

    def test_capability_event_type_must_match_external_event_contract(self) -> None:
        store = self.make_store()
        capabilities = capability_payload()
        cap = capabilities["capabilities"][0]
        contract = cap["async_event_contracts"].pop("provider_channel_repair_monitor.completed")
        cap["async_event_contracts"]["provider-channel-repair-monitor.completed"] = contract
        cap["default_completion_policy"]["expected_event_type"] = "provider-channel-repair-monitor.completed"

        validation = store.validate_payload(
            "capabilities",
            capabilities,
            active_overrides={"capabilities": capabilities},
        )

        self.assertEqual(validation["status"], "invalid")
        self.assertTrue(
            any("ExternalEvent.event_type" in error for error in validation["errors"]),
            validation["errors"],
        )

    def test_async_binding_requires_full_async_context_mapping(self) -> None:
        store = self.make_store()
        capabilities = capability_payload()
        environments = environment_payload()
        bindings = binding_payload()
        broken = copy.deepcopy(bindings)
        del broken["bindings"][0]["async_context_mapping"]["wait_id"]

        validation = store.validate_payload(
            "capability_bindings",
            broken,
            active_overrides={
                "capabilities": capabilities,
                "mcp_environments": environments,
                "capability_bindings": broken,
            },
        )

        self.assertEqual(validation["status"], "invalid")
        self.assertTrue(any("wait_id" in error for error in validation["errors"]))

    def test_binding_rejects_unknown_input_mapping_field_when_schema_is_closed(self) -> None:
        store = self.make_store()
        capabilities = capability_payload()
        environments = environment_payload()
        bindings = binding_payload()
        broken = copy.deepcopy(bindings)
        broken["bindings"][0]["input_mapping"]["unknown_input"] = "input.unknown_input"

        validation = store.validate_payload(
            "capability_bindings",
            broken,
            active_overrides={
                "capabilities": capabilities,
                "mcp_environments": environments,
                "capability_bindings": broken,
            },
        )

        self.assertEqual(validation["status"], "invalid")
        self.assertTrue(any("unknown_input" in error for error in validation["errors"]))

    def test_binding_rejects_unknown_output_mapping_field_when_schema_is_closed(self) -> None:
        store = self.make_store()
        capabilities = capability_payload()
        capabilities["capabilities"][0]["output_schema"]["additionalProperties"] = False
        environments = environment_payload()
        bindings = binding_payload()
        broken = copy.deepcopy(bindings)
        broken["bindings"][0]["output_mapping"]["unknown_output"] = "result.unknown_output"

        validation = store.validate_payload(
            "capability_bindings",
            broken,
            active_overrides={
                "capabilities": capabilities,
                "mcp_environments": environments,
                "capability_bindings": broken,
            },
        )

        self.assertEqual(validation["status"], "invalid")
        self.assertTrue(any("unknown_output" in error for error in validation["errors"]))

    def test_config_assistant_compiles_capability_step(self) -> None:
        capabilities = capability_payload()["capabilities"]
        bindings = binding_payload()["bindings"]

        result = compile_attribute_resolution_step(
            instruction=(
                "Выполни ${Capability.provider_channel_repair_monitor}. "
                "${paramCapability.provider_channel_repair_monitor.input.problem_url}<-${slot.problem_url} "
                "${paramCapability.provider_channel_repair_monitor.input.service_request}<-${case.ticket_id} "
                "${paramCapability.provider_channel_repair_monitor.input.from}<-monitor@example.test "
                "${paramCapability.provider_channel_repair_monitor.input.reply_to}<-monitor@example.test "
                "результат ${paramCapability.provider_channel_repair_monitor.output.provider_mail_body}->provider_mail_body"
            ),
            slot_schema={
                "slot_schema_id": "slot.provider_channel_repair",
                "slots": [
                    {"slot_id": "problem_url", "display_name": "Ссылка на проблему"},
                    {"slot_id": "provider_mail_body", "display_name": "Тело письма провайдера"},
                ],
            },
            tools=[],
            capabilities=capabilities,
            capability_bindings=bindings,
        )

        self.assertEqual(result["validation_errors"], [])
        structure = result["structure"]
        self.assertEqual(structure["capability_id"], "provider_channel_repair_monitor")
        self.assertNotIn("tool_name", structure)
        self.assertEqual(structure["mcp_environment_id"], "mcp.provider_ops")
        self.assertEqual(structure["input_mapping"]["problem_url"], "slot:problem_url")
        self.assertEqual(structure["output_mapping"]["provider_mail_body"], "provider_mail_body")
        self.assertEqual(
            structure["completion_policy"]["expected_event_type"],
            "provider_channel_repair_monitor.completed",
        )

    def test_config_assistant_accepts_capability_step_reference(self) -> None:
        capabilities = capability_payload()["capabilities"]
        bindings = binding_payload()["bindings"]

        result = compile_attribute_resolution_step(
            instruction=(
                "Выполни ${Capability.provider_channel_repair_monitor}. "
                "${paramCapability.provider_channel_repair_monitor.input.problem_url}<-${slot.problem_url} "
                "${paramCapability.provider_channel_repair_monitor.input.service_request}"
                "<-${step.step1.capability.provider_channel_repair_monitor.output.provider_mail_body} "
                "${paramCapability.provider_channel_repair_monitor.input.from}<-monitor@example.test "
                "${paramCapability.provider_channel_repair_monitor.input.reply_to}<-monitor@example.test "
                "результат ${paramCapability.provider_channel_repair_monitor.output.provider_mail_body}->provider_mail_body"
            ),
            slot_schema={
                "slot_schema_id": "slot.provider_channel_repair",
                "slots": [
                    {"slot_id": "problem_url", "display_name": "Ссылка на проблему"},
                    {"slot_id": "provider_mail_body", "display_name": "Тело письма провайдера"},
                ],
            },
            previous_steps=[
                {
                    "step_id": "step1",
                    "capability_id": "provider_channel_repair_monitor",
                }
            ],
            tools=[],
            capabilities=capabilities,
            capability_bindings=bindings,
        )

        self.assertEqual(result["validation_errors"], [])
        self.assertEqual(
            result["structure"]["input_mapping"]["service_request"],
            "step:step1.capability.provider_channel_repair_monitor.output.provider_mail_body",
        )

    def test_attribute_resolution_profile_accepts_capability_step(self) -> None:
        store = self.make_store()
        capabilities = capability_payload()
        environments = environment_payload()
        bindings = binding_payload()
        slot_schemas = {
            "schema_version": "1.0",
            "slot_schemas": [
                {
                    "slot_schema_id": "slot.provider_channel_repair",
                    "display_name": "Канал провайдера",
                    "slots": [
                        {
                            "slot_id": "problem_url",
                            "display_name": "Ссылка на проблему",
                            "priority_group": "context",
                            "required": True,
                            "fill_method": "operator",
                        },
                        {
                            "slot_id": "provider_mail_body",
                            "display_name": "Тело письма провайдера",
                            "priority_group": "context",
                            "required": False,
                            "fill_method": "resolution_profile",
                            "resolution_profile_id": "profile.provider.capability_monitor",
                        },
                    ],
                    "stages": [
                        {
                            "stage_id": "stage.provider",
                            "display_name": "Провайдер",
                            "order": 1,
                            "slots": [
                                {
                                    "slot_id": "problem_url",
                                    "display_name": "Ссылка на проблему",
                                    "priority_group": "context",
                                    "required": True,
                                    "fill_method": "operator",
                                },
                                {
                                    "slot_id": "provider_mail_body",
                                    "display_name": "Тело письма провайдера",
                                    "priority_group": "context",
                                    "required": False,
                                    "fill_method": "resolution_profile",
                                    "resolution_profile_id": "profile.provider.capability_monitor",
                                },
                            ],
                        }
                    ],
                }
            ],
        }
        profile = {"schema_version": "1.0", "profiles": [capability_profile()]}

        validation = store.validate_payload(
            "attribute_resolution_profiles",
            profile,
            active_overrides={
                "capabilities": capabilities,
                "mcp_environments": environments,
                "capability_bindings": bindings,
                "slot_schemas": slot_schemas,
                "attribute_resolution_profiles": profile,
            },
        )

        self.assertEqual(validation["status"], "valid", validation["errors"])

    def test_profile_launches_include_capability_mcp_metadata(self) -> None:
        store = self.make_store()
        capabilities = capability_payload()
        environments = environment_payload()
        bindings = binding_payload()

        with store.active_payload_overrides(
            {
                "capabilities": capabilities,
                "mcp_environments": environments,
                "capability_bindings": bindings,
            }
        ):
            launches = store._profile_tool_launches([capability_profile()])

        self.assertEqual(len(launches), 1)
        launch = launches[0]
        self.assertEqual(launch["launch_type"], "capability")
        self.assertEqual(launch["capability_id"], "provider_channel_repair_monitor")
        self.assertEqual(launch["mcp_environment_id"], "mcp.provider_ops")
        self.assertEqual(launch["mcp_tool_name"], "provider_channel_repair_monitor")
        self.assertEqual(launch["required_slots"], ["problem_url"])
        self.assertEqual(launch["completion_policy"]["expected_event_type"], "provider_channel_repair_monitor.completed")

    def test_later_profile_step_waits_when_previous_step_is_blocked(self) -> None:
        store = self.make_store()
        profile = capability_profile()
        profile["profile_id"] = "profile.provider.two_step"
        profile["enrichment_steps"][0]["input_mapping"]["service_request"] = "slot:incident_number"
        step2 = copy.deepcopy(profile["enrichment_steps"][0])
        step2["step_id"] = "step2"
        step2["step_name"] = "Ожидать восстановление после обновления"
        step2["input_mapping"] = {
            "problem_url": "slot:problem_url",
            "service_request": "constant:after-update",
            "from": "constant:monitor@example.test",
            "reply_to": "constant:monitor@example.test",
        }
        profile["enrichment_steps"].append(step2)

        with store.active_payload_overrides(
            {
                "capabilities": capability_payload(),
                "mcp_environments": environment_payload(),
                "capability_bindings": binding_payload(),
            }
        ):
            launches = store._profile_tool_launches([profile])
            ready, blocked, actions = store._simulate_profile_launches(
                launches,
                slot_values={"problem_url": {"value": "http://zabbix/problem"}},
                provided={},
                missing_slots=["incident_number"],
                simulation_options=normalize_simulation_options(run_mode="operator_full_debug"),
            )

        self.assertEqual(ready, [])
        self.assertEqual(actions, [])
        self.assertEqual([item["status"] for item in blocked], ["blocked_by_missing_slots", "blocked_by_previous_step"])
        self.assertEqual(blocked[1]["previous_launch_id"], "profile.provider.two_step.step1")

    def test_operator_full_debug_capability_resolution_waits_for_live_mcp_execution(self) -> None:
        store = self.make_store()
        trace: list[dict] = []

        with store.active_payload_overrides(
            {
                "capabilities": capability_payload(),
                "mcp_environments": environment_payload(),
                "capability_bindings": binding_payload(),
            }
        ):
            result = store.simulate_attribute_resolution_profile(
                profile=capability_profile(),
                slot_schema={
                    "slot_schema_id": "slot.provider_channel_repair",
                    "slots": [
                        {"slot_id": "problem_url", "display_name": "Ссылка на проблему"},
                        {"slot_id": "provider_mail_body", "display_name": "Тело письма провайдера"},
                    ],
                },
                provided={"case": {"ticket_id": "T-1"}},
                simulation_options=normalize_simulation_options(run_mode="operator_full_debug"),
                effective_thresholds=store.system_confidence_defaults(),
                execution_trace=trace,
                slot_values={"problem_url": {"value": "http://zabbix/problem"}},
            )

        self.assertEqual(result["status"], "pending_live_execution")
        self.assertEqual(result["decision"], "execute_capability")
        self.assertEqual(trace[-1]["status"], "ready")
        self.assertEqual(
            result["enrichment_step_results"]["step1"]["capability_id"],
            "provider_channel_repair_monitor",
        )

    def test_external_event_result_validates_against_capability_contract(self) -> None:
        store = self.make_store()
        wait = {
            "origin": {
                "kind": "capability",
                "capability_id": "provider_channel_repair_monitor",
            }
        }
        event = {
            "event_type": "provider_channel_repair_monitor.completed",
            "status": "success",
            "result": {"provider_mail_body": "Body"},
        }

        with store.active_payload_overrides({"capabilities": capability_payload()}):
            store.validate_external_event_result_contract(wait, event)

    def test_external_event_result_rejects_capability_status_mismatch(self) -> None:
        store = self.make_store()
        wait = {
            "origin": {
                "kind": "capability",
                "capability_id": "provider_channel_repair_monitor",
            }
        }
        event = {
            "event_type": "provider_channel_repair_monitor.completed",
            "status": "unknown",
            "result": {"provider_mail_body": "Body"},
        }

        with store.active_payload_overrides({"capabilities": capability_payload()}):
            with self.assertRaisesRegex(Exception, "не допускает status=unknown"):
                store.validate_external_event_result_contract(wait, event)


if __name__ == "__main__":
    unittest.main()
