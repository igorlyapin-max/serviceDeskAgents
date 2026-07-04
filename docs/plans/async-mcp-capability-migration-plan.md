# ServiceDeskAgents + external MCP execution environments

## Summary

Перестроить исполнение сценариев так, чтобы `ServiceDeskAgents` работал только с доменными capabilities и внешними MCP-окружениями. Прямых provider-ов `n8n`, `http`, `worker` внутри `ServiceDeskAgents` не вводим. Если исполнение физически сделано в n8n, это скрыто за внешним MCP. Legacy `n8n_*` model не сохраняем.

## Этап 1. Целевая модель контрактов

- Ввести `Capability Registry` как публичную модель сценариев: `capability_id`, `contract_version`, `input_schema`, `output_schema`, `execution_modes`, `async_event_contracts`, `default_completion_policy`, `diagnostic_schema`.
- Ввести `MCP Environment Registry`: `environment_id`, `display_name`, `transport`, `base_url`, `auth_mode`, `auth_ref`, `oidc_audience`, `allowed_capabilities`, `health_check`, `discovery_policy`.
- Ввести `Capability Binding`: `capability_id`, `environment_id`, `mcp_tool_name`, `execution_mode`, `input_mapping`, `output_mapping`, `async_context_mapping`, `status`.

## Этап 2. MCP execution contract

- Все исполнительские окружения считаются внешними MCP.
- MCP tool для capability принимает business inputs и `async_context` для async-вызовов: `correlation_id`, `wait_id`, `case_id`, `run_id`, callback/event delivery параметры, `idempotency_key_base`, `expected_event_type`, `contract_version`.
- `sync` MCP tool возвращает canonical result сразу.
- `async` MCP tool возвращает только accepted ack: `status=accepted`, `external_execution_id`, `correlation_id`, `message`, optional diagnostics.
- Terminal/progress результат приходит только как canonical `ExternalEvent`.
- MCP execution environment не меняет business state заявки, slots, workflow state или Zabbix напрямую от имени сценария.

## Этап 3. Авторизация MCP

- Для dev использовать static Bearer token, хранимый только как env/secret ref.
- Для prod использовать OIDC: `client_credentials` или workload identity, отдельный `audience` на каждое MCP-окружение, scopes/claims ограничивают allowed capabilities.
- Для inbound async events принимать только authenticated callbacks/events.
- Dev допускает token auth; prod использует OIDC Bearer JWT или подписанный event envelope.
- Проверять issuer, audience, expiry, subject/client id и capability permission.
- Auth failures писать в audit/structured logs без secret values.

## Этап 4. Runtime orchestration

- Async state остается в `ServiceDeskAgents`: `wait_state`, `processing_outbox`, retries, timeout, idempotency receipts, continuation.
- Добавить `McpExecutionConnector`: выбирает binding по `capability_id`, получает auth token, вызывает внешний MCP tool, валидирует sync result или async ack, пишет diagnostics в trace.
- Для async сначала открывать `wait_state`, затем вызывать MCP tool с `async_context`, принимать accepted ack, затем ждать `ExternalEvent`.
- Для sync валидировать result по `output_schema` и сразу заполнять output slots.

## Этап 5. Config/UI сценариев

- Убрать публичные `ReAct.n8n_*`, `paramReAct.n8n_*`, `endpoint_id`, `operation_id` из языка сценариев.
- Новый язык сценариев: `Выполни ${Capability.provider_channel_repair_monitor}`.
- Inputs берутся из `slot/case/constant/secret`.
- Outputs ссылаются на canonical capability fields.
- `attribute_resolution_profiles` перевести на `capability_id`, `input_mapping`, `output_mapping`, `completion_policy`, optional `mcp_environment_id`.
- UI показывает capability, MCP environment, execution mode, required inputs, canonical outputs, auth/health/discovery status.
- UI не показывает n8n/internal workflow details.

## Этап 6. Discovery и validation внешних MCP

- Добавить discovery внешнего MCP окружения: получить список tools/resources, найти tools с ServiceDesk async metadata, импортировать capability candidates, сверить schemas и event contracts.
- Если MCP не публикует достаточную metadata, разрешить ручной binding, но validation должна быть строгой.
- Validation rejects: отсутствующий required input, несовместимый output schema, async tool без accepted ack, async capability без valid `ExternalEvent` contract, prod environment без OIDC/auth policy, capability binding без allowed permission.

## Этап 7. Async contract skill

- Создать `.agents/skills/servicedesk-async-mcp-contract/SKILL.md`.
- Skill описывает canonical async flow, MCP execution environment responsibilities, command/ack/event model, idempotency, auth expectations и запрет backend-исполнителю менять business state.
- Детали вынести в `references/async-contract.md` и `references/mcp-execution-environment.md`.
- Обновить `servicedesk-n8n-runbooks`: он больше не является основным контрактом async исполнения, а только описывает частный случай внешнего MCP, внутри которого может жить n8n.

## Этап 8. Документ для разработчиков ранбуков

- Создать `docs/runbooks/ASYNC_MCP_RUNBOOK_DEVELOPER_GUIDE.md`.
- Документ описывает, как внешний MCP публикует capability tool, какие input schema и `async_context` обязательны, как вернуть accepted ack, как отправлять `progress/success/error/timeout/cancelled`, как формировать `idempotency_key`, как валидировать callback/event, как настраивать dev token и prod OIDC, как проверять health/discovery.
- Отдельно указать: если исполнитель внутри MCP использует n8n, Temporal, scripts или HTTP API, это внутренняя деталь MCP environment и не попадает в `ServiceDeskAgents` scenario contract.

## Этап 9. Перевод текущего provider сценария

- Описать capability `provider_channel_repair_monitor`.
- Подключить внешнее MCP environment, которое исполняет этот capability.
- Перевести profile/scenario на capability mapping: `provider_mail_body`, `provider_mail_subject`, `provider_ticket_number`, `polling_diagnostic`, `zabbix_status`.
- Удалить зависимость сценария от `n8n_monitor_provider_channel_repair`, `email_result.body`, n8n operation names и webhook paths.
- Проверить полный provider scenario: запуск capability, accepted ack, ожидание письма провайдера, заполнение `provider_mail_body`, извлечение `incident_number`, дальнейшее обновление/ожидание Zabbix через capability-level calls.

## Этап 10. Тестирование и rollout

- Schema tests: capabilities, MCP environments, capability bindings, async event contracts.
- Runtime tests: sync MCP execution, async MCP accepted ack, progress event, terminal success, timeout, duplicate idempotency key, invalid auth, wrong audience, incompatible schema.
- UI/config tests: scenario builder uses only capabilities, no `n8n_*` references in generated profiles, validation errors use canonical field names.
- Security tests: dev token accepted only for dev config, prod without OIDC rejected, callback JWT validation, secrets not logged in `Basic/Verbose`.
- Runtime gates: `/healthz`, `/readyz`, MCP environment health, async worker health, external event worker health, structured logging sink check.

## Assumptions

- `ServiceDeskAgents` не реализует собственный MCP server.
- Все исполнительские окружения являются внешними MCP.
- Прямых внутренних provider types `n8n/http/worker` не вводим.
- n8n, если используется, находится за внешним MCP и не виден `ServiceDeskAgents`.
- Legacy `n8n_*` compatibility не сохраняем.
- Async ownership остается в `ServiceDeskAgents`.
