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

Секреты задаются через `.env` или внешнее хранилище секретов:

- `POSTGRES_PASSWORD`;
- `N8N_DB_PASSWORD`;
- `OPENAI_API_KEY`;
- `LITELLM_MASTER_KEY`;
- `N8N_ENCRYPTION_KEY`;
- `N8N_WEBHOOK_TOKEN`;
- `INTEGRATION_CALLBACK_TOKEN` для local/dev или `INTEGRATION_CALLBACK_TOKEN__<SOURCE>` для shared/staging/production.

Не коммитьте `.env` в git. Docker Compose не подставляет dev-пароли по умолчанию: если обязательный секрет не задан, `docker compose config` завершится ошибкой. Значения `change_me_*` из `.env.example` предназначены только как подсказки и должны быть заменены перед запуском общего стенда или production.

Текущий MVP рассчитан на локальный single-node режим. Для общих стендов используйте `APP_ENV=shared`, `APP_ENV=staging`, `APP_ENV=uat` или `APP_ENV=preprod`; для промышленного запуска - `APP_ENV=production`. Во всех non-local окружениях замените dev-секреты, не используйте `SECURITY_AUTH_MODE=dev_header` и задайте второй log sink через `LOG_SINKS=jsonl` или `LOG_SINKS=syslog`.

Экран моделей в Admin UI может записывать секреты в `.env` только в локальном/dev режиме. При `APP_ENV=production` такая запись запрещена: ключи должны поступать из переменных окружения, контейнерного secret store или внешнего Vault.

PostgreSQL init script создает пользователя и базу n8n из `N8N_DB_NAME`, `N8N_DB_USER` и `N8N_DB_PASSWORD`. Эти значения должны совпадать с настройками сервиса `n8n`; hardcoded пароль в init-скриптах не используется.

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

## Запуск async Kafka runtime

Для долгих n8n workflow оркестратор не держит HTTP-запрос открытым. Он пишет команду в outbox, publisher отправляет ее в Kafka, а отдельный worker вызывает n8n webhook.

Опубликовать pending outbox сообщения в Kafka один раз:

```bash
.venv/bin/python -m apps.orchestrator.app.kafka_runtime publish-once --limit 50
# или
PYTHON=.venv/bin/python make async-outbox-publish-once
```

Запустить worker команд инструментов:

```bash
.venv/bin/python -m apps.orchestrator.app.kafka_runtime worker --topic ${TOOL_COMMAND_TOPIC:-tool.commands}
# или
PYTHON=.venv/bin/python make async-tool-worker
```

Для локального стенда default topic исходящих команд n8n runbook: `tool.commands`. Доступ к Kafka с host: `127.0.0.1:19092`; внутри docker network: `redpanda:9092`.

`/metrics` по умолчанию доступен только с loopback IP (`127.0.0.1`, `::1`). Для внешнего Prometheus укажите допустимые адреса или CIDR в `METRICS_ALLOWED_IPS`.

`/readyz` в production дополнительно показывает предупреждение, что SQLite state DB является MVP-хранилищем и не считается production-ready. Для промышленного запуска требуется вынести state DB в управляемое хранилище и сохранить контракты идемпотентности callback.

HTTP-статус `/readyz` равен `503` при `status=error`. Для `status=degraded` по умолчанию возвращается `200`; если балансировщик должен исключать degraded-инстансы, задайте `READYZ_STRICT=true`.

## Логирование и диагностика

Основной structured logging pipeline пишет JSON-события в stdout и во второй sink. Для MVP второй sink по умолчанию - JSONL файл:

```text
LOG_LEVEL=INFO
LOG_SINKS=stdout,jsonl
LOG_JSONL_PATH=state/logs/servicedesk-events.jsonl
```

Для production можно использовать `LOG_SINKS=stdout,syslog` и `SYSLOG_ADDRESS=/dev/log` или адрес syslog collector. Debug/diagnostic режим включается без изменения кода:

```text
DEBUG_LOGGING_ENABLED=false
DEBUG_LOGGING_LEVEL=Basic  # Basic или Verbose
```

`Verbose` предназначен только для временной диагностики; token/password/secret/key и русские аналоги маскируются перед записью.

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
- `external.events`;
- `audit.events`;
- `dead-letter`.

Topics должны управляться инфраструктурой. Сервисы приложения не должны создавать topics на старте.

`tool.commands` является default topic для исходящих async ReAct-вызовов и n8n runbook команд. Producer читает `processing_outbox`, публикует envelope-сообщение в этот topic и помечает outbox запись как `published` только после успешной отправки в Kafka. Worker подтверждает Kafka offset только после успешной обработки команды или после durable записи poison message в `dead-letter`.

`external.events` является default topic для входящих результатов внешних асинхронных операций. `ExternalEvent` consumer подтверждает Kafka offset только после durable записи результата, duplicate receipt или `dead-letter`. Для него используются отдельные переменные `EXTERNAL_EVENT_TOPIC`, `EXTERNAL_EVENT_WORKER_GROUP_ID` и `EXTERNAL_EVENT_WORKER_OFFSET_RESET`.

## Длительные действия и external events

Платформа владеет жизненным циклом длительных ожиданий. Для сценариев вроде «написали провайдеру, проверить через час» или «n8n выполняет долгий workflow» создается `wait_state` с `case_id`, `wait_id`, `correlation_id`, ожидаемым `event_type`, `deadline_at` и `origin`.

Если ожидание открыто ReAct-вызовом, `origin.kind` равен `react_call` и содержит ReAct-вызов, launch, endpoint, endpoint-операцию и параметры без секретов. Вопросы клиенту, согласования и технические таймеры используют тот же `wait_state`, но другой `origin.kind`.

Внешний исполнитель получает эти идентификаторы вместе с callback URL:

```text
POST http://127.0.0.1:18088/external-events/{source}
Header: X-ServiceDesk-Callback-Token: ${INTEGRATION_CALLBACK_TOKEN}
```

В local/dev допустим общий `INTEGRATION_CALLBACK_TOKEN`. В shared/staging/production используйте source-specific переменные, например `INTEGRATION_CALLBACK_TOKEN__N8N` для `POST /external-events/n8n`.

Для долгого n8n runbook worker передает в webhook `case_id`, `run_id`, `wait_id`, `correlation_id`, `event_type`, `callback_url`, `idempotency_key_base`, `result_transport`, `result_topic` и бизнес-параметры операции. n8n не закрывает и не эскалирует заявку напрямую: результат возвращается через разрешенный транспорт результата.

Тело события должно соответствовать envelope-контракту `contracts/integrations/external-event.schema.json`. Обязательные поля: `event_id`, `case_id`, `correlation_id`, `source`, `event_type`, `status`, `received_at`, `idempotency_key`. Допустимые статусы: `progress`, `success`, `error`, `timeout`, `cancelled`.

Envelope проверяет общую форму события. Содержимое `result` или `error` дополнительно проверяется по snapshot `async_event_contracts` endpoint-операции, которая открыла ожидание. Для старых ожиданий без snapshot допускается fallback на активную конфигурацию по `wait_state.origin.endpoint_id`, `wait_state.origin.operation_id` и `event_type`.

Внешняя система не закрывает и не эскалирует заявку напрямую. Она возвращает только результат, ошибку или progress. `idempotency_key_base` является ключом команды; каждый `ExternalEvent` должен иметь собственный стабильный `idempotency_key`, например `<idempotency_key_base>:<event_id>`. Платформа дедуплицирует событие по `idempotency_key`; повтор с тем же ключом, но другим `event_id`, `source`, `case_id`, `correlation_id`, `wait_id`, `event_type`, `status` или payload hash, отклоняется как `external_event_idempotency_conflict`. Payload события перед записью в timeline, outbox и receipt маскируется и компактируется.

`result_transport` является runtime-правилом, а не подсказкой. HTTP callback принимается только для ожиданий `http_callback` или `both`; Kafka event принимается только для `kafka_event` или `both` и только из ожидаемого `result_topic`. Для shared/staging/production Kafka producer identity должен ограничиваться ACL/SASL/mTLS или равноценным механизмом инфраструктуры.

## Production hardening backlog

Перед промышленной эксплуатацией нужно вынести MVP-ограничения в полноценную инфраструктуру:

- заменить SQLite state DB на управляемый PostgreSQL-контур для кейсов, callbacks, processing runs и idempotency keys;
- перевести rate limiting и распределенные locks на Redis;
- добавить circuit breaker для integrations и LLM backend;
- добавить CSRF-защиту для state-changing browser API;
- декомпозировать крупные backend/UI модули после стабилизации контрактов;
- добавить OpenTelemetry tracing и alert rules для latency, error rate и DLQ;
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
