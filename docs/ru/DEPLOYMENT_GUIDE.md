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

Секреты задаются через `.env` или внешнее хранилище секретов:

- `POSTGRES_PASSWORD`;
- `OPENAI_API_KEY`;
- `LITELLM_MASTER_KEY`;
- `MCP_PROVIDER_OPS_TOKEN` для dev Bearer token внешнего provider-ops MCP окружения; production должен использовать настроенный OIDC/token exchange для этого MCP окружения;
- `INTEGRATION_CALLBACK_TOKEN` или `INTEGRATION_CALLBACK_TOKEN__<SOURCE>` только для local/dev callback token mode;
- `SECURITY_CALLBACK_AUTH_MODE=oidc_jwks`, `CALLBACK_OIDC_ISSUER`, `CALLBACK_OIDC_AUDIENCE`, `CALLBACK_OIDC_ALLOWED_CLIENT_IDS`, `CALLBACK_OIDC_JWKS_URL` для shared/staging/production callbacks. `oidc_proxy_jwt` допустим только за trusted gateway/proxy и требует `CALLBACK_OIDC_PROXY_TRUSTED_IPS` или `CALLBACK_OIDC_PROXY_TRUST_HEADER` / `CALLBACK_OIDC_PROXY_TRUST_HEADER_VALUE`.

Не коммитьте `.env` в git. Docker Compose не подставляет dev-пароли по умолчанию: если обязательный секрет не задан, `docker compose config --quiet` завершится ошибкой. Значения `change_me_*` из `.env.example` предназначены только как подсказки и должны быть заменены перед запуском общего стенда или production.

Текущий MVP рассчитан на локальный single-node режим. Для общих стендов используйте `APP_ENV=shared`, `APP_ENV=staging`, `APP_ENV=uat` или `APP_ENV=preprod`; для промышленного запуска - `APP_ENV=production`. Во всех non-local окружениях замените dev-секреты, не используйте `SECURITY_AUTH_MODE=dev_header` и задайте второй log sink через `LOG_SINKS=jsonl` или `LOG_SINKS=syslog`.

Экран моделей в Admin UI может записывать секреты в `.env` только в локальном/dev режиме. При `APP_ENV=production` такая запись запрещена: ключи должны поступать из переменных окружения, контейнерного secret store или внешнего Vault.

ServiceDeskAgents не запускает n8n и не хранит его credentials. Если конкретное внешнее MCP окружение реализовано через n8n, его переменные и секреты настраиваются в отдельном проекте/контуре этого окружения.

## Сервисы Docker Compose

Базовый контур:

- `postgres` - PostgreSQL с pgvector;
- `redis` - cache, locks и временное состояние;
- `redpanda` - Kafka-compatible broker для асинхронных событий;
- `litellm` - общий локальный OpenAI-compatible gateway, доступный на `http://127.0.0.1:4000/v1`.

Опциональный LLM-профиль:

- `vllm-cpu` - локальный CPU inference backend.

## Запуск базового контура

Проверить конфигурацию:

```bash
docker compose config --quiet
```

Запустить базовые сервисы:

```bash
docker compose up -d postgres redis redpanda litellm
```

Запустить полный runtime стенд с FastAPI и async workers:

```bash
make runtime-up
make runtime-check
```

Проверить состояние:

```bash
docker compose ps
```

Внешние MCP окружения должны быть доступны по настроенным URL из `mcp_environments`. В local/dev используется Bearer token, в production - OIDC/token exchange или эквивалентная авторизация выбранного MCP окружения.

## Запуск LLM gateway и локальной CPU-модели

`make runtime-up` поднимает LiteLLM как обязательный gateway для извлечения слотов моделью. Внутри Docker Compose orchestrator обращается к `http://litellm:4000/v1`, а с хоста и из соседних локальных проектов gateway доступен по `http://127.0.0.1:4000/v1`.

Запустить vLLM CPU нужно только если активный backend - локальная CPU-модель:

```bash
docker compose --profile llm up -d vllm-cpu
```

Проверить LiteLLM:

```bash
curl -sS http://127.0.0.1:4000/v1/models \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}"
```

## Локальный запуск FastAPI без Compose

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

Такой запуск подходит для разработки API/UI. Для async MCP capability вызовов нужен полный runtime: `async-outbox-publisher`, `async-mcp-worker`, `async-external-event-worker` и `async-agent-task-worker`. В штатном локальном стенде запускайте их через `make runtime-up`.

URL интерфейсов:

```text
http://127.0.0.1:18088/admin
http://127.0.0.1:18088/debug
http://127.0.0.1:18088/operator  # alias консоли отладки для локальной совместимости
```

Проверки доступности:

```text
http://127.0.0.1:18088/healthz  # простой liveness
http://127.0.0.1:18088/readyz   # readiness по state DB, конфигурации, моделям, Kafka, MCP workers и async runtime
http://127.0.0.1:18088/metrics  # Prometheus-совместимые технические метрики MVP
```

## Запуск async Kafka runtime

Для долгого внешнего исполнения оркестратор не держит HTTP-запрос открытым. Он пишет capability-команду в outbox, publisher отправляет ее в Kafka, а отдельный worker вызывает внешнее MCP окружение.

Рекомендуемый запуск в Docker Compose:

```bash
make runtime-up
make runtime-check
```

`runtime-check` проверяет публичный LiteLLM endpoint и `/readyz`; readiness считается ошибочной, если Kafka или model gateway недоступны, если не обновляется heartbeat `async-outbox-publisher`, `async-mcp-worker`, `async-external-event-worker` или `async-agent-task-worker`, либо если `mcp.commands` остается в pending дольше допустимого порога.

Запустить постоянный publisher outbox в Kafka. Для рабочего стенда это обязательный процесс: без него async-команды останутся в `processing_outbox`, а MCP capabilities не будут вызваны.

```bash
.venv/bin/python -m apps.orchestrator.app.kafka_runtime publisher
# или
PYTHON=.venv/bin/python make async-outbox-publisher
```

Опубликовать pending outbox сообщения в Kafka один раз для ручной диагностики. Это batch-команда; без явного `--limit` Makefile использует `${OUTBOX_PUBLISH_LIMIT:-50}`:

```bash
.venv/bin/python -m apps.orchestrator.app.kafka_runtime publish-once --limit 50
# или
PYTHON=.venv/bin/python make async-outbox-publish-once
```

Запустить постоянный worker команд MCP capabilities:

```bash
.venv/bin/python -m apps.orchestrator.app.kafka_runtime mcp-worker --topic ${MCP_COMMAND_TOPIC:-mcp.commands}
# или
PYTHON=.venv/bin/python make async-mcp-worker
```

Запустить постоянный inbound worker результатов из Kafka:

```bash
.venv/bin/python -m apps.orchestrator.app.kafka_runtime external-event-worker --topic ${EXTERNAL_EVENT_TOPIC:-external.events}
# или
PYTHON=.venv/bin/python make async-external-event-worker
```

Запустить постоянный worker продолжения агента после terminal ExternalEvent:

```bash
.venv/bin/python -m apps.orchestrator.app.kafka_runtime agent-task-worker --topic ${AGENT_TASK_TOPIC:-agent.tasks}
# или
PYTHON=.venv/bin/python make async-agent-task-worker
```

Для локального стенда default topic исходящих MCP capability команд: `mcp.commands`; default topic входящих external events: `external.events`; default topic задач продолжения агента: `agent.tasks`. Доступ к Kafka с host: `127.0.0.1:19092`; внутри docker network: `redpanda:9092`.

Внешнее MCP окружение получает только canonical capability input и async context. Если оно внутри себя использует n8n, Zabbix, SMTP или другие системы, их registry, секреты и сетевые подключения настраиваются в проекте этого MCP окружения, а не в ServiceDeskAgents.

Kafka transport security настраивается администратором через env. Local/dev default:

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

# или mTLS
KAFKA_SECURITY_PROTOCOL=SSL
KAFKA_SSL_CA_FILE=/etc/kafka/ca.pem
KAFKA_SSL_CERT_FILE=/etc/kafka/client.pem
KAFKA_SSL_KEY_FILE=/etc/kafka/client.key
```

Kafka не является HTTPS-транспортом. Для production дополнительно нужны broker ACL, ограничивающие producer/consumer только согласованными topics.

`worker` и `external-event-worker` работают как long-running consumer-процессы и не завершаются по счетчику сообщений, если `--limit` не указан. Для ручной диагностики можно добавить `--limit N`, например обработать только первые 3 сообщения. В production запускайте эти процессы под supervisor, systemd или container restart policy.

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
| PostgreSQL | `15432` | Хранилище приложения и pgvector |
| Redis | `16379` | Cache, locks и временное состояние |
| Redpanda/Kafka | `19092` | Транспорт команд и событий |
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
docker compose config --quiet
```

## Kafka topics

Runtime использует Kafka-ready outbox и следующие topics:

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

Topics должны управляться инфраструктурой. Сервисы приложения не должны создавать topics на старте.

`mcp.commands` является default topic для исходящих внешних MCP capability команд. Producer читает `processing_outbox`, публикует envelope-сообщение в topic сообщения и помечает outbox запись как `published` только после успешной отправки в Kafka. Workers подтверждают Kafka offset только после успешной обработки команды или после durable записи poison message в `dead-letter`.

`external.events` является default topic для входящих результатов внешних асинхронных операций. `ExternalEvent` consumer подтверждает Kafka offset только после durable записи результата, duplicate receipt или `dead-letter`. Для него используются отдельные переменные `EXTERNAL_EVENT_TOPIC`, `EXTERNAL_EVENT_WORKER_GROUP_ID` и `EXTERNAL_EVENT_WORKER_OFFSET_RESET`.

`agent.tasks` является default topic для durable продолжения обработки после terminal ExternalEvent. `async-agent-task-worker` берет queued `langgraph_resume` задачи из state DB, связывает их с receipt внешнего события и переводит run в финальный статус. Без этого worker-а внешний результат будет принят, но сценарий останется в ожидании продолжения.

## Восстановление после падения runtime

Текущий целевой режим отказоустойчивости - single-node durability. Контейнеры могут перезапускаться без потери уже зафиксированного контекста, если `ORCHESTRATOR_STATE_DB=/app/state/orchestrator.sqlite` расположен на persistent volume `./state:/app/state`, а Kafka сохраняет topics.

После restart сохраняются `case`, `processing_runs`, заполненные слоты в снимках обработки, `wait_states`, `processing_outbox`, `tool_command_receipts`, `external_event_receipts` и `agent_tasks`. Pending outbox-сообщения будут опубликованы повторно; stale `publishing` outbox lease и stale `agent_tasks` переарендуются после истечения lease.

Для `ExternalEvent` действует идемпотентное восстановление: если сервис упал с receipt в `processing`, повторная доставка того же события с тем же payload после `ASYNC_RECOVERY_RECEIPT_STALE_SECONDS` продолжит обработку или дозавершит receipt по уже закрытому wait. Для `tool_command_receipts.status=processing` автоматический повтор не выполняется: сначала проверьте, принял ли внешний MCP/n8n исполнитель команду. Поэтому каждый async runbook обязан хранить `async_context.idempotency_key_base`, `correlation_id` и `wait_id` и делать запуск идемпотентным.

`/readyz` включает recovery-диагностику. Зависшие receipts переводят async runtime в `degraded`; это не снимает инстанс с балансировщика при `READYZ_STRICT=false`, но требует операторской проверки.

## Длительные действия и external events

Платформа владеет жизненным циклом длительных ожиданий. Для сценариев вроде «написали провайдеру, проверить через час» или «внешнее MCP окружение выполняет долгий workflow» создается `wait_state` с `case_id`, `wait_id`, `correlation_id`, ожидаемым `event_type`, `deadline_at` и `origin`.

Если ожидание открыто capability-вызовом, `origin.kind` равен `capability` и содержит `capability_id`, `mcp_environment_id`, `mcp_tool_name`, launch и параметры без секретов. Вопросы клиенту, согласования и технические таймеры используют тот же `wait_state`, но другой `origin.kind`.

Внешний исполнитель получает эти идентификаторы вместе с callback URL:

```text
POST http://127.0.0.1:18088/external-events/{source}
Header: X-ServiceDesk-Callback-Token: ${INTEGRATION_CALLBACK_TOKEN}
```

Для local/dev callback URL должен быть достижим из внешнего MCP окружения. По умолчанию используйте `ORCHESTRATOR_PUBLIC_URL=http://hostmachine:18088` для соседних локальных Docker-проектов; compose добавляет alias `hostmachine:host-gateway`, а orchestrator нужно запускать с bind `0.0.0.0`. В shared/staging/production задайте `ORCHESTRATOR_PUBLIC_URL=https://...`.

В local/dev допустим `SECURITY_CALLBACK_AUTH_MODE=source_token` с общим `INTEGRATION_CALLBACK_TOKEN` или source-specific `INTEGRATION_CALLBACK_TOKEN__<SOURCE>`.

В shared/staging/production задайте `SECURITY_CALLBACK_AUTH_MODE=oidc_jwks`. `ServiceDeskAgents` проверяет JWT подпись по `CALLBACK_OIDC_JWKS_URL` и затем валидирует claims `iss`, `aud`, `exp`, `nbf`, `sub` или `client_id`, `CALLBACK_OIDC_ALLOWED_CLIENT_IDS` и scope `CALLBACK_OIDC_REQUIRED_SCOPE` (по умолчанию `servicedesk.external_events.write`). `SECURITY_CALLBACK_AUTH_MODE=oidc_proxy_jwt` допустим только если подпись JWT уже проверена trusted gateway/proxy; задайте `CALLBACK_OIDC_PROXY_TRUSTED_IPS` или `CALLBACK_OIDC_PROXY_TRUST_HEADER` / `CALLBACK_OIDC_PROXY_TRUST_HEADER_VALUE`.

Для долгой capability-операции worker передает внешнему MCP окружению `case_id`, `run_id`, `wait_id`, `correlation_id`, `event_type`, `callback_url`, `idempotency_key_base`, `result_transport`, `result_topic` и бизнес-параметры операции. Внешний исполнитель не закрывает и не эскалирует заявку напрямую: результат возвращается через разрешенный транспорт результата.

Тело события должно соответствовать envelope-контракту `contracts/integrations/external-event.schema.json`. Обязательные поля: `event_id`, `case_id`, `correlation_id`, `source`, `event_type`, `status`, `received_at`, `idempotency_key`. Допустимые статусы: `progress`, `success`, `error`, `timeout`, `cancelled`.

Envelope проверяет общую форму события. Содержимое `result` или `error` дополнительно проверяется по async result contract capability binding, который открыл ожидание. Для старых ожиданий без snapshot требуется повторный запуск после миграции на capability binding; legacy endpoint fallback удален.

Внешняя система не закрывает и не эскалирует заявку напрямую. Она возвращает только результат, ошибку или progress. `idempotency_key_base` является ключом команды; каждый `ExternalEvent` должен иметь собственный стабильный `idempotency_key`, например `<idempotency_key_base>:<event_id>`. Платформа дедуплицирует событие по `idempotency_key`; повтор с тем же ключом, но другим `event_id`, `source`, `case_id`, `correlation_id`, `wait_id`, `event_type`, `status` или payload hash, отклоняется как `external_event_idempotency_conflict`. Payload события перед записью в timeline, outbox и receipt маскируется и компактируется.

`result_transport` является runtime-правилом, а не подсказкой. HTTP callback принимается только для ожиданий `http_callback` или `both`; Kafka event принимается только для `kafka_event` или `both` и только из ожидаемого `result_topic`. Для shared/staging/production Kafka producer identity должен ограничиваться ACL/SASL/mTLS или равноценным механизмом инфраструктуры.

Не смешивайте `result_transport` и transport auth. `result_transport` находится в async command package (`invocation.extensions.async_callback.result_transport`) и выбирает delivery mode конкретного запуска: `http_callback`, `kafka_event` или `both`. Авторизация HTTP callback задается через `SECURITY_CALLBACK_AUTH_MODE`; Kafka защищается broker ACL с `SASL_SSL`, `SSL`/mTLS, signed envelope или равноценным инфраструктурным контролем.

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
3. Выполните `docker compose config --quiet`.
4. Перезапустите измененные сервисы.
5. Перезапустите FastAPI orchestrator.
6. Выполните smoke checks.

## Troubleshooting

- Если Admin UI не показывает новые разделы, перезапустите FastAPI и обновите страницу без cache.
- Если LiteLLM не отвечает, проверьте контейнер `litellm`, `LITELLM_MASTER_KEY`, `OPENAI_API_KEY`, `LITELLM_PUBLIC_BASE_URL` и `COMPOSE_LITELLM_BASE_URL`.
- Если Kafka недоступна, проверьте контейнер `redpanda` и порт `19092`.
- Если MCP capability не вызывается, проверьте `mcp_environments`, `capability_bindings`, `MCP_COMMAND_TOPIC`, heartbeat `async-mcp-worker` и авторизацию внешнего MCP окружения.
- Если внешний исполнитель возвращает доменную ошибку, диагностируйте его собственный runtime/секреты/сети в проекте этого MCP окружения.
- Если callback отклоняется, проверьте `SECURITY_CALLBACK_AUTH_MODE`, callback source id, local/dev token или OIDC proxy JWT claims.
