# Async MCP Runbook Developer Guide

## Назначение

Этот документ описывает, как разрабатывать внешние MCP-окружения, которые исполняют capabilities для `ServiceDeskAgents`. Внутри MCP может использоваться n8n, Temporal, скрипты или HTTP API, но для `ServiceDeskAgents` это не видно.

## Базовая схема

```text
ServiceDeskAgents
  -> Capability Registry
  -> Capability Binding
  -> External MCP tool
  -> accepted ack
  -> ExternalEvent progress/success/error/timeout/cancelled
  -> ServiceDeskAgents continuation
```

`ServiceDeskAgents` владеет ожиданием, timeout, retries, idempotency, заполнением slots и переходами workflow. MCP-исполнитель только выполняет работу и возвращает результат по контракту.

## MCP capability tool

MCP tool должен принимать business inputs и, для async-вызова, объект `async_context`.

Минимальный `async_context`:

```json
{
  "case_id": "case-1",
  "run_id": "run-1",
  "wait_id": "wait-1",
  "correlation_id": "corr-1",
  "capability_id": "provider_channel_repair_monitor",
  "contract_version": "1.0",
  "expected_event_type": "provider_channel_repair_monitor.completed",
  "idempotency_key_base": "cmd-1",
  "result_transport": "http_callback",
  "callback_url": "https://servicedesk.example/external-events/mcp"
}
```

## Discovery metadata

Если MCP-окружение поддерживает discovery, `tools/list` должен вернуть tool descriptor с явной ServiceDesk metadata. Обычные MCP tools без этой metadata игнорируются.

Минимальная форма:

```json
{
  "name": "provider_channel_repair_monitor",
  "description": "Monitor provider channel repair.",
  "inputSchema": {
    "type": "object",
    "required": ["problem_url", "service_request"],
    "properties": {
      "problem_url": {
        "type": "string",
        "description": "Полный URL проблемы Zabbix или другого мониторинга."
      },
      "service_request": {
        "type": "string",
        "description": "Номер заявки ServiceDesk для корреляции результата."
      }
    }
  },
  "_meta": {
    "servicedesk": {
      "capability_id": "provider_channel_repair_monitor",
      "display_name": "Provider channel repair monitor",
      "description": "Monitor provider repair until terminal result.",
      "contract_version": "1.0",
      "execution_modes": ["async"],
      "output_schema": {
        "type": "object",
        "required": ["provider_mail_body"],
        "properties": {
          "provider_mail_body": {
            "type": "string",
            "description": "Plain text тело письма-ответа провайдера."
          },
          "provider_ticket_number": {
            "type": "string",
            "description": "Номер заявки или наряда, найденный в ответе провайдера."
          }
        }
      },
      "accepted_ack_schema": {
        "type": "object",
        "required": ["status", "external_execution_id", "correlation_id"],
        "properties": {
          "status": {"const": "accepted"},
          "external_execution_id": {"type": "string"},
          "correlation_id": {"type": "string"}
        }
      },
      "async_event_contracts": {
        "provider_channel_repair_monitor.completed": {
          "display_name": "Provider monitor completed",
          "statuses": ["progress", "success", "error", "timeout", "cancelled"],
          "result_schema": {
            "type": "object",
            "required": ["provider_mail_body"],
            "properties": {
              "provider_mail_body": {"type": "string"}
            }
          },
          "contract_version": "1.0",
          "contract_status": "valid"
        }
      },
      "default_completion_policy": {
        "mode": "external_event",
        "expected_event_type": "provider_channel_repair_monitor.completed",
        "max_wait_seconds": 3600,
        "timeout_action": "escalate_operator"
      },
      "diagnostic_schema": {
        "type": "object",
        "additionalProperties": true
      }
    }
  }
}
```

Для async capability discovery отклоняется, если нет `accepted_ack_schema`, `async_event_contracts`, `default_completion_policy.mode=external_event` или `expected_event_type` отсутствует в `async_event_contracts`. Для production MCP environment discovery допускается только с OIDC auth mode.

Descriptions в `inputSchema.properties.*.description`, `_meta.servicedesk.output_schema.properties.*.description` и descriptions самих capabilities являются рабочим контрактом для администратора и LLM assist в профилях разрешения. Если descriptions пустые, ассистент видит только техническое имя поля и хуже сопоставляет `service_request`, `problem_url`, `message`, `provider_mail_body` и похожие параметры со слотами сценария. Пишите descriptions на языке операторского сценария, без n8n/webhook/node деталей и без секретов.

Администратор ServiceDesk может запустить discovery активного MCP environment через:

```http
POST /admin/config/mcp-environments/{environment_id}/discover
```

Endpoint вызывает MCP `tools/list` только если у environment задано `discovery_policy.mode=mcp_tools`. Ответ возвращает `capability_candidates` и `ignored_tools`; он не создает и не активирует config drafts автоматически.

Чтобы импортировать найденные candidates как черновики конфигурации:

```http
POST /admin/config/mcp-environments/{environment_id}/discover/import-drafts
```

Тело запроса может ограничить импорт выбранными `capability_ids`. Endpoint создает drafts для `capabilities`, `mcp_environments` и `capability_bindings`, добавляет capability в `allowed_capabilities` выбранного environment и запускает bundle validation. Активация остается отдельным административным действием.

## Sync result

Если capability синхронная, MCP tool возвращает canonical result сразу:

```json
{
  "status": "success",
  "result": {
    "field": "value"
  },
  "diagnostics": {}
}
```

## Async accepted ack

Если capability асинхронная, MCP tool возвращает только acknowledgement:

```json
{
  "status": "accepted",
  "external_execution_id": "exec-123",
  "correlation_id": "corr-1",
  "message": "Execution accepted",
  "diagnostics": {}
}
```

Ack не заполняет business outputs и не закрывает ожидание.

## ExternalEvent

Progress и terminal outcomes возвращаются как `ExternalEvent`:

```json
{
  "event_type": "provider_channel_repair_monitor.completed",
  "status": "success",
  "case_id": "case-1",
  "run_id": "run-1",
  "wait_id": "wait-1",
  "correlation_id": "corr-1",
  "source": "mcp",
  "idempotency_key": "cmd-1:success",
  "result": {
    "provider_mail_body": "Provider response text",
    "provider_ticket_number": "MTS000000000000001"
  }
}
```

Allowed statuses: `progress`, `success`, `error`, `timeout`, `cancelled`.

## Idempotency

- Используйте один `idempotency_key_base` для команды.
- Для каждого event формируйте отдельный `idempotency_key`, например `<idempotency_key_base>:<event_id>`.
- Повторная доставка того же event с тем же payload допустима.
- Повторная доставка того же key с другим payload является ошибкой.

## Авторизация

Для dev допускается static Bearer token:

```text
Authorization: Bearer <token>
```

Токен хранится только как secret/env reference, не в config payload.

Для prod используйте OIDC:

- отдельный `audience` для каждого MCP-окружения;
- `client_credentials` или workload identity;
- scopes/claims должны ограничивать capabilities;
- callback/event receiver проверяет issuer, audience, expiry, subject/client id и capability permission.

Для inbound HTTP callback в shared/staging/production используйте `SECURITY_CALLBACK_AUTH_MODE=oidc_jwks`: `ServiceDeskAgents` проверяет JWT подпись по `CALLBACK_OIDC_JWKS_URL`, а затем валидирует claims:

- `iss` = `CALLBACK_OIDC_ISSUER`;
- `aud` содержит `CALLBACK_OIDC_AUDIENCE`;
- `exp` не истек, `nbf` не в будущем;
- `sub` или `client_id` задан и входит в `CALLBACK_OIDC_ALLOWED_CLIENT_IDS`, если список настроен;
- `scope`, `scp` или `permissions` содержит `CALLBACK_OIDC_REQUIRED_SCOPE` (по умолчанию `servicedesk.external_events.write`).

`SECURITY_CALLBACK_AUTH_MODE=oidc_proxy_jwt` допустим только за trusted gateway/proxy, который уже проверил подпись JWT; дополнительно задайте `CALLBACK_OIDC_PROXY_TRUSTED_IPS` или `CALLBACK_OIDC_PROXY_TRUST_HEADER` / `CALLBACK_OIDC_PROXY_TRUST_HEADER_VALUE`.

Local/dev может использовать `SECURITY_CALLBACK_AUTH_MODE=source_token` и header `X-ServiceDesk-Callback-Token`. Не используйте source-token режим для shared/staging/production.

## Diagnostics

Возвращайте компактную диагностику:

- `external_execution_id`;
- `correlation_id`;
- current phase;
- last checked resource;
- next poll time;
- match counters;
- non-sensitive error summary.

Не передавайте токены, пароли, resolved secret values и поля, которые контракт явно помечает как secret-bearing. Контактные и бизнес-поля не считаются секретами по умолчанию.

## Запрещено

MCP-исполнитель не должен:

- закрывать или эскалировать заявки напрямую;
- менять slots напрямую;
- менять workflow state напрямую;
- обходить `ExternalEvent` contract;
- писать секреты в logs, diagnostics или examples;
- требовать от сценария знания n8n workflow, webhook path или internal node names.

## Если внутри используется n8n

n8n является внутренней реализацией MCP-окружения. Разработчик MCP обязан скрыть n8n details за capability tool и вернуть canonical ack/events. При изменении n8n-ранбука обновляйте внешний MCP contract и артефакты проекта `../n8n`, но не протаскивайте `n8n_*` identifiers в `ServiceDeskAgents` scenarios.
