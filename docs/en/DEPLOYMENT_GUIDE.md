# AI ServiceDesk Deployment Guide

## Requirements

The local MVP requires:

- Linux host;
- Docker Engine;
- Docker Compose plugin;
- Git;
- Python 3.12+ for local backend development;
- Node.js LTS for static UI checks.

GPU is not required. The local model runs through vLLM CPU and is used as a smoke/integration backend, not as the final quality target.

## Environment Variables

Create `.env` from `.env.example`.

Key parameters:

```text
COMPOSE_PROJECT_NAME=servicedesk-agents
POSTGRES_PORT=15432
REDIS_PORT=16379
KAFKA_PORT=19092
KAFKA_BOOTSTRAP_SERVERS=127.0.0.1:19092
KAFKA_API_VERSION=2.8.0
TOOL_COMMAND_TOPIC=tool.commands
N8N_PORT=5678
ORCHESTRATOR_PORT=18088
ORCHESTRATOR_PUBLIC_URL=http://127.0.0.1:18088
LITELLM_PORT=4000
VLLM_PORT=8000
APP_ENV=local
METRICS_ALLOWED_IPS=127.0.0.1,::1
```

Secrets are configured through `.env` or an external secret store:

- `POSTGRES_PASSWORD`;
- `N8N_DB_PASSWORD`;
- `OPENAI_API_KEY`;
- `LITELLM_MASTER_KEY`;
- `N8N_ENCRYPTION_KEY`;
- `N8N_WEBHOOK_TOKEN`;
- `INTEGRATION_CALLBACK_TOKEN` for local/dev or `INTEGRATION_CALLBACK_TOKEN__<SOURCE>` for shared/staging/production.

Do not commit `.env` to git. Docker Compose no longer supplies development passwords by default: if a required secret is missing, `docker compose config` fails. `change_me_*` values in `.env.example` are placeholders and must be replaced before using a shared environment or production.

The current MVP is intended for local single-node operation. For shared stands, use `APP_ENV=shared`, `APP_ENV=staging`, `APP_ENV=uat` or `APP_ENV=preprod`; for production use `APP_ENV=production`. In all non-local environments, replace development secrets, do not use `SECURITY_AUTH_MODE=dev_header`, and configure a second log sink with `LOG_SINKS=jsonl` or `LOG_SINKS=syslog`.

The Admin UI model screen may write secrets to `.env` only in local/dev mode. With `APP_ENV=production`, this write path is forbidden: keys must come from environment variables, a container secret store or an external Vault.

The PostgreSQL init script creates the n8n user and database from `N8N_DB_NAME`, `N8N_DB_USER` and `N8N_DB_PASSWORD`. These values must match the `n8n` service settings; init scripts do not use a hardcoded password.

## Docker Compose Services

Base stack:

- `postgres` - PostgreSQL with pgvector;
- `redis` - cache, locks and temporary state;
- `redpanda` - Kafka-compatible broker for asynchronous events;
- `n8n` - integration workflows and webhooks.

LLM profile:

- `litellm` - OpenAI-compatible gateway;
- `vllm-cpu` - local CPU inference backend.

## Start the Base Stack

Validate Compose configuration:

```bash
docker compose config
```

Start base services:

```bash
docker compose up -d postgres redis redpanda n8n
```

Check service status:

```bash
docker compose ps
```

## Start the LLM Profile

Start LiteLLM and vLLM CPU:

```bash
docker compose --profile llm up -d vllm-cpu litellm
```

Check LiteLLM:

```bash
curl -sS http://127.0.0.1:4000/v1/models \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}"
```

## Start FastAPI

Install the backend into a local virtual environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

Start the orchestrator:

```bash
.venv/bin/python -m uvicorn apps.orchestrator.app.main:app \
  --host 127.0.0.1 \
  --port ${ORCHESTRATOR_PORT:-18088}
```

UI URLs:

```text
http://127.0.0.1:18088/admin
http://127.0.0.1:18088/debug
http://127.0.0.1:18088/operator  # local compatibility alias for the debug console
```

Health endpoints:

```text
http://127.0.0.1:18088/healthz  # simple liveness
http://127.0.0.1:18088/readyz   # readiness for state DB, configuration, models and knowledge base
http://127.0.0.1:18088/metrics  # MVP Prometheus-compatible technical metrics
```

By default, `/metrics` is available only from loopback IPs (`127.0.0.1`, `::1`). For an external Prometheus instance, set allowed addresses or CIDR ranges in `METRICS_ALLOWED_IPS`.

In production, `/readyz` also reports that SQLite state DB is MVP storage and is not production-ready. A production deployment must move state storage to a managed database and preserve callback idempotency contracts.

`/readyz` returns HTTP `503` when `status=error`. For `status=degraded`, it returns `200` by default; set `READYZ_STRICT=true` if the load balancer must remove degraded instances.

## Async Kafka Runtime

For long-running n8n workflows, the orchestrator does not keep the HTTP request open. It writes a command to the outbox, the publisher sends it to Kafka, and a separate worker calls the n8n webhook.

Publish pending outbox messages to Kafka once. This is a batch command; without an explicit `--limit`, the Makefile uses `${OUTBOX_PUBLISH_LIMIT:-50}`:

```bash
.venv/bin/python -m apps.orchestrator.app.kafka_runtime publish-once --limit 50
# or
PYTHON=.venv/bin/python make async-outbox-publish-once
```

Run the long-running tool command worker:

```bash
.venv/bin/python -m apps.orchestrator.app.kafka_runtime worker --topic ${TOOL_COMMAND_TOPIC:-tool.commands}
# or
PYTHON=.venv/bin/python make async-tool-worker
```

Run the long-running inbound Kafka result worker:

```bash
.venv/bin/python -m apps.orchestrator.app.kafka_runtime external-event-worker --topic ${EXTERNAL_EVENT_TOPIC:-external.events}
# or
PYTHON=.venv/bin/python make async-external-event-worker
```

For the local stand, the default outbound n8n runbook command topic is `tool.commands`; the default inbound external event topic is `external.events`. Kafka is reachable from the host at `127.0.0.1:19092` and from the docker network at `redpanda:9092`.

Kafka transport security is selected by the administrator through env. Local/dev default:

```text
KAFKA_SECURITY_PROTOCOL=PLAINTEXT
```

Production baseline:

```text
# SASL over TLS
KAFKA_SECURITY_PROTOCOL=SASL_SSL
KAFKA_SASL_MECHANISM=PLAIN|SCRAM-SHA-256|SCRAM-SHA-512
KAFKA_SASL_USERNAME=<service-account>
KAFKA_SASL_PASSWORD=<secret>
KAFKA_SSL_CA_FILE=/etc/kafka/ca.pem

# or mTLS
KAFKA_SECURITY_PROTOCOL=SSL
KAFKA_SSL_CA_FILE=/etc/kafka/ca.pem
KAFKA_SSL_CERT_FILE=/etc/kafka/client.pem
KAFKA_SSL_KEY_FILE=/etc/kafka/client.key
```

Kafka is not an HTTPS transport. Production also requires broker ACLs that restrict the producer/consumer identity to the approved topics.

`worker` and `external-event-worker` run as long-running consumer processes and do not stop after a message count unless `--limit` is provided. For manual diagnostics, add `--limit N`, for example to process only the first 3 messages. In production, run these processes under a supervisor, systemd or a container restart policy.

## Logging and Diagnostics

The primary structured logging pipeline writes JSON events to stdout and to a second sink. For the MVP, the default second sink is a JSONL file:

```text
LOG_LEVEL=INFO
LOG_SINKS=stdout,jsonl
LOG_JSONL_PATH=state/logs/servicedesk-events.jsonl
```

For production, use `LOG_SINKS=stdout,syslog` with `SYSLOG_ADDRESS=/dev/log` or a syslog collector address. Debug/diagnostic mode is enabled without code changes:

```text
DEBUG_LOGGING_ENABLED=false
DEBUG_LOGGING_LEVEL=Basic  # Basic or Verbose
```

`Verbose` is intended only for temporary diagnostics; token/password/secret/key and Russian equivalents are masked before logging.

## Ports

| Component | Host port | Purpose |
| --- | ---: | --- |
| PostgreSQL | `15432` | Application, n8n and pgvector storage |
| Redis | `16379` | Cache, locks and temporary state |
| Redpanda/Kafka | `19092` | Command and event transport |
| n8n | `5678` | Integration workflows and webhooks |
| LiteLLM | `4000` | OpenAI-compatible LLM gateway |
| vLLM CPU | `8000` | Local CPU inference backend |
| FastAPI orchestrator | `18088` | API, Admin UI and Debug Console |

## Checks

Backend, UI and contracts:

```bash
make PYTHON=.venv/bin/python stage14-check
```

The same check runs the minimal unit test suite. It can also be executed directly:

```bash
make PYTHON=.venv/bin/python test
```

Documentation:

```bash
make docs-check
```

Compose:

```bash
docker compose config
```

## Kafka Topics

The runtime uses a Kafka-ready outbox and the following topics:

- `case.inbound-events`;
- `case.events`;
- `agent.tasks`;
- `agent.results`;
- `tool.commands`;
- `tool.results`;
- `timer.commands`;
- `timer.events`;
- `integration.events`;
- `external.events`;
- `audit.events`;
- `dead-letter`.

Topics must be managed by infrastructure. Application services must not create topics at startup.

`tool.commands` is the default topic for outbound async ReAct calls and n8n runbook commands. The producer reads `processing_outbox`, publishes the envelope message to this topic and marks the outbox row as `published` only after Kafka confirms delivery. The worker commits a Kafka offset only after successful command processing or after a poison message is durably written to `dead-letter`.

`external.events` is the default topic for inbound results from external async operations. The `ExternalEvent` consumer commits a Kafka offset only after a durable result, duplicate receipt, or `dead-letter` record exists. It uses separate `EXTERNAL_EVENT_TOPIC`, `EXTERNAL_EVENT_WORKER_GROUP_ID`, and `EXTERNAL_EVENT_WORKER_OFFSET_RESET` variables.

## Long-Running Actions and External Events

The platform owns the lifecycle of long waits. For scenarios such as "a provider email was sent, check again in an hour" or "n8n is running a long workflow", the runtime creates a `wait_state` with `case_id`, `wait_id`, `correlation_id`, expected `event_type`, `deadline_at` and `origin`.

When a wait is opened by a ReAct call, `origin.kind` is `react_call` and stores the ReAct call, launch, endpoint, endpoint operation and parameters without secrets. Client questions, approvals and technical timers use the same `wait_state` model with a different `origin.kind`.

The external executor receives these identifiers together with the callback URL:

```text
POST http://127.0.0.1:18088/external-events/{source}
Header: X-ServiceDesk-Callback-Token: ${INTEGRATION_CALLBACK_TOKEN}
```

Local/dev callback URL may use `http://127.0.0.1`. In shared/staging/production set `ORCHESTRATOR_PUBLIC_URL=https://...`; outbound n8n webhook base is configured with `N8N_WEBHOOK_BASE_URL=https://...`.

In local/dev, the shared `INTEGRATION_CALLBACK_TOKEN` is allowed. In shared/staging/production, use source-specific variables, for example `INTEGRATION_CALLBACK_TOKEN__N8N` for `POST /external-events/n8n`.

For a long-running n8n runbook, the worker passes `case_id`, `run_id`, `wait_id`, `correlation_id`, `event_type`, `callback_url`, `idempotency_key_base`, `result_transport`, `result_topic`, and operation business parameters to the webhook. n8n must not close or escalate the case directly: the result is returned through the allowed result transport.

The event body must match the envelope contract in `contracts/integrations/external-event.schema.json`. Required fields are `event_id`, `case_id`, `correlation_id`, `source`, `event_type`, `status`, `received_at` and `idempotency_key`. Allowed statuses are `progress`, `success`, `error`, `timeout` and `cancelled`.

The envelope validates the common event shape. The `result` or `error` payload is additionally validated with the `async_event_contracts` snapshot from the endpoint operation that opened the wait. For old waits without a snapshot, the runtime may fall back to the active configuration by `wait_state.origin.endpoint_id`, `wait_state.origin.operation_id` and `event_type`.

External systems do not close or escalate cases directly. They only return a result, error or progress update. `idempotency_key_base` is the command key; each `ExternalEvent` must have its own stable `idempotency_key`, for example `<idempotency_key_base>:<event_id>`. The platform deduplicates events by `idempotency_key`; a repeated key with a different `event_id`, `source`, `case_id`, `correlation_id`, `wait_id`, `event_type`, `status`, or payload hash is rejected as `external_event_idempotency_conflict`. Event payload is masked and compacted before it is written to timeline, outbox and receipt storage.

`result_transport` is a runtime rule, not a hint. HTTP callback is accepted only for `http_callback` or `both` waits; Kafka events are accepted only for `kafka_event` or `both` waits and only from the expected `result_topic`. In shared/staging/production, Kafka producer identity must be restricted with ACL/SASL/mTLS or an equivalent infrastructure control.

Do not mix up `result_transport` and `transport_security`. `result_transport` lives in the async command package (`invocation.extensions.async_callback.result_transport`) and selects the delivery mode for one run: `http_callback`, `kafka_event` or `both`. `transport_security` is published in OpenAPI/endpoint/workflow catalogs as machine-readable metadata for protecting the available transports: HTTP uses administrator-selected HTTPS URLs and token auth, while Kafka is not HTTPS and is protected by broker ACLs with `SASL_SSL`, `SSL`/mTLS, signed envelopes or an equivalent infrastructure control.

## Production Hardening Backlog

Before production operation, MVP limitations must be moved to production-grade infrastructure:

- replace SQLite state DB with a managed PostgreSQL path for cases, callbacks, processing runs and idempotency keys;
- move rate limiting and distributed locks to Redis;
- add circuit breakers for integrations and LLM backends;
- add CSRF protection for state-changing browser APIs;
- decompose large backend/UI modules after contracts stabilize;
- add OpenTelemetry tracing and alert rules for latency, error rate and DLQ growth;
- connect an external collector for `/metrics` and centralized structured logs;
- move secrets from `.env` to Vault or an infrastructure secret store;
- run outbox/Kafka handlers as separate worker processes with lease, heartbeat and retry policy;
- define backup/restore procedure for state DB, configurations, captured mocks and knowledge base.

## Update and Restart

1. Pull the new code version.
2. Check `.env` and new variables.
3. Run `docker compose config`.
4. Restart changed services.
5. Restart the FastAPI orchestrator.
6. Run smoke checks.

## Troubleshooting

- If Admin UI does not show new sections, restart FastAPI and reload the page without cache.
- If LiteLLM does not respond, check `LITELLM_MASTER_KEY`, `OPENAI_API_KEY` and the `llm` profile.
- If Kafka is unavailable, check the `redpanda` container and port `19092`.
- If an n8n callback is rejected, check `INTEGRATION_CALLBACK_TOKEN` and endpoint id.
