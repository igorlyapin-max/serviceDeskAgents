# n8n Integration Adapter

n8n является первым реальным integration adapter. Orchestrator не должен вызывать n8n напрямую; он вызывает Tool Registry и Integration Dispatcher, которые выбирают endpoint binding из данных каталога.

## Начальные контракты workflow

Диагностический workflow без изменения состояния:

- Tool name: `check_zabbix_status`
- Тип n8n: webhook workflow
- Поведение на этапах 0/1: mock или статический ответ
- Выход: нормализованный JSON

Action workflow:

- Tool name: `start_systemcenter_runbook`
- Тип n8n: webhook workflow
- Поведение на этапах 0/1: mock или только непроизводственный ранбук
- Обязательная policy: согласование оператора перед вызовом webhook
- Выход: нормализованный JSON

## Шаблон workflow

Шаблон webhook для ранбука этапа 4:

- `infra/n8n/workflows/stage4-runbook-webhook.json`

Локальный integration profile по умолчанию: `mock`. Используйте `INTEGRATION_ENDPOINT_PROFILE=n8n` только после импорта и активации n8n workflow.

Workflow проверяет заголовок `X-ServiceDesk-Token` по `N8N_WEBHOOK_TOKEN` из окружения контейнера n8n и возвращает `401`, если токен отсутствует или некорректен.

## Правило безопасности

LLM никогда не должна вызывать n8n напрямую. Все вызовы проходят через:

```text
LangGraph -> Tool Registry -> Integration Dispatcher -> n8n_webhook adapter
```

Action tools требуют запись согласования до того, как adapter вызовет n8n.

## Долгие runbook workflow

Для длительных ранбуков используется асинхронный контур:

```text
processing_outbox -> Kafka tool.commands -> async worker -> n8n webhook -> POST /external-events/n8n
```

Default topic исходящих команд: `tool.commands`. Локальный Kafka/Redpanda endpoint с host: `127.0.0.1:19092`, внутри docker network: `redpanda:9092`.

Worker передает в webhook `body.invocation.extensions.async_callback`: `case_id`, `ticket_id`, `run_id`, `wait_id`, `correlation_id`, `event_type`, `callback_url`, `source` и `idempotency_key`. Workflow должен вернуть `progress`, `success`, `error`, `timeout` или `cancelled` на `callback_url`; n8n не закрывает и не эскалирует заявку напрямую.
