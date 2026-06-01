# AI ServiceDesk Administrator Guide

## Purpose

The administrator console is used to configure and control the AI ServiceDesk Platform. It is not intended for day-to-day customer ticket handling.

The administrator manages:

- processing scenarios;
- slots and slot autofill;
- attribute resolution;
- classification and routing;
- ReAct planning;
- ReAct calls and launch matrix;
- decision and escalation rules;
- prompt packs;
- knowledge base;
- models;
- integrations;
- processing flow;
- debug console and dry-run simulations;
- audit, security and permissions.

Administrator console URL:

```text
http://127.0.0.1:18088/admin
```

## Roles and Permissions

Main roles:

- `admin` - full access to the administration plane and debug console;
- `operator` - ticket handling and action approval;
- `support_l1` - case reading and basic operator actions;
- `support_l2` - reading, operator actions and ReAct-call diagnostics;
- `readonly` - read-only access to cases, models, workflow and audit;
- `endpoint` - technical role for callbacks.

Processing-flow permissions:

- `processing.read` - view runs, tasks, waits and events;
- `processing.manage` - safe commands: cancel, retry, release lease, force timeout, escalate.

## Processing Scenarios

The `Processing Scenarios` area configures orchestrator behavior around five steps:

- `0. Slots` - data structure that must be collected;
- `0.1 Slot Autofill` - deterministic slot filling through read-only ReAct calls;
- `1. Attribute Resolution` - context enrichment sequence and LLM decision rule;
- `2. Classification and Route` - rules, confidence and ticket route;
- `3. ReAct Planning` - iteration limits and stop conditions;
- `4. ReAct Calls and Launch Matrix` - scenario-available calls and launch mode;
- `5. Decision and Escalation` - close, wait and operator handoff conditions;
- `6. Prompts` - prompt pack with mandatory system prompt blocks.

Scenario changes go through draft, validation, regression and activation. Active configuration changes only after successful activation.

## Calls and Integrations

The `Calls and Integrations` area separates three levels:

- `Integrations` - technical endpoint adapters and endpoint operations;
- `AI ReAct Calls` - business-level calls available to the orchestrator;
- `Operation Binding` - mapping a ReAct call to an endpoint operation and its parameters.

The LLM never calls external systems directly. It can propose a structured ReAct call, while the backend applies Tool Registry, Execution Policy and Integration Dispatcher.

## Models

The `Models` area manages connections through LiteLLM.

Supported MVP profiles:

- `vllm_cpu` - local vLLM CPU backend for smoke and integration checks;
- `openai` - OpenAI API through LiteLLM;
- additional LiteLLM connections.

Secrets are not displayed in the UI. If a value is configured, the UI shows `parameter hidden`; if it is missing, it shows `parameter not filled`.

Secret writes through the UI are intended only for the local MVP and development stands. In production, Admin UI must not modify `.env`; secrets are provided by external infrastructure.

## Knowledge Base

The `Knowledge Base` area is used to view sources, index status, chunks and test retrieval.

Knowledge-base rebuild is an explicit operator or administrator action. Knowledge sources may include wiki, markdown, PDF, DOCX, HTML, CMDB export, runbooks and FAQ.

## Processing Flow

The `Processing Flow` area shows runtime state for asynchronous processing:

- active `processing_run`;
- `agent_task` with attempt, heartbeat, lease and idempotency key;
- `wait_state` for client wait, external event wait or approval wait;
- Kafka-ready `processing_outbox`;
- selected case timeline;
- runtime processing graph over the orchestration graph.

Only safe actions are allowed:

- cancel run;
- retry retryable task;
- release stale lease;
- force wait timeout;
- escalate case.

Direct editing of slots, workflow state and context from the admin console is forbidden.

## Debug Console

The debug console is used to test scenarios, multi-agent flow and the mock transition from test integrations to real endpoint calls.

URL:

```text
http://127.0.0.1:18088/debug
```

The `/operator` route remains as a local compatibility alias. The interface name is now `Debug Console`.

Console areas:

- `Single Run` - manual check of one ticket, slots, the five orchestrator steps and dry-run trace;
- `Multi-Agent Flow` - generate cases from scenarios, preview, edit and start the flow;
- `Case Traces` - case-centric inspection of the full processing cycle by `case_id` in the five orchestrator steps format;
- `Active Waits` - client, timer, external-event and approval waits;
- `Mocks from Endpoint Calls` - capture real endpoint calls, sanitize them and create mock output.

Ticket flows are generated from scenarios as the source of truth. If a scenario changes, a new flow must reflect its current slots, ReAct calls and expected branches.

The ticket text generator uses slot `examples` first, then scenario description and extraction instructions. Technical expected values are not inserted into the customer message. They are displayed separately:

- `In ticket text` - data that is actually present in the customer message;
- `Expected from autofill` - values that should come from ReAct/autofill;
- `Expected from attribute resolution` - values that should be produced by a resolution profile;
- `Expected result` - completion, wait, escalation or out-of-scope.

After start, the console shows `Agent Outcome`. This is the business verdict above the technical runtime status:

- `Completed automatically` - required data is collected and automated processing reached a final result;
- `Question to customer` - the agent cannot continue without a customer answer;
- `Escalation required` - automated processing stopped and must be handed off to an operator or escalation channel;
- `Error` - mock, contract, configuration or execution failed.

The technical `completed` status only means that the engine finished the run. Use `Agent Outcome` and the call trace to evaluate what actually happened.

In multi-ticket dry-run, the generator's expected branch is compared with the actual agent outcome. If a variant expected a customer clarification but the agent completed the case as successful, the outcome is shown as `Escalation required` with mismatch details in the trace.

The `Case Traces` screen shows a case not as a flat event log, but as five steps: intake and normalization, classification, ReAct planning, tool execution, decision and escalation. For cases created by a multi-agent dry-run it reuses the same functional `Five Steps` view as the single-run debugger: filled slots, customer questions, ReAct calls, call parameters, endpoint parameters and results are visible. The raw timeline remains available in the collapsible `Technical timeline events` block. If an older case has no scenario snapshot, the console shows a fallback trace with the available facts.

Out-of-scope tickets should be close to the target scenario by format, but not by meaning. For example, a finance request may contain a contact person and employee full name, but must not trigger the password reset scenario.

Importing real service desk tickets and chatbot conversations is reserved as a dry-run scaffold. Real data must be marked as `contains_real_data` and must not run state-changing operations without a separate safe mode.

## Mocks from Real Endpoint Calls

To move from test scenarios to real integrations, capture can be enabled for a selected endpoint operation.

Workflow:

1. Enable capture for `endpoint_id` and `operation_id`.
2. Execute a controlled read-only or otherwise safe call.
3. Verify that the response passes `response_schema`.
4. Sanitize the captured response.
5. Create a mock example and make it the operation's current `mock_output`.

A captured response with `not_sanitized` status cannot be used in bulk dry-run. If the response does not match the contract, a mock is not created automatically: update the contract or mark the operation as broken.

## Observability

Every HTTP response receives `X-Request-ID`, and audit events store the request id in event details. This makes it possible to connect a UI action, backend log and audit event.

The `/metrics` endpoint exposes Prometheus-compatible counters and duration sums for HTTP requests, integration calls and duplicate callbacks. In the MVP this is a lightweight built-in registry without an external collector.

A repeated callback with the same `invocation_id` is treated as idempotent: the backend returns the previously saved result and marks the response as `duplicate`.

## Audit and Security

All sensitive administrative actions require a permission check and write an audit event. Secrets must be stored in environment variables or an external secret store; configuration stores only secret references.

Before ticket text is sent to an LLM, minimal redaction is applied: email addresses, phone numbers, bearer/API tokens and assignments such as `password=...`, `token=...`, `секрет=...`, `ключ=...` are replaced with technical markers. Dry-run traces show only the redaction fact and marker types, not the original values.

## Language Rules

The UI supports Russian and English. Technical identifiers are not translated: API paths, environment variables, JSON fields, service names, Kafka topics, enum/status ids, tool names, endpoint ids and operation ids.
