from __future__ import annotations

import copy
import tempfile
import unittest
import os
from pathlib import Path
from unittest.mock import patch

from apps.orchestrator.app.cases import CaseStore
from apps.orchestrator.app.config_registry import ConfigStore
from apps.orchestrator.app.contracts import ContractRegistry
from apps.orchestrator.app.kafka_runtime import McpCommandWorker
from apps.orchestrator.app.mcp_execution import (
    McpExecutionError,
    build_discovery_import_payloads,
    build_async_context,
    build_mcp_jsonrpc_tool_call,
    build_mcp_tool_request,
    discover_mcp_capability_candidates,
    invoke_mcp_tool_request,
    invoke_mcp_tools_list,
    mcp_auth_headers,
    normalize_async_diagnostics,
    normalize_mcp_tool_result,
    select_capability_binding,
    validate_async_ack,
    validate_sync_result,
)
from apps.orchestrator.app.processing import ProcessingConflict, ProcessingStore
from apps.orchestrator.app.workflow import TicketWorkflow


def capability() -> dict:
    return {
        "capability_id": "provider_channel_repair_monitor",
        "contract_version": "1.0",
        "execution_modes": ["async"],
        "input_schema": {
            "type": "object",
            "required": ["problem_url"],
            "properties": {
                "problem_url": {
                    "type": "string",
                    "minLength": 1,
                    "description": "Полный URL проблемы Zabbix для корреляции с провайдером.",
                }
            },
        },
        "output_schema": {
            "type": "object",
            "required": ["provider_mail_body"],
            "properties": {
                "provider_mail_body": {
                    "type": "string",
                    "description": "Тело письма-ответа провайдера.",
                }
            },
        },
        "default_completion_policy": {
            "mode": "external_event",
            "expected_event_type": "provider_channel_repair_monitor.completed",
            "max_wait_seconds": 3600,
            "timeout_action": "escalate_operator",
        },
    }


def accepted_ack_schema() -> dict:
    return {
        "type": "object",
        "required": ["status", "external_execution_id", "correlation_id"],
        "properties": {
            "status": {"const": "accepted"},
            "external_execution_id": {"type": "string", "minLength": 1},
            "correlation_id": {"type": "string", "minLength": 1},
        },
        "additionalProperties": True,
    }


def service_desk_tool_descriptor() -> dict:
    cap = capability()
    return {
        "name": "provider_channel_repair_monitor",
        "description": "Monitor provider channel repair.",
        "inputSchema": cap["input_schema"],
        "_meta": {
            "servicedesk": {
                "capability_id": cap["capability_id"],
                "display_name": "Provider channel repair monitor",
                "description": "Monitor provider channel repair through async MCP execution.",
                "contract_version": "1.0",
                "execution_modes": ["async"],
                "output_schema": cap["output_schema"],
                "accepted_ack_schema": accepted_ack_schema(),
                "async_event_contracts": {
                    "provider_channel_repair_monitor.completed": {
                        "display_name": "Provider monitor completed",
                        "statuses": ["progress", "success", "error", "timeout", "cancelled"],
                        "result_schema": cap["output_schema"],
                        "progress_schema": {
                            "type": "object",
                            "properties": {"phase": {"type": "string"}},
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
                "default_completion_policy": cap["default_completion_policy"],
                "diagnostic_schema": {"type": "object", "additionalProperties": True},
            }
        },
    }


class StaticConfigStore:
    def __init__(self, payloads: dict[str, dict]) -> None:
        self.payloads = payloads

    def active_payload(self, domain: str) -> dict:
        return self.payloads[domain]

    def capability_event_contract_snapshot(self, *, capability_id: str, event_type: str) -> dict:
        cap = next(
            item
            for item in self.payloads["capabilities"]["capabilities"]
            if item["capability_id"] == capability_id
        )
        return {
            "capability_id": capability_id,
            "event_type": event_type,
            "contract": cap["async_event_contracts"][event_type],
        }


class McpExecutionTest(unittest.TestCase):
    def test_ticket_analyze_initial_capability_action_enqueues_async_mcp_command(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            db_path = Path(tempdir) / "state.sqlite"
            contracts = ContractRegistry()
            config_store = ConfigStore(contracts, db_path=db_path)
            case_store = CaseStore(contracts, db_path=db_path)
            processing_store = ProcessingStore(case_store, config_store=config_store, db_path=db_path)
            workflow = TicketWorkflow(
                contracts=contracts,
                case_store=case_store,
                config_store=config_store,
                processing_store=processing_store,
            )
            action = {
                "tool_name": "provider_channel_repair_monitor",
                "action_id": "profile.provider.step1.action",
                "action_type": "read_only",
                "parameters": {
                    "problem_url": "http://zabbix/problem",
                    "service_request": "ticket-initial-mcp-1",
                    "from": "monitor@example.test",
                    "reply_to": "monitor@example.test",
                },
                "reason": "Проверочный запуск MCP capability.",
                "risk_level": "low",
                "expected_effect": "Будет вызвана MCP capability.",
                "requires_state_change": False,
                "extensions": {
                    "capability_id": "provider_channel_repair_monitor",
                    "mcp_environment_id": "mcp.provider_ops",
                    "mcp_tool_name": "provider_channel_repair_monitor",
                    "execution_mode": "async",
                    "completion_policy": {
                        "mode": "external_event",
                        "expected_event_type": "provider_channel_repair_monitor.completed",
                        "result_transport": "kafka_event",
                        "result_topic": "external.events",
                        "max_wait_seconds": 3600,
                        "timeout_action": "escalate_operator",
                    },
                    "source_profile_id": "profile.provider",
                    "source_step_id": "step1",
                    "source_slot_schema_id": "slot.provider",
                    "source_output_slots_order": [
                        {
                            "slot_id": "provider_mail_body",
                            "source_hint": "${step.step1.capability.provider_channel_repair_monitor.output.provider_mail_body}",
                        }
                    ],
                    "debug_launch_id": "profile.provider.step1",
                },
            }
            ticket = {
                "ticket_id": "ticket-initial-mcp-1",
                "user": "ivanov",
                "service": "provider",
                "description": "Проверить канал провайдера.",
                "priority": "p3",
                "scenario": "action",
                "debug_bypass_policy_gates": True,
                "decision_override": {
                    "schema_version": "1.0",
                    "decision": {
                        "type": "action_proposed",
                        "summary": "Запустить capability.",
                        "confidence": 1,
                    },
                    "operator_message": "Capability запускается.",
                    "internal_reasoning_summary": "Unit test.",
                    "citations": [],
                    "proposed_actions": [action],
                },
            }

            with config_store.active_payload_overrides(
                {
                    "capabilities": {"schema_version": "1.0", "capabilities": [capability()]},
                    "mcp_environments": {
                        "schema_version": "1.0",
                        "environments": [
                            {
                                "environment_id": "mcp.provider_ops",
                                "display_name": "Provider ops MCP",
                                "status": "active",
                                "environment_tier": "dev",
                                "transport": "streamable_http",
                                "base_url": "http://127.0.0.1:9000/mcp",
                                "auth_mode": "dev_bearer_token",
                                "auth_ref": "env:MCP_TOKEN",
                                "allowed_capabilities": ["provider_channel_repair_monitor"],
                            }
                        ],
                    },
                    "capability_bindings": {
                        "schema_version": "1.0",
                        "bindings": [
                            {
                                "binding_id": "binding.provider",
                                "capability_id": "provider_channel_repair_monitor",
                                "environment_id": "mcp.provider_ops",
                                "mcp_tool_name": "provider_channel_repair_monitor",
                                "execution_mode": "async",
                                "status": "active",
                            }
                        ],
                    },
                }
            ):
                analysis = workflow.analyze(ticket)

            tool_result = analysis["tool_results"][0]
            self.assertEqual(tool_result["status"], "success")
            self.assertEqual(tool_result["adapter_type"], "mcp_tool")
            self.assertEqual(tool_result["endpoint_id"], "mcp.provider_ops")
            self.assertEqual(tool_result["operation_id"], "provider_channel_repair_monitor")
            self.assertEqual(tool_result["output"]["runbook_status"], "accepted")
            self.assertNotEqual(tool_result.get("error", {}).get("code"), "legacy_operation_binding_removed")
            wait = processing_store.active_wait(analysis["case_id"])
            self.assertIsNotNone(wait)
            assert wait is not None
            self.assertEqual(wait["expected_event_type"], "provider_channel_repair_monitor.completed")
            self.assertEqual(wait["origin"]["capability_id"], "provider_channel_repair_monitor")
            outbox = processing_store.outbox_message_by_idempotency_key(
                f"{analysis['case_id']}:capability_command:{tool_result['invocation_id']}"
            )
            self.assertIsNotNone(outbox)
            assert outbox is not None
            self.assertEqual(outbox["topic"], "mcp.commands")
            self.assertEqual(outbox["payload"]["command_type"], "async_mcp_capability_invocation")

    def test_async_capability_enqueue_rejects_missing_required_inputs_before_wait(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            db_path = Path(tempdir) / "state.sqlite"
            contracts = ContractRegistry()
            config_store = ConfigStore(contracts, db_path=db_path)
            case_store = CaseStore(contracts, db_path=db_path)
            processing_store = ProcessingStore(case_store, config_store=config_store, db_path=db_path)
            ticket_input = {
                "ticket_id": "ticket-missing-capability-inputs-1",
                "user": "ivanov",
                "service": "provider",
                "description": "Проверить канал провайдера.",
            }
            analysis = {
                "ticket_id": "ticket-missing-capability-inputs-1",
                "workflow_state": {
                    "id": "running",
                    "category": "processing",
                    "terminal": False,
                    "can_advance": True,
                    "requires_operator_action": False,
                },
                "ai_decision": {
                    "schema_version": "1.0",
                    "decision": {
                        "type": "answer_proposed",
                        "summary": "Запустить capability.",
                        "confidence": 0.8,
                    },
                    "operator_message": "Capability запускается.",
                    "internal_reasoning_summary": "Unit test.",
                    "citations": [],
                    "proposed_actions": [],
                },
                "approval_requests": [],
                "rag_trace": {},
                "tool_trace": [],
                "tool_results": [],
            }
            case = case_store.create_from_analysis(ticket_input, analysis)
            processing_store.record_analysis(ticket_input, {**analysis, "case_id": case["case_id"]})
            cap = capability()
            cap["input_schema"]["required"] = ["problem_url", "from", "reply_to"]
            cap["input_schema"]["properties"]["from"] = {"type": "string", "minLength": 1}
            cap["input_schema"]["properties"]["reply_to"] = {"type": "string", "minLength": 1}
            environment = {
                "environment_id": "mcp.provider_ops",
                "auth_mode": "dev_bearer_token",
                "auth_ref": "env:MCP_TOKEN",
            }
            binding = {
                "binding_id": "binding.provider",
                "capability_id": cap["capability_id"],
                "environment_id": environment["environment_id"],
                "mcp_tool_name": "provider_channel_repair_monitor",
                "execution_mode": "async",
                "status": "active",
            }
            invocation_id = "inv-missing-required-inputs"
            idempotency_key = f"{case['case_id']}:capability_command:{invocation_id}"

            with self.assertRaisesRegex(ProcessingConflict, "from, reply_to"):
                processing_store.enqueue_async_capability_command(
                    {
                        "invocation_id": invocation_id,
                        "case_id": case["case_id"],
                        "parameters": {"problem_url": "http://zabbix/problem"},
                    },
                    capability=cap,
                    environment=environment,
                    binding=binding,
                    expected_event_type="provider_channel_repair_monitor.completed",
                    callback_base_url="http://127.0.0.1:18088",
                )

            self.assertIsNone(processing_store.active_wait_by_correlation(idempotency_key, case_id=case["case_id"]))
            self.assertIsNone(processing_store.outbox_message_by_idempotency_key(idempotency_key))

    def test_normalize_async_diagnostics_whitelists_and_redacts_fields(self) -> None:
        normalized = normalize_async_diagnostics(
            {
                "level": "Verbose",
                "source": "scenario_simulation",
                "run_mode": "operator_full_debug",
                "token": "secret-token",
                "payload": {"password": "raw"},
            }
        )

        self.assertEqual(
            normalized,
            {
                "level": "verbose",
                "source": "scenario_simulation",
                "run_mode": "operator_full_debug",
            },
        )
        self.assertIsNone(normalize_async_diagnostics({"level": "off"}))

    def test_async_capability_enqueue_sanitizes_diagnostics_and_rejects_idempotency_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            db_path = Path(tempdir) / "state.sqlite"
            contracts = ContractRegistry()
            config_store = ConfigStore(contracts, db_path=db_path)
            case_store = CaseStore(contracts, db_path=db_path)
            processing_store = ProcessingStore(case_store, config_store=config_store, db_path=db_path)
            ticket_input = {
                "ticket_id": "ticket-async-diagnostics-1",
                "user": "ivanov",
                "service": "provider",
                "description": "Проверить канал провайдера.",
            }
            analysis = {
                "ticket_id": "ticket-async-diagnostics-1",
                "workflow_state": {
                    "id": "running",
                    "category": "processing",
                    "terminal": False,
                    "can_advance": True,
                    "requires_operator_action": False,
                },
                "ai_decision": {
                    "schema_version": "1.0",
                    "decision": {
                        "type": "answer_proposed",
                        "summary": "Запустить capability.",
                        "confidence": 0.8,
                    },
                    "operator_message": "Capability запускается.",
                    "internal_reasoning_summary": "Unit test.",
                    "citations": [],
                    "proposed_actions": [],
                },
                "approval_requests": [],
                "rag_trace": {},
                "tool_trace": [],
                "tool_results": [],
            }
            case = case_store.create_from_analysis(ticket_input, analysis)
            processing_store.record_analysis(ticket_input, {**analysis, "case_id": case["case_id"]})
            run = processing_store.latest_run(case["case_id"])
            assert run is not None
            run["status"] = "running"
            run["completed_at"] = None
            processing_store._save_run(run)
            cap = capability()
            environment = {
                "environment_id": "mcp.provider_ops",
                "auth_mode": "dev_bearer_token",
                "auth_ref": "env:MCP_TOKEN",
            }
            binding = {
                "binding_id": "binding.provider",
                "capability_id": cap["capability_id"],
                "environment_id": environment["environment_id"],
                "mcp_tool_name": "provider_channel_repair_monitor",
                "execution_mode": "async",
                "status": "active",
            }
            invocation = {
                "invocation_id": "inv-diagnostics-1",
                "case_id": case["case_id"],
                "parameters": {"problem_url": "http://zabbix/problem"},
                "extensions": {
                    "async_diagnostics": {
                        "level": "verbose",
                        "source": "scenario_simulation",
                        "run_mode": "operator_full_debug",
                        "token": "raw-secret-token",
                    }
                },
            }

            queued = processing_store.enqueue_async_capability_command(
                invocation,
                capability=cap,
                environment=environment,
                binding=binding,
                expected_event_type="provider_channel_repair_monitor.completed",
                callback_base_url="http://127.0.0.1:18088",
            )

            diagnostics = queued["command"]["invocation"]["extensions"]["async_diagnostics"]
            async_context = queued["command"]["invocation"]["extensions"]["async_context"]
            self.assertEqual(
                diagnostics,
                {
                    "level": "verbose",
                    "source": "scenario_simulation",
                    "run_mode": "operator_full_debug",
                },
            )
            self.assertEqual(async_context["async_diagnostics"], diagnostics)
            self.assertEqual(queued["wait"]["origin"]["async_diagnostics"], diagnostics)

            duplicate = processing_store.enqueue_async_capability_command(
                invocation,
                capability=cap,
                environment=environment,
                binding=binding,
                expected_event_type="provider_channel_repair_monitor.completed",
                callback_base_url="http://127.0.0.1:18088",
            )
            self.assertTrue(duplicate["duplicate"])

            conflicting_invocation = copy.deepcopy(invocation)
            conflicting_invocation["parameters"]["problem_url"] = "http://zabbix/other"
            with self.assertRaisesRegex(ProcessingConflict, "idempotency conflict"):
                processing_store.enqueue_async_capability_command(
                    conflicting_invocation,
                    capability=cap,
                    environment=environment,
                    binding=binding,
                    expected_event_type="provider_channel_repair_monitor.completed",
                    callback_base_url="http://127.0.0.1:18088",
                )

    def test_build_async_mcp_tool_request(self) -> None:
        cap = capability()
        environment = {
            "environment_id": "mcp.provider_ops",
            "auth_mode": "dev_bearer_token",
            "auth_ref": "env:MCP_TOKEN",
        }
        binding = {
            "binding_id": "binding.provider",
            "capability_id": cap["capability_id"],
            "environment_id": environment["environment_id"],
            "mcp_tool_name": "provider_channel_repair_monitor",
            "execution_mode": "async",
            "status": "active",
        }
        context = build_async_context(
            case_id="case-1",
            run_id="run-1",
            wait_id="wait-1",
            correlation_id="corr-1",
            capability=cap,
            expected_event_type="provider_channel_repair_monitor.completed",
            idempotency_key_base="cmd-1",
            result_transport="http_callback",
            callback_url="http://127.0.0.1/external-events/mcp",
            async_diagnostics={
                "level": "verbose",
                "source": "scenario_simulation",
                "run_mode": "operator_full_debug",
            },
        )

        request = build_mcp_tool_request(
            capability=cap,
            environment=environment,
            binding=binding,
            inputs={"problem_url": "http://zabbix/problem"},
            async_context=context,
        )

        self.assertEqual(request["mcp_tool_name"], "provider_channel_repair_monitor")
        self.assertEqual(request["async_context"]["wait_id"], "wait-1")
        self.assertEqual(request["async_context"]["async_diagnostics"]["level"], "verbose")

    def test_build_async_mcp_tool_request_coerces_string_constants_by_input_schema(self) -> None:
        cap = capability()
        cap["input_schema"] = {
            "type": "object",
            "required": ["problem_url", "poll_interval_minutes", "timeout_minutes"],
            "properties": {
                "problem_url": {"type": "string", "minLength": 1},
                "poll_interval_minutes": {"type": "integer", "minimum": 1},
                "timeout_minutes": {"type": "integer", "minimum": 1},
            },
        }
        environment = {"environment_id": "mcp.provider_ops"}
        binding = {
            "mcp_tool_name": "provider_channel_repair_monitor",
            "execution_mode": "async",
        }
        context = build_async_context(
            case_id="case-1",
            run_id="run-1",
            wait_id="wait-1",
            correlation_id="corr-1",
            capability=cap,
            expected_event_type="provider_channel_repair_monitor.completed",
            idempotency_key_base="cmd-1",
            result_transport="http_callback",
            callback_url="http://127.0.0.1/external-events/mcp",
        )

        request = build_mcp_tool_request(
            capability=cap,
            environment=environment,
            binding=binding,
            inputs={
                "problem_url": "http://zabbix/problem",
                "poll_interval_minutes": "1",
                "timeout_minutes": "20",
            },
            async_context=context,
        )

        self.assertEqual(request["inputs"]["poll_interval_minutes"], 1)
        self.assertEqual(request["inputs"]["timeout_minutes"], 20)

    def test_builds_mcp_tools_call_jsonrpc_envelope(self) -> None:
        request = {
            "mcp_tool_name": "provider_channel_repair_monitor",
            "inputs": {"problem_url": "http://zabbix/problem"},
            "async_context": {"wait_id": "wait-1"},
        }

        envelope = build_mcp_jsonrpc_tool_call(request, request_id="cmd-1")

        self.assertEqual(envelope["method"], "tools/call")
        self.assertEqual(envelope["params"]["name"], "provider_channel_repair_monitor")
        self.assertEqual(envelope["params"]["arguments"]["inputs"]["problem_url"], "http://zabbix/problem")
        self.assertEqual(envelope["params"]["arguments"]["async_context"]["wait_id"], "wait-1")

    def test_normalizes_structured_mcp_tool_result(self) -> None:
        result = normalize_mcp_tool_result(
            {
                "structuredContent": {
                    "status": "accepted",
                    "external_execution_id": "exec-1",
                    "correlation_id": "corr-1",
                }
            }
        )

        self.assertEqual(result["status"], "accepted")

    def test_invokes_mcp_tool_and_validates_jsonrpc_response_id(self) -> None:
        cap = capability()
        context = build_async_context(
            case_id="case-1",
            run_id="run-1",
            wait_id="wait-1",
            correlation_id="corr-1",
            capability=cap,
            expected_event_type="provider_channel_repair_monitor.completed",
            idempotency_key_base="cmd-1",
            result_transport="http_callback",
            callback_url="http://127.0.0.1/external-events/mcp",
        )
        mcp_request = build_mcp_tool_request(
            capability=cap,
            environment={"environment_id": "mcp.provider_ops"},
            binding={"mcp_tool_name": "provider_channel_repair_monitor", "execution_mode": "async"},
            inputs={"problem_url": "http://zabbix/problem"},
            async_context=context,
        )

        with patch("apps.orchestrator.app.mcp_execution.urlopen_with_retry") as urlopen:
            urlopen.return_value = (
                b'{"jsonrpc":"2.0","id":"cmd-1","result":{"status":"accepted",'
                b'"external_execution_id":"exec-1","correlation_id":"corr-1"}}'
            )
            result = invoke_mcp_tool_request(
                environment={
                    "environment_id": "mcp.provider_ops",
                    "transport": "streamable_http",
                    "base_url": "http://127.0.0.1:9000/mcp",
                    "auth_mode": "dev_bearer_token",
                    "auth_ref": "env:MCP_TOKEN",
                },
                mcp_request=mcp_request,
                secret_resolver=lambda key: "token-123" if key == "MCP_TOKEN" else None,
                request_id="cmd-1",
            )

        self.assertEqual(result["status"], "accepted")

    def test_invokes_mcp_tools_list(self) -> None:
        with patch("apps.orchestrator.app.mcp_execution.urlopen_with_retry") as urlopen:
            urlopen.return_value = (
                b'{"jsonrpc":"2.0","id":"mcp.provider_ops.tools.list",'
                b'"result":{"tools":[{"name":"provider_channel_repair_monitor","inputSchema":{"type":"object"}}]}}'
            )
            tools = invoke_mcp_tools_list(
                environment={
                    "environment_id": "mcp.provider_ops",
                    "transport": "streamable_http",
                    "base_url": "http://127.0.0.1:9000/mcp",
                    "auth_mode": "dev_bearer_token",
                    "auth_ref": "env:MCP_TOKEN",
                },
                secret_resolver=lambda key: "token-123" if key == "MCP_TOKEN" else None,
            )

        self.assertEqual(tools[0]["name"], "provider_channel_repair_monitor")

    def test_discovers_service_desk_capability_candidate_from_mcp_tool_metadata(self) -> None:
        discovery = discover_mcp_capability_candidates(
            environment={
                "environment_id": "mcp.provider_ops",
                "environment_tier": "dev",
                "auth_mode": "dev_bearer_token",
            },
            tools=[
                {"name": "ordinary_tool", "inputSchema": {"type": "object"}},
                service_desk_tool_descriptor(),
            ],
        )

        candidate = discovery["capability_candidates"][0]
        self.assertEqual(discovery["tools_checked"], 2)
        self.assertEqual(discovery["ignored_tools"][0]["tool_name"], "ordinary_tool")
        self.assertEqual(candidate["capability"]["capability_id"], "provider_channel_repair_monitor")
        self.assertIn("URL проблемы Zabbix", candidate["capability"]["input_schema"]["properties"]["problem_url"]["description"])
        self.assertIn(
            "письма-ответа провайдера",
            candidate["capability"]["output_schema"]["properties"]["provider_mail_body"]["description"],
        )
        self.assertEqual(candidate["binding"]["environment_id"], "mcp.provider_ops")
        self.assertEqual(candidate["binding"]["execution_mode"], "async")
        self.assertIn("wait_id", candidate["binding"]["async_context_mapping"])

    def test_discovery_rejects_async_tool_without_accepted_ack_schema(self) -> None:
        tool = service_desk_tool_descriptor()
        del tool["_meta"]["servicedesk"]["accepted_ack_schema"]

        with self.assertRaisesRegex(McpExecutionError, "accepted_ack_schema"):
            discover_mcp_capability_candidates(
                environment={
                    "environment_id": "mcp.provider_ops",
                    "environment_tier": "dev",
                    "auth_mode": "dev_bearer_token",
                },
                tools=[tool],
            )

    def test_discovery_rejects_prod_environment_without_oidc_auth(self) -> None:
        with self.assertRaisesRegex(McpExecutionError, "prod MCP discovery requires OIDC"):
            discover_mcp_capability_candidates(
                environment={
                    "environment_id": "mcp.provider_ops",
                    "environment_tier": "prod",
                    "auth_mode": "dev_bearer_token",
                },
                tools=[service_desk_tool_descriptor()],
            )

    def test_build_discovery_import_payloads_updates_catalogs(self) -> None:
        discovery = discover_mcp_capability_candidates(
            environment={
                "environment_id": "mcp.provider_ops",
                "environment_tier": "dev",
                "auth_mode": "dev_bearer_token",
            },
            tools=[service_desk_tool_descriptor()],
        )

        result = build_discovery_import_payloads(
            active_capabilities={"schema_version": "1.0", "capabilities": []},
            active_environments={
                "schema_version": "1.0",
                "environments": [
                    {
                        "environment_id": "mcp.provider_ops",
                        "allowed_capabilities": [],
                    }
                ],
            },
            active_bindings={"schema_version": "1.0", "bindings": []},
            environment_id="mcp.provider_ops",
            candidates=discovery["capability_candidates"],
        )

        self.assertEqual(result["imported_capability_ids"], ["provider_channel_repair_monitor"])
        self.assertEqual(
            result["payloads"]["mcp_environments"]["environments"][0]["allowed_capabilities"],
            ["provider_channel_repair_monitor"],
        )
        self.assertEqual(
            result["payloads"]["capability_bindings"]["bindings"][0]["capability_id"],
            "provider_channel_repair_monitor",
        )

    def test_invokes_mcp_tool_rejects_jsonrpc_error(self) -> None:
        with patch("apps.orchestrator.app.mcp_execution.urlopen_with_retry") as urlopen:
            urlopen.return_value = b'{"jsonrpc":"2.0","id":"cmd-1","error":{"code":-32602,"message":"bad args"}}'
            with self.assertRaisesRegex(McpExecutionError, "bad args"):
                invoke_mcp_tool_request(
                    environment={
                        "environment_id": "mcp.provider_ops",
                        "transport": "streamable_http",
                        "base_url": "http://127.0.0.1:9000/mcp",
                        "auth_mode": "dev_bearer_token",
                        "auth_ref": "env:MCP_TOKEN",
                    },
                    mcp_request={"mcp_tool_name": "provider_channel_repair_monitor", "inputs": {}},
                    secret_resolver=lambda key: "token-123" if key == "MCP_TOKEN" else None,
                    request_id="cmd-1",
                )

    def test_select_binding_rejects_ambiguous_active_bindings(self) -> None:
        bindings = [
            {
                "binding_id": "a",
                "capability_id": "cap.one",
                "execution_mode": "async",
                "status": "active",
            },
            {
                "binding_id": "b",
                "capability_id": "cap.one",
                "execution_mode": "async",
                "status": "active",
            },
        ]

        with self.assertRaisesRegex(McpExecutionError, "несколько active"):
            select_capability_binding(capability_id="cap.one", execution_mode="async", bindings=bindings)

    def test_dev_token_auth_uses_secret_resolver(self) -> None:
        headers = mcp_auth_headers(
            {"environment_id": "mcp.dev", "auth_mode": "dev_bearer_token", "auth_ref": "env:MCP_TOKEN"},
            secret_resolver=lambda key: "token-123" if key == "MCP_TOKEN" else None,
        )

        self.assertEqual(headers["Authorization"], "Bearer token-123")

    def test_async_ack_correlation_is_required(self) -> None:
        with self.assertRaisesRegex(McpExecutionError, "correlation_id"):
            validate_async_ack(
                {"status": "accepted", "external_execution_id": "exec-1", "correlation_id": "other"},
                correlation_id="corr-1",
            )

    def test_sync_result_validates_output_schema(self) -> None:
        validate_sync_result(
            {"status": "success", "result": {"provider_mail_body": "body"}},
            capability(),
        )

    def test_processing_store_enqueues_async_capability_command(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            db_path = Path(tempdir) / "state.sqlite"
            contracts = ContractRegistry()
            case_store = CaseStore(contracts, db_path=db_path)
            processing_store = ProcessingStore(case_store, db_path=db_path)
            ticket_input = {
                "ticket_id": "ticket-mcp-1",
                "user": "ivanov",
                "service": "provider",
                "description": "Проверить канал провайдера.",
            }
            analysis = {
                "ticket_id": "ticket-mcp-1",
                "workflow_state": {
                    "id": "waiting_external_event",
                    "category": "waiting",
                    "terminal": False,
                    "can_advance": False,
                    "requires_operator_action": False,
                },
                "ai_decision": {
                    "schema_version": "1.0",
                    "decision": {
                        "type": "answer_proposed",
                        "summary": "Ожидается внешнее событие для продолжения.",
                        "confidence": 0.8,
                    },
                    "operator_message": "Ожидается внешнее событие.",
                    "internal_reasoning_summary": "Тестовая ветка ожидания MCP.",
                    "citations": [],
                    "proposed_actions": [],
                },
                "approval_requests": [],
                "rag_trace": {},
                "tool_trace": [],
                "tool_results": [],
            }
            case = case_store.create_from_analysis(ticket_input, analysis)
            processing_store.record_analysis(ticket_input, {**analysis, "case_id": case["case_id"]})

            environment = {
                "environment_id": "mcp.provider_ops",
                "auth_mode": "dev_bearer_token",
                "auth_ref": "env:MCP_TOKEN",
            }
            binding = {
                "binding_id": "binding.provider",
                "capability_id": capability()["capability_id"],
                "environment_id": environment["environment_id"],
                "mcp_tool_name": "provider_channel_repair_monitor",
                "execution_mode": "async",
                "status": "active",
            }

            result = processing_store.enqueue_async_capability_command(
                {
                    "invocation_id": "inv-mcp-1",
                    "case_id": case["case_id"],
                    "parameters": {"problem_url": "http://zabbix/problem"},
                    "extensions": {
                        "async_diagnostics": {
                            "level": "verbose",
                            "source": "scenario_simulation",
                            "run_mode": "operator_full_debug",
                        }
                    },
                },
                capability=capability(),
                environment=environment,
                binding=binding,
                expected_event_type="profile.provider.step1.completed",
                callback_base_url="http://127.0.0.1:18088",
            )

            wait = result["wait"]
            command = result["command"]
            claim = processing_store.begin_tool_command(command, worker_id="worker-1")
            dispatch_started = processing_store.mark_tool_command_dispatch_started(command, worker_id="worker-1")
            completed = processing_store.complete_tool_command(
                command,
                {"schema_version": "1.0", "mcp_result": {"status": "success"}},
                worker_id="worker-1",
            )

        self.assertEqual(wait["origin"]["kind"], "capability")
        self.assertEqual(wait["origin"]["capability_id"], "provider_channel_repair_monitor")
        self.assertEqual(wait["expected_event_type"], "profile.provider.step1.completed")
        self.assertEqual(command["command_type"], "async_mcp_capability_invocation")
        self.assertEqual(command["topic"], "mcp.commands")
        self.assertEqual(command["mcp_request"]["async_context"]["wait_id"], wait["wait_id"])
        self.assertEqual(command["mcp_request"]["async_context"]["correlation_id"], wait["correlation_id"])
        self.assertEqual(command["mcp_request"]["async_context"]["expected_event_type"], "profile.provider.step1.completed")
        self.assertEqual(wait["origin"]["async_diagnostics"]["level"], "verbose")
        self.assertEqual(command["invocation"]["extensions"]["async_diagnostics"]["level"], "verbose")
        self.assertEqual(command["mcp_request"]["async_context"]["async_diagnostics"]["level"], "verbose")
        self.assertEqual(claim["status"], "claimed")
        self.assertEqual(dispatch_started["status"], "dispatch_started")
        self.assertEqual(completed["status"], "completed")

    def test_mcp_command_worker_records_accepted_ack_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            db_path = Path(tempdir) / "state.sqlite"
            contracts = ContractRegistry()
            config_store = ConfigStore(contracts, db_path=db_path)
            case_store = CaseStore(contracts, db_path=db_path)
            processing_store = ProcessingStore(case_store, config_store=config_store, db_path=db_path)
            ticket_input = {
                "ticket_id": "ticket-mcp-worker-1",
                "user": "ivanov",
                "service": "provider",
                "description": "Проверить канал провайдера.",
            }
            analysis = {
                "ticket_id": "ticket-mcp-worker-1",
                "workflow_state": {
                    "id": "waiting_external_event",
                    "category": "waiting",
                    "terminal": False,
                    "can_advance": False,
                    "requires_operator_action": False,
                },
                "ai_decision": {
                    "schema_version": "1.0",
                    "decision": {
                        "type": "answer_proposed",
                        "summary": "Ожидается внешнее событие для продолжения.",
                        "confidence": 0.8,
                    },
                    "operator_message": "Ожидается внешнее событие.",
                    "internal_reasoning_summary": "Тестовая ветка ожидания MCP.",
                    "citations": [],
                    "proposed_actions": [],
                },
                "approval_requests": [],
                "rag_trace": {},
                "tool_trace": [],
                "tool_results": [],
            }
            case = case_store.create_from_analysis(ticket_input, analysis)
            processing_store.record_analysis(ticket_input, {**analysis, "case_id": case["case_id"]})
            environment = {
                "environment_id": "mcp.provider_ops",
                "transport": "streamable_http",
                "base_url": "http://127.0.0.1:9000/mcp",
                "auth_mode": "dev_bearer_token",
                "auth_ref": "env:MCP_TOKEN",
            }
            binding = {
                "binding_id": "binding.provider",
                "capability_id": capability()["capability_id"],
                "environment_id": environment["environment_id"],
                "mcp_tool_name": "provider_channel_repair_monitor",
                "execution_mode": "async",
                "status": "active",
            }
            queued = processing_store.enqueue_async_capability_command(
                {
                    "invocation_id": "inv-mcp-worker-1",
                    "case_id": case["case_id"],
                    "parameters": {"problem_url": "http://zabbix/problem"},
                },
                capability=capability(),
                environment=environment,
                binding=binding,
                expected_event_type="provider_channel_repair_monitor.completed",
                callback_base_url="http://127.0.0.1:18088",
            )

            forged_command = copy.deepcopy(queued["command"])
            forged_command["mcp_environment_snapshot"]["base_url"] = "http://attacker.invalid/mcp"
            forged_command["mcp_request"]["inputs"]["problem_url"] = "http://attacker.invalid/problem"

            with patch.dict(os.environ, {"MCP_TOKEN": "token-123"}), patch(
                "apps.orchestrator.app.mcp_execution.urlopen_with_retry"
            ) as urlopen:
                urlopen.return_value = (
                    f'{{"jsonrpc":"2.0","id":"{queued["command"]["command_id"]}",'
                    f'"result":{{"status":"accepted","external_execution_id":"exec-1",'
                    f'"correlation_id":"{queued["command"]["correlation_id"]}"}}}}'
                ).encode("utf-8")
                result = McpCommandWorker(processing_store, config_store).process_command(forged_command)

            receipt = processing_store.tool_command_receipt(queued["command"]["idempotency_key"])
            snapshot = processing_store.async_tool_delivery_snapshot(
                {
                    "wait_id": queued["wait"]["wait_id"],
                    "correlation_id": queued["command"]["correlation_id"],
                    "topic": "mcp.commands",
                    "command_id": queued["command"]["command_id"],
                }
            )

        self.assertEqual(result["mcp_result"]["status"], "success")
        self.assertNotIn("capability_id", result["mcp_result"])
        contracts.require_valid("tool_result", result["mcp_result"])
        self.assertEqual(urlopen.call_args.args[0].full_url, "http://127.0.0.1:9000/mcp")
        self.assertIn("http://zabbix/problem", urlopen.call_args.args[0].data.decode("utf-8"))
        self.assertNotIn("attacker.invalid", urlopen.call_args.args[0].data.decode("utf-8"))
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["result"]["mcp_result"]["output"]["status"], "accepted")
        self.assertIn("MCP-окружение", snapshot["message"])
        self.assertNotIn("n8n", snapshot["message"])

    def test_external_event_continuation_dispatches_capability_to_mcp_outbox(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            db_path = Path(tempdir) / "state.sqlite"
            cap = capability()
            cap["async_event_contracts"] = {
                "provider_channel_repair_monitor.completed": {
                    "display_name": "Provider monitor completed",
                    "statuses": ["success", "error", "timeout"],
                    "result_schema": cap["output_schema"],
                    "contract_version": "1.0",
                    "contract_status": "valid",
                }
            }
            environment = {
                "environment_id": "mcp.provider_ops",
                "transport": "streamable_http",
                "base_url": "http://127.0.0.1:9000/mcp",
                "auth_mode": "dev_bearer_token",
                "auth_ref": "env:MCP_TOKEN",
            }
            binding = {
                "binding_id": "binding.provider",
                "capability_id": cap["capability_id"],
                "environment_id": environment["environment_id"],
                "mcp_tool_name": "provider_channel_repair_monitor",
                "execution_mode": "async",
                "status": "active",
            }
            config_store = StaticConfigStore(
                {
                    "capabilities": {"schema_version": "1.0", "capabilities": [cap]},
                    "mcp_environments": {"schema_version": "1.0", "environments": [environment]},
                    "capability_bindings": {"schema_version": "1.0", "bindings": [binding]},
                }
            )
            contracts = ContractRegistry()
            case_store = CaseStore(contracts, db_path=db_path)
            processing_store = ProcessingStore(case_store, config_store=config_store, db_path=db_path)
            ticket_input = {
                "ticket_id": "ticket-mcp-continuation-1",
                "user": "ivanov",
                "service": "provider",
                "description": "Проверить канал провайдера.",
            }
            analysis = {
                "ticket_id": "ticket-mcp-continuation-1",
                "workflow_state": {
                    "id": "waiting_external_event",
                    "category": "waiting",
                    "terminal": False,
                    "can_advance": False,
                    "requires_operator_action": False,
                },
                "ai_decision": {
                    "schema_version": "1.0",
                    "decision": {
                        "type": "answer_proposed",
                        "summary": "Ожидается внешнее событие.",
                        "confidence": 0.8,
                    },
                    "operator_message": "Ожидается внешнее событие.",
                    "internal_reasoning_summary": "Тест capability continuation.",
                    "citations": [],
                    "proposed_actions": [],
                },
                "approval_requests": [],
                "rag_trace": {},
                "tool_trace": [],
                "tool_results": [],
            }
            case = case_store.create_from_analysis(ticket_input, analysis)
            processing_store.record_analysis(ticket_input, {**analysis, "case_id": case["case_id"]})
            run = processing_store.latest_run(case["case_id"])
            launch = {
                "launch_id": "profile.provider.step1",
                "launch_type": "capability",
                "profile_id": "profile.provider",
                "step_id": "step1",
                "slot_schema_id": "provider_slots",
                "target_slot_id": "provider_mail_body",
                "capability_id": cap["capability_id"],
                "mcp_environment_id": environment["environment_id"],
                "mcp_tool_name": binding["mcp_tool_name"],
                "execution_mode": "async",
                "completion_policy": cap["default_completion_policy"],
                "parameters": {"problem_url": "http://zabbix/problem"},
            }
            action = processing_store._action_for_tool_launch(launch, {})

            dispatch = processing_store._dispatch_capability_launch_after_external_event(
                run=run,
                launch=launch,
                action=action,
            )

            async_wait = dispatch["tool_result"]["extensions"]["async_wait"]
            outbox = processing_store.outbox_message_by_idempotency_key(async_wait["correlation_id"])
            wait = processing_store.require_wait(async_wait["wait_id"])

        contracts.require_valid("tool_result", dispatch["tool_result"])
        self.assertEqual(dispatch["tool_result"]["adapter_type"], "mcp_tool")
        self.assertEqual(outbox["topic"], "mcp.commands")
        self.assertEqual(outbox["payload"]["command_type"], "async_mcp_capability_invocation")
        self.assertEqual(wait["origin"]["kind"], "capability")
        self.assertEqual(wait["origin"]["capability_id"], cap["capability_id"])

    def test_external_event_continuation_dispatches_sync_capability(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            db_path = Path(tempdir) / "state.sqlite"
            cap = {
                "capability_id": "zabbix_problem_update",
                "contract_version": "1.0",
                "execution_modes": ["sync"],
                "input_schema": {
                    "type": "object",
                    "required": ["problem_url", "message"],
                    "properties": {
                        "problem_url": {"type": "string", "minLength": 1},
                        "message": {"type": "string", "minLength": 1},
                    },
                    "additionalProperties": False,
                },
                "output_schema": {
                    "type": "object",
                    "required": ["status"],
                    "properties": {"status": {"type": "string"}, "message": {"type": "string"}},
                    "additionalProperties": True,
                },
                "default_completion_policy": {
                    "mode": "sync",
                    "max_wait_seconds": 0,
                    "timeout_action": "resume_agent",
                },
            }
            environment = {
                "environment_id": "mcp.provider_ops",
                "transport": "streamable_http",
                "base_url": "http://127.0.0.1:9000/mcp",
                "auth_mode": "dev_bearer_token",
                "auth_ref": "env:MCP_TOKEN",
            }
            binding = {
                "binding_id": "binding.zabbix",
                "capability_id": cap["capability_id"],
                "environment_id": environment["environment_id"],
                "mcp_tool_name": "zabbix_problem_update",
                "execution_mode": "sync",
                "status": "active",
            }
            config_store = StaticConfigStore(
                {
                    "capabilities": {"schema_version": "1.0", "capabilities": [cap]},
                    "mcp_environments": {"schema_version": "1.0", "environments": [environment]},
                    "capability_bindings": {"schema_version": "1.0", "bindings": [binding]},
                }
            )
            contracts = ContractRegistry()
            case_store = CaseStore(contracts, db_path=db_path)
            processing_store = ProcessingStore(case_store, config_store=config_store, db_path=db_path)
            ticket_input = {
                "ticket_id": "ticket-mcp-sync-continuation-1",
                "user": "ivanov",
                "service": "provider",
                "description": "Обновить Zabbix.",
            }
            analysis = {
                "ticket_id": "ticket-mcp-sync-continuation-1",
                "workflow_state": {
                    "id": "waiting_external_event",
                    "category": "waiting",
                    "terminal": False,
                    "can_advance": False,
                    "requires_operator_action": False,
                },
                "ai_decision": {
                    "schema_version": "1.0",
                    "decision": {
                        "type": "answer_proposed",
                        "summary": "Ожидается внешнее событие.",
                        "confidence": 0.8,
                    },
                    "operator_message": "Ожидается внешнее событие.",
                    "internal_reasoning_summary": "Тест sync capability continuation.",
                    "citations": [],
                    "proposed_actions": [],
                },
                "approval_requests": [],
                "rag_trace": {},
                "tool_trace": [],
                "tool_results": [],
            }
            case = case_store.create_from_analysis(ticket_input, analysis)
            processing_store.record_analysis(ticket_input, {**analysis, "case_id": case["case_id"]})
            run = processing_store.latest_run(case["case_id"])
            launch = {
                "launch_id": "profile.zabbix.step1",
                "launch_type": "capability",
                "profile_id": "profile.zabbix",
                "step_id": "step1",
                "slot_schema_id": "provider_slots",
                "capability_id": cap["capability_id"],
                "mcp_environment_id": environment["environment_id"],
                "mcp_tool_name": binding["mcp_tool_name"],
                "execution_mode": "sync",
                "completion_policy": cap["default_completion_policy"],
                "parameters": {
                    "problem_url": "http://zabbix/problem",
                    "message": "МТС000000000000001",
                },
            }
            action = processing_store._action_for_tool_launch(launch, {})

            with patch(
                "apps.orchestrator.app.processing.invoke_mcp_tool_request",
                return_value={"status": "success", "result": {"status": "updated", "message": "ok"}},
            ) as invoke:
                dispatch = processing_store._dispatch_capability_launch_after_external_event(
                    run=run,
                    launch=launch,
                    action=action,
                )

            outbox = processing_store.outbox_message_by_idempotency_key(
                f"{case['case_id']}:capability_sync:{run['run_id']}:profile.zabbix.step1"
            )

        contracts.require_valid("tool_result", dispatch["tool_result"])
        self.assertEqual(dispatch["tool_result"]["status"], "success")
        self.assertEqual(dispatch["tool_result"]["output"]["result"]["status"], "updated")
        self.assertEqual(outbox["topic"], "case.events")
        self.assertEqual(outbox["payload"]["tool_result"]["extensions"]["capability_id"], "zabbix_problem_update")
        invoke.assert_called_once()


if __name__ == "__main__":
    unittest.main()
