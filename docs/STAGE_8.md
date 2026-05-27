# Этап 8: минимальный Operator UI

Этап 8 дает рабочий workflow оператора без отдельного frontend build stack. FastAPI отдает статический UI на `/operator`, а UI использует те же backend API, которые напрямую вызывают smoke-проверки.

## Базовые решения

- UI является статическим HTML/CSS/JS в `apps/operator-ui/static`.
- FastAPI отдает UI и статические assets, поэтому настройка CORS не нужна.
- UI не обходит backend policy или action gates.
- Согласование ранбука проходит через `/approvals/{approval_id}/decision`.
- Перестроение базы знаний остается явным действием оператора через `/knowledge/rebuild`.
- Интеграция с ServiceDesk пока ручная: через копируемый текст.

## Workflow оператора

1. Оператор открывает `/operator`.
2. Оператор вводит поля заявки и запускает анализ.
3. UI показывает состояние workflow, AI-решение, статус RAG, ссылки на источники и трассировку инструментов.
4. Если нужно согласование, UI показывает детали ранбука и элементы управления для согласования или отклонения.
5. Согласование выполняется через backend action gates.
6. UI показывает результат ранбука и копируемую сводку для ServiceDesk.
7. Оператор может перестроить индекс базы знаний с того же экрана.

## Используемые backend endpoints

- `GET /operator`
- `GET /operator/static/app.js`
- `GET /operator/static/styles.css`
- `GET /knowledge/status`
- `POST /knowledge/rebuild`
- `POST /tickets/analyze`
- `POST /approvals/{approval_id}/decision`

## Команды

Запустить проверки:

```bash
PYTHON=.venv/bin/python make stage8-check
```

Запустить smoke-проверку этапа 8:

```bash
./scripts/stage8-smoke.sh
```

Запустить API:

```bash
PYTHON=.venv/bin/python make stage3-run
```

Затем открыть `http://127.0.0.1:18088/operator`.

## Критерии выхода

- `/operator` отдает UI.
- Статические JS и CSS assets доступны.
- Оператор может анализировать заявку.
- Оператор может перестроить индекс базы знаний.
- Ссылки RAG и трассировка видимы после перестроения.
- Оператор может согласовать или отклонить ожидающий ранбук.
- UI формирует копируемый текст для ServiceDesk.
