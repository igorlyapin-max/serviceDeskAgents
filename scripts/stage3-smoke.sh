#!/usr/bin/env bash
set -euo pipefail

if [ -x ".venv/bin/python" ]; then
  PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

HOST="${ORCHESTRATOR_HOST:-127.0.0.1}"
PORT="${ORCHESTRATOR_PORT:-18088}"
BASE_URL="http://${HOST}:${PORT}"
LOG_FILE="${STAGE3_LOG_FILE:-/tmp/servicedesk-stage3-orchestrator.log}"

"${PYTHON_BIN}" -m uvicorn apps.orchestrator.app.main:app --host "${HOST}" --port "${PORT}" >"${LOG_FILE}" 2>&1 &
SERVER_PID="$!"

cleanup() {
  kill "${SERVER_PID}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

for _ in $(seq 1 60); do
  if curl -fsS "${BASE_URL}/healthz" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

curl -fsS "${BASE_URL}/healthz" >/dev/null

assert_scenario() {
  local scenario="$1"
  local expected_state="$2"
  local payload
  payload="$(printf '{"user":"ivan","service":"billing-worker","environment":"test","description":"Smoke-проверка этапа 3: %s","priority":"p3","scenario":"%s"}' "${scenario}" "${scenario}")"

  response="$(curl -fsS \
    -H "Content-Type: application/json" \
    -d "${payload}" \
    "${BASE_URL}/tickets/analyze")"

  RESPONSE="${response}" EXPECTED_STATE="${expected_state}" SCENARIO="${scenario}" "${PYTHON_BIN}" - <<'PY'
import json
import os

response = json.loads(os.environ["RESPONSE"])
expected_state = os.environ["EXPECTED_STATE"]
scenario = os.environ["SCENARIO"]
actual_state = response["workflow_state"]["id"]
if actual_state != expected_state:
    raise SystemExit(f"{scenario}: expected {expected_state}, got {actual_state}")
print(f"{scenario} ok: {actual_state}")
PY
}

assert_scenario "answer" "resolved"
assert_scenario "clarification" "waiting_for_user"
assert_scenario "escalation" "escalation_required"
assert_scenario "runbook" "pending_approval"
assert_scenario "invalid_model_output" "model_output_invalid"

echo "Smoke-проверка этапа 3 завершена."
