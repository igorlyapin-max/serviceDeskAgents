# Этап 9: обратная связь и цикл оценки

Этап 9 записывает обратную связь оператора с достаточным контекстом, чтобы превратить реальные проверки оператора в начальный набор регрессионных данных. Этап не вводит полноценный evaluation runner, RBAC, полный аудит или автоматическое обучение модели.

## Базовые решения

- Обратная связь хранится как backend-запись, а не только как состояние UI.
- Каждая запись обратной связи хранит входные данные заявки и точный snapshot анализа, который проверял оператор.
- Результаты согласований можно прикрепить как `approval_snapshot`.
- Оценка `edited` требует исправленный ответ.
- Обратную связь можно экспортировать как JSONL evaluation cases.
- Локальное MVP-хранилище использует ту же SQLite database, что и action gates.
- Полноценный evaluation runner, curated evaluation sets, история обратной связи в UI, аналитика качества и поиск дублей отложены в этап 10.5.

## Контракты

Новые контракты:

- `contracts/feedback/feedback-request.schema.json`
- `contracts/feedback/feedback-record.schema.json`
- `contracts/feedback/evaluation-case.schema.json`
- `contracts/feedback/evaluation-run.schema.json`
- `contracts/feedback/evaluation-result.schema.json`

## API

- `POST /feedback`
- `GET /tickets/{ticket_id}/feedback`
- `GET /feedback/export`

`GET /feedback/export` возвращает newline-delimited JSON evaluation cases.

## UI

Operator UI добавляет:

- `correct`
- `incorrect`
- `edited`
- заметку оператора
- исправленный ответ для `edited`
- статус сохранения обратной связи

## Команды

Запустить проверки:

```bash
PYTHON=.venv/bin/python make stage9-check
```

Запустить smoke-проверку этапа 9:

```bash
./scripts/stage9-smoke.sh
```

## Критерии выхода

- Обратную связь можно сохранить для конкретного snapshot анализа заявки.
- `edited` требует исправленный текст.
- Обратная связь может включать snapshot результатов согласований и инструментов.
- Обратную связь можно получить списком по заявке.
- Обратную связь можно экспортировать как JSONL evaluation cases.
- Существующие smoke-проверки анализа, RAG, инструментов, согласований и UI продолжают проходить.

## Отложено в этап 10.5

- Реализация evaluation runner для `evaluation-run` и `evaluation-result`.
- Workflow curated evaluation set.
- История обратной связи и controls экспорта или скачивания в Operator UI.
- Аналитика качества и сводка regression pass/fail.
- Сохранение version metadata для модели, prompt/config, индекса базы знаний и tool registry.
- Идемпотентность обратной связи и поиск дублей.
- Связи case timeline для событий обратной связи и оценки.
