# Этап 2: контракты AI-решений

Этап 2 задает machine-readable boundary между моделью, оркестратором и будущей execution policy. Модель предлагает, что нужно сделать. Backend решает, будет ли action заблокирован, выполнен вручную, потребует согласование оператора, пойдет как dry run или сможет быть auto-executed.

## Граница контрактов

AI output должен быть документом `ai_decision`:

- `schema_version`
- `decision.type`
- `operator_message`
- опционально `internal_reasoning_summary`
- опционально `citations`
- опционально `proposed_actions`
- опционально `extensions`

Разрешенные типы решений:

- `answer_proposed`
- `clarification_needed`
- `escalation_needed`
- `action_proposed`

Модель может предлагать actions через `proposed_actions[]`, но не может задавать execution mode, approval status, policy rule или execution result. Эти поля относятся к execution policy result, а не к model output.

## Execution policy

Policy layer принимает валидированное AI-решение и metadata инструмента. На выходе он возвращает `execution_policy_result` с одним из режимов:

- `manual_only`
- `operator_approval`
- `auto_execute`
- `dry_run`
- `blocked`

Для MVP `start_systemcenter_runbook` всегда мапится на `operator_approval`. Позднее low-risk ранбуки из allowlist можно перевести в `auto_execute` без изменения AI decision schema.

## Файлы

- `contracts/decisions/ai-decision.schema.json`
- `contracts/tools/proposed-action.schema.json`
- `contracts/execution/execution-policy-result.schema.json`
- `contracts/execution/model-output-invalid.schema.json`
- `contracts/workflow/workflow-state.schema.json`
- `contracts/examples/ai-decisions/valid/`
- `contracts/examples/ai-decisions/invalid/`
- `contracts/examples/execution-policy/valid/`
- `contracts/examples/failures/valid/`
- `apps/orchestrator/src/decision-contracts.mjs`
- `scripts/validate-contracts.mjs`
- `scripts/validate-contracts.sh`

## Валидация

Запуск:

```bash
./scripts/validate-contracts.sh
```

Validator проверяет:

- все contract schemas являются валидным JSON;
- valid fixtures проходят;
- invalid AI fixtures падают;
- model output не содержит policy или execution fields;
- `action_proposed` содержит минимум один valid proposed action;
- non-action decisions не несут proposed actions;
- execution policy fixtures соответствуют mode-specific constraints;
- invalid model output может быть превращен в `workflow_state.id=model_output_invalid` с `can_advance=false`.

## Критерии выхода

- Invalid model output не может продвинуть workflow state.
- Action proposals не могут обойти policy evaluation.
- MVP runbook path представлен как `action_proposed` плюс `operator_approval`.
- Те же контракты поддержат будущие `auto_execute` outcomes от policy.
