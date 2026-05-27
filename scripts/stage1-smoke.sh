#!/usr/bin/env bash
set -euo pipefail

VLLM_PORT="${VLLM_PORT:-8000}"
LITELLM_PORT="${LITELLM_PORT:-4000}"
LITELLM_MASTER_KEY="${LITELLM_MASTER_KEY:-sk-dev-litellm-master-key}"
LITELLM_MODEL_ALIAS="${LITELLM_MODEL_ALIAS:-local-opt-125m}"

echo "Checking vLLM model endpoint..."
curl -fsS --max-time 15 "http://127.0.0.1:${VLLM_PORT}/v1/models" >/dev/null

echo "Checking LiteLLM model endpoint..."
curl -fsS --max-time 15 \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}" \
  "http://127.0.0.1:${LITELLM_PORT}/v1/models" >/dev/null

payload="$(printf '{"model":"%s","messages":[{"role":"user","content":"Привет из smoke-проверки этапа 1."}],"max_tokens":8,"temperature":0}' "${LITELLM_MODEL_ALIAS}")"

echo "Checking LiteLLM chat completion..."
curl -fsS --max-time 180 \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}" \
  -H "Content-Type: application/json" \
  -d "${payload}" \
  "http://127.0.0.1:${LITELLM_PORT}/v1/chat/completions"

echo
echo "Smoke-проверка этапа 1 завершена."
