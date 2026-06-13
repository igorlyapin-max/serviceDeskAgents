# serviceDeskAgents n8n/Kafka Current Stand

## Defaults

- Default async command topic: `tool.commands`
- Default external result topic: `external.events`
- Host Kafka bootstrap: `127.0.0.1:19092`
- Docker-network Kafka bootstrap: `redpanda:9092`
- n8n webhook base: `http://127.0.0.1:5678/webhook`
- Orchestrator public URL for callbacks: `http://127.0.0.1:18088`
- Long-running n8n callback endpoint: `POST /external-events/n8n`

## Environment

```text
KAFKA_BOOTSTRAP_SERVERS=127.0.0.1:19092
KAFKA_API_VERSION=2.8.0
TOOL_COMMAND_TOPIC=tool.commands
TOOL_COMMAND_WORKER_GROUP_ID=servicedesk-tool-workers
EXTERNAL_EVENT_TOPIC=external.events
EXTERNAL_EVENT_WORKER_GROUP_ID=servicedesk-external-event-workers
EXTERNAL_EVENT_WORKER_OFFSET_RESET=earliest
N8N_WEBHOOK_BASE_URL=http://127.0.0.1:5678/webhook
ORCHESTRATOR_PUBLIC_URL=http://127.0.0.1:18088
INTEGRATION_CALLBACK_TOKEN=...
INTEGRATION_CALLBACK_TOKEN__N8N=...
```

For local/dev, the shared `INTEGRATION_CALLBACK_TOKEN` is acceptable. For shared/staging/production, prefer `INTEGRATION_CALLBACK_TOKEN__N8N`.

## Runtime Commands

```bash
PYTHON=.venv/bin/python make async-outbox-publish-once
PYTHON=.venv/bin/python make async-tool-worker
PYTHON=.venv/bin/python make async-external-event-worker
```

Direct module forms:

```bash
.venv/bin/python -m apps.orchestrator.app.kafka_runtime publish-once --limit 50
.venv/bin/python -m apps.orchestrator.app.kafka_runtime worker --topic ${TOOL_COMMAND_TOPIC:-tool.commands}
.venv/bin/python -m apps.orchestrator.app.kafka_runtime external-event-worker --topic ${EXTERNAL_EVENT_TOPIC:-external.events}
```

`publish-once` is a bounded batch command. `worker` and `external-event-worker` are long-running consumers by default; add `--limit N` only for manual diagnostics or tests.

## n8n Runbook Payload

The async worker passes a normal n8n webhook payload with the full `invocation` plus operation parameters. Runbook workflows should read the correlation package from:

```text
body.invocation.extensions.async_callback
```

Required callback fields for long-running runbooks:

- `case_id`
- `run_id`
- `wait_id`
- `correlation_id`
- `event_type`
- `callback_url`
- `idempotency_key_base`
- `result_transport`
- `result_topic`
- business parameters such as `runbook_code`

Return progress or completion using `contracts/integrations/external-event.schema.json`. Each returned event must use a stable per-event `idempotency_key`, for example `<idempotency_key_base>:<event_id>`. Kafka results are accepted only when the wait allows `kafka_event` or `both` and the consumed topic matches `result_topic`.

## Source Files

- `.env.example`
- `docker-compose.yml`
- `docs/ru/DEPLOYMENT_GUIDE.md`
- `docs/en/DEPLOYMENT_GUIDE.md`
- `apps/orchestrator/app/processing.py`
- `apps/orchestrator/app/kafka_runtime.py`
- `contracts/integrations/external-event.schema.json`
