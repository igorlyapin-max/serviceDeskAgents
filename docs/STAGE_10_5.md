# Этап 10.5: evaluation runner и операции обратной связи

Этап 10.5 завершает отложенный на этапе 9 цикл оценки после того, как этап 10 вводит долговечные кейсы, timeline и обработку callback.

## Scope

Этап 9 собирает обратную связь и экспортирует JSONL evaluation cases. Этап 10.5 превращает эти данные в операционный цикл качества.

## Базовые решения

- Записи кейсов и timelines являются долговечным источником snapshots.
- Сырая обратная связь не становится regression gate автоматически; выбранные записи продвигаются в curated evaluation set.
- Evaluation runs по умолчанию используют dry-run, mock или sandboxed execution policy.
- Реальные external actions не запускаются в evaluation runs, если оператор явно не включил безопасный test endpoint.
- RBAC и полный аудит остаются в этапе 11, но evaluation records должны хранить ссылки на actor, case и version.

## Плановые работы

- Реализовать evaluation runner с:
  - `contracts/feedback/evaluation-run.schema.json`
  - `contracts/feedback/evaluation-result.schema.json`
- Добавить CLI или API entrypoint для запуска curated evaluation sets.
- Добавить продвижение записей обратной связи в curated evaluation cases.
- Добавить историю обратной связи и controls экспорта или скачивания в Operator UI.
- Добавить базовую quality analytics:
  - rating distribution.
  - corrected-response rate.
  - regression pass/fail summary.
- Сохранять version metadata:
  - model.
  - prompt/config.
  - индекс базы знаний.
  - tool registry/config.
- Добавить идемпотентность и поиск дублей для отправки обратной связи.
- Связать события обратной связи и оценки с case timeline.

## Критерии выхода

- Curated evaluation set можно повторно запускать против текущего workflow.
- Evaluation results показывают статус pass/fail и полезные различия для изменений модели, prompt, RAG и инструментов.
- Операторы могут смотреть историю обратной связи из UI.
- События обратной связи и оценки видимы в case timeline.
- Существующие smoke-проверки этапов 3-10 продолжают проходить.
