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
