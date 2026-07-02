#!/usr/bin/env bash
set -euo pipefail

COMPOSE_BIN="${COMPOSE:-docker compose}"
HOST="${ORCHESTRATOR_HOST:-127.0.0.1}"
PORT="${ORCHESTRATOR_PORT:-18088}"
BASE_URL="http://${HOST}:${PORT}"

${COMPOSE_BIN} ps postgres redis redpanda n8n litellm orchestrator async-outbox-publisher async-tool-worker async-external-event-worker async-agent-task-worker

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

${COMPOSE_BIN} exec -T n8n node - <<'JS'
const requiredRaw = String(process.env.ZABBIX_RUNBOOK_REQUIRED_ORIGINS || '').trim();
const registryRaw = String(process.env.ZABBIX_API_TOKENS_BY_ORIGIN || '').trim();
const apiRegistryRaw = String(process.env.ZABBIX_API_URLS_BY_ORIGIN || '').trim();

if (!requiredRaw && !registryRaw && !apiRegistryRaw) {
  console.log('Zabbix runbook registry check skipped: ZABBIX_RUNBOOK_REQUIRED_ORIGINS is not set.');
  process.exit(0);
}

function parseJsonObject(name, raw) {
  if (!raw) return {};
  try {
    const value = JSON.parse(raw);
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      throw new Error('not_object');
    }
    return value;
  } catch (error) {
    throw new Error(`${name} must be a JSON object.`);
  }
}

const tokenRegistry = parseJsonObject('ZABBIX_API_TOKENS_BY_ORIGIN', registryRaw);
const apiUrlRegistry = parseJsonObject('ZABBIX_API_URLS_BY_ORIGIN', apiRegistryRaw);
const requiredOrigins = (requiredRaw
  ? requiredRaw.split(/[,\s]+/).filter(Boolean)
  : Object.keys(tokenRegistry)
);

if (!requiredOrigins.length) {
  throw new Error('ZABBIX_RUNBOOK_REQUIRED_ORIGINS is empty and token registry has no origins.');
}

for (const origin of requiredOrigins) {
  const token = String(tokenRegistry[origin] || '').trim();
  if (!token) {
    throw new Error(`Missing Zabbix API token mapping for origin ${origin}.`);
  }
  const apiUrl = String(apiUrlRegistry[origin] || `${origin.replace(/\/+$/, '')}/api_jsonrpc.php`).trim();
  if (!/^https?:\/\/[^?#]+$/i.test(apiUrl)) {
    throw new Error(`Invalid Zabbix API URL for origin ${origin}: ${apiUrl}`);
  }
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);
  try {
    const response = await fetch(apiUrl, {
      method: 'POST',
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json-rpc',
        Accept: 'application/json',
      },
      body: JSON.stringify({
        jsonrpc: '2.0',
        method: 'apiinfo.version',
        params: {},
        id: 1,
      }),
    });
    const text = await response.text();
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    let payload;
    try {
      payload = JSON.parse(text);
    } catch {
      throw new Error('non_json_response');
    }
    if (payload.error) {
      throw new Error(`JSON-RPC error ${payload.error.code || 'unknown'}`);
    }
    if (!payload.result) {
      throw new Error('missing apiinfo.version result');
    }
    const authResponse = await fetch(apiUrl, {
      method: 'POST',
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json-rpc',
        Accept: 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        jsonrpc: '2.0',
        method: 'event.get',
        params: {
          output: ['eventid'],
          limit: 1,
          sortfield: 'eventid',
          sortorder: 'DESC',
        },
        id: 2,
      }),
    });
    const authText = await authResponse.text();
    if (!authResponse.ok) {
      throw new Error(`authenticated event.get HTTP ${authResponse.status}`);
    }
    let authPayload;
    try {
      authPayload = JSON.parse(authText);
    } catch {
      throw new Error('authenticated event.get returned non JSON response');
    }
    if (authPayload.error) {
      throw new Error(`authenticated event.get failed with JSON-RPC error ${authPayload.error.code || 'unknown'}`);
    }
    console.log(`Zabbix API registry OK: ${origin} -> ${apiUrl}`);
  } finally {
    clearTimeout(timeout);
  }
}
JS

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
