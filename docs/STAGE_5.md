# Этап 5: расширение Tool Registry и policy

Этап 5 расширяет integration boundary из этапа 4 до полноценного MVP tool catalog и policy model. AI decision contract все еще только предлагает `tool_name` и parameters; endpoint selection, execution mode, approval, timeout, retry и adapter behavior остаются ответственностью backend.

## Базовые решения

- `contracts/tools/tool-catalog.json` содержит все MVP tools.
- У каждого tool есть `parameters_schema`, `result_schema` и policy metadata.
- Dispatcher валидирует normalized tool results по result schema конкретного tool.
- Trace fields нормализованы в `tool_result`: `policy_rule_id`, `duration_ms`, `attempts`.
- `direct_http` существует как skeleton adapter, но реальные прямые вызовы Zabbix/CMDB пока disabled.
- Unsupported future adapter types представлены catalog data и возвращают normalized errors.

## MVP tools

- `check_zabbix_status`
- `query_cmdb_object`
- `get_service_owner`
- `search_known_incidents`
- `start_systemcenter_runbook`

## Policy metadata

Каждый tool задает:

- default timeout;
- retry policy;
- allowed environments;
- approval hint;
- auto-execution eligibility flag;
- maximum allowed risk level.

Execution policy по-прежнему решает effective execution mode. В MVP read-only tools переходят в `dry_run`, предложения с критическим риском блокируются, а `start_systemcenter_runbook` требует согласование оператора.

## Adapter profiles

Начальные profiles:

- `mock`: локальный execution profile по умолчанию.
- `n8n`: реальный n8n webhook adapter для runbook execution.
- `direct_http`: disabled skeleton для будущих direct APIs.
- `queue`: catalog-only skeleton для проверки unsupported adapter handling.

## Команды

Запустить проверки синтаксиса и контрактов:

```bash
PYTHON=.venv/bin/python make stage5-check
```

Запустить smoke-проверку этапа 5 и negative checks:

```bash
./scripts/stage5-smoke.sh
```

## Критерии выхода

- Все MVP tools есть в catalog.
- Tool parameters и successful outputs валидируются схемами.
- Action tools не могут обойти policy и approval.
- Disabled endpoints и unsupported adapters возвращают normalized errors.
- Missing required parameters и unknown tools падают validation.
- Tool trace содержит endpoint, adapter, policy rule, duration, attempts и normalized error code.
