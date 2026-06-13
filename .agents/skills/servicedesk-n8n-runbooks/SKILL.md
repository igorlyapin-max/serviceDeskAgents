---
name: servicedesk-n8n-runbooks
description: "Use in /home/lsk/projects/serviceDeskAgents when creating, reviewing, importing, or wiring n8n runbook workflows, Kafka tool commands, and external-event callbacks for this repository."
---

# ServiceDeskAgents n8n Runbooks

Use this project-local skill after the global `n8n-runbook-conventions` rules. This file contains current stand facts for this repository.

## Current Stand

- Default outbound command topic: `tool.commands`.
- Kafka/Redpanda from host: `127.0.0.1:19092`.
- Kafka/Redpanda from docker network: `redpanda:9092`.
- Env: `KAFKA_BOOTSTRAP_SERVERS=127.0.0.1:19092`, `TOOL_COMMAND_TOPIC=tool.commands`.
- n8n webhook base URL: `N8N_WEBHOOK_BASE_URL=http://127.0.0.1:5678/webhook`.
- Orchestrator callback base: `ORCHESTRATOR_PUBLIC_URL=http://127.0.0.1:18088`.
- Long-running n8n callback: `POST /external-events/n8n` with `X-ServiceDesk-Callback-Token`.

## Workflow Contract

- Outbound flow: `ProcessingStore wait_state -> processing_outbox -> Kafka tool.commands -> async worker -> n8n webhook`.
- Inbound flow: `n8n -> POST /external-events/n8n -> wait_state update -> agent.tasks continuation`.
- n8n payload must carry `case_id`, `run_id`, `wait_id`, `correlation_id`, `event_type`, `callback_url`, `idempotency_key`, and runbook business parameters such as `runbook_code`.
- n8n must return external events only; it must not close or escalate cases directly.

## Source Of Truth

Read `references/current-stand.md` for exact repo paths and operator commands before changing workflows or documentation.
