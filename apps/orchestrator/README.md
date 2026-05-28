# FastAPI AI Orchestrator

Плановые зоны ответственности:

- Предоставлять API оператора и администратора.
- Запускать LangGraph workflows.
- Валидировать контракты AI-решений через JSON Schema из `contracts/`.
- Использовать Python `jsonschema` в runtime FastAPI.
- Определять состояние workflow из каталога и правил переходов, а не из hardcoded enum.
- Вызывать LiteLLM для model inference.
- Вызывать Tool Registry и Integration Dispatcher для интеграций.
- Хранить состояние жизненного цикла кейса, согласования, трассировки инструментов, callbacks и обратную связь.

Первый API endpoint: `POST /tickets/analyze`.

## Локальные команды этапа 3

Установить локальные Python-зависимости:

```bash
make stage3-install
```

Запустить проверки:

```bash
make stage3-check
```

Запустить API:

```bash
PYTHON=.venv/bin/python make stage3-run
```

Запустить smoke-сценарии API:

```bash
./scripts/stage3-smoke.sh
```

## Локальные команды этапа 4

Запустить проверки слоя интеграций:

```bash
PYTHON=.venv/bin/python make stage4-check
```

Запустить smoke-сценарии dispatcher и adapter:

```bash
./scripts/stage4-smoke.sh
```

## Локальные команды этапа 5

Запустить проверки расширенного tool registry:

```bash
PYTHON=.venv/bin/python make stage5-check
```

Запустить smoke-сценарии каталога инструментов и негативных кейсов:

```bash
./scripts/stage5-smoke.sh
```

## Локальные команды этапа 6

Запустить проверки согласований action gate:

```bash
PYTHON=.venv/bin/python make stage6-check
```

Запустить smoke-сценарии API согласований:

```bash
./scripts/stage6-smoke.sh
```

Локальное хранилище согласований по умолчанию использует `state/orchestrator.sqlite`. Для изолированных тестов переопределите его через `ORCHESTRATOR_STATE_DB`.

## Локальные команды этапа 7

Перестроить локальный индекс базы знаний как действие оператора:

```bash
KNOWLEDGE_REBUILD_OPERATOR=operator-1 ./scripts/rebuild-knowledge.sh
```

Запустить проверки загрузки базы знаний и поиска:

```bash
PYTHON=.venv/bin/python make stage7-check
```

Запустить smoke-сценарии RAG API:

```bash
./scripts/stage7-smoke.sh
```

Индекс базы знаний по умолчанию использует `state/knowledge-index.json`. Для изолированных тестов переопределите его через `KNOWLEDGE_INDEX_PATH`.

## Локальные команды этапа 8

Запустить проверки Operator UI:

```bash
PYTHON=.venv/bin/python make stage8-check
```

Запустить smoke-сценарии Operator UI:

```bash
./scripts/stage8-smoke.sh
```

Запустите API и откройте `http://127.0.0.1:18088/operator`.

## Локальные команды этапа 9

Запустить проверки обратной связи и оценки:

```bash
PYTHON=.venv/bin/python make stage9-check
```

Запустить smoke-сценарии API обратной связи:

```bash
./scripts/stage9-smoke.sh
```

## Локальные команды этапа 10

Запустить проверки жизненного цикла кейса и callback:

```bash
PYTHON=.venv/bin/python make stage10-check
```

Запустить smoke-сценарии жизненного цикла кейса:

```bash
./scripts/stage10-smoke.sh
```

Этап 10 добавляет:

- `POST /cases`
- `GET /cases/{case_id}`
- `GET /cases/{case_id}/timeline`
- `POST /integrations/callbacks/{endpoint_id}`

`POST /tickets/analyze` остается совместимым и создает запись кейса внутри.

## Локальные команды этапа 10.5

Запустить проверки основы Admin API и операций оценки:

```bash
PYTHON=.venv/bin/python make stage10_5-check
```

Запустить smoke-сценарии Admin API:

```bash
./scripts/stage10_5-smoke.sh
```

Этап 10.5 добавляет административные endpoint'ы:

- `GET /admin/dashboard`
- `GET /admin/knowledge/status`
- `GET /admin/knowledge/sources`
- `POST /admin/knowledge/rebuild`
- `GET /admin/knowledge/chunks`
- `POST /admin/knowledge/retrieval/test`
- `GET /admin/catalog`
- `GET /admin/models/config`
- `POST /admin/evaluations/promote-feedback`
- `POST /admin/evaluations/run`

## Локальные команды этапа 11

Запустить проверки RBAC, аудита и контрактов безопасности:

```bash
PYTHON=.venv/bin/python make stage11-check
```

Запустить smoke-сценарии основы безопасности:

```bash
./scripts/stage11-smoke.sh
```

Этап 11 добавляет endpoint'ы безопасности:

- `GET /admin/security/session`
- `GET /admin/security/catalog`
- `GET /admin/security/secret-references`
- `GET /admin/security/audit`
- `GET /admin/security/audit/summary`

Dev auth использует `X-ServiceDesk-Actor`. Если header не задан, применяется `SECURITY_DEV_ACTOR`, по умолчанию `admin-1`.

Integration callback endpoint `POST /integrations/callbacks/{endpoint_id}` теперь требует `X-ServiceDesk-Callback-Token`, значение берется из `INTEGRATION_CALLBACK_TOKEN`.

## Локальные команды этапа 12

Запустить проверки MVP консоли администратора:

```bash
PYTHON=.venv/bin/python make stage12-check
```

Запустить smoke-сценарии интерфейса администратора и Admin API:

```bash
./scripts/stage12-smoke.sh
```

Этап 12 добавляет интерфейс администратора:

- `GET /admin`
- `GET /admin/static/app.js`
- `GET /admin/static/styles.css`

Новые Admin API:

- `GET /admin/prompts/catalog`
- `GET /admin/feedback`
- `GET /admin/evaluations/runs`

Откройте `http://127.0.0.1:18088/admin`.

## Локальные команды этапа 12.5

Запустить проверки сценарной модели оркестратора:

```bash
PYTHON=.venv/bin/python make stage12_5-check
```

Запустить smoke-сценарии сценарной консоли:

```bash
./scripts/stage12_5-smoke.sh
```

Этап 12.5 добавляет Admin API:

- `GET /admin/scenarios`
- `GET /admin/scenarios/{scenario_id}`
- `POST /admin/scenarios/{scenario_id}/simulate`

В интерфейсе администратора используйте раздел `Сценарии`.

## Локальные команды этапа 12.7

Запустить проверки resolver-профиля разрешения атрибута:

```bash
PYTHON=.venv/bin/python make stage12_7-check
```

Запустить smoke-сценарии матрицы решений и dry-run состояния:

```bash
./scripts/stage12_7-smoke.sh
```

Этап 12.7 упрощает `Сценарии обработки -> 1. Разрешение атрибутов`: профиль заполняет слот как resolver с признаками, операцией разрешения, правилами оценки результата, матрицей решений, вопросом уточнения и пакетом передачи человеку.

Этап 13.5 добавляет домен `interaction_channels`: сценарий выбирает канал взаимодействия, а канал задает доставку вопросов, ожидание ответа, действие при незавершенном обсуждении и действие эскалации.

Этапы 13.6-13.7 расширяют `interaction_channels` профилями действий канала. Политика эскалации задает условия решения, а канал выбирает фактическое действие по `event_type`: отладочная остановка, создание наряда, вызов специалиста или оповещение дежурных.

Этап 13.8 заменяет технические поля `l2_conditions` и `escalation_package` на `handoff_conditions` и `handoff_package`. Консоль администратора редактирует их чекбоксами, а backend не поддерживает старые поля.

Этап 13.9 заменяет техническое поле `allowed_tool_classes` на `allowed_react_action_groups`. Блок `3. ReAct-планирование` редактирует группы действий и стоп-условия чекбоксами, а backend не поддерживает старое поле.

## Локальные команды этапа 13

Запустить проверки реестра конфигурации и расширенной консоли администратора:

```bash
PYTHON=.venv/bin/python make stage13-check
```

Запустить smoke-сценарии draft/validate/regression/activate/rollback:

```bash
./scripts/stage13-smoke.sh
```

Этап 13 добавляет Admin API:

- `GET /admin/config/domains`
- `GET /admin/config/active/{domain}`
- `POST /admin/config/drafts`
- `POST /admin/config/drafts/{draft_id}/validate`
- `POST /admin/config/drafts/{draft_id}/regression`
- `POST /admin/config/drafts/{draft_id}/activate`
- `GET /admin/config/versions`
- `POST /admin/config/versions/{version_id}/rollback`
- `GET /admin/n8n/workflows`

В интерфейсе администратора используйте раздел `Изменения конфигурации`.
