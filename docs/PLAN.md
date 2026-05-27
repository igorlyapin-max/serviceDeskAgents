# AI ServiceDesk Assistant: верхнеуровневый план

План основан на `sDa.txt` и учитывает CPU-only разработку, раннее выделение расширяемого интеграционного слоя, n8n как первый adapter endpoint и выполнение ранбуков только после согласования оператора в MVP.

## Правило языка

- Документация, пользовательские тексты и Operator UI ведутся только на русском языке.
- Технические идентификаторы не переводятся: API paths, JSON-поля, contract names, enum/status values, имена команд, имена файлов, tool names и adapter types.
- Если backend-строка отображается в UI оператору, она тоже должна быть написана по-русски.

## Базовые решения

- Оркестратор обращается только к LiteLLM, а не напрямую к vLLM, Ollama или будущему GPU backend.
- vLLM CPU используется в разработке как OpenAI-compatible smoke/integration backend, а не как финальный ориентир качества.
- n8n вводится рано, потому что запуск ранбуков дает высокую ценность, но n8n является только первым adapter и не должен стать единственным типом endpoint.
- Запуск ранбука является action tool и в MVP всегда требует явного согласования оператора.
- LangGraph решает, что должно произойти; Execution Policy, Tool Registry и Integration Dispatcher решают, можно ли вызывать интеграции и каким способом.
- Integration endpoints описываются каталогом/конфигурацией. AI может предложить tool action, но не может выбирать adapter, endpoint URL, execution mode или approval status.
- RAG добавляется после стабилизации основных контрактов решений и tool-call.
- Case API владеет жизненным циклом service desk case. Endpoint adapters, включая n8n, возвращают нормализованные результаты через синхронный tool result или callback API.

## Целевой жизненный цикл

```text
Operator UI
  -> FastAPI Case API
  -> AI Orchestrator
  -> LangGraph / Workflow Engine
  -> Execution Policy + Action Gate
  -> Tool Registry
  -> Integration Dispatcher
  -> Endpoint Adapter: mock / n8n_webhook / direct_http / queue / future
  -> External Systems
  -> Callback API / normalized tool result
  -> Case Store
  -> UI update / escalation / resolve / feedback
```

n8n является одним endpoint adapter в этом жизненном цикле. Он не является единственным путем исполнения и не должен протекать в AI decision contracts или case lifecycle contracts.

## Последовательность разработки

### Этап 0: базовый контур разработки

Цель: создать воспроизводимую локальную среду для CPU-only разработки.

Поставки:

- Docker Compose структура.
- PostgreSQL с возможностью pgvector.
- Redis.
- n8n в минимальном self-hosted режиме.
- LiteLLM и vLLM CPU за опциональным профилем.
- Шаблон окружения.
- Структура директорий проекта.
- Healthcheck и команды smoke-проверок.

Критерии выхода:

- `docker compose config` проходит.
- Порты и имена сервисов задокументированы.
- Основные сервисы можно запускать независимо от тяжелого LLM runtime.

### Этап 1: LLM gateway

Цель: открыть локальный OpenAI-compatible endpoint через LiteLLM.

Поставки:

- vLLM CPU с маленькой smoke-моделью `facebook/opt-125m`; `Qwen/Qwen3-0.6B` остается более поздним кандидатом по качеству.
- LiteLLM routing к vLLM.
- Smoke-проверка для `POST /v1/chat/completions`.
- Безопасные для CPU лимиты model length и KV cache.

Критерии выхода:

- FastAPI/LangGraph может обращаться к LiteLLM через стабильный model alias.
- У оркестратора нет прямой зависимости от vLLM-specific API.

### Этап 2: контракты AI-решений

Цель: сделать результаты AI машинно-валидируемыми до реализации сложных workflow.

Поставки:

- Расширяемые JSON Schema для:
  - envelope AI-решения.
  - типы решений: `answer_proposed`, `clarification_needed`, `escalation_needed`, `action_proposed`.
  - proposed actions.
  - результат execution policy.
- Слой валидации для model output.
- Policy boundary, отделяющий AI proposals от execution decisions.
- Failure path для invalid model output.

Критерии выхода:

- Invalid model output не может продвинуть workflow state.
- Model output может предлагать actions, но не может помечать их approved или auto-executable.
- Runbook proposals представлены как proposed actions; MVP policy мапит `start_systemcenter_runbook` на согласование оператора.
- Контракт позднее поддержит `auto_execute`, `dry_run`, `operator_approval`, `manual_only` и `blocked`.

### Этап 3: FastAPI и LangGraph skeleton

Цель: реализовать первый исполняемый service workflow.

Поставки:

- `POST /tickets/analyze`.
- Python FastAPI app.
- JSON Schema validation через Python `jsonschema`, где `contracts/` является source of truth.
- Модели ticket request/response без дублирования enum-логики в Python.
- Workflow state catalog и transition rules.
- Проверки обязательных полей.
- Начальный classification node.
- Decision node.
- Execution policy node.
- Mock tool node.
- Расширяемый `workflow_state` для ранбуков, invalid model output, clarification, escalation и будущих auto-execution states.

Критерии выхода:

- API валидирует AI decisions, proposed actions, execution policy results и workflow states по JSON Schema из `contracts/`.
- Backend обрабатывает answer, clarification, escalation и action proposals.
- Approval или auto-execution mode выводится из policy, а не из raw model output.
- Workflow state выводится из catalog и transition rules, а не из hardcoded enum.
- Новые workflow state IDs можно добавлять данными config/schema без изменения core workflow code.
- Сценарии можно тестировать без реальных внешних систем.

### Этап 4: основа интеграционного слоя

Цель: рано ввести расширяемый integration layer. n8n является первым реальным adapter, но не единственной моделью endpoint.

Поставки:

- Минимальные контракты Tool Registry:
  - tool definition.
  - tool invocation.
  - normalized tool result.
- Контракты integration endpoint:
  - endpoint definition.
  - adapter type.
  - auth reference.
  - operation mapping.
- Endpoint catalog минимум с:
  - `mock` endpoint для локальных тестов.
  - `n8n_webhook` endpoint для запуска ранбуков.
- Tool catalog минимум с:
  - `start_systemcenter_runbook`, привязанным к configurable endpoint.
  - одним read-only diagnostics stub, привязанным к `mock`.
- Python Integration Dispatcher.
- Adapter interface.
- `mock` adapter.
- `n8n_webhook` adapter.
- Минимальный n8n webhook workflow для запуска ранбука.
- Token-based защита webhook.
- Общий normalized JSON result contract для всех adapters.

Критерии выхода:

- Оркестратор никогда не вызывает n8n напрямую.
- `start_systemcenter_runbook` проходит через Tool Registry и Integration Dispatcher к configured endpoint.
- Endpoint можно заменить с n8n на mock или будущий direct API через config/catalog data.
- Action tools требуют execution policy и согласование оператора до вызова dispatcher.
- n8n workflows можно mock-ать без изменения orchestrator workflow code.
- AI output не может выбирать endpoint URL, adapter type или execution mode.

### Этап 5: расширение Tool Registry и policy

Цель: расширить tool catalog и policy model после стабилизации dispatcher boundary.

Поставки:

- Полные declarative tool definitions для MVP tools.
- Tool types: `read_only` и `action`.
- Tool-specific input/output schemas.
- Timeout и retry policies.
- Approval policy per tool.
- Auto-execution policy per tool and environment.
- Adapter-specific operation mapping.
- Опциональные будущие adapters: `direct_http` или queue-based invocation.
- Tool trace и normalized error fields.

Начальные tools:

- `check_zabbix_status` как `read_only`.
- `query_cmdb_object` как `read_only`.
- `get_service_owner` как `read_only`.
- `search_known_incidents` как `read_only`.
- `start_systemcenter_runbook` как `action` с обязательным согласованием.

Критерии выхода:

- LLM output не может напрямую вызывать external systems.
- Action tools требуют policy evaluation до Integration Dispatcher.
- MVP policy требует согласование оператора для `start_systemcenter_runbook`; позднее policy может разрешить low-risk auto-execution по allowlist.
- Добавление или замена endpoint adapter не требует изменения AI decision contracts.

### Этап 6: ранбуки с согласованием оператора

Цель: дать раннюю высокую ценность через backend-owned action gate и сохранить human approval gate для MVP runbooks.

Поток:

1. Оператор отправляет заявку.
2. LangGraph анализирует заявку и read-only diagnostics.
3. AI возвращает `action_proposed` с runbook proposal.
4. Backend оценивает execution policy.
5. Backend создает persisted action gate record.
6. Backend возвращает `operator_approval` и `approval_requests` для MVP runbooks.
7. UI показывает runbook name, reason, parameters, expected effect и risk notes.
8. Оператор согласует или отклоняет по `approval_id`.
9. Backend вызывает Integration Dispatcher только после approval, используя сохраненные action и policy result.
10. Dispatcher вызывает configured endpoint; в MVP это mock или n8n webhook.
11. Endpoint возвращает normalized result через adapter.
12. Заявка получает runbook result, rejection state или escalation summary.

Архитектурные решения:

- Использовать action-gate record вместо UI-supplied approval flag.
- Поддержать `gate_type=operator_approval` сейчас и зарезервировать `gate_type=auto_policy` для будущего auto-execution.
- Хранить action-gate contracts в JSON Schema и валидировать их в Python backend.
- Хранить MVP gate records в local SQLite через replaceable store abstraction.
- Workflow states и transitions остаются catalog-driven.

Критерии выхода:

- Модель может предложить runbook, но не может его выполнить.
- У каждого runbook execution есть approval record.
- Каждый внешний runbook call проходит через Tool Registry и Integration Dispatcher.
- Public dispatch API отклоняет client-supplied `approved_by_operator=true`.
- Отклоненные approvals не вызывают integrations.
- Повторное approval decision не может выполнить тот же runbook дважды.

### Этап 7: загрузка базы знаний и минимальный RAG

Цель: использовать внутренние знания из нескольких источников, не блокируя раннюю ценность tools/runbooks.

Поставки:

- Knowledge source catalog для local files, corporate wiki, ServiceDesk KB, CMDB exports, Git repositories и future API sources.
- Connector interface для source ingestion.
- Реализованный `local_files` connector для `.md` и `.txt` документов разработки.
- Disabled/config-ready skeletons для remote sources, например corporate wiki.
- Normalized document contract, общий для всех источников.
- Chunking job и local lexical index для CPU-only разработки.
- pgvector-backed retrieval как target backend за тем же retriever interface, не hard dependency локальной разработки.
- Operator-triggered knowledge rebuild action с manifest, status, counts, errors и timestamps.
- Retriever node в LangGraph/FastAPI workflow, использующий последний успешный индекс.
- Source references в operator response.

Архитектурные решения:

- `knowledge/` является только локальным development source, а не всей RAG architecture.
- `/tickets/analyze` не должен синхронно загружать произвольные wiki/API pages.
- Перестроение базы знаний является явным действием оператора, а не автоматикой на каждый анализ заявки.
- Analysis использует latest successful index и деградирует корректно при retrieval failure.
- Corporate wiki и другие remote sources загружаются через connectors и нормализуются до индексирования.

Критерии выхода:

- В config/catalog data можно представить несколько source types.
- Local source ingestion и retrieval работают end to end.
- Disabled remote source skeletons не ломают rebuild или analysis.
- Rebuild создает validated index manifest.
- Workflow может цитировать найденные документы.
- RAG failures приводят к escalation/clarification или обычному ответу, а не к поломанному response.

### Этап 8: минимальный Operator UI

Цель: предоставить рабочий end-to-end manual workflow.

Поставки:

- Static operator UI, отдаваемый FastAPI на `/operator`.
- Форма ввода заявки.
- Отображение AI decision.
- Отображение clarification.
- Отображение escalation.
- Контролы approve/reject для runbook.
- Отображение integration/runbook execution result.
- Контрол перестроения базы знаний оператором.
- Отображение knowledge index status.
- Copy-to-service-desk text.
- Tool call и RAG trace view.

Архитектурные решения:

- UI этапа 8 остается static и backend-served, без отдельного frontend toolchain.
- Использовать тот же approval API, что и backend smoke tests; не разрешать UI-side execution bypass.
- Feedback collection вынесен из scope этапа 8.
- RBAC/login вынесен в этап 11.

Критерии выхода:

- Оператор может вручную обработать заявку от input до copyable final result.
- Runbook approval видим и явен.
- Перестроение базы знаний видно и явно выполняется как действие оператора.

### Этап 9: обратная связь и цикл оценки

Цель: собрать данные обратной связи для будущей оценки качества перед расширением agents.

Поставки:

- Контракты JSON Schema для обратной связи.
- Operator feedback: `correct`, `incorrect`, `edited`.
- Сохраненный ticket input.
- Сохраненный decision output.
- Сохраненные RAG hits.
- Сохраненные tool outputs.
- Опциональный snapshot результата согласования или ранбука.
- SQLite-backed feedback store.
- Контролы обратной связи в Operator UI.
- Exportable regression dataset seed.

Архитектурные решения:

- Обратная связь должна ссылаться на точный analysis snapshot, который видел оператор.
- `edited` feedback требует corrected response.
- Export format: JSONL evaluation cases для будущих regression runs.
- Full evaluation runner, feedback history UI и quality analytics отложены в этап 10.5.
- RBAC, full audit log и automated model training вне scope.

Критерии выхода:

- Обратную связь можно сохранить и экспортировать без изменения ticket workflow state.
- Exported feedback содержит достаточно контекста, чтобы стать curated evaluation set в этапе 10.5.

### Этап 10: жизненный цикл кейса и callback API

Цель: ввести durable case lifecycle boundary перед hardening pilot surface.

Поставки:

- Контракты кейсов:
  - `case-record`.
  - `case-event`.
  - `case-timeline`.
  - `integration-callback`.
- SQLite-backed `CaseStore` abstraction.
- Case API:
  - `POST /cases` или compatible case creation через `/tickets/analyze`.
  - `GET /cases/{case_id}`.
  - `GET /cases/{case_id}/timeline`.
  - callback endpoint для normalized integration results.
- Persisted case lifecycle state:
  - ticket input.
  - current workflow state.
  - AI decision snapshot.
  - RAG trace.
  - tool trace.
  - action gate references.
  - feedback references.
  - final resolution, escalation или failed state.
- Correlation identifiers для async work:
  - `case_id`.
  - `ticket_id`.
  - `action_id`.
  - `invocation_id`.
  - `endpoint_id`.
- Callback handling для long-running endpoint adapters.
- UI polling case status и timeline.
- Smoke scenario для async-style runbook result:
  - create/analyze case.
  - create pending action gate.
  - simulate endpoint callback.
  - update case state and timeline.
  - read updated case through API/UI.

Архитектурные решения:

- Case API владеет lifecycle state; Integration Dispatcher и adapters возвращают только normalized tool results/callbacks.
- n8n callback payloads нормализуются на границе и не становятся core case schema.
- Synchronous adapter results и asynchronous callbacks используют один normalized result model.
- UI начинает с polling; WebSocket/SSE не нужны на этом этапе.
- Hardening идет после стабилизации lifecycle/callback boundary.

Критерии выхода:

- Case можно создать, прочитать и обновить через normalized workflow events.
- Long-running endpoint results могут обновить case после initial acceptance.
- Case timeline показывает analysis, approval, dispatch, callback/result и feedback events.
- Existing ticket-oriented endpoints остаются compatible или мапятся на case records.
- Добавление или замена endpoint adapter не требует изменения case lifecycle contracts.

### Этап 10.5: evaluation runner и операции обратной связи

Цель: завершить отложенный на этапе 9 evaluation loop поверх durable case lifecycle.

Поставки:

- Реализация evaluation runner с существующими feedback contracts:
  - `evaluation-run`.
  - `evaluation-result`.
- CLI или API для запуска curated evaluation set против текущего workflow.
- Promotion workflow из raw feedback records в curated evaluation set.
- История обратной связи в Operator UI:
  - предыдущие feedback records для case/ticket.
  - действие export/download.
  - status evaluation run.
- Quality analytics:
  - ratings over time.
  - corrected-response rate.
  - regression pass/fail summary.
- Version metadata capture:
  - model.
  - prompt/config.
  - knowledge index.
  - tool registry/config.
- Feedback idempotency и duplicate detection.
- Case timeline links для feedback и evaluation events.

Архитектурные решения:

- CaseStore и case timeline являются durable source для snapshots; raw feedback этапа 9 остается import/export input.
- Evaluation runs по умолчанию используют dry-run, mock или явно sandboxed execution policy и не запускают реальные external actions.
- Curated evaluation cases отделены от raw feedback, чтобы шумные operator notes не становились regression gates автоматически.
- RBAC, full audit log и secret hardening остаются в этапе 11, но этап 10.5 пишет actor/version metadata для будущей audit integration.

Критерии выхода:

- Curated evaluation set можно повторно запускать против текущего workflow.
- Evaluation results показывают pass/fail status и differences для model, prompt, RAG и tool changes.
- Operators могут смотреть feedback history и export/download evaluation data из UI.
- Feedback и evaluation events видимы в case timeline.

### Этап 11: hardening

Цель: подготовить MVP к более безопасному пилотному использованию.

Поставки:

- Журнал аудита.
- История согласований.
- Базовый RBAC.
- Управление секретами.
- Rate limits.
- Timeouts and retries.
- Structured logs.
- Healthchecks.
- Процедура резервного копирования PostgreSQL.
- Набор регрессионных сценариев.

Критерии выхода:

- Action tools не могут обходить approvals.
- Активность оператора и интеграций трассируема.
