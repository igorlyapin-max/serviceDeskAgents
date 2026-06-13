# AI ServiceDesk Administrator Guide

## Purpose

The administrator console is used to configure and control the AI ServiceDesk Platform. It is not intended for day-to-day customer ticket handling.

The administrator manages:

- processing scenarios;
- slots and slot resolution;
- classification and routing;
- ReAct calls and resolution profiles;
- ReAct limits, decision rules and escalation through scenario settings and backend policy;
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
- `1. Slot Resolution` - ReAct enrichment steps, direct result mapping to slots, or an LLM decision rule after the steps;
- `2. Classification and Route` - rules, confidence and ticket route;
- `Scenarios` - scenario links, ReAct iteration limit and consecutive ReAct-call error threshold before escalation;
- `4. ReAct Calls and Launch Matrix` - scenario-available calls and launch mode;
- `6. Prompts` - prompt pack with mandatory system prompt blocks.

The system prompt for slot resolution is edited under `Settings -> System Prompts`. ReAct planning and escalation policies remain backend configuration and are applied through scenario references.

## Runtime Variables in Templates

Prompts, messages, slot-resolution rules and ReAct-step instructions may use `${...}` references. The UI opens a helper menu after typing `${`.

Main reference namespaces:

- `${case.<field>}` - case data: `scenario_id`, `input_text`, `ticket_id`, `priority`, `channel_id`;
- `${slot.<slot_id>}` - current scenario slot value;
- `${step.<step_id>.react.<react_call>.input.<parameter>}` - input parameter of an executed ReAct step;
- `${step.<step_id>.react.<react_call>.output.<field>}` - result field of an executed ReAct step;
- `${stage.<number>.<field>}` - aggregated orchestrator-stage result, for example `${stage.2.classification}` or `${stage.5.agent_outcome}`;
- `${wait.<field>}` - active wait or async-result data: `wait_id`, `correlation_id`, `status`, `result_transport`, `result_topic`.

Inside an enrichment step, references may point only to already executed previous steps. Legacy `entity:*` and `${entity.*}` references are forbidden; use `step.*` instead. The debug console dry-run trace shows `Available Runtime Variables`, where the actual values from the current run can be inspected.

Scenario changes go through draft, validation, regression and activation. Active configuration changes only after successful activation.

Client-response waiting is an interaction-channel property, not a slot-schema property. The `Interaction Channels` area configures the first reminder, discussion timeout, no-answer action, SLA pause and client-wait auto-close.

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
- `Expected from slot resolution` - values that should be produced by a resolution profile through direct ReAct-step result mapping or an LLM rule after the steps;
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

The `/metrics` endpoint exposes Prometheus-compatible counters and duration sums for HTTP requests, integration calls and duplicate callbacks. In the MVP this is a lightweight built-in registry without an external collector. By default, the endpoint is available only from loopback IPs; an external collector must be explicitly added to `METRICS_ALLOWED_IPS`.

A repeated callback with the same `invocation_id` is treated as idempotent: the backend returns the previously saved result and marks the response as `duplicate`.

Long-running actions use `wait_state` plus an external result. The platform creates a wait with `case_id`, `wait_id`, `correlation_id`, `origin`, `result_transport` and `result_topic`, while n8n, a timer worker or another endpoint returns the result to `POST /external-events/{source}` or to a Kafka topic. `origin` shows what opened the wait: a ReAct call, client question, approval, timer or system policy. The external system never changes case business state directly: it sends an `external_event` with `progress`, `success`, `error`, `timeout` or `cancelled` status, and the platform closes the wait, records the timeline event and queues processing continuation.

For asynchronous ReAct calls, the worker passes n8n a callback package with `idempotency_key_base`. This is the command key, not the result key. Each `progress`, `success`, `error`, `timeout` or `cancelled` result must be returned as a separate `ExternalEvent` with a stable `idempotency_key`, for example `<idempotency_key_base>:<event_id>`. HTTP callback is accepted only for `http_callback` or `both` waits; Kafka events are accepted only for `kafka_event` or `both` waits and only from the expected `result_topic`.

`result_transport` selects result delivery for one run. Endpoint/OpenAPI/workflow-level `transport_security` only describes protection for those transports and must not contain `selected_transport` or change the delivery mode.

The result contract is defined on the endpoint operation through `async_event_contracts`. The contract key must match `expected_event_type` from the resolution profile step. When a wait is opened, the platform stores a contract snapshot in `wait_state`, so already running waits are not affected by later endpoint-operation edits. For old waits without a snapshot, the runtime may fall back to the active configuration by `origin.endpoint_id`, `origin.operation_id` and `event_type`. The platform validates `success.result`, `progress.result` and `error.error` with that JSON Schema before updating `wait_state`. `wait_state` and the idempotency receipt store a safe compact external event version: secrets are masked and large payloads are replaced with a summary.

## Audit and Security

All sensitive administrative actions require a permission check and write an audit event. Secrets must be stored in environment variables or an external secret store; configuration stores only secret references.

Before ticket text is sent to an LLM, minimal redaction is applied: email addresses, phone numbers, bearer/API tokens and assignments such as `password=...`, `token=...`, `секрет=...`, `ключ=...` are replaced with technical markers. Dry-run traces show only the redaction fact and marker types, not the original values.

## Language Rules

The UI supports Russian and English. Technical identifiers are not translated: API paths, environment variables, JSON fields, service names, Kafka topics, enum/status ids, tool names, endpoint ids and operation ids.
