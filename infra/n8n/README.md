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
processing_outbox -> Kafka tool.commands -> async worker -> n8n webhook -> ExternalEvent
```

Default topic исходящих команд: `tool.commands`. Локальный Kafka/Redpanda endpoint с host: `127.0.0.1:19092`, внутри docker network: `redpanda:9092`.

Worker передает в webhook `body.invocation.extensions.async_callback`: `case_id`, `ticket_id`, `run_id`, `wait_id`, `correlation_id`, `event_type`, `callback_url`, `source`, `idempotency_key_base`, `result_transport` и `result_topic`.

Workflow должен вернуть `progress`, `success`, `error`, `timeout` или `cancelled` как канонический `ExternalEvent`. Транспорт выбирается по `result_transport`:

- `http_callback` - отправить `ExternalEvent` на `callback_url`;
- `kafka_event` - опубликовать `ExternalEvent` в Kafka topic `result_topic`, локальный default `external.events`;
- `both` - допускается оба транспорта, повторная доставка того же события должна использовать тот же per-event `idempotency_key`.

`idempotency_key_base` нельзя копировать как ключ всех результатов. Для каждого результата workflow формирует стабильный `idempotency_key`, например `<idempotency_key_base>:<event_id>`, чтобы `progress` и финальный `success/error` не конфликтовали. Для Kafka-доставки producer должен быть аутентифицирован инфраструктурой Kafka, а событие принимается orchestrator только из ожидаемого `result_topic`.

n8n не закрывает и не эскалирует заявку напрямую: он только возвращает внешний результат в orchestrator.
