# Этап 13.9: чекбоксы ReAct-планирования

Этап 13.9 делает блок `3. ReAct-планирование` предметным: администратор выбирает группы действий и стоп-условия, а не вводит внутренние идентификаторы через CSV.

## Реализовано

- В `orchestrator_policy` используется новое поле `allowed_react_action_groups`.
- Старое поле `allowed_tool_classes` удалено из активной модели и не поддерживается.
- `stop_conditions` использует новые предметные значения:
  - `all_required_slots_filled`;
  - `tool_success`;
  - `clarification_required`;
  - `handoff_required`;
  - `iteration_limit`;
  - `consecutive_tool_errors`.
- В Admin UI блока `3`:
  - `Максимум итераций` остается числовым полем;
  - `Ошибок инструментов подряд до передачи` остается числовым полем;
  - `Разрешенные группы действий ReAct` выбираются чекбоксами;
  - `Стоп-условия` выбираются чекбоксами;
  - у каждого пункта есть пояснение.
- Operator UI показывает группы действий ReAct и стоп-условия русскими названиями.

## Валидация

- `allowed_react_action_groups` должен быть непустым.
- `stop_conditions` должен быть непустым.
- `consecutive_tool_errors_to_escalate` не может быть больше `max_iterations`.
- Payload со старым `allowed_tool_classes` не проходит JSON Schema.

## Проверки

```bash
PYTHON=.venv/bin/python make stage13_9-check
./scripts/stage13_9-smoke.sh
```

## URL

- Интерфейс администратора: `http://127.0.0.1:18088/admin`.
- Панель оператора: `http://127.0.0.1:18088/operator`.
