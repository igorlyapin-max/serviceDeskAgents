#!/usr/bin/env bash
set -euo pipefail

if [ -x ".venv/bin/python" ]; then
  PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

HOST="${ORCHESTRATOR_HOST:-127.0.0.1}"
PORT="${ORCHESTRATOR_PORT:-18100}"
BASE_URL="http://${HOST}:${PORT}"
LOG_FILE="${STAGE10_5_LOG_FILE:-/tmp/servicedesk-stage10_5-orchestrator.log}"
STATE_DB="${STAGE10_5_STATE_DB:-/tmp/servicedesk-stage10_5-orchestrator-${PORT}-$$.sqlite}"
INDEX_PATH="${STAGE10_5_INDEX_PATH:-/tmp/servicedesk-stage10_5-knowledge-${PORT}-$$.json}"

ORCHESTRATOR_STATE_DB="${STATE_DB}" \
KNOWLEDGE_INDEX_PATH="${INDEX_PATH}" \
INTEGRATION_ENDPOINT_PROFILE="${INTEGRATION_ENDPOINT_PROFILE:-mock}" \
  "${PYTHON_BIN}" -m uvicorn apps.orchestrator.app.main:app --host "${HOST}" --port "${PORT}" >"${LOG_FILE}" 2>&1 &
SERVER_PID="$!"

cleanup() {
  kill "${SERVER_PID}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

BASE_URL="${BASE_URL}" "${PYTHON_BIN}" - <<'PY'
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

base_url = os.environ["BASE_URL"]


def request(path, payload=None, expected_status=200):
    data = None
    method = "GET"
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        method = "POST"
        headers["Content-Type"] = "application/json"
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

dashboard_before = request("/admin/dashboard")
assert dashboard_before["schema_version"] == "1.0", dashboard_before
assert dashboard_before["cases"]["total"] == 0, dashboard_before
assert dashboard_before["integrations"]["profile"] == "mock", dashboard_before
print("admin dashboard initial ok")

catalog = request("/admin/catalog")
assert "tools" in catalog and "integration_endpoints" in catalog, catalog
workflow_catalog = request("/admin/catalog/workflow")
assert workflow_catalog["state_catalog"]["states"], workflow_catalog
model_config = request("/admin/models/config")
assert model_config["default_model_alias"], model_config
print("admin catalog inventory ok")

rebuild = request("/admin/knowledge/rebuild", {"operator_id": "admin-stage10_5"})
assert rebuild["status"] == "success", rebuild
sources = request("/admin/knowledge/sources")
assert sources["sources"], sources
chunks = request("/admin/knowledge/chunks?limit=1")
assert chunks["status"] == "success", chunks
assert len(chunks["chunks"]) == 1, chunks
retrieval = request(
    "/admin/knowledge/retrieval/test",
    {
        "query": "billing-worker restart runbook",
        "top_k": 2,
    },
)
assert retrieval["status"] == "success", retrieval
assert retrieval["matches"], retrieval
print("admin knowledge endpoints ok")

ticket_input = {
    "ticket_id": "stage10_5-ticket",
    "user": "ivan",
    "service": "billing-worker",
    "environment": "test",
    "description": "перезапустить billing-worker через ранбук",
    "priority": "p3",
    "scenario": "runbook",
}
created = request("/cases", ticket_input)
analysis = created["analysis"]
case_id = analysis["case_id"]
assert analysis["workflow_state"]["id"] == "pending_approval", analysis
feedback_payload = {
    "schema_version": "1.0",
    "ticket_id": analysis["ticket_id"],
    "operator_id": "operator-stage10_5",
    "rating": "correct",
    "ticket_input": ticket_input,
    "analysis_snapshot": analysis,
    "operator_note": "Smoke-проверка этапа 10.5: корректный ответ.",
    "extensions": {
        "case_id": case_id,
        "idempotency_key": "stage10_5-feedback-key"
    },
}
feedback = request("/feedback", feedback_payload)
feedback_replay = request("/feedback", feedback_payload)
assert feedback_replay["feedback_id"] == feedback["feedback_id"], feedback_replay

duplicate_payload = {
    **feedback_payload,
    "extensions": {
        "case_id": case_id,
        "smoke": "duplicate-detection"
    },
}
duplicate = request("/feedback", duplicate_payload)
assert duplicate["extensions"]["duplicate"] is True, duplicate
assert duplicate["extensions"]["duplicate_of_feedback_id"] == feedback["feedback_id"], duplicate
print("feedback idempotency and duplicate detection ok")

promotion = request(
    "/admin/evaluations/promote-feedback",
    {
        "operator_id": "admin-stage10_5",
        "feedback_ids": [feedback["feedback_id"]],
    },
)
assert promotion["promoted_count"] == 1, promotion
evaluation_cases = request("/admin/evaluations/cases")
assert evaluation_cases["case_count"] == 1, evaluation_cases
evaluation_case_id = evaluation_cases["cases"][0]["case_id"]
print("feedback promotion ok")

run_result = request(
    "/admin/evaluations/run",
    {
        "operator_id": "admin-stage10_5",
        "case_ids": [evaluation_case_id],
    },
)
run = run_result["run"]
assert run["status"] == "completed", run_result
assert run_result["summary"]["total"] == 1, run_result
assert run_result["results"][0]["status"] == "passed", run_result
loaded_run = request(f"/admin/evaluations/runs/{run['run_id']}")
assert loaded_run["run"]["run_id"] == run["run_id"], loaded_run
assert len(loaded_run["results"]) == 1, loaded_run
print("evaluation runner ok")

timeline = request(f"/cases/{case_id}/timeline")
event_types = [event["event_type"] for event in timeline["events"]]
assert event_types.count("feedback_recorded") == 2, timeline
assert "evaluation_result_recorded" in event_types, timeline
print("evaluation timeline event ok")

dashboard_after = request("/admin/dashboard")
assert dashboard_after["cases"]["total"] >= 2, dashboard_after
assert dashboard_after["feedback"]["total"] == 2, dashboard_after
assert dashboard_after["feedback"]["duplicates"] == 1, dashboard_after
assert dashboard_after["feedback"]["curated_evaluation_cases"] == 1, dashboard_after
assert dashboard_after["feedback"]["evaluation_runs"] == 1, dashboard_after
print("admin dashboard after activity ok")

print("Smoke-проверка этапа 10.5 завершена.")
PY
