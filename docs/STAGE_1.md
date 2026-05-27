# Этап 1: LLM gateway

Этап 1 открывает локальный OpenAI-compatible endpoint через LiteLLM. vLLM CPU является backend для inference в разработке и изолирован за LiteLLM gateway.

## Компоненты

- vLLM CPU на host port `8000`.
- LiteLLM на host port `4000`.
- Модельный alias по умолчанию для приложения: `local-opt-125m`.
- Upstream model по умолчанию: `facebook/opt-125m`.
- Более поздний кандидат по качеству: `Qwen/Qwen3-0.6B`.

## Настройки CPU по умолчанию

Настройки по умолчанию делают запуск надежнее, а не быстрее:

- `VLLM_DTYPE=float32`
- `VLLM_MAX_MODEL_LEN=2048`
- `VLLM_MAX_NUM_SEQS=1`
- `--enforce-eager`
- `VLLM_CHAT_TEMPLATE=/app/vllm/simple-chat-template.jinja`
- `VLLM_CPU_KVCACHE_SPACE=4`
- `VLLM_CPU_NUM_OF_RESERVED_CPU=1`

Текущая машина разработки не показывает AVX-512, поэтому `float32` безопаснее `bfloat16` для первого запуска. Модель намеренно маленькая: этап 1 проверяет gateway, а не качество ответов ServiceDesk.

`--enforce-eager` включен для CPU-контура, чтобы избежать долгого startup path Torch Inductor. vLLM все равно может компилировать небольшие CPU helper kernels при warmup, но запуск становится предсказуемее для MVP и smoke-проверок без GPU.

`facebook/opt-125m` не является native chat/instruct model. Этап 1 монтирует минимальный chat template из `infra/vllm/simple-chat-template.jinja`, чтобы OpenAI-compatible `/v1/chat/completions` можно было проверить через LiteLLM. Для будущего качества нужно перейти на instruct model и заменить или убрать smoke template.

Smoke-проверка проверяет совместимость endpoint и форму JSON-ответа. Она не проверяет качество ответа или следование инструкциям.

Для будущей проверки Qwen:

```bash
VLLM_MODEL=Qwen/Qwen3-0.6B \
LITELLM_UPSTREAM_MODEL=hosted_vllm/Qwen/Qwen3-0.6B \
LITELLM_MODEL_ALIAS=local-qwen3-0.6b \
VLLM_MAX_MODEL_LEN=8192 \
docker compose --profile llm up -d vllm-cpu litellm
```

## Команды

Проверить конфигурацию Compose с профилем LLM:

```bash
docker compose --profile llm config
```

Запустить vLLM CPU и LiteLLM:

```bash
make stage1-up
```

Смотреть логи:

```bash
make stage1-logs
```

Запустить smoke-проверки:

```bash
make stage1-smoke
```

Эквивалентная команда:

```bash
./scripts/stage1-smoke.sh
```

## OpenAI-compatible request

Приложения должны обращаться к LiteLLM, а не напрямую к vLLM:

```bash
curl -fsS http://127.0.0.1:4000/v1/chat/completions \
  -H "Authorization: Bearer sk-dev-litellm-master-key" \
  -H "Content-Type: application/json" \
  -d '{"model":"local-opt-125m","messages":[{"role":"user","content":"Привет из smoke-проверки этапа 1."}],"max_tokens":8,"temperature":0}'
```

## Критерии выхода

- vLLM CPU открывает `/v1/models`.
- LiteLLM открывает `/v1/models`.
- LiteLLM возвращает chat completion для model alias `local-opt-125m`.
- Будущий код orchestrator зависит только от LiteLLM на `http://127.0.0.1:4000/v1`.
