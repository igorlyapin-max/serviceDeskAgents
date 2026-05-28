from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .action_gates import ActionGateConflict, ActionGateNotFound, utc_now
from .cases import CaseNotFound
from .config_registry import (
    CONFIG_DOMAINS,
    ConfigDraftNotFound,
    ConfigRegistryError,
    ConfigStore,
    ConfigVersionNotFound,
)
from .contracts import ContractValidationError
from .local_env import LocalEnvError, set_local_env_value
from .security import (
    AuditStore,
    CallbackTokenInvalid,
    PermissionDenied,
    RateLimitExceeded,
    SecurityContext,
    SecurityManager,
)
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


class AdminRetrievalTestRequest(BaseModel):
    schema_version: str = Field(default="1.0")
    query: str = Field()
    top_k: int = Field(default=3)
    filters: dict[str, Any] | None = Field(default=None)


class AdminFeedbackPromotionRequest(BaseModel):
    operator_id: str = Field()
    feedback_ids: list[str] | None = Field(default=None)


class AdminEvaluationRunRequest(BaseModel):
    operator_id: str = Field()
    case_ids: list[str] | None = Field(default=None)
    limit: int | None = Field(default=None)


class AdminConfigDraftCreateRequest(BaseModel):
    domain: str = Field()
    payload: dict[str, Any] = Field()
    operator_id: str = Field()
    base_version_id: str | None = Field(default=None)


class AdminConfigDraftActionRequest(BaseModel):
    operator_id: str = Field()
    limit: int | None = Field(default=None)


class AdminConfigRollbackRequest(BaseModel):
    operator_id: str = Field()


class AdminN8nWorkflowOperationRequest(BaseModel):
    operator_id: str = Field()
    execution_id: str | None = Field(default=None)


class AdminScenarioSimulationRequest(BaseModel):
    text: str = Field()
    provided_slots: dict[str, Any] | None = Field(default=None)
    operator_id: str = Field(default="admin-1")


class AdminModelSecretUpdateRequest(BaseModel):
    provider_id: str = Field(min_length=1, max_length=160)
    env_name: str = Field(min_length=1, max_length=160)
    secret_value: str = Field(min_length=1, max_length=8192, repr=False)


class OperatorScenarioSimulationRequest(BaseModel):
    text: str = Field()
    provided_slots: dict[str, Any] | None = Field(default=None)
    operator_id: str = Field(default="operator-1")


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
config_store = ConfigStore(workflow.contracts)
workflow.attach_config_store(config_store)
security = SecurityManager(workflow.contracts)
audit_store = AuditStore(workflow.contracts)
OPERATOR_UI_ROOT = Path(__file__).resolve().parents[2] / "operator-ui" / "static"
ADMIN_UI_ROOT = Path(__file__).resolve().parents[2] / "admin-ui" / "static"
app.mount(
    "/operator/static",
    StaticFiles(directory=OPERATOR_UI_ROOT),
    name="operator-static",
)
app.mount(
    "/admin/static",
    StaticFiles(directory=ADMIN_UI_ROOT),
    name="admin-static",
)


def model_to_dict(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def context_or_raise(request: Request) -> SecurityContext:
    context: SecurityContext | None = None
    try:
        context = security.context_from_headers(
            request.headers,
            ip_address=client_ip(request),
        )
        security.check_rate_limit(context)
        return context
    except RateLimitExceeded as error:
        audit_store.record(
            context or security.anonymous_context(ip_address=client_ip(request)),
            action="security.rate_limit",
            resource_type="session",
            outcome="denied",
            request_method=request.method,
            request_path=request.url.path,
            status_code=429,
            details={"message": str(error)},
        )
        raise HTTPException(
            status_code=429,
            detail={
                "code": "rate_limit_exceeded",
                "message": str(error),
            },
        ) from error
    except PermissionDenied as error:
        audit_store.record(
            security.anonymous_context(ip_address=client_ip(request)),
            action="security.authenticate",
            resource_type="session",
            outcome="denied",
            request_method=request.method,
            request_path=request.url.path,
            status_code=403,
            details={"message": str(error)},
        )
        raise HTTPException(
            status_code=403,
            detail={
                "code": "permission_denied",
                "message": str(error),
            },
        ) from error


def permission_dependency(
    permission: str,
    *,
    action: str,
    resource_type: str,
):
    def dependency(request: Request) -> SecurityContext:
        context = context_or_raise(request)
        try:
            security.require_permission(context, permission)
            return context
        except PermissionDenied as error:
            audit_store.record(
                context,
                action=action,
                resource_type=resource_type,
                permission=permission,
                outcome="denied",
                request_method=request.method,
                request_path=request.url.path,
                status_code=403,
                details={"message": str(error)},
            )
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "permission_denied",
                    "message": str(error),
                },
            ) from error

    return dependency


def callback_context_dependency(
    endpoint_id: str,
    request: Request,
) -> SecurityContext:
    try:
        context = security.callback_context(
            request.headers,
            endpoint_id=endpoint_id,
            ip_address=client_ip(request),
        )
        security.check_rate_limit(context)
        security.require_permission(context, "callbacks.write")
        return context
    except CallbackTokenInvalid as error:
        audit_store.record(
            security.anonymous_context(
                actor_id=f"endpoint:{endpoint_id}",
                ip_address=client_ip(request),
            ),
            action="callbacks.receive",
            resource_type="integration_endpoint",
            resource_id=endpoint_id,
            permission="callbacks.write",
            outcome="denied",
            request_method=request.method,
            request_path=request.url.path,
            status_code=403,
            details={"message": str(error)},
        )
        raise HTTPException(
            status_code=403,
            detail={
                "code": "callback_token_invalid",
                "message": str(error),
            },
        ) from error
    except RateLimitExceeded as error:
        audit_store.record(
            security.anonymous_context(
                actor_id=f"endpoint:{endpoint_id}",
                ip_address=client_ip(request),
            ),
            action="security.rate_limit",
            resource_type="integration_endpoint",
            resource_id=endpoint_id,
            permission="callbacks.write",
            outcome="denied",
            request_method=request.method,
            request_path=request.url.path,
            status_code=429,
            details={"message": str(error)},
        )
        raise HTTPException(
            status_code=429,
            detail={
                "code": "rate_limit_exceeded",
                "message": str(error),
            },
        ) from error
    except PermissionDenied as error:
        audit_store.record(
            security.anonymous_context(
                actor_id=f"endpoint:{endpoint_id}",
                ip_address=client_ip(request),
            ),
            action="callbacks.receive",
            resource_type="integration_endpoint",
            resource_id=endpoint_id,
            permission="callbacks.write",
            outcome="denied",
            request_method=request.method,
            request_path=request.url.path,
            status_code=403,
            details={"message": str(error)},
        )
        raise HTTPException(
            status_code=403,
            detail={
                "code": "permission_denied",
                "message": str(error),
            },
        ) from error


def audit_success(
    context: SecurityContext,
    request: Request,
    *,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    permission: str | None = None,
    status_code: int = 200,
    details: dict[str, Any] | None = None,
) -> None:
    audit_store.record(
        context,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        permission=permission,
        outcome="success",
        request_method=request.method,
        request_path=request.url.path,
        status_code=status_code,
        details=details,
    )


def audit_error(
    context: SecurityContext,
    request: Request,
    *,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    permission: str | None = None,
    status_code: int = 400,
    message: str,
) -> None:
    audit_store.record(
        context,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        permission=permission,
        outcome="error",
        request_method=request.method,
        request_path=request.url.path,
        status_code=status_code,
        details={"message": message},
    )


def require_config_permission(
    context: SecurityContext,
    request: Request,
    *,
    domain: str,
    mode: str,
    action: str,
) -> str:
    domain_config = CONFIG_DOMAINS.get(domain)
    if not domain_config:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "config_domain_unknown",
                "message": f"Неизвестный домен конфигурации: {domain}",
            },
        )
    permission = domain_config.manage_permission if mode == "manage" else domain_config.read_permission
    try:
        security.require_permission(context, permission)
    except PermissionDenied as error:
        audit_store.record(
            context,
            action=action,
            resource_type="config",
            resource_id=domain,
            permission=permission,
            outcome="denied",
            request_method=request.method,
            request_path=request.url.path,
            status_code=403,
            details={"message": str(error)},
        )
        raise HTTPException(
            status_code=403,
            detail={
                "code": "permission_denied",
                "message": str(error),
            },
        ) from error
    return permission


def config_error_response(error: Exception) -> HTTPException:
    if isinstance(error, ConfigDraftNotFound):
        return HTTPException(
            status_code=404,
            detail={
                "code": "config_draft_not_found",
                "message": f"Черновик конфигурации не найден: {error}",
            },
        )
    if isinstance(error, ConfigVersionNotFound):
        return HTTPException(
            status_code=404,
            detail={
                "code": "config_version_not_found",
                "message": f"Версия конфигурации не найдена: {error}",
            },
        )
    return HTTPException(
        status_code=400,
        detail={
            "code": "config_registry_error",
            "message": str(error),
        },
    )


def build_config_regression(
    draft: dict[str, Any],
    *,
    operator_id: str,
    limit: int | None = None,
) -> dict[str, Any]:
    validation = draft.get("validation")
    if validation is None or validation.get("status") != "valid":
        return {
            "schema_version": "1.0",
            "domain": draft["domain"],
            "status": "failed",
            "run_at": utc_now(),
            "gates": [
                {
                    "gate_id": "validation_required",
                    "status": "failed",
                    "message": "Перед регрессионной проверкой черновик должен пройти валидацию.",
                }
            ],
        }

    evaluation_cases = workflow.list_evaluation_cases()
    if not evaluation_cases:
        return {
            "schema_version": "1.0",
            "domain": draft["domain"],
            "status": "skipped",
            "run_at": utc_now(),
            "gates": [
                {
                    "gate_id": "evaluation_dataset",
                    "status": "skipped",
                    "message": "Подготовленный набор оценочных кейсов пуст; активация разрешена как безопасный bootstrap.",
                }
            ],
        }

    result = workflow.run_evaluation(operator_id=operator_id, limit=limit)
    failed = int(result.get("summary", {}).get("failed", 0))
    status = "failed" if failed else "passed"
    return {
        "schema_version": "1.0",
        "domain": draft["domain"],
        "status": status,
        "run_at": result["run"]["started_at"],
        "run_id": result["run"]["run_id"],
        "summary": result.get("summary", {}),
        "gates": [
            {
                "gate_id": "evaluation_dataset",
                "status": status,
                "message": "Подготовленный набор оценочных кейсов выполнен.",
            }
        ],
    }


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/operator")
def operator_ui() -> FileResponse:
    return FileResponse(OPERATOR_UI_ROOT / "index.html")


@app.get("/operator/scenarios")
def operator_scenarios(
    context: SecurityContext = Depends(
        permission_dependency(
            "cases.operate",
            action="operator.scenarios.read",
            resource_type="scenario",
        )
    ),
) -> dict[str, Any]:
    _ = context
    return config_store.scenario_overview()


@app.get("/operator/scenarios/{scenario_id}")
def operator_scenario_detail(
    scenario_id: str,
    context: SecurityContext = Depends(
        permission_dependency(
            "cases.operate",
            action="operator.scenarios.detail.read",
            resource_type="scenario",
        )
    ),
) -> dict[str, Any]:
    _ = context
    try:
        return config_store.scenario_detail(scenario_id)
    except ConfigRegistryError as error:
        raise config_error_response(error) from error


@app.post("/operator/scenarios/{scenario_id}/simulate")
def operator_simulate_scenario(
    scenario_id: str,
    request: OperatorScenarioSimulationRequest,
    http_request: Request,
    context: SecurityContext = Depends(
        permission_dependency(
            "cases.operate",
            action="operator.scenarios.simulate",
            resource_type="scenario",
        )
    ),
) -> dict[str, Any]:
    try:
        result = config_store.simulate_scenario(
            scenario_id,
            text=request.text,
            provided_slots=request.provided_slots,
        )
        audit_success(
            context,
            http_request,
            action="operator.scenarios.simulate",
            resource_type="scenario",
            resource_id=scenario_id,
            permission="cases.operate",
            details={
                "operator_id": request.operator_id,
                "dry_run": True,
                "final_decision": result["final_decision"],
            },
        )
        return result
    except ConfigRegistryError as error:
        raise config_error_response(error) from error


@app.get("/admin")
def admin_ui() -> FileResponse:
    return FileResponse(ADMIN_UI_ROOT / "index.html")


@app.post("/tickets/analyze")
def analyze_ticket(
    request: TicketAnalyzeRequest,
    http_request: Request,
    context: SecurityContext = Depends(
        permission_dependency(
            "cases.operate",
            action="tickets.analyze",
            resource_type="case",
        )
    ),
) -> dict[str, Any]:
    try:
        analysis = workflow.analyze(model_to_dict(request))
        audit_success(
            context,
            http_request,
            action="tickets.analyze",
            resource_type="case",
            resource_id=analysis.get("case_id"),
            permission="cases.operate",
            details={"ticket_id": analysis.get("ticket_id")},
        )
        return analysis
    except ContractValidationError as error:
        raise HTTPException(
            status_code=400,
            detail={
                "contract_name": error.contract_name,
                "errors": error.errors,
            },
        ) from error


@app.post("/cases")
def create_case(
    request: TicketAnalyzeRequest,
    http_request: Request,
    context: SecurityContext = Depends(
        permission_dependency(
            "cases.operate",
            action="cases.create",
            resource_type="case",
        )
    ),
) -> dict[str, Any]:
    try:
        analysis = workflow.analyze(model_to_dict(request))
        audit_success(
            context,
            http_request,
            action="cases.create",
            resource_type="case",
            resource_id=analysis.get("case_id"),
            permission="cases.operate",
            details={"ticket_id": analysis.get("ticket_id")},
        )
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
def get_case(
    case_id: str,
    context: SecurityContext = Depends(
        permission_dependency(
            "cases.read",
            action="cases.read",
            resource_type="case",
        )
    ),
) -> dict[str, Any]:
    _ = context
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
def get_case_timeline(
    case_id: str,
    context: SecurityContext = Depends(
        permission_dependency(
            "cases.read",
            action="cases.timeline.read",
            resource_type="case",
        )
    ),
) -> dict[str, Any]:
    _ = context
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
def dispatch_tool(
    request: ToolDispatchRequest,
    http_request: Request,
    context: SecurityContext = Depends(
        permission_dependency(
            "tools.manage",
            action="tools.dispatch",
            resource_type="tool",
        )
    ),
) -> dict[str, Any]:
    if request.approved_by_operator:
        audit_error(
            context,
            http_request,
            action="tools.dispatch",
            resource_type="tool",
            resource_id=request.action.get("tool_name"),
            permission="tools.manage",
            status_code=400,
            message="Действия с согласованием оператора должны выполняться через approval endpoint.",
        )
        raise HTTPException(
            status_code=400,
            detail={
                "code": "approval_endpoint_required",
                "message": "Действия с согласованием оператора должны выполняться через /approvals/{approval_id}/decision.",
            },
        )
    try:
        result = workflow.dispatch_tool(
            request.action,
            request.policy_result,
            case_id=request.case_id,
            ticket_id=request.ticket_id,
            approved_by_operator=request.approved_by_operator,
            operator_id=request.operator_id,
        )
        audit_success(
            context,
            http_request,
            action="tools.dispatch",
            resource_type="tool",
            resource_id=result["invocation"]["tool_name"],
            permission="tools.manage",
            details={
                "case_id": result["invocation"].get("case_id"),
                "invocation_id": result["invocation"].get("invocation_id"),
                "status": result["tool_result"].get("status"),
            },
        )
        return result
    except ContractValidationError as error:
        audit_error(
            context,
            http_request,
            action="tools.dispatch",
            resource_type="tool",
            resource_id=request.action.get("tool_name"),
            permission="tools.manage",
            status_code=400,
            message="Вызов инструмента не прошел валидацию контракта.",
        )
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
    http_request: Request,
    context: SecurityContext = Depends(callback_context_dependency),
) -> dict[str, Any]:
    payload = {
        key: value
        for key, value in model_to_dict(request).items()
        if value is not None
    }
    if payload["endpoint_id"] != endpoint_id:
        audit_error(
            context,
            http_request,
            action="callbacks.receive",
            resource_type="integration_endpoint",
            resource_id=endpoint_id,
            permission="callbacks.write",
            status_code=400,
            message="endpoint_id в callback не совпадает с URL path.",
        )
        raise HTTPException(
            status_code=400,
            detail={
                "code": "endpoint_id_mismatch",
                "message": "endpoint_id в callback должен совпадать с URL path.",
            },
        )
    try:
        result = workflow.handle_integration_callback(payload)
        audit_success(
            context,
            http_request,
            action="callbacks.receive",
            resource_type="integration_endpoint",
            resource_id=endpoint_id,
            permission="callbacks.write",
            details={
                "case_id": result["case"].get("case_id"),
                "invocation_id": payload.get("invocation_id"),
                "status": payload.get("status"),
            },
        )
        return result
    except CaseNotFound as error:
        audit_error(
            context,
            http_request,
            action="callbacks.receive",
            resource_type="integration_endpoint",
            resource_id=endpoint_id,
            permission="callbacks.write",
            status_code=404,
            message=str(error),
        )
        raise HTTPException(
            status_code=404,
            detail={
                "code": "case_not_found",
                "message": f"Кейс не найден по корреляции callback: {error}",
            },
        ) from error
    except (ContractValidationError, ValueError) as error:
        audit_error(
            context,
            http_request,
            action="callbacks.receive",
            resource_type="integration_endpoint",
            resource_id=endpoint_id,
            permission="callbacks.write",
            status_code=400,
            message=str(error),
        )
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
def get_approval(
    approval_id: str,
    context: SecurityContext = Depends(
        permission_dependency(
            "cases.read",
            action="approvals.read",
            resource_type="approval",
        )
    ),
) -> dict[str, Any]:
    _ = context
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
def list_ticket_approvals(
    ticket_id: str,
    context: SecurityContext = Depends(
        permission_dependency(
            "cases.read",
            action="approvals.list",
            resource_type="approval",
        )
    ),
) -> dict[str, Any]:
    _ = context
    return {
        "schema_version": "1.0",
        "ticket_id": ticket_id,
        "approvals": workflow.list_ticket_action_gates(ticket_id),
    }


@app.post("/approvals/{approval_id}/decision")
def decide_approval(
    approval_id: str,
    request: ApprovalDecisionRequest,
    http_request: Request,
    context: SecurityContext = Depends(
        permission_dependency(
            "approvals.decide",
            action="approvals.decide",
            resource_type="approval",
        )
    ),
) -> dict[str, Any]:
    try:
        payload = {
            key: value
            for key, value in model_to_dict(request).items()
            if value is not None
        }
        result = workflow.decide_action_gate(approval_id, payload)
        audit_success(
            context,
            http_request,
            action="approvals.decide",
            resource_type="approval",
            resource_id=approval_id,
            permission="approvals.decide",
            details={
                "decision": payload.get("decision"),
                "operator_id": payload.get("operator_id"),
                "case_id": result.get("case", {}).get("case_id"),
            },
        )
        return result
    except ActionGateNotFound as error:
        audit_error(
            context,
            http_request,
            action="approvals.decide",
            resource_type="approval",
            resource_id=approval_id,
            permission="approvals.decide",
            status_code=404,
            message=str(error),
        )
        raise HTTPException(
            status_code=404,
            detail={
                "code": "approval_not_found",
                "message": f"Согласование не найдено: {approval_id}",
            },
        ) from error
    except ActionGateConflict as error:
        audit_error(
            context,
            http_request,
            action="approvals.decide",
            resource_type="approval",
            resource_id=approval_id,
            permission="approvals.decide",
            status_code=409,
            message=str(error),
        )
        raise HTTPException(
            status_code=409,
            detail={
                "code": "approval_conflict",
                "message": str(error),
            },
        ) from error
    except ContractValidationError as error:
        audit_error(
            context,
            http_request,
            action="approvals.decide",
            resource_type="approval",
            resource_id=approval_id,
            permission="approvals.decide",
            status_code=400,
            message="Решение по согласованию не прошло валидацию контракта.",
        )
        raise HTTPException(
            status_code=400,
            detail={
                "contract_name": error.contract_name,
                "errors": error.errors,
            },
        ) from error


@app.post("/knowledge/rebuild")
def rebuild_knowledge(
    request: KnowledgeRebuildRequest,
    http_request: Request,
    context: SecurityContext = Depends(
        permission_dependency(
            "knowledge.manage",
            action="knowledge.rebuild",
            resource_type="knowledge_index",
        )
    ),
) -> dict[str, Any]:
    try:
        result = workflow.rebuild_knowledge(request.operator_id)
        audit_success(
            context,
            http_request,
            action="knowledge.rebuild",
            resource_type="knowledge_index",
            resource_id=result.get("index_id"),
            permission="knowledge.manage",
            details={
                "operator_id": request.operator_id,
                "status": result.get("status"),
                "document_count": result.get("document_count"),
            },
        )
        return result
    except ContractValidationError as error:
        audit_error(
            context,
            http_request,
            action="knowledge.rebuild",
            resource_type="knowledge_index",
            permission="knowledge.manage",
            status_code=400,
            message="Перестроение базы знаний не прошло валидацию контракта.",
        )
        raise HTTPException(
            status_code=400,
            detail={
                "contract_name": error.contract_name,
                "errors": error.errors,
            },
        ) from error


@app.get("/knowledge/status")
def knowledge_status(
    context: SecurityContext = Depends(
        permission_dependency(
            "knowledge.read",
            action="knowledge.status.read",
            resource_type="knowledge_index",
        )
    ),
) -> dict[str, Any]:
    _ = context
    return workflow.knowledge_status()


@app.get("/admin/dashboard")
def admin_dashboard(
    context: SecurityContext = Depends(
        permission_dependency(
            "audit.read",
            action="admin.dashboard.read",
            resource_type="admin_dashboard",
        )
    ),
) -> dict[str, Any]:
    _ = context
    return workflow.admin_dashboard()


@app.get("/admin/knowledge/status")
def admin_knowledge_status(
    context: SecurityContext = Depends(
        permission_dependency(
            "knowledge.read",
            action="admin.knowledge.status.read",
            resource_type="knowledge_index",
        )
    ),
) -> dict[str, Any]:
    _ = context
    return workflow.knowledge_status()


@app.get("/admin/knowledge/sources")
def admin_knowledge_sources(
    context: SecurityContext = Depends(
        permission_dependency(
            "knowledge.read",
            action="admin.knowledge.sources.read",
            resource_type="knowledge_source",
        )
    ),
) -> dict[str, Any]:
    _ = context
    return workflow.knowledge_sources()


@app.post("/admin/knowledge/rebuild")
def admin_rebuild_knowledge(
    request: KnowledgeRebuildRequest,
    http_request: Request,
    context: SecurityContext = Depends(
        permission_dependency(
            "knowledge.manage",
            action="admin.knowledge.rebuild",
            resource_type="knowledge_index",
        )
    ),
) -> dict[str, Any]:
    try:
        result = workflow.rebuild_knowledge(request.operator_id)
        audit_success(
            context,
            http_request,
            action="admin.knowledge.rebuild",
            resource_type="knowledge_index",
            resource_id=result.get("index_id"),
            permission="knowledge.manage",
            details={
                "operator_id": request.operator_id,
                "status": result.get("status"),
                "document_count": result.get("document_count"),
            },
        )
        return result
    except ContractValidationError as error:
        audit_error(
            context,
            http_request,
            action="admin.knowledge.rebuild",
            resource_type="knowledge_index",
            permission="knowledge.manage",
            status_code=400,
            message="Перестроение базы знаний не прошло валидацию контракта.",
        )
        raise HTTPException(
            status_code=400,
            detail={
                "contract_name": error.contract_name,
                "errors": error.errors,
            },
        ) from error


@app.get("/admin/knowledge/chunks")
def admin_knowledge_chunks(
    source_id: str | None = None,
    limit: int = Query(default=50, ge=0, le=200),
    context: SecurityContext = Depends(
        permission_dependency(
            "knowledge.read",
            action="admin.knowledge.chunks.read",
            resource_type="knowledge_chunk",
        )
    ),
) -> dict[str, Any]:
    _ = context
    return workflow.knowledge_chunks(source_id=source_id, limit=limit)


@app.post("/admin/knowledge/retrieval/test")
def admin_test_retrieval(
    request: AdminRetrievalTestRequest,
    context: SecurityContext = Depends(
        permission_dependency(
            "knowledge.read",
            action="admin.knowledge.retrieval.test",
            resource_type="knowledge_index",
        )
    ),
) -> dict[str, Any]:
    _ = context
    try:
        return workflow.test_retrieval(model_to_dict(request))
    except ContractValidationError as error:
        raise HTTPException(
            status_code=400,
            detail={
                "contract_name": error.contract_name,
                "errors": error.errors,
            },
        ) from error


@app.get("/admin/catalog")
def admin_catalog(
    context: SecurityContext = Depends(
        permission_dependency(
            "tools.read",
            action="admin.catalog.read",
            resource_type="catalog",
        )
    ),
) -> dict[str, Any]:
    _ = context
    return workflow.catalog_inventory()


@app.get("/admin/catalog/tools")
def admin_tools_catalog(
    context: SecurityContext = Depends(
        permission_dependency(
            "tools.read",
            action="admin.catalog.tools.read",
            resource_type="tool",
        )
    ),
) -> dict[str, Any]:
    _ = context
    return workflow.contracts.tool_catalog


@app.get("/admin/catalog/integration-endpoints")
def admin_integration_endpoint_catalog(
    context: SecurityContext = Depends(
        permission_dependency(
            "tools.read",
            action="admin.catalog.integration_endpoints.read",
            resource_type="integration_endpoint",
        )
    ),
) -> dict[str, Any]:
    _ = context
    return workflow.contracts.integration_endpoint_catalog


@app.get("/admin/catalog/workflow")
def admin_workflow_catalog(
    context: SecurityContext = Depends(
        permission_dependency(
            "workflow.read",
            action="admin.catalog.workflow.read",
            resource_type="workflow",
        )
    ),
) -> dict[str, Any]:
    _ = context
    return {
        "schema_version": "1.0",
        "state_catalog": workflow.contracts.workflow_state_catalog,
        "transition_rules": workflow.contracts.workflow_transition_rules,
    }


@app.get("/admin/models/config")
def admin_model_config(
    context: SecurityContext = Depends(
        permission_dependency(
            "models.read",
            action="admin.models.config.read",
            resource_type="model_config",
        )
    ),
) -> dict[str, Any]:
    _ = context
    return workflow.model_config()


@app.post("/admin/models/secrets")
def admin_model_secret_update(
    payload: AdminModelSecretUpdateRequest,
    request: Request,
    context: SecurityContext = Depends(
        permission_dependency(
            "models.manage",
            action="admin.models.secret.update",
            resource_type="model_secret",
        )
    ),
) -> dict[str, Any]:
    try:
        set_local_env_value(payload.env_name, payload.secret_value)
    except LocalEnvError as error:
        audit_store.record(
            context,
            action="admin.models.secret.update",
            resource_type="model_secret",
            resource_id=payload.provider_id,
            permission="models.manage",
            outcome="error",
            request_method=request.method,
            request_path=str(request.url.path),
            status_code=400,
            details={
                "provider_id": payload.provider_id,
                "env_name": payload.env_name,
                "error": str(error),
            },
        )
        raise HTTPException(
            status_code=400,
            detail={
                "code": "local_env_error",
                "message": str(error),
            },
        ) from error

    audit_store.record(
        context,
        action="admin.models.secret.update",
        resource_type="model_secret",
        resource_id=payload.provider_id,
        permission="models.manage",
        outcome="success",
        request_method=request.method,
        request_path=str(request.url.path),
        status_code=200,
        details={
            "provider_id": payload.provider_id,
            "env_name": payload.env_name,
            "secret_value": "updated",
        },
    )
    return {
        "schema_version": "1.0",
        "provider_id": payload.provider_id,
        "env_name": payload.env_name,
        "configured": True,
        "display_value": "параметр скрыт",
        "requires_litellm_restart": True,
    }


@app.get("/admin/prompts/catalog")
def admin_prompts_catalog(
    context: SecurityContext = Depends(
        permission_dependency(
            "prompts.read",
            action="admin.prompts.catalog.read",
            resource_type="prompt",
        )
    ),
) -> dict[str, Any]:
    _ = context
    return workflow.prompt_catalog()


@app.get("/admin/scenarios")
def admin_scenarios(
    context: SecurityContext = Depends(
        permission_dependency(
            "workflow.read",
            action="admin.scenarios.read",
            resource_type="scenario",
        )
    ),
) -> dict[str, Any]:
    _ = context
    return config_store.scenario_overview()


@app.get("/admin/scenarios/{scenario_id}")
def admin_scenario_detail(
    scenario_id: str,
    context: SecurityContext = Depends(
        permission_dependency(
            "workflow.read",
            action="admin.scenarios.detail.read",
            resource_type="scenario",
        )
    ),
) -> dict[str, Any]:
    _ = context
    try:
        return config_store.scenario_detail(scenario_id)
    except ConfigRegistryError as error:
        raise config_error_response(error) from error


@app.post("/admin/scenarios/{scenario_id}/simulate")
def admin_simulate_scenario(
    scenario_id: str,
    request: AdminScenarioSimulationRequest,
    http_request: Request,
    context: SecurityContext = Depends(
        permission_dependency(
            "workflow.read",
            action="admin.scenarios.simulate",
            resource_type="scenario",
        )
    ),
) -> dict[str, Any]:
    try:
        result = config_store.simulate_scenario(
            scenario_id,
            text=request.text,
            provided_slots=request.provided_slots,
        )
        audit_success(
            context,
            http_request,
            action="admin.scenarios.simulate",
            resource_type="scenario",
            resource_id=scenario_id,
            permission="workflow.read",
            details={
                "operator_id": request.operator_id,
                "dry_run": True,
                "final_decision": result["final_decision"],
            },
        )
        return result
    except ConfigRegistryError as error:
        raise config_error_response(error) from error


@app.get("/admin/config/domains")
def admin_config_domains(
    context: SecurityContext = Depends(context_or_raise),
) -> dict[str, Any]:
    _ = context
    return config_store.domains()


@app.get("/admin/config/active/{domain}")
def admin_config_active(
    domain: str,
    http_request: Request,
    context: SecurityContext = Depends(context_or_raise),
) -> dict[str, Any]:
    require_config_permission(
        context,
        http_request,
        domain=domain,
        mode="read",
        action="admin.config.active.read",
    )
    try:
        return config_store.active_config(domain)
    except ConfigRegistryError as error:
        raise config_error_response(error) from error


@app.get("/admin/config/drafts")
def admin_config_drafts(
    http_request: Request,
    domain: str | None = None,
    limit: int = Query(default=100, ge=0, le=1000),
    context: SecurityContext = Depends(context_or_raise),
) -> dict[str, Any]:
    if domain:
        require_config_permission(
            context,
            http_request,
            domain=domain,
            mode="read",
            action="admin.config.drafts.read",
        )
    try:
        drafts = config_store.list_drafts(domain=domain, limit=limit)
    except ConfigRegistryError as error:
        raise config_error_response(error) from error
    return {
        "schema_version": "1.0",
        "draft_count": len(drafts),
        "drafts": drafts,
    }


@app.post("/admin/config/drafts")
def admin_create_config_draft(
    request: AdminConfigDraftCreateRequest,
    http_request: Request,
    context: SecurityContext = Depends(context_or_raise),
) -> dict[str, Any]:
    permission = require_config_permission(
        context,
        http_request,
        domain=request.domain,
        mode="manage",
        action="admin.config.draft.create",
    )
    try:
        draft = config_store.create_draft(
            domain=request.domain,
            payload=request.payload,
            created_by=request.operator_id,
            base_version_id=request.base_version_id,
        )
        audit_success(
            context,
            http_request,
            action="admin.config.draft.create",
            resource_type="config",
            resource_id=draft["draft_id"],
            permission=permission,
            details={
                "domain": request.domain,
                "operator_id": request.operator_id,
            },
        )
        return draft
    except ConfigRegistryError as error:
        audit_error(
            context,
            http_request,
            action="admin.config.draft.create",
            resource_type="config",
            resource_id=request.domain,
            permission=permission,
            status_code=400,
            message=str(error),
        )
        raise config_error_response(error) from error


@app.get("/admin/config/drafts/{draft_id}")
def admin_get_config_draft(
    draft_id: str,
    http_request: Request,
    context: SecurityContext = Depends(context_or_raise),
) -> dict[str, Any]:
    try:
        draft = config_store.require_draft(draft_id)
        require_config_permission(
            context,
            http_request,
            domain=draft["domain"],
            mode="read",
            action="admin.config.draft.read",
        )
        return draft
    except (ConfigDraftNotFound, ConfigRegistryError) as error:
        raise config_error_response(error) from error


@app.post("/admin/config/drafts/{draft_id}/validate")
def admin_validate_config_draft(
    draft_id: str,
    request: AdminConfigDraftActionRequest,
    http_request: Request,
    context: SecurityContext = Depends(context_or_raise),
) -> dict[str, Any]:
    try:
        draft = config_store.require_draft(draft_id)
        permission = require_config_permission(
            context,
            http_request,
            domain=draft["domain"],
            mode="manage",
            action="admin.config.draft.validate",
        )
        draft = config_store.validate_draft(draft_id)
        audit_success(
            context,
            http_request,
            action="admin.config.draft.validate",
            resource_type="config",
            resource_id=draft_id,
            permission=permission,
            details={
                "domain": draft["domain"],
                "operator_id": request.operator_id,
                "status": draft.get("validation", {}).get("status"),
            },
        )
        return draft
    except (ConfigDraftNotFound, ConfigRegistryError) as error:
        raise config_error_response(error) from error


@app.post("/admin/config/drafts/{draft_id}/regression")
def admin_regression_config_draft(
    draft_id: str,
    request: AdminConfigDraftActionRequest,
    http_request: Request,
    context: SecurityContext = Depends(context_or_raise),
) -> dict[str, Any]:
    try:
        draft = config_store.require_draft(draft_id)
        permission = require_config_permission(
            context,
            http_request,
            domain=draft["domain"],
            mode="manage",
            action="admin.config.draft.regression",
        )
        if draft.get("validation", {}).get("status") != "valid":
            draft = config_store.validate_draft(draft_id)
        regression = build_config_regression(
            draft,
            operator_id=request.operator_id,
            limit=request.limit,
        )
        draft = config_store.save_regression(draft_id, regression)
        audit_success(
            context,
            http_request,
            action="admin.config.draft.regression",
            resource_type="config",
            resource_id=draft_id,
            permission=permission,
            details={
                "domain": draft["domain"],
                "operator_id": request.operator_id,
                "status": regression["status"],
            },
        )
        return draft
    except (ConfigDraftNotFound, ConfigRegistryError) as error:
        raise config_error_response(error) from error


@app.post("/admin/config/drafts/{draft_id}/activate")
def admin_activate_config_draft(
    draft_id: str,
    request: AdminConfigDraftActionRequest,
    http_request: Request,
    context: SecurityContext = Depends(context_or_raise),
) -> dict[str, Any]:
    try:
        draft = config_store.require_draft(draft_id)
        permission = require_config_permission(
            context,
            http_request,
            domain=draft["domain"],
            mode="manage",
            action="admin.config.draft.activate",
        )
        version = config_store.activate_draft(draft_id, request.operator_id)
        workflow.apply_config_payload(version["domain"], version["payload"])
        audit_success(
            context,
            http_request,
            action="admin.config.draft.activate",
            resource_type="config",
            resource_id=version["version_id"],
            permission=permission,
            details={
                "domain": version["domain"],
                "draft_id": draft_id,
                "operator_id": request.operator_id,
                "previous_version_id": version.get("previous_version_id"),
            },
        )
        return version
    except (ConfigDraftNotFound, ConfigRegistryError) as error:
        raise config_error_response(error) from error


@app.get("/admin/config/versions")
def admin_config_versions(
    http_request: Request,
    domain: str | None = None,
    limit: int = Query(default=100, ge=0, le=1000),
    context: SecurityContext = Depends(context_or_raise),
) -> dict[str, Any]:
    if domain:
        require_config_permission(
            context,
            http_request,
            domain=domain,
            mode="read",
            action="admin.config.versions.read",
        )
    try:
        versions = config_store.list_versions(domain=domain, limit=limit)
    except ConfigRegistryError as error:
        raise config_error_response(error) from error
    return {
        "schema_version": "1.0",
        "version_count": len(versions),
        "versions": versions,
    }


@app.post("/admin/config/versions/{version_id}/rollback")
def admin_rollback_config_version(
    version_id: str,
    request: AdminConfigRollbackRequest,
    http_request: Request,
    context: SecurityContext = Depends(context_or_raise),
) -> dict[str, Any]:
    try:
        version = config_store.require_version(version_id)
        permission = require_config_permission(
            context,
            http_request,
            domain=version["domain"],
            mode="manage",
            action="admin.config.version.rollback",
        )
        result = config_store.rollback(
            domain=version["domain"],
            version_id=version_id,
            operator_id=request.operator_id,
        )
        workflow.apply_config_payload(version["domain"], version["payload"])
        audit_success(
            context,
            http_request,
            action="admin.config.version.rollback",
            resource_type="config",
            resource_id=version_id,
            permission=permission,
            details={
                "domain": version["domain"],
                "operator_id": request.operator_id,
            },
        )
        return result
    except (ConfigVersionNotFound, ConfigRegistryError) as error:
        raise config_error_response(error) from error


@app.get("/admin/n8n/workflows")
def admin_n8n_workflows(
    context: SecurityContext = Depends(
        permission_dependency(
            "tools.read",
            action="admin.n8n.workflows.read",
            resource_type="n8n_workflow",
        )
    ),
) -> dict[str, Any]:
    _ = context
    return workflow.n8n_workflow_catalog()


@app.post("/admin/n8n/workflows/{workflow_id}/restart")
def admin_restart_n8n_workflow(
    workflow_id: str,
    request: AdminN8nWorkflowOperationRequest,
    http_request: Request,
    context: SecurityContext = Depends(
        permission_dependency(
            "tools.manage",
            action="admin.n8n.workflow.restart",
            resource_type="n8n_workflow",
        )
    ),
) -> dict[str, Any]:
    audit_success(
        context,
        http_request,
        action="admin.n8n.workflow.restart",
        resource_type="n8n_workflow",
        resource_id=workflow_id,
        permission="tools.manage",
        details={
            "operator_id": request.operator_id,
            "execution_id": request.execution_id,
            "status": "unsupported_in_mvp",
        },
    )
    return {
        "schema_version": "1.0",
        "accepted": False,
        "workflow_id": workflow_id,
        "status": "unsupported",
        "message": "Перезапуск workflow требует рабочего n8n management API и остается отключенным в локальном MVP.",
    }


@app.post("/admin/n8n/workflows/{workflow_id}/cancel")
def admin_cancel_n8n_workflow(
    workflow_id: str,
    request: AdminN8nWorkflowOperationRequest,
    http_request: Request,
    context: SecurityContext = Depends(
        permission_dependency(
            "tools.manage",
            action="admin.n8n.workflow.cancel",
            resource_type="n8n_workflow",
        )
    ),
) -> dict[str, Any]:
    audit_success(
        context,
        http_request,
        action="admin.n8n.workflow.cancel",
        resource_type="n8n_workflow",
        resource_id=workflow_id,
        permission="tools.manage",
        details={
            "operator_id": request.operator_id,
            "execution_id": request.execution_id,
            "status": "unsupported_in_mvp",
        },
    )
    return {
        "schema_version": "1.0",
        "accepted": False,
        "workflow_id": workflow_id,
        "status": "unsupported",
        "message": "Отмена workflow требует рабочего n8n management API и остается отключенной в локальном MVP.",
    }


@app.post("/admin/evaluations/promote-feedback")
def admin_promote_feedback(
    request: AdminFeedbackPromotionRequest,
    http_request: Request,
    context: SecurityContext = Depends(
        permission_dependency(
            "evaluation.run",
            action="admin.evaluations.promote_feedback",
            resource_type="evaluation_case",
        )
    ),
) -> dict[str, Any]:
    result = workflow.promote_feedback_to_evaluation_cases(
        operator_id=request.operator_id,
        feedback_ids=request.feedback_ids,
    )
    audit_success(
        context,
        http_request,
        action="admin.evaluations.promote_feedback",
        resource_type="evaluation_case",
        permission="evaluation.run",
        details={
            "operator_id": request.operator_id,
            "requested_feedback_count": len(request.feedback_ids or []),
            "promoted_count": result.get("promoted_count"),
        },
    )
    return result


@app.get("/admin/evaluations/cases")
def admin_evaluation_cases(
    context: SecurityContext = Depends(
        permission_dependency(
            "evaluation.run",
            action="admin.evaluations.cases.read",
            resource_type="evaluation_case",
        )
    ),
) -> dict[str, Any]:
    _ = context
    cases = workflow.list_evaluation_cases()
    return {
        "schema_version": "1.0",
        "case_count": len(cases),
        "cases": cases,
    }


@app.get("/admin/feedback")
def admin_feedback(
    limit: int = Query(default=100, ge=0, le=1000),
    context: SecurityContext = Depends(
        permission_dependency(
            "evaluation.run",
            action="admin.feedback.read",
            resource_type="feedback",
        )
    ),
) -> dict[str, Any]:
    _ = context
    records = workflow.list_feedback(limit=limit)
    return {
        "schema_version": "1.0",
        "feedback_count": len(records),
        "feedback": records,
    }


@app.get("/admin/evaluations/runs")
def admin_evaluation_runs(
    limit: int = Query(default=100, ge=0, le=1000),
    context: SecurityContext = Depends(
        permission_dependency(
            "evaluation.run",
            action="admin.evaluations.runs.list",
            resource_type="evaluation_run",
        )
    ),
) -> dict[str, Any]:
    _ = context
    runs = workflow.list_evaluation_runs(limit=limit)
    return {
        "schema_version": "1.0",
        "run_count": len(runs),
        "runs": runs,
    }


@app.post("/admin/evaluations/run")
def admin_run_evaluation(
    request: AdminEvaluationRunRequest,
    http_request: Request,
    context: SecurityContext = Depends(
        permission_dependency(
            "evaluation.run",
            action="admin.evaluations.run",
            resource_type="evaluation_run",
        )
    ),
) -> dict[str, Any]:
    result = workflow.run_evaluation(
        operator_id=request.operator_id,
        case_ids=request.case_ids,
        limit=request.limit,
    )
    audit_success(
        context,
        http_request,
        action="admin.evaluations.run",
        resource_type="evaluation_run",
        resource_id=result.get("run", {}).get("run_id"),
        permission="evaluation.run",
        details={
            "operator_id": request.operator_id,
            "requested_case_count": len(request.case_ids or []),
            "status": result.get("run", {}).get("status"),
            "summary": result.get("summary"),
        },
    )
    return result


@app.get("/admin/evaluations/runs/{run_id}")
def admin_get_evaluation_run(
    run_id: str,
    context: SecurityContext = Depends(
        permission_dependency(
            "evaluation.run",
            action="admin.evaluations.runs.read",
            resource_type="evaluation_run",
        )
    ),
) -> dict[str, Any]:
    _ = context
    run = workflow.get_evaluation_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "evaluation_run_not_found",
                "message": f"Запуск оценки не найден: {run_id}",
            },
        )
    return run


@app.post("/feedback")
def submit_feedback(
    request: FeedbackRequest,
    http_request: Request,
    context: SecurityContext = Depends(
        permission_dependency(
            "feedback.write",
            action="feedback.submit",
            resource_type="feedback",
        )
    ),
) -> dict[str, Any]:
    try:
        payload = {
            key: value
            for key, value in model_to_dict(request).items()
            if value is not None
        }
        result = workflow.submit_feedback(payload)
        audit_success(
            context,
            http_request,
            action="feedback.submit",
            resource_type="feedback",
            resource_id=result.get("feedback_id"),
            permission="feedback.write",
            details={
                "ticket_id": result.get("ticket_id"),
                "rating": result.get("rating"),
                "operator_id": result.get("operator_id"),
            },
        )
        return result
    except ContractValidationError as error:
        audit_error(
            context,
            http_request,
            action="feedback.submit",
            resource_type="feedback",
            permission="feedback.write",
            status_code=400,
            message="Обратная связь не прошла валидацию контракта.",
        )
        raise HTTPException(
            status_code=400,
            detail={
                "contract_name": error.contract_name,
                "errors": error.errors,
            },
        ) from error


@app.get("/tickets/{ticket_id}/feedback")
def list_ticket_feedback(
    ticket_id: str,
    context: SecurityContext = Depends(
        permission_dependency(
            "cases.read",
            action="feedback.list",
            resource_type="feedback",
        )
    ),
) -> dict[str, Any]:
    _ = context
    return {
        "schema_version": "1.0",
        "ticket_id": ticket_id,
        "feedback": workflow.list_ticket_feedback(ticket_id),
    }


@app.get("/feedback/export")
def export_feedback(
    context: SecurityContext = Depends(
        permission_dependency(
            "evaluation.run",
            action="feedback.export",
            resource_type="feedback",
        )
    ),
) -> PlainTextResponse:
    _ = context
    return PlainTextResponse(
        workflow.export_feedback_jsonl(),
        media_type="application/x-ndjson",
    )


@app.get("/admin/security/session")
def admin_security_session(
    context: SecurityContext = Depends(context_or_raise),
) -> dict[str, Any]:
    return security.session_info(context)


@app.get("/admin/security/catalog")
def admin_security_catalog(
    context: SecurityContext = Depends(
        permission_dependency(
            "security.manage",
            action="admin.security.catalog.read",
            resource_type="security_catalog",
        )
    ),
) -> dict[str, Any]:
    _ = context
    return security.sanitized_catalog()


@app.get("/admin/security/secret-references")
def admin_security_secret_references(
    context: SecurityContext = Depends(
        permission_dependency(
            "security.manage",
            action="admin.security.secret_references.read",
            resource_type="secret_reference",
        )
    ),
) -> dict[str, Any]:
    _ = context
    return security.secret_references()


@app.get("/admin/security/audit")
def admin_security_audit(
    limit: int = Query(default=100, ge=0, le=1000),
    outcome: str | None = None,
    actor_id: str | None = None,
    action: str | None = None,
    context: SecurityContext = Depends(
        permission_dependency(
            "audit.read",
            action="admin.security.audit.read",
            resource_type="audit_event",
        )
    ),
) -> dict[str, Any]:
    _ = context
    events = audit_store.list_all(
        limit=limit,
        outcome=outcome,
        actor_id=actor_id,
        action=action,
    )
    return {
        "schema_version": "1.0",
        "event_count": len(events),
        "events": events,
    }


@app.get("/admin/security/audit/summary")
def admin_security_audit_summary(
    context: SecurityContext = Depends(
        permission_dependency(
            "audit.read",
            action="admin.security.audit.summary.read",
            resource_type="audit_event",
        )
    ),
) -> dict[str, Any]:
    _ = context
    return audit_store.summary()
