# Этап 6: action gates с согласованием оператора

Этап 6 превращает согласование ранбука в backend-owned workflow. Модель по-прежнему может только предложить action. Client не может выполнить approved runbook через `approved_by_operator=true`; state-changing execution должен проходить через сохраненный action gate.

## Базовые решения

- `action_gate` является server-side execution gate для state-changing actions.
- Этап 6 использует `gate_type=operator_approval`.
- Та же форма record уже резервирует `gate_type=auto_policy` для будущего auto-execution.
- Action, policy result, operator decision, audit events и tool result хранятся вместе.
- Local MVP store: SQLite в `ORCHESTRATOR_STATE_DB` или `state/orchestrator.sqlite`.
- SQLite является implementation detail; API и JSON contracts являются boundary.

## Контракты

Новые контракты:

- `contracts/execution/action-gate-record.schema.json`
- `contracts/execution/action-gate-decision.schema.json`
- `contracts/execution/action-gate-result.schema.json`

Workflow states расширены:

- `approval_rejected`
- `action_execution_succeeded`
- `action_execution_failed`

Transitions остаются catalog-driven через `contracts/workflow/workflow-transition-rules.json`.

## API flow

1. `POST /tickets/analyze` возвращает `approval_requests` для actions, которым нужно approval.
2. `GET /approvals/{approval_id}` возвращает сохраненный gate record.
3. `GET /tickets/{ticket_id}/approvals` показывает gates по заявке.
4. `POST /approvals/{approval_id}/decision` принимает `approve` или `reject`.
5. Approve вызывает Tool Registry и Integration Dispatcher с сохраненными action и policy result.
6. Reject обновляет gate и не вызывает dispatcher.

`POST /tools/dispatch` остается доступным для dry-run и policy gate checks, но отклоняет client-supplied `approved_by_operator=true`.

## Команды

Запустить проверки синтаксиса и контрактов:

```bash
PYTHON=.venv/bin/python make stage6-check
```

Запустить smoke-проверки потока согласования:

```bash
./scripts/stage6-smoke.sh
```

## Критерии выхода

- Runbook proposal создает pending approval/action-gate record.
- Оператор может согласовать или отклонить по `approval_id`.
- Согласованные runbooks выполняются через Tool Registry и Integration Dispatcher.
- Отклоненные runbooks не вызывают integrations.
- Повторные decisions не могут выполнить runbook дважды.
- External clients не могут обойти approval endpoint через `approved_by_operator=true`.
- Record format может представить будущий policy-approved auto-execution.
