# Этап 10.5: основа Admin API и операции оценки

Этап 10.5 создает backend-основу административной плоскости до полноценной React-консоли администратора и завершает отложенный на этапе 9 цикл оценки поверх долговечного жизненного цикла кейса.

## Базовые решения

- Admin API живет в отдельном пространстве, например `/admin/*`.
- Admin API не обходит Case API, Tool Registry, Execution Policy или Integration Dispatcher.
- Первые endpoint'ы должны быть только для чтения или безопасными действиями.
- Изменение production-конфигурации позже идет через draft/validate/activate.
- Запуски оценки по умолчанию используют dry-run, mock или sandboxed execution policy.
- Реальные внешние действия не запускаются при оценке.
- Административные действия уже пишут actor/version metadata для будущей интеграции с аудитом.

## Плановые работы

- Добавить endpoint'ы панели обзора только для чтения:
  - счетчики по кейсам.
  - ожидающие согласования.
  - ошибки инструментов и интеграций.
  - статус индекса RAG.
  - статус LiteLLM/model backend.
  - счетчики обратной связи.
- Добавить административные endpoint'ы базы знаний:
  - просмотр каталога источников.
  - действие перестроения.
  - манифест индекса.
  - просмотр фрагментов.
  - тестовый поиск.
- Добавить endpoint'ы инвентаризации каталогов:
  - инструменты.
  - точки интеграции.
  - состояния workflow и правила переходов.
  - конфигурация маршрутизации моделей.
- Реализовать evaluation runner с:
  - `contracts/feedback/evaluation-run.schema.json`
  - `contracts/feedback/evaluation-result.schema.json`
- Добавить процесс переноса raw feedback records в подготовленные оценочные кейсы.
- Сохранять метаданные версии:
  - модель.
  - промпт/config.
  - индекс базы знаний.
  - tool registry/config.
- Добавить идемпотентность и поиск дублей для обратной связи.
- Связать события обратной связи и оценки с timeline кейса.

## API

- `GET /admin/dashboard`
- `GET /admin/knowledge/status`
- `GET /admin/knowledge/sources`
- `POST /admin/knowledge/rebuild`
- `GET /admin/knowledge/chunks`
- `POST /admin/knowledge/retrieval/test`
- `GET /admin/catalog`
- `GET /admin/catalog/tools`
- `GET /admin/catalog/integration-endpoints`
- `GET /admin/catalog/workflow`
- `GET /admin/models/config`
- `POST /admin/evaluations/promote-feedback`
- `GET /admin/evaluations/cases`
- `POST /admin/evaluations/run`
- `GET /admin/evaluations/runs/{run_id}`

## Команды

Запустить проверки:

```bash
PYTHON=.venv/bin/python make stage10_5-check
```

Запустить smoke-проверку этапа 10.5:

```bash
./scripts/stage10_5-smoke.sh
```

## Критерии выхода

- Admin API дает безопасный обзор платформы без прямого изменения business state кейса.
- Перестроение базы знаний и тестовый поиск доступны как административные действия.
- Подготовленный набор оценочных кейсов можно повторно запускать против текущего workflow.
- Результаты оценки показывают статус pass/fail и полезные различия для изменений модели, промпта, RAG и инструментов.
- События обратной связи и оценки видимы в timeline кейса.
- Существующие smoke-проверки этапов 3-10 продолжают проходить.
