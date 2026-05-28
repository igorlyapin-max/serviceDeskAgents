# Этап 11: RBAC, аудит и основа безопасности

Этап 11 закрывает backend-основу безопасности до полноценной консоли администратора: проверки прав, audit log, защита callback token, представление сессии и ссылки на секреты без хранения секретных значений в API-ответах.

## Реализовано

- Каталог безопасности в `contracts/security/security-catalog.json`.
- JSON Schema для:
  - `security-catalog`.
  - `audit-event`.
- Валидация Python через `ContractRegistry`.
- Валидация Node через `scripts/validate-contracts.mjs`.
- RBAC dependency layer для FastAPI.
- Dev auth mode через headers:
  - `X-ServiceDesk-Actor`.
  - `X-ServiceDesk-Session`.
- Dev actor по умолчанию: `admin-1`.
- Callback auth через `X-ServiceDesk-Callback-Token`.
- Audit log в SQLite в общем `ORCHESTRATOR_STATE_DB`.
- Rate limit на actor/session в памяти процесса.
- Инвентаризация секретов только со ссылками.

## Роли

- `admin`.
- `operator`.
- `support_l1`.
- `support_l2`.
- `readonly`.
- `endpoint` как техническая роль для integration callbacks.

## Права

- `cases.read`.
- `cases.operate`.
- `approvals.decide`.
- `callbacks.write`.
- `feedback.write`.
- `knowledge.read`.
- `knowledge.manage`.
- `tools.read`.
- `tools.manage`.
- `prompts.read`.
- `prompts.manage`.
- `workflow.read`.
- `workflow.manage`.
- `models.read`.
- `models.manage`.
- `evaluation.run`.
- `audit.read`.
- `security.manage`.

## Admin Security API

- `GET /admin/security/session`.
- `GET /admin/security/catalog`.
- `GET /admin/security/secret-references`.
- `GET /admin/security/audit`.
- `GET /admin/security/audit/summary`.

## Защищенные действия

- `POST /tickets/analyze` требует `cases.operate`.
- `POST /cases` требует `cases.operate`.
- `GET /cases/{case_id}` и timeline требуют `cases.read`.
- `POST /approvals/{approval_id}/decision` требует `approvals.decide`.
- `POST /tools/dispatch` требует `tools.manage` и по-прежнему запрещает client-supplied `approved_by_operator=true`.
- `POST /knowledge/rebuild` и `POST /admin/knowledge/rebuild` требуют `knowledge.manage`.
- `POST /feedback` требует `feedback.write`.
- `POST /admin/evaluations/*` требует `evaluation.run`.
- `POST /integrations/callbacks/{endpoint_id}` требует callback token и техническое право `callbacks.write`.

## Аудит

Событие аудита пишет:

- actor.
- roles.
- session.
- action.
- resource type/id.
- permission.
- outcome: `success`, `denied`, `error`.
- request method/path.
- status code.
- безопасные details без значений secret/token/password/key.

Минимально аудируются:

- создание/анализ кейса.
- вызов инструментов.
- решения по согласованиям.
- обработка callback.
- перестроение базы знаний.
- отправка обратной связи.
- перенос обратной связи в оценочные кейсы.
- запуски оценки.
- отказы проверок прав.
- отказы callback token.
- отказы по rate limit.

## Конфигурация

```bash
SECURITY_AUTH_MODE=dev_header
SECURITY_DEV_ACTOR=admin-1
SECURITY_RATE_LIMIT_PER_MINUTE=600
INTEGRATION_CALLBACK_TOKEN=dev-callback-token
```

`SECURITY_AUTH_MODE=disabled` оставлен только для локальной диагностики.

## Проверки

```bash
PYTHON=.venv/bin/python make stage11-check
./scripts/stage11-smoke.sh
```

## Ограничения этапа

- Это не production identity provider.
- Пользователи и роли пока задаются catalog data, а не через UI.
- Rate limit хранится в памяти процесса.
- Ссылки на секреты показывают только references и configured flag, не значения.
- MFA, IP restrictions, интеграция с Vault и полноценное управление пользователями остаются для следующих этапов.
