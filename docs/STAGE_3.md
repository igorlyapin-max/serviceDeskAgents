# Этап 3: FastAPI и LangGraph skeleton

Этап 3 создает первый исполняемый backend workflow. Endpoint полезен для интеграционной работы и UI, но пока не выполняет реальные external actions.

## Базовые решения

- JSON Schema файлы в `contracts/` являются source of truth.
- Python/FastAPI валидирует runtime payloads через `jsonschema`.
- Pydantic models могут описывать HTTP transport, но не должны становиться вторым source of truth для enum decision/action/policy/workflow-state.
- `workflow_state` является объектом из catalog, а не hardcoded Python enum.
- Модель может предлагать actions, но execution mode и workflow state приходят из policy и transition rules.

## Endpoint

`POST /tickets/analyze`

Поля входа:

- `user`
- `service`
- `description`
- `priority`

Форма ответа:

```json
{
  "ticket_id": "local-...",
  "workflow_state": {
    "id": "pending_approval",
    "category": "waiting",
    "terminal": false,
    "can_advance": false,
    "requires_operator_action": true
  },
  "ai_decision": {},
  "execution_policy_results": [],
  "operator_message": "Проверьте предложенный ранбук перед выполнением.",
  "tool_results": [],
  "tool_trace": []
}
```

## Узлы workflow

1. `intake_validation`
2. `classification_node`
3. `decision_node`
4. `contract_validation_node`
5. `execution_policy_node`
6. `workflow_state_resolution_node`
7. `mock_tool_node`
8. `response_builder`

Режим решения по умолчанию должен быть deterministic fixtures/rules. LiteLLM mode можно добавить за flag, но invalid model JSON должен превращаться в `model_output_invalid` и не должен продвигать workflow.

## Каталог состояний workflow

Known states являются данными, а не code constants. Начальные entries:

- `resolved`
- `waiting_for_user`
- `escalation_required`
- `pending_approval`
- `model_output_invalid`
- `policy_blocked`
- `auto_execution_ready`
- `auto_execution_running`
- `auto_execution_succeeded`
- `auto_execution_failed`

Transition rules мапят валидированные факты контракта на state IDs:

```json
{
  "when": {
    "decision_type": "action_proposed",
    "execution_mode": "operator_approval"
  },
  "state_id": "pending_approval"
}
```

## Валидация

FastAPI должен загружать и валидировать через `jsonschema`:

- `contracts/decisions/ai-decision.schema.json`
- `contracts/tools/proposed-action.schema.json`
- `contracts/execution/execution-policy-result.schema.json`
- `contracts/execution/model-output-invalid.schema.json`
- `contracts/workflow/workflow-state.schema.json`
- `contracts/workflow/workflow-state-catalog.schema.json`
- `contracts/workflow/workflow-transition-rules.schema.json`
- `contracts/execution/execution-policy-rules.schema.json`

## Команды

Установить зависимости в локальное виртуальное окружение:

```bash
make stage3-install
```

Запустить проверки синтаксиса и контрактов:

```bash
PYTHON=.venv/bin/python make stage3-check
```

Запустить API:

```bash
PYTHON=.venv/bin/python make stage3-run
```

Запустить smoke-сценарии:

```bash
./scripts/stage3-smoke.sh
```

## Вне scope

- Real integration adapter calls, включая n8n.
- Real System Center execution.
- Auto-execution enablement.
- RAG.
- PostgreSQL persistence кроме опциональных локальных трассировок.

## Критерии выхода

- `POST /tickets/analyze` работает без external systems.
- Покрыты четыре сценария решения: answer, clarification, escalation, action proposal.
- `start_systemcenter_runbook` через policy и transition rules переходит в `pending_approval`.
- Invalid model output переходит в `model_output_invalid` с `can_advance=false`.
- Workflow state выводится из catalog data, а не hardcoded Python literals.
