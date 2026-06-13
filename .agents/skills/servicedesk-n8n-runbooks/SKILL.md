---
name: servicedesk-n8n-runbooks
description: "Use in /home/lsk/projects/serviceDeskAgents when creating, reviewing, importing, or wiring n8n runbook workflows, Kafka tool commands, and external-event callbacks for this repository."
---

# ServiceDeskAgents n8n Runbooks

Use this project-local skill after the global `n8n-runbook-conventions` rules. This file contains current stand facts for this repository.

## Current Stand

- Default outbound command topic: `tool.commands`.
- Default inbound external result topic: `external.events`.
- Kafka/Redpanda from host: `127.0.0.1:19092`.
- Kafka/Redpanda from docker network: `redpanda:9092`.
- Env: `KAFKA_BOOTSTRAP_SERVERS=127.0.0.1:19092`, `TOOL_COMMAND_TOPIC=tool.commands`, `EXTERNAL_EVENT_TOPIC=external.events`.
- n8n webhook base URL: `N8N_WEBHOOK_BASE_URL=http://127.0.0.1:5678/webhook`.
- Orchestrator callback base: `ORCHESTRATOR_PUBLIC_URL=http://127.0.0.1:18088`.
- Long-running n8n callback: `POST /external-events/n8n` with `X-ServiceDesk-Callback-Token`.

## Workflow Contract

- Outbound flow: `ProcessingStore wait_state -> processing_outbox -> Kafka tool.commands -> async worker -> n8n webhook`.
- Inbound flow: `n8n -> POST /external-events/n8n` or `n8n -> Kafka external.events` -> `wait_state update -> agent.tasks continuation`.
- n8n payload must carry `case_id`, `run_id`, `wait_id`, `correlation_id`, `event_type`, `callback_url`, `idempotency_key_base`, `result_transport`, `result_topic`, and runbook business parameters such as `runbook_code`.
- Keep result delivery and transport security separate: `result_transport` in `invocation.extensions.async_callback` selects `http_callback`, `kafka_event`, or `both` for one run; `transport_security` in endpoint/OpenAPI/workflow metadata only describes how HTTP or Kafka is protected.
- Each returned ExternalEvent must use a stable per-event `idempotency_key`, for example `<idempotency_key_base>:<event_id>`.
- Kafka result delivery is accepted only for waits with `result_transport=kafka_event|both` and only from the expected `result_topic`.
- n8n must return external events only; it must not close or escalate cases directly.

## Source Of Truth

Read `references/current-stand.md` for exact repo paths and operator commands before changing workflows or documentation.
