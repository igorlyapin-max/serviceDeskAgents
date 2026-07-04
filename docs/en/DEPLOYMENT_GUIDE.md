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
KAFKA_API_VERSION=2.3
ORCHESTRATOR_KAFKA_API_VERSION=2.3
MCP_COMMAND_TOPIC=mcp.commands
EXTERNAL_EVENT_TOPIC=external.events
AGENT_TASK_TOPIC=agent.tasks
MCP_PROVIDER_OPS_BASE_URL=http://hostmachine:9000/mcp
ORCHESTRATOR_PORT=18088
ORCHESTRATOR_PUBLIC_URL=http://hostmachine:18088
CMDBUILD_BASE_URL=http://hostmachine:8090/cmdbuild
LITELLM_PORT=4000
LITELLM_PUBLIC_BASE_URL=http://127.0.0.1:4000/v1
COMPOSE_LITELLM_BASE_URL=http://litellm:4000/v1
VLLM_PORT=8000
APP_ENV=local
METRICS_ALLOWED_IPS=127.0.0.1,::1
```

Secrets are configured through `.env` or an external secret store:

- `POSTGRES_PASSWORD`;
- `OPENAI_API_KEY`;
- `LITELLM_MASTER_KEY`;
- `MCP_PROVIDER_OPS_TOKEN` for the dev Bearer token used by the external provider-ops MCP environment; production should use the configured OIDC/token exchange for that MCP environment;
- `INTEGRATION_CALLBACK_TOKEN` or `INTEGRATION_CALLBACK_TOKEN__<SOURCE>` only for local/dev callback token mode;
- `SECURITY_CALLBACK_AUTH_MODE=oidc_jwks`, `CALLBACK_OIDC_ISSUER`, `CALLBACK_OIDC_AUDIENCE`, `CALLBACK_OIDC_ALLOWED_CLIENT_IDS`, `CALLBACK_OIDC_JWKS_URL` for shared/staging/production callbacks. `oidc_proxy_jwt` is allowed only behind a trusted gateway/proxy and requires `CALLBACK_OIDC_PROXY_TRUSTED_IPS` or `CALLBACK_OIDC_PROXY_TRUST_HEADER` / `CALLBACK_OIDC_PROXY_TRUST_HEADER_VALUE`.

Do not commit `.env` to git. Docker Compose no longer supplies development passwords by default: if a required secret is missing, `docker compose config --quiet` fails. `change_me_*` values in `.env.example` are placeholders and must be replaced before using a shared environment or production.

The current MVP is intended for local single-node operation. For shared stands, use `APP_ENV=shared`, `APP_ENV=staging`, `APP_ENV=uat` or `APP_ENV=preprod`; for production use `APP_ENV=production`. In all non-local environments, replace development secrets, do not use `SECURITY_AUTH_MODE=dev_header`, and configure a second log sink with `LOG_SINKS=jsonl` or `LOG_SINKS=syslog`.

The Admin UI model screen may write secrets to `.env` only in local/dev mode. With `APP_ENV=production`, this write path is forbidden: keys must come from environment variables, a container secret store or an external Vault.

ServiceDeskAgents does not run n8n and does not store its credentials. If a concrete external MCP environment is implemented with n8n, its variables and secrets are configured in that environment's own project/runtime.

## Docker Compose Services

Base stack:

- `postgres` - PostgreSQL with pgvector;
- `redis` - cache, locks and temporary state;
- `redpanda` - Kafka-compatible broker for asynchronous events;
- `litellm` - shared local OpenAI-compatible gateway on `http://127.0.0.1:4000/v1`.

Optional LLM profile:

- `vllm-cpu` - local CPU inference backend.

## Start the Base Stack

Validate Compose configuration:

```bash
docker compose config --quiet
```

Start base services:

```bash
docker compose up -d postgres redis redpanda litellm
```

Start the full runtime stand with FastAPI and async workers:

```bash
make runtime-up
make runtime-check
```

Check service status:

```bash
docker compose ps
```

External MCP environments must be reachable through the URLs configured in `mcp_environments`. Local/dev uses a Bearer token; production uses OIDC/token exchange or equivalent authorization for the selected MCP environment.

## Start the LLM Gateway and Local CPU Model

`make runtime-up` starts LiteLLM as the required gateway for model-based slot extraction. Inside Docker Compose the orchestrator uses `http://litellm:4000/v1`; from the host and from other local projects the gateway is available at `http://127.0.0.1:4000/v1`.

Start vLLM CPU only when the active backend is the local CPU model:

```bash
docker compose --profile llm up -d vllm-cpu
```

Check LiteLLM:

```bash
curl -sS http://127.0.0.1:4000/v1/models \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}"
```

## Start FastAPI Locally Without Compose

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

This mode is useful for API/UI development. Async MCP capability calls require the full runtime: `async-outbox-publisher`, `async-mcp-worker`, `async-external-event-worker`, and `async-agent-task-worker`. For the standard local stand, start them with `make runtime-up`.

UI URLs:

```text
http://127.0.0.1:18088/admin
http://127.0.0.1:18088/debug
http://127.0.0.1:18088/operator  # local compatibility alias for the debug console
```

Health endpoints:

```text
http://127.0.0.1:18088/healthz  # simple liveness
http://127.0.0.1:18088/readyz   # readiness for state DB, configuration, models, Kafka, MCP workers and async runtime
http://127.0.0.1:18088/metrics  # MVP Prometheus-compatible technical metrics
```

By default, `/metrics` is available only from loopback IPs (`127.0.0.1`, `::1`). For an external Prometheus instance, set allowed addresses or CIDR ranges in `METRICS_ALLOWED_IPS`.

In production, `/readyz` also reports that SQLite state DB is MVP storage and is not production-ready. A production deployment must move state storage to a managed database and preserve callback idempotency contracts.

`/readyz` returns HTTP `503` when `status=error`. For `status=degraded`, it returns `200` by default; set `READYZ_STRICT=true` if the load balancer must remove degraded instances.

## Async Kafka Runtime

For long-running external execution, the orchestrator does not keep the HTTP request open. It writes a capability command to the outbox, the publisher sends it to Kafka, and a separate worker calls an external MCP environment.

Recommended Docker Compose start:

```bash
make runtime-up
make runtime-check
```

`runtime-check` verifies the public LiteLLM endpoint and `/readyz`; readiness fails when Kafka or the model gateway is unavailable, when heartbeat is stale for `async-outbox-publisher`, `async-mcp-worker`, `async-external-event-worker` or `async-agent-task-worker`, or when `mcp.commands` remains pending longer than the allowed threshold.

Run the long-running outbox publisher to Kafka. This process is required for a working stand: without it, async commands stay in `processing_outbox` and MCP capabilities are not called.

```bash
.venv/bin/python -m apps.orchestrator.app.kafka_runtime publisher
# or
PYTHON=.venv/bin/python make async-outbox-publisher
```

Publish pending outbox messages to Kafka once for manual diagnostics. This is a batch command; without an explicit `--limit`, the Makefile uses `${OUTBOX_PUBLISH_LIMIT:-50}`:

```bash
.venv/bin/python -m apps.orchestrator.app.kafka_runtime publish-once --limit 50
# or
PYTHON=.venv/bin/python make async-outbox-publish-once
```

Run the long-running MCP capability command worker:

```bash
.venv/bin/python -m apps.orchestrator.app.kafka_runtime mcp-worker --topic ${MCP_COMMAND_TOPIC:-mcp.commands}
# or
PYTHON=.venv/bin/python make async-mcp-worker
```

Run the long-running inbound Kafka result worker:

```bash
.venv/bin/python -m apps.orchestrator.app.kafka_runtime external-event-worker --topic ${EXTERNAL_EVENT_TOPIC:-external.events}
# or
PYTHON=.venv/bin/python make async-external-event-worker
```

Run the long-running agent continuation worker after terminal ExternalEvent:

```bash
.venv/bin/python -m apps.orchestrator.app.kafka_runtime agent-task-worker --topic ${AGENT_TASK_TOPIC:-agent.tasks}
# or
PYTHON=.venv/bin/python make async-agent-task-worker
```

For the local stand, the default outbound MCP capability command topic is `mcp.commands`; the default inbound external event topic is `external.events`; the default agent continuation task topic is `agent.tasks`. Kafka is reachable from the host at `127.0.0.1:19092` and from the docker network at `redpanda:9092`.

The external MCP environment receives only canonical capability input and async context. If it internally uses n8n, Zabbix, SMTP or other systems, their registries, secrets and network links are configured in that MCP environment's project, not in ServiceDeskAgents.

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
| PostgreSQL | `15432` | Application and pgvector storage |
| Redis | `16379` | Cache, locks and temporary state |
| Redpanda/Kafka | `19092` | Command and event transport |
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
docker compose config --quiet
```

## Kafka Topics

The runtime uses a Kafka-ready outbox and the following topics:

- `case.inbound-events`;
- `case.events`;
- `agent.tasks`;
- `agent.results`;
- `mcp.commands`;
- `timer.commands`;
- `timer.events`;
- `external.events`;
- `audit.events`;
- `dead-letter`.

Topics must be managed by infrastructure. Application services must not create topics at startup.

`mcp.commands` is the default topic for outbound external MCP capability commands. The producer reads `processing_outbox`, publishes the envelope message to the message topic and marks the outbox row as `published` only after Kafka confirms delivery. Workers commit Kafka offsets only after successful command processing or after a poison message is durably written to `dead-letter`.

`external.events` is the default topic for inbound results from external async operations. The `ExternalEvent` consumer commits a Kafka offset only after a durable result, duplicate receipt, or `dead-letter` record exists. It uses separate `EXTERNAL_EVENT_TOPIC`, `EXTERNAL_EVENT_WORKER_GROUP_ID`, and `EXTERNAL_EVENT_WORKER_OFFSET_RESET` variables.

`agent.tasks` is the default topic for durable continuation after terminal ExternalEvent. `async-agent-task-worker` claims queued `langgraph_resume` tasks from the state DB, links them to the external-event receipt, and moves the run to its final status. Without this worker, an external result can be accepted while the scenario remains waiting for continuation.

## Runtime Crash Recovery

The current target is single-node durability. Containers can restart without losing already committed context when `ORCHESTRATOR_STATE_DB=/app/state/orchestrator.sqlite` is stored on the persistent `./state:/app/state` volume and Kafka keeps its topics durable.

After restart, the runtime keeps `case`, `processing_runs`, filled slot snapshots, `wait_states`, `processing_outbox`, `tool_command_receipts`, `external_event_receipts` and `agent_tasks`. Pending outbox messages are published again; stale `publishing` outbox leases and stale `agent_tasks` are reclaimed after their lease expires.

`ExternalEvent` recovery is idempotent: if the service crashes with a receipt in `processing`, redelivery of the same event with the same payload after `ASYNC_RECOVERY_RECEIPT_STALE_SECONDS` continues processing or completes the receipt from an already closed wait. `tool_command_receipts.status=processing` is not retried automatically: first verify whether the external MCP/n8n executor accepted the command. Every async runbook must persist `async_context.idempotency_key_base`, `correlation_id` and `wait_id` and make execution idempotent.

`/readyz` includes recovery diagnostics. Stuck receipts make async runtime `degraded`; with `READYZ_STRICT=false` this does not remove the instance from the load balancer, but it requires operator inspection.

## Long-Running Actions and External Events

The platform owns the lifecycle of long waits. For scenarios such as "a provider email was sent, check again in an hour" or "an external MCP environment is running a long workflow", the runtime creates a `wait_state` with `case_id`, `wait_id`, `correlation_id`, expected `event_type`, `deadline_at` and `origin`.

When a wait is opened by a capability call, `origin.kind` is `capability` and stores `capability_id`, `mcp_environment_id`, `mcp_tool_name`, launch and parameters without secrets. Client questions, approvals and technical timers use the same `wait_state` model with a different `origin.kind`.

The external executor receives these identifiers together with the callback URL:

```text
POST http://127.0.0.1:18088/external-events/{source}
Header: X-ServiceDesk-Callback-Token: ${INTEGRATION_CALLBACK_TOKEN}
```

For local/dev, the callback URL must be reachable from the external MCP environment. Use `ORCHESTRATOR_PUBLIC_URL=http://hostmachine:18088` by default for neighboring local Docker projects; compose adds the `hostmachine:host-gateway` alias, and the orchestrator must bind to `0.0.0.0`. In shared/staging/production set `ORCHESTRATOR_PUBLIC_URL=https://...`.

In local/dev, `SECURITY_CALLBACK_AUTH_MODE=source_token` is allowed with either shared `INTEGRATION_CALLBACK_TOKEN` or source-specific `INTEGRATION_CALLBACK_TOKEN__<SOURCE>`.

In shared/staging/production, set `SECURITY_CALLBACK_AUTH_MODE=oidc_jwks`. `ServiceDeskAgents` verifies the JWT signature against `CALLBACK_OIDC_JWKS_URL`, then validates `iss`, `aud`, `exp`, `nbf`, `sub` or `client_id`, `CALLBACK_OIDC_ALLOWED_CLIENT_IDS`, and `CALLBACK_OIDC_REQUIRED_SCOPE` (default `servicedesk.external_events.write`). `SECURITY_CALLBACK_AUTH_MODE=oidc_proxy_jwt` is allowed only when the JWT signature is already verified by a trusted gateway/proxy; configure `CALLBACK_OIDC_PROXY_TRUSTED_IPS` or `CALLBACK_OIDC_PROXY_TRUST_HEADER` / `CALLBACK_OIDC_PROXY_TRUST_HEADER_VALUE`.

For a long-running capability operation, the worker passes `case_id`, `run_id`, `wait_id`, `correlation_id`, `event_type`, `callback_url`, `idempotency_key_base`, `result_transport`, `result_topic`, and operation business parameters to the external MCP environment. The external executor must not close or escalate the case directly: the result is returned through the allowed result transport.

The event body must match the envelope contract in `contracts/integrations/external-event.schema.json`. Required fields are `event_id`, `case_id`, `correlation_id`, `source`, `event_type`, `status`, `received_at` and `idempotency_key`. Allowed statuses are `progress`, `success`, `error`, `timeout` and `cancelled`.

The envelope validates the common event shape. The `result` or `error` payload is additionally validated with the async result contract from the capability binding that opened the wait. Old waits without a snapshot must be restarted after migration to capability bindings; legacy endpoint fallback has been removed.

External systems do not close or escalate cases directly. They only return a result, error or progress update. `idempotency_key_base` is the command key; each `ExternalEvent` must have its own stable `idempotency_key`, for example `<idempotency_key_base>:<event_id>`. The platform deduplicates events by `idempotency_key`; a repeated key with a different `event_id`, `source`, `case_id`, `correlation_id`, `wait_id`, `event_type`, `status`, or payload hash is rejected as `external_event_idempotency_conflict`. Event payload is masked and compacted before it is written to timeline, outbox and receipt storage.

`result_transport` is a runtime rule, not a hint. HTTP callback is accepted only for `http_callback` or `both` waits; Kafka events are accepted only for `kafka_event` or `both` waits and only from the expected `result_topic`. In shared/staging/production, Kafka producer identity must be restricted with ACL/SASL/mTLS or an equivalent infrastructure control.

Do not mix up `result_transport` and transport auth. `result_transport` lives in the async command package (`invocation.extensions.async_callback.result_transport`) and selects the delivery mode for one run: `http_callback`, `kafka_event` or `both`. HTTP callback authorization is configured with `SECURITY_CALLBACK_AUTH_MODE`; Kafka is protected by broker ACLs with `SASL_SSL`, `SSL`/mTLS, signed envelopes or an equivalent infrastructure control.

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
3. Run `docker compose config --quiet`.
4. Restart changed services.
5. Restart the FastAPI orchestrator.
6. Run smoke checks.

## Troubleshooting

- If Admin UI does not show new sections, restart FastAPI and reload the page without cache.
- If LiteLLM does not respond, check the `litellm` container, `LITELLM_MASTER_KEY`, `OPENAI_API_KEY`, `LITELLM_PUBLIC_BASE_URL` and `COMPOSE_LITELLM_BASE_URL`.
- If Kafka is unavailable, check the `redpanda` container and port `19092`.
- If an MCP capability is not called, check `mcp_environments`, `capability_bindings`, `MCP_COMMAND_TOPIC`, `async-mcp-worker` heartbeat and external MCP environment authorization.
- If an external executor returns a domain error, diagnose that MCP environment's own runtime, secrets and network links in its project.
- If a callback is rejected, check `SECURITY_CALLBACK_AUTH_MODE`, callback source id, local/dev token or OIDC proxy JWT claims.
