from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .action_gates import ActionGateConflict, ActionGateNotFound
from .cases import CaseNotFound
from .contracts import ContractValidationError
from .workflow import TicketWorkflow


class TicketAnalyzeRequest(BaseModel):
    user: str | None = Field(default=None)
    service: str | None = Field(default=None)
    environment: str | None = Field(default=None)
    description: str | None = Field(default=None)
    priority: str | None = Field(default=None)
    scenario: str | None = Field(default=None)
    ticket_id: str | None = Field(default=None)
    case_id: str | None = Field(default=None)
    decision_override: dict[str, Any] | None = Field(default=None)


class ToolDispatchRequest(BaseModel):
    action: dict[str, Any] = Field()
    policy_result: dict[str, Any] = Field()
    approved_by_operator: bool = Field(default=False)
    case_id: str | None = Field(default=None)
    ticket_id: str | None = Field(default=None)
    operator_id: str | None = Field(default=None)


class ApprovalDecisionRequest(BaseModel):
    schema_version: str = Field(default="1.0")
    decision: str = Field()
    operator_id: str = Field()
    comment: str | None = Field(default=None)


class KnowledgeRebuildRequest(BaseModel):
    operator_id: str = Field()


class FeedbackRequest(BaseModel):
    schema_version: str = Field(default="1.0")
    ticket_id: str = Field()
    operator_id: str = Field()
    rating: str = Field()
    ticket_input: dict[str, Any] = Field()
    analysis_snapshot: dict[str, Any] = Field()
    approval_snapshot: dict[str, Any] | None = Field(default=None)
    operator_note: str | None = Field(default=None)
    corrected_response: str | None = Field(default=None)
    extensions: dict[str, Any] | None = Field(default=None)


class IntegrationCallbackRequest(BaseModel):
    schema_version: str = Field(default="1.0")
    case_id: str | None = Field(default=None)
    ticket_id: str | None = Field(default=None)
    invocation_id: str = Field()
    action_id: str = Field()
    tool_name: str = Field()
    endpoint_id: str = Field()
    adapter_type: str = Field()
    operation_id: str = Field()
    status: str = Field()
    policy_rule_id: str = Field()
    duration_ms: int | None = Field(default=None)
    attempts: int | None = Field(default=None)
    output: dict[str, Any] | None = Field(default=None)
    error: dict[str, Any] | None = Field(default=None)
    received_at: str | None = Field(default=None)
    extensions: dict[str, Any] | None = Field(default=None)


app = FastAPI(title="ServiceDesk AI Orchestrator", version="0.1.0")
workflow = TicketWorkflow()
OPERATOR_UI_ROOT = Path(__file__).resolve().parents[2] / "operator-ui" / "static"
app.mount(
    "/operator/static",
    StaticFiles(directory=OPERATOR_UI_ROOT),
    name="operator-static",
)


def model_to_dict(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/operator")
def operator_ui() -> FileResponse:
    return FileResponse(OPERATOR_UI_ROOT / "index.html")


@app.post("/tickets/analyze")
def analyze_ticket(request: TicketAnalyzeRequest) -> dict[str, Any]:
    try:
        return workflow.analyze(model_to_dict(request))
    except ContractValidationError as error:
        raise HTTPException(
            status_code=400,
            detail={
                "contract_name": error.contract_name,
                "errors": error.errors,
            },
        ) from error


@app.post("/cases")
def create_case(request: TicketAnalyzeRequest) -> dict[str, Any]:
    try:
        analysis = workflow.analyze(model_to_dict(request))
        return {
            "schema_version": "1.0",
            "case": workflow.get_case(analysis["case_id"]),
            "analysis": analysis,
        }
    except ContractValidationError as error:
        raise HTTPException(
            status_code=400,
            detail={
                "contract_name": error.contract_name,
                "errors": error.errors,
            },
        ) from error


@app.get("/cases/{case_id}")
def get_case(case_id: str) -> dict[str, Any]:
    try:
        return workflow.get_case(case_id)
    except CaseNotFound as error:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "case_not_found",
                "message": f"Кейс не найден: {case_id}",
            },
        ) from error


@app.get("/cases/{case_id}/timeline")
def get_case_timeline(case_id: str) -> dict[str, Any]:
    try:
        return workflow.get_case_timeline(case_id)
    except CaseNotFound as error:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "case_not_found",
                "message": f"Кейс не найден: {case_id}",
            },
        ) from error


@app.post("/tools/dispatch")
def dispatch_tool(request: ToolDispatchRequest) -> dict[str, Any]:
    if request.approved_by_operator:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "approval_endpoint_required",
                "message": "Действия с согласованием оператора должны выполняться через /approvals/{approval_id}/decision.",
            },
        )
    try:
        return workflow.dispatch_tool(
            request.action,
            request.policy_result,
            case_id=request.case_id,
            ticket_id=request.ticket_id,
            approved_by_operator=request.approved_by_operator,
            operator_id=request.operator_id,
        )
    except ContractValidationError as error:
        raise HTTPException(
            status_code=400,
            detail={
                "contract_name": error.contract_name,
                "errors": error.errors,
            },
        ) from error


@app.post("/integrations/callbacks/{endpoint_id}")
def integration_callback(
    endpoint_id: str,
    request: IntegrationCallbackRequest,
) -> dict[str, Any]:
    payload = {
        key: value
        for key, value in model_to_dict(request).items()
        if value is not None
    }
    if payload["endpoint_id"] != endpoint_id:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "endpoint_id_mismatch",
                "message": "endpoint_id в callback должен совпадать с URL path.",
            },
        )
    try:
        return workflow.handle_integration_callback(payload)
    except CaseNotFound as error:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "case_not_found",
                "message": f"Кейс не найден по корреляции callback: {error}",
            },
        ) from error
    except (ContractValidationError, ValueError) as error:
        if isinstance(error, ContractValidationError):
            detail = {
                "contract_name": error.contract_name,
                "errors": error.errors,
            }
        else:
            detail = {
                "code": "callback_rejected",
                "message": str(error),
            }
        raise HTTPException(status_code=400, detail=detail) from error


@app.get("/approvals/{approval_id}")
def get_approval(approval_id: str) -> dict[str, Any]:
    try:
        return workflow.get_action_gate(approval_id)
    except ActionGateNotFound as error:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "approval_not_found",
                "message": f"Согласование не найдено: {approval_id}",
            },
        ) from error


@app.get("/tickets/{ticket_id}/approvals")
def list_ticket_approvals(ticket_id: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "ticket_id": ticket_id,
        "approvals": workflow.list_ticket_action_gates(ticket_id),
    }


@app.post("/approvals/{approval_id}/decision")
def decide_approval(
    approval_id: str,
    request: ApprovalDecisionRequest,
) -> dict[str, Any]:
    try:
        payload = {
            key: value
            for key, value in model_to_dict(request).items()
            if value is not None
        }
        return workflow.decide_action_gate(approval_id, payload)
    except ActionGateNotFound as error:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "approval_not_found",
                "message": f"Согласование не найдено: {approval_id}",
            },
        ) from error
    except ActionGateConflict as error:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "approval_conflict",
                "message": str(error),
            },
        ) from error
    except ContractValidationError as error:
        raise HTTPException(
            status_code=400,
            detail={
                "contract_name": error.contract_name,
                "errors": error.errors,
            },
        ) from error


@app.post("/knowledge/rebuild")
def rebuild_knowledge(request: KnowledgeRebuildRequest) -> dict[str, Any]:
    try:
        return workflow.rebuild_knowledge(request.operator_id)
    except ContractValidationError as error:
        raise HTTPException(
            status_code=400,
            detail={
                "contract_name": error.contract_name,
                "errors": error.errors,
            },
        ) from error


@app.get("/knowledge/status")
def knowledge_status() -> dict[str, Any]:
    return workflow.knowledge_status()


@app.post("/feedback")
def submit_feedback(request: FeedbackRequest) -> dict[str, Any]:
    try:
        payload = {
            key: value
            for key, value in model_to_dict(request).items()
            if value is not None
        }
        return workflow.submit_feedback(payload)
    except ContractValidationError as error:
        raise HTTPException(
            status_code=400,
            detail={
                "contract_name": error.contract_name,
                "errors": error.errors,
            },
        ) from error


@app.get("/tickets/{ticket_id}/feedback")
def list_ticket_feedback(ticket_id: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "ticket_id": ticket_id,
        "feedback": workflow.list_ticket_feedback(ticket_id),
    }


@app.get("/feedback/export")
def export_feedback() -> PlainTextResponse:
    return PlainTextResponse(
        workflow.export_feedback_jsonl(),
        media_type="application/x-ndjson",
    )
