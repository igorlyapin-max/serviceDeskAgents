# Этап 13: расширенное управление платформой

Этап 13 превращает консоль администратора из обзорной консоли в управляемый контур изменения конфигурации AI-платформы.

## Реализовано

- Реестр конфигурации с состояниями черновиков, версий и активной версии в SQLite.
- Процесс `draft/validate/regression/activate` для доменов:
  - `service_scenarios`;
  - `slot_schemas`;
  - `classification_routes`;
  - `orchestrator_policy`;
  - `tool_launch_matrix`;
  - `prompt_packs`;
  - `escalation_policies`;
  - `attribute_resolution_profiles`;
  - `tools`;
  - `integration_endpoints`;
  - `workflow_states`;
  - `workflow_transitions`;
  - `prompts`;
  - `model_routing`;
  - `n8n_workflows`;
  - `interaction_channels`.
- Неизменяемые версии конфигурации.
- Откат указателя активной версии на ранее активированную версию.
- Валидация по JSON Schema перед активацией.
- Регрессионная проверка перед активацией:
  - `skipped`, если подготовленный набор оценочных кейсов пуст;
  - `passed`, если запуск оценки не дал упавших кейсов;
  - `failed`, если валидация или оценочная проверка не прошли.
- События аудита для:
  - создания черновика;
  - валидации черновика;
  - проверки регрессии;
  - активации черновика;
  - отката версии.
- Ручной раздел консоли администратора `Изменения конфигурации` убран из UI: правка JSON payload вручную слишком рискованна и заменяется предметными формами.
- Каталог workflow n8n:
  - регистрация;
  - связь workflow с бизнес-сценарием;
  - ссылка на callback endpoint;
  - флаги управления.
- Каналы взаимодействия:
  - мессенджер-бот для онлайн-диалога с пользователем;
  - сервисдеск для офлайн-обсуждения и создания наряда;
  - отладочный режим для локального MVP;
  - доставка вопросов, таймауты ожидания, действие при отсутствии ответа и действие эскалации;
  - профили действий канала для обычной передачи, отсутствия ответа, Major Incident и policy blocked;
  - блок `5. Решение и эскалация` задает только условия решения, а профиль действия выбирается автоматически по `event_type` канала.
- Блок `5. Решение и эскалация`:
  - условия передачи выбираются чекбоксами в `handoff_conditions`;
  - состав пакета передачи выбирается чекбоксами в `handoff_package`;
  - старые поля `l2_conditions` и `escalation_package` не поддерживаются.
- Блок `3. ReAct-планирование`:
  - группы действий выбираются чекбоксами в `allowed_react_action_groups`;
  - стоп-условия выбираются чекбоксами в `stop_conditions`;
  - старое поле `allowed_tool_classes` не поддерживается.
- Защитные endpoint'ы для n8n restart/cancel без реального исполнения в локальном MVP.
- Раздел `Модели` переделан в реальную форму настройки:
  - активное подключение LiteLLM: базовые `vLLM CPU` и `OpenAI API` плюс пользовательские подключения;
  - добавление, редактирование и удаление пользовательских подключений через UI;
  - для новых подключений без отдельной записи в `litellm.yaml` alias может быть provider-prefixed model, например `openai/gpt-4.1-mini`;
  - стабильные профили подключений, параметры которых сохраняются независимо от активного выбора;
  - быстрое переключение кнопкой `Сделать активным` без потери настроек остальных профилей;
  - endpoint, alias, имя модели, context length, temperature, max tokens, timeout и rate limits;
  - OpenAI token задается только через переменную окружения, по умолчанию `OPENAI_API_KEY`;
  - значение секрета можно ввести через UI без отображения после сохранения: статус показывает только `параметр скрыт` или `параметр не заполнен`;
  - введенный через UI секрет сохраняется в локальный `.env`, применяется в текущем процессе orchestrator и требует перезапуска LiteLLM, если ключ должен попасть в уже запущенный контейнер;
  - для MVP единая точка настройки секрета - `.env` в корне репозитория, этот файл исключен из git;
  - Docker Compose передает OpenAI-настройки в LiteLLM, а локальный orchestrator сам читает root `.env` при старте;
  - пустой token и placeholder-значения не считаются настроенным ключом;
  - маршрутизация задач по alias: ответы, классификация, суммаризация, выбор инструментов и разрешение атрибутов;
  - fallback между alias.

## Новые контракты

- `contracts/config/config-draft.schema.json`.
- `contracts/config/config-version.schema.json`.
- `contracts/config/prompt-catalog.schema.json`.
- `contracts/config/model-routing.schema.json`.
- `contracts/config/n8n-workflow-catalog.schema.json`.
- `contracts/config/n8n-workflow-catalog.json`.
- `contracts/config/interaction-channels.schema.json`.

## Новые Admin API

- `GET /admin/config/domains`.
- `GET /admin/config/active/{domain}`.
- `GET /admin/config/drafts`.
- `POST /admin/config/drafts`.
- `GET /admin/config/drafts/{draft_id}`.
- `POST /admin/config/drafts/{draft_id}/validate`.
- `POST /admin/config/drafts/{draft_id}/regression`.
- `POST /admin/config/drafts/{draft_id}/activate`.
- `GET /admin/config/versions`.
- `POST /admin/config/versions/{version_id}/rollback`.
- `GET /admin/n8n/workflows`.
- `POST /admin/n8n/workflows/{workflow_id}/restart`.
- `POST /admin/n8n/workflows/{workflow_id}/cancel`.

## Модель прав

- `tools` и `integration_endpoints`: `tools.read` / `tools.manage`.
- `workflow_states` и `workflow_transitions`: `workflow.read` / `workflow.manage`.
- `prompts`: `prompts.read` / `prompts.manage`.
- `model_routing`: `models.read` / `models.manage`.
- `n8n_workflows`: `tools.read` / `tools.manage`.
- `interaction_channels`: `workflow.read` / `workflow.manage`.
- `service_scenarios`, `slot_schemas`, `classification_routes`, `orchestrator_policy`, `escalation_policies`: `workflow.read` / `workflow.manage`.
- `attribute_resolution_profiles`: `workflow.read` / `workflow.manage`.
- `tool_launch_matrix`: `tools.read` / `tools.manage`.
- `prompt_packs`: `prompts.read` / `prompts.manage`.

## Поведение во время выполнения

Активированные версии применяются в текущем процессе для:

- каталог инструментов;
- каталог точек интеграции;
- каталог состояний рабочего процесса;
- правила переходов рабочего процесса;
- каталог workflow n8n;
- каналы взаимодействия;
- представление каталога промптов;
- представление маршрутизации моделей.

Продуктовые действия по-прежнему проходят через Case API, Tool Registry, Execution Policy и Action Gate.

## Проверки

```bash
PYTHON=.venv/bin/python make stage13-check
./scripts/stage13-smoke.sh
PYTHON=.venv/bin/python make stage13_5-check
./scripts/stage13_5-smoke.sh
PYTHON=.venv/bin/python make stage13_6-check
./scripts/stage13_6-smoke.sh
PYTHON=.venv/bin/python make stage13_7-check
./scripts/stage13_7-smoke.sh
PYTHON=.venv/bin/python make stage13_8-check
./scripts/stage13_8-smoke.sh
PYTHON=.venv/bin/python make stage13_9-check
./scripts/stage13_9-smoke.sh
```

## URL

- Интерфейс администратора: `http://127.0.0.1:18088/admin`.
- Изменения конфигурации выполняются через профильные разделы консоли администратора, а не через общий JSON-редактор.

## Ограничения этапа

- Реальные n8n restart/cancel не выполняются без n8n management API; endpoint'ы возвращают guarded `unsupported`.
- Config Registry API остается внутренним механизмом для форм и smoke-проверок; прямой ручной JSON-редактор в UI не показывается.
- Vault, MFA и IP restrictions остаются целевыми расширениями безопасности.
- Регрессионная проверка использует текущий подготовленный набор оценочных кейсов; если он пуст, активация разрешена как bootstrap с явным `skipped`.
- Реестр конфигурации хранит состояние в локальном SQLite; целевое production-хранилище остается PostgreSQL.
