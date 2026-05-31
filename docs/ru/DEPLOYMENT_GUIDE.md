# Инструкция по развертыванию AI ServiceDesk

## Требования

Для локального MVP нужны:

- Linux host;
- Docker Engine;
- Docker Compose plugin;
- Git;
- Python 3.12+ для локального backend-разработчика;
- Node.js LTS для проверки статического UI.

GPU не требуется. Локальная модель запускается через vLLM CPU и используется как smoke/integration backend, а не как финальный ориентир качества.

## Переменные окружения

Создайте `.env` на основе `.env.example`.

Ключевые параметры:

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

Секреты задаются через `.env` или внешнее хранилище секретов:

- `OPENAI_API_KEY`;
- `LITELLM_MASTER_KEY`;
- `N8N_ENCRYPTION_KEY`;
- `N8N_WEBHOOK_TOKEN`;
- `INTEGRATION_CALLBACK_TOKEN`.

Не коммитьте `.env` в git.

Текущий MVP рассчитан на локальный single-node режим. Для production обязательно задайте `APP_ENV=production`, замените все dev-секреты и не используйте `SECURITY_AUTH_MODE=dev_header`. При production-окружении приложение остановится на старте, если обнаружит dev auth или default secrets.

Экран моделей в Admin UI может записывать секреты в `.env` только в локальном/dev режиме. При `APP_ENV=production` такая запись запрещена: ключи должны поступать из переменных окружения, контейнерного secret store или внешнего Vault.

## Сервисы Docker Compose

Базовый контур:

- `postgres` - PostgreSQL с pgvector;
- `redis` - cache, locks и временное состояние;
- `redpanda` - Kafka-compatible broker для асинхронных событий;
- `n8n` - интеграционные workflows и webhooks.

LLM-профиль:

- `litellm` - OpenAI-compatible gateway;
- `vllm-cpu` - локальный CPU inference backend.

## Запуск базового контура

Проверить конфигурацию:

```bash
docker compose config
```

Запустить базовые сервисы:

```bash
docker compose up -d postgres redis redpanda n8n
```

Проверить состояние:

```bash
docker compose ps
```

## Запуск LLM-профиля

Запустить LiteLLM и vLLM CPU:

```bash
docker compose --profile llm up -d vllm-cpu litellm
```

Проверить LiteLLM:

```bash
curl -sS http://127.0.0.1:4000/v1/models \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}"
```

## Запуск FastAPI

Установить backend в локальное окружение:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

Запустить оркестратор:

```bash
.venv/bin/python -m uvicorn apps.orchestrator.app.main:app \
  --host 127.0.0.1 \
  --port ${ORCHESTRATOR_PORT:-18088}
```

URL интерфейсов:

```text
http://127.0.0.1:18088/admin
http://127.0.0.1:18088/debug
http://127.0.0.1:18088/operator  # alias консоли отладки для локальной совместимости
```

Проверки доступности:

```text
http://127.0.0.1:18088/healthz  # простой liveness
http://127.0.0.1:18088/readyz   # readiness по state DB, конфигурации, моделям и базе знаний
http://127.0.0.1:18088/metrics  # Prometheus-совместимые технические метрики MVP
```

`/readyz` в production дополнительно показывает предупреждение, что SQLite state DB является MVP-хранилищем и не считается production-ready. Для промышленного запуска требуется вынести state DB в управляемое хранилище и сохранить контракты идемпотентности callback.

## Порты

| Компонент | Host port | Назначение |
| --- | ---: | --- |
| PostgreSQL | `15432` | Хранилище приложения, n8n и pgvector |
| Redis | `16379` | Cache, locks и временное состояние |
| Redpanda/Kafka | `19092` | Транспорт команд и событий |
| n8n | `5678` | Integration workflows и webhooks |
| LiteLLM | `4000` | OpenAI-compatible LLM gateway |
| vLLM CPU | `8000` | Local CPU inference backend |
| FastAPI orchestrator | `18088` | API, Admin UI и консоль отладки |

## Проверки

Backend, UI и контракты:

```bash
make PYTHON=.venv/bin/python stage14-check
```

Минимальный набор unit tests запускается той же командой и отдельно:

```bash
make PYTHON=.venv/bin/python test
```

Документация:

```bash
make docs-check
```

Compose:

```bash
docker compose config
```

## Kafka topics

Runtime использует Kafka-ready outbox и следующие topics:

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

Topics должны управляться инфраструктурой. Сервисы приложения не должны создавать topics на старте.

## Production hardening backlog

Перед промышленной эксплуатацией нужно вынести MVP-ограничения в полноценную инфраструктуру:

- заменить SQLite state DB на управляемый PostgreSQL-контур для кейсов, callbacks, processing runs и idempotency keys;
- подключить внешний collector для `/metrics` и централизованные structured logs;
- вынести секреты из `.env` в Vault или инфраструктурный secret store;
- запустить обработчики outbox/Kafka как отдельные worker-процессы с lease, heartbeat и retry policy;
- зафиксировать backup/restore процедуру для state DB, конфигураций, mock-захватов и базы знаний.

## Обновление и перезапуск

1. Получите новую версию кода.
2. Проверьте `.env` и новые переменные.
3. Выполните `docker compose config`.
4. Перезапустите измененные сервисы.
5. Перезапустите FastAPI orchestrator.
6. Выполните smoke checks.

## Troubleshooting

- Если Admin UI не показывает новые разделы, перезапустите FastAPI и обновите страницу без cache.
- Если LiteLLM не отвечает, проверьте `LITELLM_MASTER_KEY`, `OPENAI_API_KEY` и профиль `llm`.
- Если Kafka недоступна, проверьте контейнер `redpanda` и порт `19092`.
- Если n8n callback отклоняется, проверьте `INTEGRATION_CALLBACK_TOKEN` и endpoint id.
