# AI ServiceDesk Assistant: верхнеуровневый план

План основан на `sDa.txt` и учитывает CPU-only разработку, раннее выделение расширяемого интеграционного слоя, n8n как первый adapter endpoint и выполнение ранбуков только после согласования оператора в MVP.

## Правило языка

- Документация, пользовательские тексты, операторский интерфейс и консоль администратора ведутся только на русском языке.
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

## Административная плоскость

Операторский интерфейс и консоль администратора являются разными интерфейсами с разными границами ответственности.

Операторский интерфейс:

- обрабатывает обращения пользователей;
- запускает анализ заявки;
- согласует или отклоняет действия по конкретному кейсу;
- сохраняет обратную связь по ответу AI;
- не меняет глобальную конфигурацию платформы.

Административная консоль:

- управляет поведением AI;
- управляет базой знаний;
- управляет инструментами, endpoint adapters и интеграциями;
- управляет конфигурацией рабочего процесса;
- контролирует качество AI;
- управляет безопасностью, доступом и аудитом;
- не используется для обработки обращений пользователей.

Целевая административная архитектура:

```text
React-консоль администратора
  -> Admin API
  -> Config Registry / Audit / Quality
  -> Case API / Knowledge / Tool Registry / LiteLLM / Integration Dispatcher
```

Консоль администратора не должна напрямую менять business state кейса и не должна обходить Case API, Tool Registry, Execution Policy или Integration Dispatcher. Любое опасное административное действие должно иметь permission check, audit event и, где применимо, режим draft/validate/activate.

Начальный стек консоли администратора:

- React.
- TypeScript.
- Vite.
- Ant Design.
- React Query.
- React Router.

Начальные административные разделы:

- Панель обзора платформы.
- Сценарии обработки обращений как главный рабочий раздел администратора:
  - Сценарии;
  - 0. Разрешение атрибутов;
  - 1. Слоты;
  - 2. Классификация и маршрут;
  - 3. ReAct-планирование;
  - 4. Инструменты и матрица запуска;
  - 5. Решение и эскалация;
  - 6. Промпты;
- База знаний / RAG.
- Инструменты и интеграции.
- Конфигурация рабочего процесса.
- Модели.
- Пользователи, роли и права.
- Аудит и наблюдаемость.
- Контроль качества.
- Безопасность.

Немедленный приоритет административной консоли:

- Перестроить модель управления вокруг сценария обращения, а не вокруг разрозненных таблиц `tools`, `prompts`, `workflow` и `endpoints`.
- Закрепить пять шагов оркестратора как основную навигацию внутри сценария: слоты, классификация, ReAct-планирование, инструменты, решение/эскалация.
- Добавить матрицу запуска инструментов с привязкой к слотам, сценарию, endpoint profile, уровню риска, текущему уровню согласования и целевому уровню автоисполнения.
- Перевести промпты из свободного каталога в prompt pack с обязательными блоками system prompt.
- Выполнить эти изменения до любых следующих расширений консоли администратора, observability, Vault, MFA, live n8n management и multi-model routing.

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

- Каталог источников знаний для local files, corporate wiki, ServiceDesk KB, CMDB exports, Git repositories и будущих API-источников.
- Интерфейс connector для загрузки источников.
- Реализованный connector `local_files` для `.md` и `.txt` документов разработки.
- Отключенные/config-ready skeletons для remote sources, например corporate wiki.
- Нормализованный контракт документа, общий для всех источников.
- Chunking job и локальный лексический индекс для CPU-only разработки.
- pgvector-backed retrieval как целевой backend за тем же интерфейсом retriever, не жесткая зависимость локальной разработки.
- Действие перестроения базы знаний, запускаемое оператором, с manifest, status, counts, errors и timestamps.
- Retriever node в LangGraph/FastAPI workflow, использующий последний успешный индекс.
- Ссылки на источники в ответе оператору.

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

Цель: ввести durable case lifecycle boundary перед усилением безопасности пилотного контура.

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

### Этап 10.5: основа Admin API и операции оценки

Цель: создать backend-основу административной плоскости до полноценной React-консоли администратора и завершить отложенный на этапе 9 evaluation loop поверх durable case lifecycle.

Поставки:

- Пространство Admin API, например `/admin/*`, без обхода существующих доменных API.
- Endpoint'ы панели обзора только для чтения:
  - счетчики по кейсам;
  - ожидающие согласования;
  - ошибки инструментов и интеграций;
  - статус индекса RAG;
  - статус LiteLLM/model backend;
  - счетчики обратной связи.
- Административные endpoint'ы базы знаний:
  - просмотр каталога источников;
  - действие перестроения;
  - манифест индекса;
  - просмотр фрагментов;
  - тестовый поиск.
- Endpoint'ы инвентаризации каталогов:
  - инструменты;
  - точки интеграции;
  - состояния workflow и правила переходов;
  - конфигурация маршрутизации моделей.
- Реализация evaluation runner с существующими контрактами обратной связи:
  - `evaluation-run`.
  - `evaluation-result`.
- Процесс переноса raw feedback records в подготовленный набор оценочных кейсов.
- Захват метаданных версии:
  - model.
  - prompt/config.
  - knowledge index.
  - tool registry/config.
- Идемпотентность обратной связи и поиск дублей.
- Ссылки timeline кейса на события обратной связи и оценки.

Архитектурные решения:

- Admin API сначала работает в режимах только для чтения или safe-action-first; изменение конфигурации идет позже через draft/validate/activate.
- CaseStore и case timeline являются durable source для snapshots; raw feedback этапа 9 остается import/export input.
- Запуски оценки по умолчанию используют dry-run, mock или явно sandboxed execution policy и не запускают реальные внешние действия.
- Подготовленные оценочные кейсы отделены от raw feedback, чтобы шумные заметки оператора не становились регрессионными проверками автоматически.
- Административные действия уже пишут actor/version metadata, даже если полноценный RBAC и усиление аудита завершаются на этапе 11.

Критерии выхода:

- Admin API дает безопасный обзор платформы без прямого изменения business state кейса.
- Перестроение базы знаний и тестовый поиск доступны как административные действия.
- Подготовленный набор оценочных кейсов можно повторно запускать против текущего workflow.
- Результаты оценки показывают pass/fail status и differences для изменений модели, промпта, RAG и инструментов.
- События обратной связи и оценки видимы в timeline кейса.

### Этап 11: RBAC, аудит и основа безопасности

Цель: закрыть административные и операторские действия permission checks, audit log и базовой безопасностью до полноценной консоли администратора.

Поставки:

- Пользователи, роли и права.
- Начальные роли:
  - `admin`;
  - `operator`;
  - `support_l1`;
  - `support_l2`;
  - `readonly`.
- Модель прав:
  - `cases.read`;
  - `cases.operate`;
  - `approvals.decide`;
  - `callbacks.write`;
  - `feedback.write`;
  - `knowledge.read`;
  - `knowledge.manage`;
  - `tools.read`;
  - `tools.manage`;
  - `prompts.read`;
  - `prompts.manage`;
  - `workflow.read`;
  - `workflow.manage`;
  - `models.read`;
  - `models.manage`;
  - `evaluation.run`;
  - `audit.read`;
  - `security.manage`.
- Audit log для:
  - действий оператора;
  - действий администратора;
  - вызова инструментов;
  - решений по согласованиям;
  - обработки callback;
  - изменений конфигурации.
- Ссылки на секреты:
  - API-ключи;
  - webhook-секреты;
  - ссылки на учетные данные интеграций;
  - будущая интеграция с Vault.
- Управление сессиями.
- Лимиты запросов.
- Совместимость с существующим `/healthz`.

Архитектурные решения:

- RBAC применяется на Admin API и Operator API.
- Audit log пишет факт действия и actor, но не сохраняет секретные значения.
- Управление секретами хранит ссылки, а не секреты в plain config.
- Action tools не могут обходить approvals даже при наличии admin role.
- Callback endpoint'ы требуют token и пишут audit events.
- На этапе 11 используется dev-header auth; production identity provider, MFA, Vault и IP restrictions остаются следующими шагами.

Критерии выхода:

- Все опасные operator/admin действия требуют permission.
- Активность оператора, администратора и интеграций трассируема.
- Callback endpoints защищены и auditable.
- Case lifecycle changes attributable.

### Этап 12: MVP React-консоли администратора

Цель: дать администратору отдельную консоль управления платформой поверх Admin API.

Поставки:

- Консоль администратора на `/admin`.
- Статический MVP, обслуживаемый backend, без npm-зависимостей для текущего локального контура.
- Целевая миграция интерфейса на React/TypeScript/Vite/Ant Design поверх тех же Admin API.
- Frontend-стек:
  - React.
  - TypeScript.
  - Vite.
  - Ant Design.
  - React Query.
  - React Router.
- Раздел "Панель обзора":
  - количество обращений;
  - auto-resolve;
  - escalation;
  - ожидающие согласования;
  - ошибки интеграций;
  - состояние LLM;
  - состояние индексации RAG;
  - использование инструментов.
- Раздел "База знаний / RAG":
  - источники;
  - перестроение индекса;
  - манифест;
  - фрагменты;
  - тестовый поиск;
  - заметки о качестве поиска.
- Раздел "Инструменты и интеграции":
  - просмотр каталога инструментов;
  - просмотр каталога точек интеграции;
  - привязки endpoint;
  - таймауты, повторы и уровень риска;
  - тестовый запуск в sandbox;
  - история вызовов инструментов.
- Раздел "Модели":
  - реальная настройка подключений LiteLLM;
  - профиль `vLLM CPU` для локальной CPU-разработки через OpenAI-compatible endpoint;
  - профиль `OpenAI API` с реальной моделью и token только через переменную окружения/секрет;
  - создание, модификация и удаление пользовательских подключений LiteLLM;
  - поддержка provider-prefixed model в alias для подключений без отдельной записи в `litellm.yaml`;
  - стабильное хранение настроек каждого подключения отдельно от активного выбора;
  - быстрое переключение между подключениями без повторного ввода параметров;
  - выбор активного подключения;
  - alias модели по умолчанию;
  - ввод значения секрета без последующего отображения: `параметр скрыт` при наличии и `параметр не заполнен` при отсутствии;
  - маршрутизация задач: ответы, классификация, суммаризация, выбор инструментов, разрешение атрибутов;
  - fallback между подключениями;
  - context length, temperature, max tokens, timeout и rate limits.
- Раздел "Контроль качества":
  - список обратной связи;
  - подготовленный набор оценочных кейсов;
  - статус запусков оценки;
  - сводка регрессии.
- Раздел "Аудит":
  - действия администратора;
  - действия оператора;
  - вызовы инструментов;
  - события workflow;
  - ошибки.
- Раздел "Безопасность":
  - пользователи;
  - роли;
  - права;
  - ссылки на API-ключи;
  - ссылки на webhook-секреты.

Архитектурные решения:

- Консоль администратора использует только Admin API и не обращается напрямую к хранилищу.
- Любой тестовый запуск инструмента использует `mock`, `dry_run` или явно sandboxed endpoint.
- Редактирование production-конфигурации не выполняется прямой записью; используется draft/validate/activate.
- Управление workflow n8n является частью интеграций, а не отдельным владельцем business state.

Критерии выхода:

- Администратор может наблюдать состояние платформы и запускать безопасные административные действия.
- Перестроение базы знаний и тестовый поиск доступны из консоли администратора.
- Инструменты, endpoints, промпты, модели, качество и аудит доступны минимум в режиме только для чтения или безопасного действия.
- Операторский интерфейс и консоль администратора разделены по маршрутам, ролям и permissions.

### Этап 12.5: сценарная модель оркестратора и связная консоль администратора

Цель: устранить разрозненность консоли администратора и сделать основной единицей управления сценарий обработки обращения, проходящий через пять шагов оркестратора.

Этот этап выполняется раньше всех остальных расширений административной консоли: observability, Vault, MFA, live n8n management, multi-model routing и прочие улучшения не начинаются, пока сценарная модель не закреплена контрактами и UI.

Поставки:

- Новые домены конфигурации в Config Registry:
  - `service_scenarios`;
  - `slot_schemas`;
  - `classification_routes`;
  - `orchestrator_policy`;
  - `tool_launch_matrix`;
  - `prompt_packs`;
  - `escalation_policies`.
- JSON Schema для каждого нового домена; схемы остаются источником истины для Python backend через `jsonschema`.
- Главный раздел консоли администратора "Сценарии обработки -> Сценарии":
  - выбор сценария обращений через выпадающее меню;
  - операции "Создать", "Модифицировать", "Удалить";
  - поля редактирования для создания и модификации сценария;
  - выбор подготовленных блоков `0-5` через выпадающие поля: профиль разрешения атрибутов выбирается в схеме слотов, сам сценарий выбирает схему слотов, маршрут, ReAct-политику, матрицу инструментов, пакет промптов и политику эскалации;
  - статус готовности сценария;
  - связанные слоты, маршруты, инструменты, prompt pack и escalation policy;
  - предупреждения о неполных или несогласованных связях.
- Отдельные подпункты меню с сохраненными номерами шагов оркестратора:
  - "0. Разрешение атрибутов";
  - "1. Слоты";
  - "2. Классификация и маршрут";
  - "3. ReAct-планирование";
  - "4. Инструменты и матрица запуска";
  - "5. Решение и эскалация";
  - "6. Промпты".
- Подпункты `0-5` являются самостоятельными каталогами подготовленных блоков:
  - в самих блоках нет управляемой связи со сценариями;
  - у каждого блока есть поле "Название";
  - доступны операции "Создать", "Модифицировать", "Удалить";
  - блок "Где используется" показывает сценарии, которые выбрали этот блок;
  - удаление запрещено, пока блок используется сценарием или схемой слотов.
- Шаг 1, слоты:
  - добавление, изменение и удаление отдельных слотов через форму;
  - существующие слоты в интерфейсе свернуты по умолчанию, кнопка удаления находится справа в строке слота, новый слот раскрывается после добавления;
  - технические идентификаторы сценария, схемы слотов, маршрута, политик, запусков инструментов и prompt pack не выводятся как поля управления, но сохраняются в payload для связей, логов и audit trail;
  - пояснения под основными полями слота, чтобы администратор понимал смысл `slot_id`, `display_name`, `priority_group`, `required`, `fill_method`, `resolution_profile_id`, `question` и `auto_fill_ref`;
  - без ручного JSON-редактора для состава слотов;
  - required slots;
  - auto-fill slots;
  - порядок вопросов;
  - приоритет "кто -> что -> когда";
  - timeout 3 минуты для напоминания;
  - timeout 8 минут для черновика заявки и сохранения контекста;
  - выбор готового профиля разрешения атрибута из каталога `0. Разрешение атрибутов`.
- Шаг 2, классификация и маршрут:
  - правила и ключевые слова;
  - LLM few-shot fallback;
  - пороги confidence;
  - маршрут на автоагента, Л1, Л2, approver или Major Incident;
  - матрица "категория -> приоритет -> маршрут -> действие".
- Шаг 3, ReAct-планирование:
  - лимит итераций;
  - правило двух ошибок инструментов подряд;
  - стоп-условия;
  - разрешенные классы инструментов для сценария;
  - связь с workflow states и transition rules.
- Шаг 4, инструменты:
  - матрица запуска инструментов с привязкой к сценарию и слотам;
  - `required_slots` для каждого запуска;
  - `parameter_bindings` из slot/constant/secret/case/context;
  - `execution_level` для текущего режима MVP;
  - `target_execution_level` для будущего автоисполнения;
  - роль согласования;
  - endpoint profile;
  - risk level;
  - audit/log флаги;
  - stop-on-error политика.
- Шаг 5, решение и эскалация:
  - условия автозакрытия;
  - режим ожидания ответа пользователя;
  - правила остановки SLA;
  - автозакрытие через 24 часа;
  - эскалация на Л2;
  - Major Incident threshold;
  - состав escalation package.
- Раздел консоли администратора "Сценарии обработки -> 6. Промпты":
  - выбор пакета промптов через выпадающее меню;
  - операции "Создать", "Модифицировать", "Удалить";
  - редактирование блока "Пакет промптов: обязательные блоки";
  - защита от удаления пакета, если активный сценарий продолжает на него ссылаться.
- Prompt pack вместо свободного списка промптов:
  - `role_context`;
  - `behavior_principles`;
  - `slot_schemas`;
  - `classification_confidence`;
  - `react_planning`;
  - `tool_rules`;
  - `escalation_response`.
- Preview итогового system prompt доступен на уровне API и отладочных данных, но не дублируется как отдельный блок в основном UI.
- Отдельный preview системного промпта не нужен в основном UI, если обязательные блоки prompt pack уже показаны как редактируемый шаблон в меню "Сценарии обработки -> 6. Промпты".
- Переработанная панель оператора:
  - одно неструктурированное поле текста заявки вместо прежней формы с фиксированными полями;
  - выбор сценария обработки;
  - галочка "Тестовый прогон сценария" для dry-run проверки слотов, классификации и доступных инструментов;
  - раскрытая карта пяти шагов оркестратора для выбранного сценария;
  - вопросы обогащения заявки по одному недостающему слоту;
  - отображение текущей готовности инструментов по матрице запуска и привязке к слотам;
  - сохранение действующих операторских функций: анализ, согласование action tools, feedback, RAG/tool trace и timeline кейса.

Архитектурные решения:

- `service_scenarios` становится верхним уровнем управления, а текущие `tools`, `integration_endpoints`, `workflow_states`, `workflow_transitions`, `prompts`, `model_routing` и `n8n_workflows` становятся связанными нижнеуровневыми справочниками.
- `service_scenarios` собирает сценарий из независимых блоков: сами `slot_schemas`, `classification_routes`, `orchestrator_policy`, `tool_launch_matrix` и `escalation_policies` не содержат управляемой ссылки на сценарий.
- Матрица запуска инструментов строже каталога инструментов: инструмент нельзя предложить к запуску в сценарии, если не заполнены required slots или нет корректного parameter binding.
- `execution_level` отражает текущую политику исполнения, а `target_execution_level` фиксирует целевую схему автоисполнения; это позволяет включать автоисполнение позже без смены контрактов.
- Prompt pack не редактируется как один свободный system prompt; UI обязан разделять его на семь обязательных блоков в меню "Сценарии обработки -> 6. Промпты".
- Блоки prompt pack, зависящие от слотов, классификации, ReAct и tools, должны собираться из структурированной конфигурации, чтобы промпты не расходились с реальным поведением backend.
- Все изменения проходят через существующий процесс draft/validate/regression/activate.
- В разделе "Сценарии обработки -> Сценарии" не используется отдельная таблица "Карта сценариев", если доступен выпадающий выбор сценария.
- Каждый из пяти шагов сценария редактируется через свой домен Config Registry, а не через ручную правку JSON в разделе общей конфигурации.
- Операторская панель читает сценарную модель через отдельные operator endpoint'ы с правом `cases.operate`; ей не требуются административные permissions.

Валидации перед активацией:

- Каждый сценарий имеет slot schema.
- Каждый required slot либо задается вопросом, либо имеет auto-fill источник.
- Порядок вопросов не нарушает приоритет "кто -> что -> когда".
- Каждый route ссылается на допустимое состояние workflow и выбирается сценарием через `classification_route_id`.
- Каждая матрица инструментов выбирается сценарием через `tool_launch_matrix_id`.
- Каждый tool launch binding ссылается на существующий tool, endpoint profile и operation.
- Каждый параметр запуска инструмента имеет binding на slot, constant, secret, case или context.
- `execution_level=auto` запрещен для blocked/high-risk действий без явного разрешения policy.
- `target_execution_level=auto` разрешен как целевое состояние, но не меняет поведение MVP без отдельной активации.
- Каждый prompt pack содержит все семь обязательных блоков.
- Escalation package содержит слоты, историю ReAct, результаты инструментов, гипотезу причины, остаток SLA и текст уведомления пользователя.
- Major Incident threshold задан явно для сценариев, где возможен массовый инцидент.

Критерии выхода:

- Администратор видит сценарий как связную карту: слоты, классификация, ReAct, инструменты, решение и эскалация.
- Оператор видит тот же сценарий как рабочую карту обработки заявки и может обогащать обращение вопросами по слотам до запуска анализа.
- Нельзя активировать сценарий с неполной матрицей слотов, tool bindings или prompt pack.
- В операторском UI можно включить тестовый прогон сценария без реального вызова внешних систем.
- Текущий MVP остается с подтверждением оператора для action tools, но в конфигурации уже видны целевые места будущего автоисполнения.
- Разрозненные разделы tools/prompts/workflow остаются доступными, но перестают быть основным способом настройки поведения AI.

### Этап 12.6: профили разрешения атрибутов для заполнения слотов

Цель: заменить простое поле "Источник" в слоте на расширяемую модель "атрибут -> правило заполнения", где схема слотов выбирает готовое правило, а сами правила управляются в отдельном разделе консоли администратора.

Поставки:

- Новый домен Config Registry `attribute_resolution_profiles`.
- JSON Schema для профилей разрешения атрибутов; схема остается источником истины для Python backend через `jsonschema`.
- Новый пункт меню консоли администратора "Сценарии обработки -> 0. Разрешение атрибутов".
- Операции в меню "Сценарии обработки -> 0. Разрешение атрибутов":
  - "Создать";
  - "Модифицировать";
  - "Удалить".
- UI-обвязка CRUD:
  - выбор профиля из выпадающего списка;
  - форма создания профиля;
  - форма модификации профиля;
  - редактирование шагов профиля через раскрывающиеся карточки с полями, без JSON textarea;
  - форма удаления с подтверждением;
  - общий процесс draft/validate/regression/activate;
  - audit event для каждой операции.
- Структура профиля разрешения атрибута:
  - название;
  - статус;
  - целевой атрибут/слот;
  - входные атрибуты/слоты;
  - выходные атрибуты/слоты;
  - упорядоченные шаги заполнения;
  - условия переходов между шагами;
  - правила уточняющих вопросов;
  - лимит попыток уточнения;
  - confidence threshold;
  - fallback: спросить пользователя, передать оператору, эскалировать или оставить незаполненным;
  - audit/log флаги.
- Типы шагов профиля:
  - извлечение из текста через LLM;
  - чтение из текущего кейса;
  - вызов инструмента;
  - поиск по истории закрытых заявок;
  - условие;
  - уточняющий вопрос;
  - заполнение слота;
  - остановка с эскалацией.
- Пример профиля "Поиск логина в AD по ФИО":
  - извлечь фамилию, имя и отчество из текста обращения;
  - вызвать поиск пользователя в AD;
  - если найден один пользователь, заполнить `login_name`;
  - если найдено несколько совпадений, запросить должность, подразделение или табельный номер;
  - повторить поиск с уточнением;
  - если результат неоднозначен после лимита попыток, передать оператору.
- Профиль истории заявок как отдельная настройка:
  - статусы заявок;
  - период;
  - минимальная оценка качества;
  - similarity threshold;
  - разрешенные поля;
  - исключенные категории.
- Интеграция с инструментами:
  - tool остается runtime-сущностью исполнения;
  - профиль разрешения атрибута ссылается на конкретные tool operations только внутри шагов;
  - сценарий не группирует инструменты вручную и не показывает полный каталог tools для заполнения слота.
- Изменение редактора слотов в разделе "Сценарии":
  - убрать прямой выбор "Источник" как основную настройку;
  - добавить "Способ заполнения": вопрос пользователю, текущий кейс, LLM extraction, профиль разрешения атрибута, ручное заполнение оператором;
  - если выбран профиль, показывать только выпадающий список профилей, которые могут выдавать целевой слот;
  - показывать read-only сводку профиля: входы, выходы, fallback, audit и требуемые уточнения.
- Изменение операторской панели:
  - при недостающем слоте показывать следующий шаг профиля разрешения атрибута;
  - если профиль требует уточнение, оператор видит конкретный вопрос и варианты уточняемых полей;
  - оператор не выбирает tool вручную для заполнения атрибута.

Архитектурные решения:

- Slot filling не является свободным ReAct loop; для заполнения атрибутов используется детерминированный ordered pipeline с условиями.
- Tools не удаляются из архитектуры: они остаются исполняемыми адаптерами, но не являются основной сущностью настройки слота.
- `case` и `llm_extraction` считаются встроенными способами заполнения; AD, CMDB, IAM, история заявок и внешние системы подключаются через профили разрешения атрибутов.
- История заявок не используется глобально: каждый профиль явно задает, какие заявки и поля допустимы.
- Профили разрешения атрибутов не владеют business state кейса; результат заполнения проходит через Case API и workflow state.
- Сценарий остается компактным: он выбирает схему слотов, а схема слотов выбирает готовые правила заполнения без описания endpoint, retry, tool execution и фильтров истории внутри сценария.

Валидации перед активацией:

- Каждый профиль имеет уникальный технический ключ, но ключ не выводится как поле управления в UI.
- Слот может ссылаться только на существующий профиль, который выдает этот слот как output.
- Профиль может объявлять дополнительные `output_slots`, которые не входят в конкретную схему слотов; такие выходы считаются возможностями профиля и не блокируют сохранение схемы.
- Каждый step с типом tool call ссылается на существующий tool, endpoint profile и operation.
- Каждый step использует только объявленные входные и выходные атрибуты.
- Clarification step содержит вопрос и список уточняемых атрибутов.
- History step содержит фильтры статусов, качества, периода и разрешенных полей.
- Fallback задан явно для каждого неоднозначного или неуспешного пути.
- Нельзя активировать слот, который ссылается на профиль, не выдающий именно этот слот как output.

Критерии выхода:

- В консоли администратора есть отдельный раздел "0. Разрешение атрибутов" с операциями создать, модифицировать и удалить.
- В разделе "0. Разрешение атрибутов" нет сводной таблицы профилей и JSON-редактора шагов; поведение профиля настраивается формовыми полями.
- В сценариях слот выбирает готовый профиль разрешения атрибута, а не технический источник данных.
- Для сценария сброса пароля можно описать pipeline поиска `login_name` через LLM extraction, AD lookup и уточняющий вопрос при неоднозначности.
- История заявок используется только через явно настроенный профиль.
- UI и backend не содержат hardcoded списка источников слота.
- Тестовый прогон сценария показывает шаги разрешения атрибутов и вопросы уточнения без реального вызова внешних систем.

### Этап 12.7: разрешение слота как mini-workflow

Цель: уточнить модель `0. Разрешение атрибутов`, чтобы профиль заполнения слота был не линейным списком источников, а управляемым mini-workflow с несколькими попытками, промежуточными атрибутами, ветвлением по неоднозначности и передачей Л1.

Поставки:

- Расширение JSON Schema профилей разрешения атрибутов:
  - режим выполнения `resolution_mode`;
  - область лимита попыток `attempt_scope`;
  - промежуточные атрибуты `intermediate_attributes`;
  - отдельные пороги `confidence_thresholds`;
  - политика неоднозначности `ambiguity_policy`;
  - пакет передачи Л1 `operator_handoff_package`;
  - переход шага `on_ambiguous_step`;
  - условие неоднозначности `ambiguity_condition`.
- Новые типы шагов:
  - `rag_search`;
  - `operator_handoff`.
- Переработка default-профиля сброса пароля:
  - извлечение логина, ФИО и контактов из текста;
  - поиск подсказок в RAG/истории;
  - проверка найденного логина в AD;
  - поиск по ФИО;
  - проверка единственного кандидата;
  - уточнение должности, подразделения или табельного номера;
  - повторная попытка поиска;
  - заполнение `user_login`;
  - передача Л1 с пакетом контекста при неоднозначности.
- Backend dry-run возвращает `resolution_state` по каждому слоту:
  - текущий шаг;
  - выполненные шаги;
  - номер попытки;
  - следующий вопрос;
  - причина неоднозначности;
  - пакет передачи Л1.
- Admin UI в `Сценарии обработки -> 0. Разрешение атрибутов` показывает настройки mini-workflow без JSON-редактора.
- Operator UI в шаге `1. Приём и нормализация` показывает оператору ход разрешения слота, вопрос и следующий ожидаемый шаг.

Архитектурные решения:

- Слот остается бизнес-атрибутом. Профиль разрешения описывает, как получить значение слота.
- Промежуточные атрибуты профиля не обязаны быть слотами сценария.
- Неоднозначность результата отделяется от технической ошибки инструмента.
- Tools остаются runtime-адаптерами внутри шагов профиля и не становятся основной сущностью настройки слота.
- Передача Л1 получает не только исходный текст заявки, но и состояние mini-workflow разрешения атрибута.

Валидации перед активацией:

- `on_success_step`, `on_failure_step` и `on_ambiguous_step` ссылаются на существующие шаги.
- Каждый input/output шага объявлен как входной слот, выходной слот или промежуточный атрибут профиля.
- `from_attribute` шага заполнения ссылается на объявленный атрибут.
- `ambiguity_policy` с действием уточнения содержит вопрос и уточняемые атрибуты.
- Пороги confidence идут от строгого автозаполнения к более мягкой передаче Л1.
- `operator_handoff` имеет пакет передачи Л1.

Критерии выхода:

- Профиль `Поиск логина в AD по ФИО` описывает несколько попыток разрешения `user_login`.
- Dry-run показывает текущий шаг, вопрос и пакет Л1 для недостающего слота.
- Админский UI позволяет настроить неоднозначность и переходы без ручной правки JSON.
- Операторский UI показывает, почему задан вопрос и какой шаг будет следующим.

### Этап 13: расширенное управление платформой

Цель: после завершения сценарной модели и профилей разрешения атрибутов превратить консоль администратора из обзорной консоли в управляемый контур изменения конфигурации AI-платформы.

Поставки:

- Процесс draft/validate/activate для:
  - инструментов;
  - точек интеграции;
  - состояний рабочего процесса;
  - правил переходов;
  - промптов;
  - маршрутизации моделей;
  - каталога workflow n8n.
- Валидация по JSON Schema как обязательная проверка перед активацией.
- Регрессионные проверки перед активацией конфигурации промптов, инструментов и workflow.
- Оценка промптов и качества поиска.
- Расширенные операции workflow n8n:
  - регистрация;
  - связь workflow с бизнес-сценарием;
  - конфигурация callback;
  - история запусков;
  - restart/cancel для поддерживаемых workflow.
- Маршрутизация нескольких моделей:
  - сценарий -> модель;
  - цепочки fallback;
  - лимиты запросов;
  - длина контекста;
  - настройки temperature.
- Интеграция с Vault.
- IP-ограничения.
- Поддержка MFA.
- Расширенная наблюдаемость:
  - LangGraph tracing;
  - структурированные логи;
  - расход токенов;
  - задержка;
  - SLA metrics;
  - аналитика ошибок интеграций.
- Процедура backup/restore для PostgreSQL и будущих persistent stores.

Архитектурные решения:

- Любая активация создает событие аудита и неизменяемую версию конфигурации.
- Регрессионные проверки могут блокировать активацию.
- Пустой подготовленный набор оценочных кейсов допускает bootstrap-активацию только со статусом gate `skipped`.
- Продуктовые действия по-прежнему проходят через Case API, Tool Registry и Execution Policy.
- n8n выполняет integrations, timers и polling, но не владеет business state кейса.
- Реальные n8n restart/cancel требуют n8n management API; до этого операции остаются guarded/unsupported.

Критерии выхода:

- Администратор может безопасно менять поведение AI, RAG, инструменты, workflow и model routing через версионированный процесс.
- Версии конфигурации можно откатить.
- Перед изменением production-поведения можно запустить evaluation/regression suite.
- Безопасность и наблюдаемость достаточны для пилотной эксплуатации.

### Этап 14: переоценка реестра промптов как библиотеки шаблонов

Цель: если система развивается дальше одного сценарного prompt pack, переосмыслить низкоуровневый домен `prompts` не как отдельный раздел настройки поведения агента, а как библиотеку переиспользуемых шаблонов промптов.

Поставки:

- Решение, нужен ли отдельный каталог шаблонов поверх `prompt_packs`.
- Модель "шаблон промпта -> где используется":
  - prompt pack;
  - сценарий;
  - тип блока system prompt;
  - evaluation/regression set.
- CRUD для шаблонов только при подтвержденной потребности переиспользования.
- Versioning шаблонов и безопасный rollback.
- Проверка, что изменение шаблона не меняет поведение сценариев без явного draft/validate/regression/activate.
- UI-название "Библиотека шаблонов промптов", если раздел будет возвращен в интерфейс.

Архитектурные решения:

- Основной UI настройки поведения AI остается в `Сценарии обработки -> 6. Промпты`.
- Библиотека шаблонов не должна конкурировать с prompt pack и не должна быть вторым местом изменения сценарного system prompt.
- Шаблон может быть только источником переиспользуемого текста или фрагмента, а фактическая активная конфигурация сценария фиксируется в prompt pack.

Критерии выхода:

- Принято решение: удалить низкоуровневый `prompts` из пользовательской плоскости окончательно или вернуть его как библиотеку шаблонов.
- Если библиотека нужна, администратор видит связи "где используется" и не может удалить шаблон, пока он используется.
- Если библиотека не нужна, сценарная модель остается единственным UI для промптов.
