# Этап 10: жизненный цикл кейса и callback API

Этап 10 вводит долговечную границу жизненного цикла кейса перед hardening. Анализ заявки, согласования, callback интеграций, обратная связь и статус UI сходятся в единой записи кейса и timeline.

## Целевой жизненный цикл

```text
Operator UI
  -> FastAPI Case API
  -> AI Orchestrator
  -> LangGraph / Workflow Engine
  -> Execution Policy + Action Gate
  -> Tool Registry
  -> Integration Dispatcher
  -> Endpoint Adapter: mock / n8n_webhook / direct_http / queue / future
  -> External Systems
  -> Callback API / normalized tool result
  -> Case Store
  -> UI update / escalation / resolve / feedback
```

n8n является одним endpoint adapter в этом потоке. Жизненный цикл также должен поддерживать mock, direct HTTP, queue-based и будущие adapters.

## Базовые решения

- Case API владеет состоянием жизненного цикла.
- Endpoint adapters не владеют состоянием кейса.
- Callback payloads нормализуются перед обновлением кейсов.
- Синхронные результаты инструментов и асинхронные callbacks используют одну нормализованную модель результата.
- Опроса UI достаточно для этапа 10; WebSocket/SSE может подождать.
- Hardening переносится после этого этапа, потому что форма жизненного цикла и callback должна стабилизироваться.

## Контракты

- `contracts/cases/case-record.schema.json`
- `contracts/cases/case-event.schema.json`
- `contracts/cases/case-timeline.schema.json`
- `contracts/integrations/integration-callback.schema.json`

## API

- `POST /cases`
- `GET /cases/{case_id}`
- `GET /cases/{case_id}/timeline`
- `POST /integrations/callbacks/{endpoint_id}`

`POST /tickets/analyze` остается совместимым и теперь создает case record внутри. `POST /cases` возвращает case record и snapshot анализа.

Callbacks должны использовать нормализованный контракт `integration-callback`. Payloads конкретного endpoint, включая формы n8n webhook, должны быть преобразованы до обновления кейса.

## Runtime state

Локальное MVP использует ту же SQLite database, которую выбирает `ORCHESTRATOR_STATE_DB` или `state/orchestrator.sqlite`.

Новые tables:

- `cases`
- `case_events`
- `case_correlations`

Корреляции кейса включают `case_id`, `ticket_id`, `gate_id`, `action_id`, `invocation_id`, `endpoint_id` и `operation_id`, если они доступны.

## UI

Operator UI показывает:

- case id.
- текущее состояние workflow кейса.
- количество событий и время обновления.
- последние события timeline.

UI опрашивает `GET /cases/{case_id}` и `GET /cases/{case_id}/timeline`; WebSocket/SSE остается вне scope.

## Команды

Запустить проверки:

```bash
PYTHON=.venv/bin/python make stage10-check
```

Запустить smoke-проверку этапа 10:

```bash
./scripts/stage10-smoke.sh
```

## Критерии выхода

- Записи кейсов хранят входные данные заявки, текущее состояние workflow, AI-решение, трассировку RAG, трассировку инструментов, согласования, ссылки на обратную связь и итоговый результат.
- Case timeline записывает события анализа, согласования, dispatch, callback/result и обратной связи.
- Endpoint callbacks могут обновлять кейс после начального результата accepted/pending.
- n8n-specific payloads не протекают в core case contracts.
- Существующие smoke-проверки этапов 3-9 продолжают проходить.
