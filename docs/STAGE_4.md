# Этап 4: основа интеграционного слоя

Этап 4 вводит integration boundary до глубокой связки с real automation. n8n используется как первый реальный execution adapter, но orchestrator не должен зависеть от n8n webhook URLs или n8n-specific payloads.

## Базовые решения

- Orchestrator вызывает Tool Registry и Integration Dispatcher, а не n8n напрямую.
- n8n является одним adapter type: `n8n_webhook`.
- Локальные тесты должны проходить через `mock` adapter.
- Tool definitions и endpoint definitions являются catalog data.
- AI output может предлагать `tool_name` и tool parameters, но не может выбирать endpoint URL, adapter type, execution mode, approval state или policy rule.
- Action tools в MVP требуют execution policy и согласование оператора до dispatcher invocation.

## Целевой поток

```text
FastAPI Orchestrator
  -> Execution Policy
  -> Tool Registry
  -> Integration Dispatcher
  -> Adapter: mock
  -> Adapter: n8n_webhook
  -> Adapter: direct_http later
  -> Adapter: queue later
```

Для `start_systemcenter_runbook` MVP path:

```text
action_proposed
  -> operator_approval
  -> pending_approval
  -> operator approves
  -> Integration Dispatcher
  -> n8n_webhook adapter
  -> normalized tool result
```

## Контракты

Контракты JSON Schema:

- `contracts/tools/tool-definition.schema.json`
- `contracts/tools/tool-catalog.schema.json`
- `contracts/tools/tool-invocation.schema.json`
- `contracts/tools/tool-result.schema.json`
- `contracts/integrations/integration-endpoint.schema.json`
- `contracts/integrations/integration-endpoint-catalog.schema.json`

Файлы каталогов:

- `contracts/tools/tool-catalog.json`
- `contracts/integrations/integration-endpoint-catalog.json`

Начальные требования к каталогу:

- `start_systemcenter_runbook` существует как `action` tool.
- `start_systemcenter_runbook` мапится на configurable endpoint operation, а не на hardcoded n8n URL.
- Есть минимум один read-only diagnostic stub для smoke-проверок dispatcher.
- Endpoint catalog содержит `mock` endpoint.
- Endpoint catalog содержит `n8n_webhook` endpoint для runbook execution.

## Runtime components

Python components в orchestrator:

- `ToolRegistry`
- `IntegrationDispatcher`
- `IntegrationAdapter` interface
- `MockAdapter`
- `N8nWebhookAdapter`

Dispatcher input является валидированным tool invocation. Dispatcher output является normalized tool result. Adapter-specific details должны быть в `extensions`, а не в общих result fields.

## Scope n8n

n8n на этом этапе минимален:

- один internal webhook для runbook execution;
- token-based webhook protection через header `X-ServiceDesk-Token` и `N8N_WEBHOOK_TOKEN`;
- стабильный нормализованный success/error response;
- нет прямой зависимости orchestrator от workflow internals.

Workflow template:

- `infra/n8n/workflows/stage4-runbook-webhook.json`

Локальный профиль по умолчанию: `mock`. Переключайте `INTEGRATION_ENDPOINT_PROFILE=n8n` только после import/activation n8n workflow и передачи `N8N_WEBHOOK_TOKEN` в environment контейнера n8n.

## API surface

`POST /tickets/analyze` возвращает normalized `tool_results` и `tool_trace`. Для `start_systemcenter_runbook` результат остается `pending_approval` до dispatch, согласованного оператором.

`POST /tools/dispatch` принимает:

- `action`
- `policy_result`
- `approved_by_operator`
- optional `ticket_id`
- optional `operator_id`

Endpoint применяет policy до adapter invocation. Если требуется approval и `approved_by_operator=false`, возвращается normalized `pending_approval`, adapter не вызывается.

## Команды

Запустить проверки синтаксиса и контрактов:

```bash
PYTHON=.venv/bin/python make stage4-check
```

Запустить smoke-проверку интеграционного слоя:

```bash
./scripts/stage4-smoke.sh
```

## Вне scope

- Прямая интеграция с System Center API.
- Включение auto-execution.
- Полный hardening tool catalog.
- Расширенная retry/backoff policy.
- Поток согласования в Operator UI.
- Production secret management.

## Критерии выхода

- Orchestrator никогда не вызывает n8n напрямую.
- `start_systemcenter_runbook` проходит через Tool Registry и Integration Dispatcher.
- Endpoint target переключается между `mock` и `n8n_webhook` через catalog/config data.
- n8n можно mock-ать без изменения orchestrator workflow code.
- Action tools не могут обойти execution policy и согласование оператора.
- AI output не может выбирать endpoint URL, adapter type, execution mode или approval status.
