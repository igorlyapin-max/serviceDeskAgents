# serviceDeskAgents n8n/Kafka Current Stand

## Defaults

- Default async command topic: `tool.commands`
- Default external result topic: `external.events`
- Host Kafka bootstrap: `127.0.0.1:19092`
- Docker-network Kafka bootstrap: `redpanda:9092`
- n8n webhook base: `http://127.0.0.1:5678/webhook`
- Orchestrator public URL for host-side tools: `http://127.0.0.1:18088`
- Orchestrator public URL for callbacks from dockerized n8n: `http://hostmachine:18088`
- CMDBuild base URL for dockerized n8n: `http://hostmachine:8090/cmdbuild`
- Long-running n8n callback endpoint: `POST /external-events/n8n`

## Environment

```text
KAFKA_BOOTSTRAP_SERVERS=127.0.0.1:19092
N8N_KAFKA_BOOTSTRAP_SERVERS=redpanda:9092
KAFKA_API_VERSION=2.3
ORCHESTRATOR_KAFKA_API_VERSION=2.3
TOOL_COMMAND_TOPIC=tool.commands
TOOL_COMMAND_WORKER_GROUP_ID=servicedesk-tool-workers
EXTERNAL_EVENT_TOPIC=external.events
EXTERNAL_EVENT_WORKER_GROUP_ID=servicedesk-external-event-workers
EXTERNAL_EVENT_WORKER_OFFSET_RESET=earliest
AGENT_TASK_TOPIC=agent.tasks
AGENT_TASK_LEASE_SECONDS=60
N8N_WEBHOOK_BASE_URL=http://127.0.0.1:5678/webhook
N8N_WEBHOOK_TOKEN=...
N8N_BLOCK_ENV_ACCESS_IN_NODE=false
N8N_OPENAPI_DEFAULT_LOCALE=ru
N8N_WORKFLOW_DEBUG=off
ORCHESTRATOR_PUBLIC_URL=http://hostmachine:18088
CMDBUILD_BASE_URL=http://hostmachine:8090/cmdbuild
APP_ENV=local
SERVICE_DESK_ENV=local
N8N_ENVIRONMENT=local
N8N_INTERNAL_WEBHOOK_BASE_URL=http://127.0.0.1:5678/webhook
INTEGRATION_CALLBACK_TOKEN=...
INTEGRATION_CALLBACK_TOKEN__N8N=...
ZABBIX_RUNBOOK_REQUIRED_ORIGINS=
ZABBIX_API_URLS_BY_ORIGIN=
ZABBIX_API_TOKENS_BY_ORIGIN=
```

`N8N_WEBHOOK_TOKEN` is the shared secret for orchestrator/async-tool-worker -> n8n webhook calls via `X-ServiceDesk-Token`; it must be present in the orchestrator-side runtime and in n8n. For local/dev, the shared `INTEGRATION_CALLBACK_TOKEN` is acceptable for n8n -> orchestrator callbacks. For shared/staging/production, prefer `INTEGRATION_CALLBACK_TOKEN__N8N`.

The n8n container also needs the callback and Kafka result-delivery env values. In compose, `ORCHESTRATOR_PUBLIC_URL`, `INTEGRATION_CALLBACK_TOKEN`, `INTEGRATION_CALLBACK_TOKEN__N8N`, `N8N_KAFKA_BOOTSTRAP_SERVERS`, Kafka security variables, and `EXTERNAL_EVENT_TOPIC` are passed into n8n so long-running workflows can return ExternalEvent results.

Email workflows receive SMTP `from` and `replyTo` as required runbook payload fields. For provider-monitor runbooks, `replyTo` is also the mailbox address used to filter the indexed provider reply.

Provider/email polling workflows must write a compact progress diagnostic on every polling cycle before the next wait. On this stand the diagnostic must be returned as `ExternalEvent.status=progress` and include `service_request`, `reply_mailbox_address`, `mailbox_indexed_count`, `match_count`, `poll_iteration`, `last_poll_at`, `next_poll_at`, `correlation_id`, and `wait_id`. The terminal `ExternalEvent` remains the only business result that closes the wait.

Zabbix runbooks additionally need `ZABBIX_API_TOKENS_BY_ORIGIN` and `ZABBIX_API_URLS_BY_ORIGIN` in the n8n container when a smoke or deployment requires live Zabbix. The default local `.env.example` leaves `ZABBIX_RUNBOOK_REQUIRED_ORIGINS` empty so a fresh runtime-check does not require a token. The origin key is the UI origin from `problemUrl`, for example `http://localhost:8081`. If Zabbix runs in a separate Docker Compose project, start this stack with `docker-compose.zabbix.yml` so n8n can resolve `zabbix-web` on the external Docker network.

## Runtime Commands

Recommended Compose runtime:

```bash
make runtime-up
make runtime-check
```

`runtime-up` starts `orchestrator`, `async-outbox-publisher`, `async-tool-worker`, `async-external-event-worker`, and `async-agent-task-worker` together with the required infrastructure. `runtime-check` calls `/readyz` and fails if Kafka, n8n, or one of the async worker heartbeats is not ready.

```bash
PYTHON=.venv/bin/python make async-outbox-publisher
PYTHON=.venv/bin/python make async-outbox-publish-once
PYTHON=.venv/bin/python make async-tool-worker
PYTHON=.venv/bin/python make async-external-event-worker
PYTHON=.venv/bin/python make async-agent-task-worker
```

Direct module forms:

```bash
.venv/bin/python -m apps.orchestrator.app.kafka_runtime publisher --topic ${TOOL_COMMAND_TOPIC:-tool.commands}
.venv/bin/python -m apps.orchestrator.app.kafka_runtime publish-once --limit 50
.venv/bin/python -m apps.orchestrator.app.kafka_runtime worker --topic ${TOOL_COMMAND_TOPIC:-tool.commands}
.venv/bin/python -m apps.orchestrator.app.kafka_runtime external-event-worker --topic ${EXTERNAL_EVENT_TOPIC:-external.events}
.venv/bin/python -m apps.orchestrator.app.kafka_runtime agent-task-worker --topic ${AGENT_TASK_TOPIC:-agent.tasks}
```

`publisher`, `worker`, `external-event-worker`, and `agent-task-worker` are long-running processes by default. `publish-once` is a bounded batch command for manual diagnostics. Add `--limit N` only for manual diagnostics or tests.

`Contracts: OpenAPI discovery` in n8n reads locale settings from env. If `N8N_BLOCK_ENV_ACCESS_IN_NODE=true`, `GET /webhook/contracts/openapi.json` fails in the Code node and can return an empty body; keep it `false` for the local stand.

When the active n8n workflow must be reconciled with generated workflow JSON, use the n8n-side publish/update helper instead of bespoke patch scripts:

```bash
cd ../n8n
node scripts/publish-generated-workflow.mjs workflows/provider-channel-repair-monitor-webhook.json providerChannelRepairMonitor
docker restart servicedesk-agents-n8n
```

Generated workflow JSON is the source of truth; bespoke patch scripts must not duplicate business workflow logic.

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

`result_transport` is delivery selection for this run. `transport_security` belongs to endpoint/OpenAPI/workflow metadata and only describes protection for HTTP callback or Kafka/event-queue transport.

## Source Files

- `.env.example`
- `docker-compose.yml`
- `docs/ru/DEPLOYMENT_GUIDE.md`
- `docs/en/DEPLOYMENT_GUIDE.md`
- `apps/orchestrator/app/processing.py`
- `apps/orchestrator/app/kafka_runtime.py`
- `contracts/integrations/external-event.schema.json`
