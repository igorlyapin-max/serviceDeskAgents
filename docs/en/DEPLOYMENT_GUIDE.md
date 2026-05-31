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
N8N_PORT=5678
ORCHESTRATOR_PORT=18088
LITELLM_PORT=4000
VLLM_PORT=8000
APP_ENV=local
```

Secrets are configured through `.env` or an external secret store:

- `OPENAI_API_KEY`;
- `LITELLM_MASTER_KEY`;
- `N8N_ENCRYPTION_KEY`;
- `N8N_WEBHOOK_TOKEN`;
- `INTEGRATION_CALLBACK_TOKEN`.

Do not commit `.env` to git.

The current MVP is intended for local single-node operation. For production, set `APP_ENV=production`, replace all development secrets and do not use `SECURITY_AUTH_MODE=dev_header`. In a production environment the application fails at startup if it detects dev auth or default secrets.

The Admin UI model screen may write secrets to `.env` only in local/dev mode. With `APP_ENV=production`, this write path is forbidden: keys must come from environment variables, a container secret store or an external Vault.

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

In production, `/readyz` also reports that SQLite state DB is MVP storage and is not production-ready. A production deployment must move state storage to a managed database and preserve callback idempotency contracts.

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
- `audit.events`;
- `dead-letter`.

Topics must be managed by infrastructure. Application services must not create topics at startup.

## Production Hardening Backlog

Before production operation, MVP limitations must be moved to production-grade infrastructure:

- replace SQLite state DB with a managed PostgreSQL path for cases, callbacks, processing runs and idempotency keys;
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
