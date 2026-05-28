#!/usr/bin/env bash
set -euo pipefail

if [ -x ".venv/bin/python" ]; then
  PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

HOST="${ORCHESTRATOR_HOST:-127.0.0.1}"
PORT="${ORCHESTRATOR_PORT:-18102}"
BASE_URL="http://${HOST}:${PORT}"
LOG_FILE="${STAGE11_LOG_FILE:-/tmp/servicedesk-stage11-orchestrator.log}"
STATE_DB="${STAGE11_STATE_DB:-/tmp/servicedesk-stage11-orchestrator-${PORT}-$$.sqlite}"
INDEX_PATH="${STAGE11_INDEX_PATH:-/tmp/servicedesk-stage11-knowledge-${PORT}-$$.json}"
CALLBACK_TOKEN="${INTEGRATION_CALLBACK_TOKEN:-dev-callback-token}"

ORCHESTRATOR_STATE_DB="${STATE_DB}" \
KNOWLEDGE_INDEX_PATH="${INDEX_PATH}" \
INTEGRATION_ENDPOINT_PROFILE="${INTEGRATION_ENDPOINT_PROFILE:-mock}" \
SECURITY_AUTH_MODE="${SECURITY_AUTH_MODE:-dev_header}" \
SECURITY_DEV_ACTOR="${SECURITY_DEV_ACTOR:-admin-1}" \
SECURITY_RATE_LIMIT_PER_MINUTE="${SECURITY_RATE_LIMIT_PER_MINUTE:-600}" \
INTEGRATION_CALLBACK_TOKEN="${CALLBACK_TOKEN}" \
  "${PYTHON_BIN}" -m uvicorn apps.orchestrator.app.main:app --host "${HOST}" --port "${PORT}" >"${LOG_FILE}" 2>&1 &
SERVER_PID="$!"

cleanup() {
  kill "${SERVER_PID}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

BASE_URL="${BASE_URL}" INTEGRATION_CALLBACK_TOKEN="${CALLBACK_TOKEN}" "${PYTHON_BIN}" - <<'PY'
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from apps.orchestrator.app.security import AuditStore

base_url = os.environ["BASE_URL"]
callback_headers = {"X-ServiceDesk-Callback-Token": os.environ["INTEGRATION_CALLBACK_TOKEN"]}


def actor_headers(actor_id):
    return {"X-ServiceDesk-Actor": actor_id, "X-ServiceDesk-Session": f"smoke:{actor_id}"}


def request(path, payload=None, expected_status=200, headers_extra=None):
    data = None
    method = "GET"
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        method = "POST"
        headers["Content-Type"] = "application/json"
    if headers_extra:
        headers.update(headers_extra)
    req = Request(f"{base_url}{path}", data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=5) as response:
            status = response.status
            body = response.read().decode("utf-8")
    except HTTPError as error:
        status = error.code
        body = error.read().decode("utf-8")

    parsed = json.loads(body) if body else {}
    if status != expected_status:
        raise SystemExit(f"{path}: expected HTTP {expected_status}, got {status}: {parsed}")
    return parsed


last_error = None
for _ in range(60):
    try:
        if request("/healthz") == {"status": "ok"}:
            break
    except (HTTPError, URLError, TimeoutError) as error:
        last_error = error
        time.sleep(0.5)
else:
    raise SystemExit(f"healthz did not become ready: {last_error}")

sanitized = AuditStore._sanitize_details(
    {
        "token": "plain-token",
        "пароль": "plain-password",
        "секрет": "plain-secret",
        "ключДоступа": "plain-key",
        "учетные_данные": "plain-credentials",
        "normal": {
            "visible": "ok",
            "токен": "nested-token",
        },
    }
)
assert sanitized["token"] == "***", sanitized
assert sanitized["пароль"] == "***", sanitized
assert sanitized["секрет"] == "***", sanitized
assert sanitized["ключДоступа"] == "***", sanitized
assert sanitized["учетные_данные"] == "***", sanitized
assert sanitized["normal"]["visible"] == "ok", sanitized
assert sanitized["normal"]["токен"] == "***", sanitized
print("audit details sanitization ok")

admin_session = request("/admin/security/session", headers_extra=actor_headers("admin-1"))
assert admin_session["actor_id"] == "admin-1", admin_session
assert "security.manage" in admin_session["permissions"], admin_session
readonly_session = request("/admin/security/session", headers_extra=actor_headers("readonly-1"))
assert readonly_session["roles"] == ["readonly"], readonly_session
print("security session ok")

security_catalog = request("/admin/security/catalog", headers_extra=actor_headers("admin-1"))
permission_ids = {permission["permission_id"] for permission in security_catalog["permissions"]}
for expected in {"cases.read", "knowledge.manage", "audit.read", "security.manage"}:
    assert expected in permission_ids, security_catalog
print("security catalog ok")

dashboard = request("/admin/dashboard", headers_extra=actor_headers("readonly-1"))
assert dashboard["schema_version"] == "1.0", dashboard
denied_rebuild = request(
    "/admin/knowledge/rebuild",
    {"operator_id": "readonly-stage11"},
    expected_status=403,
    headers_extra=actor_headers("readonly-1"),
)
assert denied_rebuild["detail"]["code"] == "permission_denied", denied_rebuild
print("readonly access boundaries ok")

rebuild = request(
    "/admin/knowledge/rebuild",
    {"operator_id": "admin-stage11"},
    headers_extra=actor_headers("admin-1"),
)
assert rebuild["status"] == "success", rebuild
print("admin knowledge rebuild audited ok")

ticket_input = {
    "ticket_id": "stage11-ticket",
    "user": "ivan",
    "service": "billing-worker",
    "environment": "test",
    "description": "перезапустить billing-worker через ранбук",
    "priority": "p3",
    "scenario": "runbook",
}
created = request("/cases", ticket_input, headers_extra=actor_headers("operator-1"))
analysis = created["analysis"]
case_id = analysis["case_id"]
assert analysis["workflow_state"]["id"] == "pending_approval", analysis
approval_id = analysis["approval_requests"][0]["approval_id"]
approval = request(
    f"/approvals/{approval_id}/decision",
    {
        "decision": "approve",
        "operator_id": "operator-1",
        "comment": "Smoke-проверка этапа 11: RBAC approval.",
    },
    headers_extra=actor_headers("operator-1"),
)
assert approval["tool_result"]["status"] == "success", approval
print("operator case and approval permissions ok")

approved_tool_result = approval["tool_result"]
callback_payload = {
    "schema_version": "1.0",
    "case_id": case_id,
    "ticket_id": analysis["ticket_id"],
    "invocation_id": approved_tool_result["invocation_id"],
    "action_id": approved_tool_result["action_id"],
    "tool_name": approved_tool_result["tool_name"],
    "endpoint_id": approved_tool_result["endpoint_id"],
    "adapter_type": approved_tool_result["adapter_type"],
    "operation_id": approved_tool_result["operation_id"],
    "status": "success",
    "policy_rule_id": approved_tool_result["policy_rule_id"],
    "duration_ms": 90,
    "attempts": 1,
    "output": {
        "runbook_status": "completed",
        "message": "Stage 11 callback.",
    },
}
denied_callback = request(
    f"/integrations/callbacks/{approved_tool_result['endpoint_id']}",
    callback_payload,
    expected_status=403,
)
assert denied_callback["detail"]["code"] == "callback_token_invalid", denied_callback
callback = request(
    f"/integrations/callbacks/{approved_tool_result['endpoint_id']}",
    callback_payload,
    headers_extra=callback_headers,
)
assert callback["accepted"] is True, callback
print("callback token protection ok")

secret_references = request(
    "/admin/security/secret-references",
    headers_extra=actor_headers("admin-1"),
)
dump = json.dumps(secret_references, ensure_ascii=False)
assert os.environ["INTEGRATION_CALLBACK_TOKEN"] not in dump, secret_references
assert "INTEGRATION_CALLBACK_TOKEN" in dump, secret_references
readonly_secret_refs = request(
    "/admin/security/secret-references",
    expected_status=403,
    headers_extra=actor_headers("readonly-1"),
)
assert readonly_secret_refs["detail"]["code"] == "permission_denied", readonly_secret_refs
print("secret references are reference-only ok")

audit_summary = request("/admin/security/audit/summary", headers_extra=actor_headers("admin-1"))
assert audit_summary["total"] >= 5, audit_summary
assert audit_summary["by_outcome"].get("denied", 0) >= 2, audit_summary
assert audit_summary["by_outcome"].get("success", 0) >= 3, audit_summary
audit_events = request(
    "/admin/security/audit?limit=50",
    headers_extra=actor_headers("admin-1"),
)
actions = {event["action"] for event in audit_events["events"]}
for expected in {
    "admin.knowledge.rebuild",
    "cases.create",
    "approvals.decide",
    "callbacks.receive",
}:
    assert expected in actions, audit_events
assert any(event["outcome"] == "denied" for event in audit_events["events"]), audit_events
print("audit log ok")

print("Smoke-проверка этапа 11 завершена.")
PY
