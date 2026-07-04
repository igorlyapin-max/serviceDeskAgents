#!/usr/bin/env bash
set -euo pipefail

COMPOSE_BIN="${COMPOSE:-docker compose}"
HOST="${ORCHESTRATOR_HOST:-127.0.0.1}"
PORT="${ORCHESTRATOR_PORT:-18088}"
BASE_URL="http://${HOST}:${PORT}"

${COMPOSE_BIN} ps postgres redis redpanda litellm orchestrator async-outbox-publisher async-mcp-worker async-external-event-worker async-agent-task-worker

python3 - <<'PY'
import os
from pathlib import Path
import urllib.request


def env_value(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value:
        return value
    env_path = Path(".env")
    if not env_path.exists():
        return default
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        if key.strip() == name:
            return raw_value.strip().strip('"').strip("'")
    return default


port = env_value("LITELLM_PORT", "4000")
base_url = env_value("LITELLM_PUBLIC_BASE_URL", f"http://127.0.0.1:{port}/v1").rstrip("/")
api_key = env_value("LITELLM_MASTER_KEY")
headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
url = f"{base_url}/models"
try:
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=5) as response:
        status = int(getattr(response, "status", 0) or 0)
except OSError as error:
    raise SystemExit(f"LiteLLM public gateway недоступен: {url}: {error}") from error
if not 200 <= status < 300:
    raise SystemExit(f"LiteLLM public gateway вернул HTTP {status}: {url}")
print(f"LiteLLM public gateway OK: {url}")
PY

python3 - "${BASE_URL}/readyz" <<'PY'
import json
import sys
import urllib.error
import urllib.request

url = sys.argv[1]
try:
    with urllib.request.urlopen(url, timeout=5) as response:
        status_code = response.status
        body = response.read().decode("utf-8")
except urllib.error.HTTPError as error:
    status_code = error.code
    body = error.read().decode("utf-8")
except OSError as error:
    raise SystemExit(f"readyz недоступен: {error}")

try:
    report = json.loads(body)
except json.JSONDecodeError as error:
    raise SystemExit(f"readyz вернул не JSON: HTTP {status_code}: {error}: {body[:300]}")

print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
if status_code >= 400 or report.get("status") != "ok":
    messages = []
    for check in report.get("checks", []):
        if check.get("status") != "ok":
            messages.append(f"{check.get('name')}: {check.get('message')}")
    raise SystemExit("runtime-check не пройден: " + "; ".join(messages))
PY
