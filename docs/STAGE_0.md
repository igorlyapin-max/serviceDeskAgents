# Этап 0: базовый контур разработки

Этап 0 подготавливает локальную CPU-only среду разработки. GPU не требуется; тяжелый LLM runtime запускается отдельно через профиль Docker Compose.

## Целевые локальные компоненты

Основные сервисы:

- PostgreSQL с возможностью pgvector на host port `15432`.
- Redis на host port `16379`.
- n8n на port `5678`.

Опциональные LLM-сервисы:

- LiteLLM на port `4000`.
- vLLM CPU OpenAI-compatible server на port `8000`.

## Инструменты на host

Обязательно:

- Docker Engine.
- Docker Compose plugin.
- Git.

Рекомендуется:

- Python 3.12 для локальной backend-разработки.
- Node.js LTS для локальной UI-разработки.
- `uv` для управления Python dependencies.

Repository использует containers для базового контура, поэтому версии Python и Node на host не считаются production runtime versions.

## Наблюдение по текущему host

На текущей машине разработки обнаружено:

- Docker установлен.
- Docker Compose установлен.
- Python установлен как `3.14.4`.
- Node.js установлен как `25.9.0`.
- `uv` не установлен.

Позднее проект должен использовать зафиксированные container runtimes, например Python `3.12` для FastAPI и LTS Node image для frontend.

## Команды

Проверить конфигурацию Compose:

```bash
docker compose config
```

Запустить легкие основные сервисы:

```bash
docker compose up -d postgres redis n8n
```

Позднее запустить LiteLLM и vLLM CPU:

```bash
docker compose --profile llm up -d litellm vllm-cpu
```

Показать состояние сервисов:

```bash
docker compose ps
```

Запустить smoke-проверки:

```bash
make stage0-smoke
```

Остановить сервисы:

```bash
docker compose down
```

Остановить сервисы и удалить локальные volumes:

```bash
docker compose down -v
```

## Порты

| Компонент | Порт | Назначение |
| --- | ---: | --- |
| PostgreSQL | `15432` на host, `5432` в сети Compose | Хранилище приложения, n8n и pgvector |
| Redis | `16379` на host, `6379` в сети Compose | Cache и координация workflow |
| n8n | `5678` | Integration workflows и webhooks |
| LiteLLM | `4000` | OpenAI-compatible LLM gateway |
| vLLM CPU | `8000` | Local CPU inference backend |

## Критерии выхода этапа 0

- `docker compose config` проходит.
- `.env.example` задает обязательные environment variables.
- Имена и порты основных сервисов задокументированы.
- LLM runtime можно включить отдельно через профиль `llm`.

Host ports намеренно не используют стандартные локальные порты PostgreSQL и Redis.
