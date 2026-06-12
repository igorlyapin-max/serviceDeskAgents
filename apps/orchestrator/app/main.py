from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .action_gates import ActionGateConflict, ActionGateNotFound, utc_now
from .cases import CaseNotFound
from .config_assistant import compile_attribute_resolution_step, compile_slot_autofill_profile
from .config_registry import (
    CONFIG_DOMAINS,
    ConfigDraftNotFound,
    ConfigRegistryError,
    ConfigStore,
    ConfigVersionNotFound,
)
from .contracts import ContractValidationError
from .debug_runtime import DebugRuntime, DebugRuntimeError
from .local_env import LocalEnvError, set_local_env_value
from .metrics import metrics
from .openapi_contracts import OpenApiContractError, preview_openapi_contract
from .processing import ExternalEventIdempotencyConflict, ProcessingConflict, ProcessingNotFound, ProcessingStore
from .runtime_guardrails import (
    RuntimeConfigurationError,
    configure_logging,
    is_production_environment,
    log_json,
    log_local_security_warnings,
    metrics_client_allowed,
    readiness_http_status,
    readiness_report,
    require_local_secret_write_allowed,
    security_headers,
    validate_startup_environment,
)
from .security import (
    AuditStore,
    CallbackTokenInvalid,
    PermissionDenied,
    RateLimitExceeded,
    SecurityContext,
    SecurityManager,
)
from .workflow import TicketWorkflow


configure_logging()
logger = logging.getLogger("servicedesk.orchestrator")
validate_startup_environment()
log_local_security_warnings(logger)


class TicketAnalyzeRequest(BaseModel):
    user: str | None = Field(default=None)
    service: str | None = Field(default=None)
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


class AdminOpenApiContractPreviewRequest(BaseModel):
    operator_id: str = Field(default="admin-1")
    endpoint_id: str | None = Field(default=None)
    endpoint: dict[str, Any] | None = Field(default=None)
    contract_source: dict[str, Any] | None = Field(default=None)


class AdminSlotAutofillCompileRequest(BaseModel):
    operator_id: str = Field(default="admin-1")
    instruction: str = Field(default="", max_length=4000)
    slot_schema_id: str = Field()
    react_call: str | None = Field(default=None)
    target_slots: list[str] | None = Field(default=None)


class AdminAttributeResolutionStepCompileRequest(BaseModel):
    operator_id: str = Field(default="admin-1")
    instruction: str = Field(default="", max_length=4000)
    scenario_id: str | None = Field(default=None)
    slot_schema_id: str | None = Field(default=None)
    react_call: str | None = Field(default=None)
    step_name: str | None = Field(default=None)
    previous_steps: list[dict[str, Any]] | None = Field(default=None)


class AdminScenarioSimulationRequest(BaseModel):
    text: str = Field()
    provided_slots: dict[str, Any] | None = Field(default=None)
    operator_id: str = Field(default="admin-1")
    run_mode: str | None = Field(default=None)
    allow_llm: bool | None = Field(default=None)
    allow_readonly_integrations: bool | None = Field(default=None)
    allow_mock_integrations: bool | None = Field(default=None)
    allow_action_with_approval: bool | None = Field(default=None)


class AdminModelSecretUpdateRequest(BaseModel):
    provider_id: str = Field(min_length=1, max_length=160)
    env_name: str = Field(min_length=1, max_length=160)
    secret_value: str = Field(min_length=1, max_length=8192, repr=False)


class AdminProcessingCommandRequest(BaseModel):
    operator_id: str = Field(default="admin-1")
    reason: str | None = Field(default=None)


class OperatorScenarioSimulationRequest(BaseModel):
    text: str = Field()
    provided_slots: dict[str, Any] | None = Field(default=None)
    operator_id: str = Field(default="operator-1")
    run_mode: str = Field(default="config_check")
    allow_llm: bool | None = Field(default=None)
    allow_readonly_integrations: bool | None = Field(default=None)
    allow_mock_integrations: bool | None = Field(default=None)
    allow_action_with_approval: bool | None = Field(default=None)


class DebugSimulationPrepareRequest(BaseModel):
    source: str = Field(default="scenario_profiles")
    scenario_ids: list[str] | None = Field(default=None)
    count_per_scenario: int = Field(default=1, ge=1, le=100)
    channel_id: str = Field(default="debug")
    seed: str | None = Field(default=None)
    include_wrong_department: bool = Field(default=False)
    mode: str = Field(default="dry_run")
    dry_run: bool = Field(default=True)
    contains_real_data: bool = Field(default=False)
    sanitized: bool = Field(default=False)


class DebugSimulationItemPatchRequest(BaseModel):
    patch: dict[str, Any] = Field(default_factory=dict)


class DebugSimulationStartRequest(BaseModel):
    operator_id: str = Field(default="admin-1")
    selected_item_ids: list[str] | None = Field(default=None)
    stop_on_mismatch: bool = Field(default=False)


class DebugEndpointCaptureStartRequest(BaseModel):
    endpoint_id: str = Field()
    operation_id: str = Field()
    operator_id: str = Field(default="admin-1")


class DebugEndpointCaptureStopRequest(BaseModel):
    session_id: str = Field()
    operator_id: str = Field(default="admin-1")


class DebugEndpointCaptureSanitizeRequest(BaseModel):
    operator_id: str = Field(default="admin-1")


class DebugEndpointCaptureCreateMockRequest(BaseModel):
    operator_id: str = Field(default="admin-1")
    example_name: str | None = Field(default=None)
    description: str | None = Field(default=None)
    tags: list[str] | None = Field(default=None)


class DebugEndpointCaptureMarkBrokenRequest(BaseModel):
    operator_id: str = Field(default="admin-1")
    reason: str | None = Field(default=None)


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


class ExternalEventRequest(BaseModel):
    schema_version: str = Field(default="1.0")
    event_id: str = Field()
    case_id: str = Field()
    ticket_id: str | None = Field(default=None)
    wait_id: str | None = Field(default=None)
    correlation_id: str = Field()
    source: str | None = Field(default=None)
    event_type: str = Field()
    status: str = Field()
    received_at: str | None = Field(default=None)
    idempotency_key: str = Field()
    result: dict[str, Any] | None = Field(default=None)
    error: dict[str, Any] | None = Field(default=None)
    attachments: list[dict[str, Any]] | None = Field(default=None)
    raw_reference: str | None = Field(default=None)
    metadata: dict[str, Any] | None = Field(default=None)


app = FastAPI(title="ServiceDesk AI Orchestrator", version="0.1.0")
workflow = TicketWorkflow()
config_store = ConfigStore(workflow.contracts)
workflow.attach_config_store(config_store)
processing_store = ProcessingStore(workflow.case_store)
debug_runtime = DebugRuntime(workflow, config_store, processing_store)
workflow.capture_recorder = debug_runtime
workflow.integration_dispatcher.capture_recorder = debug_runtime
security = SecurityManager(workflow.contracts)
audit_store = AuditStore(workflow.contracts)
OPERATOR_UI_ROOT = Path(__file__).resolve().parents[2] / "operator-ui" / "static"
ADMIN_UI_ROOT = Path(__file__).resolve().parents[2] / "admin-ui" / "static"


def ui_index_response(path: Path) -> FileResponse:
    response = FileResponse(path)
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.middleware("http")
async def request_context_and_security_headers(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or f"req-{uuid.uuid4().hex[:12]}"
    request.state.request_id = request_id
    started_at = time.monotonic()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception:
        log_json(
            logger,
            logging.ERROR,
            "http_request_failed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )
        raise
    finally:
        duration_ms = int((time.monotonic() - started_at) * 1000)
        log_json(
            logger,
            logging.INFO,
            "http_request_completed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            duration_ms=duration_ms,
        )
        metrics.increment(
            "http_requests_total",
            {"method": request.method, "path": request.url.path, "status": status_code},
        )
        metrics.observe(
            "http_request_duration_seconds",
            duration_ms / 1000,
            {"method": request.method, "path": request.url.path, "status": status_code},
        )
    response.headers["X-Request-ID"] = request_id
    forwarded_proto = request.headers.get("x-forwarded-proto", "").lower()
    https_enabled = request.url.scheme == "https" or forwarded_proto == "https"
    https_enabled = https_enabled or is_production_environment()
    for header, value in security_headers(https_enabled=https_enabled).items():
        response.headers.setdefault(header, value)
    return response


app.mount(
    "/operator/static",
    StaticFiles(directory=OPERATOR_UI_ROOT),
    name="operator-static",
)
app.mount(
    "/debug/static",
    StaticFiles(directory=OPERATOR_UI_ROOT),
    name="debug-static",
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


def request_id(request: Request) -> str | None:
    value = getattr(request.state, "request_id", None)
    return str(value) if value else None


def context_or_raise(request: Request) -> SecurityContext:
    context: SecurityContext | None = None
    try:
        context = security.context_from_headers(
            request.headers,
            ip_address=client_ip(request),
            request_id=request_id(request),
        )
        security.check_rate_limit(context)
        return context
    except RateLimitExceeded as error:
        audit_store.record(
            context or security.anonymous_context(ip_address=client_ip(request), request_id=request_id(request)),
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
            security.anonymous_context(ip_address=client_ip(request), request_id=request_id(request)),
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
            request_id=request_id(request),
        )
        security.check_rate_limit(context)
        security.require_permission(context, "callbacks.write")
        return context
    except CallbackTokenInvalid as error:
        audit_store.record(
            security.anonymous_context(
                actor_id=f"endpoint:{endpoint_id}",
                ip_address=client_ip(request),
                request_id=request_id(request),
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
                request_id=request_id(request),
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
                request_id=request_id(request),
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


def external_event_context_dependency(
    source: str,
    request: Request,
) -> SecurityContext:
    try:
        context = security.callback_context(
            request.headers,
            endpoint_id=source,
            ip_address=client_ip(request),
            request_id=request_id(request),
        )
        security.check_rate_limit(context)
        security.require_permission(context, "callbacks.write")
        return context
    except CallbackTokenInvalid as error:
        audit_store.record(
            security.anonymous_context(
                actor_id=f"endpoint:{source}",
                ip_address=client_ip(request),
                request_id=request_id(request),
            ),
            action="external_events.receive",
            resource_type="external_event_source",
            resource_id=source,
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
                actor_id=f"endpoint:{source}",
                ip_address=client_ip(request),
                request_id=request_id(request),
            ),
            action="security.rate_limit",
            resource_type="external_event_source",
            resource_id=source,
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
                actor_id=f"endpoint:{source}",
                ip_address=client_ip(request),
                request_id=request_id(request),
            ),
            action="external_events.receive",
            resource_type="external_event_source",
            resource_id=source,
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


def existing_callback_result(payload: dict[str, Any]) -> dict[str, Any] | None:
    invocation_id = payload.get("invocation_id")
    if not invocation_id:
        return None
    receipt = workflow.case_store.callback_receipt(invocation_id)
    if receipt:
        result = receipt.get("result", {})
        if isinstance(result, dict):
            duplicate = dict(result)
            duplicate.setdefault("schema_version", "1.0")
            duplicate.setdefault("accepted", True)
            duplicate["duplicate"] = True
            return duplicate
    record = workflow.case_store.by_correlation("invocation_id", invocation_id)
    if not record:
        return None
    tool_result = next(
        (
            item
            for item in record.get("tool_results", [])
            if item.get("invocation_id") == invocation_id
        ),
        None,
    )
    if not tool_result:
        return None
    return {
        "schema_version": "1.0",
        "accepted": True,
        "duplicate": True,
        "case": record,
        "tool_result": tool_result,
        "workflow_state": record.get("current_workflow_state"),
    }


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


def processing_error_response(error: Exception) -> HTTPException:
    if isinstance(error, ProcessingNotFound):
        return HTTPException(
            status_code=404,
            detail={
                "code": "processing_item_not_found",
                "message": f"Объект потока обработки не найден: {error}",
            },
        )
    if isinstance(error, CaseNotFound):
        return HTTPException(
            status_code=404,
            detail={
                "code": "case_not_found",
                "message": f"Кейс не найден: {error}",
            },
        )
    if isinstance(error, ProcessingConflict):
        return HTTPException(
            status_code=409,
            detail={
                "code": "processing_conflict",
                "message": str(error),
            },
        )
    return HTTPException(
        status_code=400,
        detail={
            "code": "processing_error",
            "message": str(error),
        },
    )


def debug_error_response(error: Exception) -> HTTPException:
    if isinstance(error, DebugRuntimeError):
        return HTTPException(
            status_code=400,
            detail={
                "code": "debug_runtime_error",
                "message": str(error),
            },
        )
    if isinstance(error, ConfigRegistryError):
        return config_error_response(error)
    if isinstance(error, (ProcessingConflict, ProcessingNotFound, CaseNotFound, ValueError)):
        return processing_error_response(error)
    return HTTPException(
        status_code=500,
        detail={
            "code": "debug_runtime_error",
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


@app.get("/readyz")
def readyz(response: Response) -> dict[str, Any]:
    report = readiness_report(
        config_store=config_store,
        workflow=workflow,
        processing_store=processing_store,
    )
    response.status_code = readiness_http_status(report)
    return report


@app.get("/metrics")
def metrics_endpoint(request: Request) -> PlainTextResponse:
    ip_address = client_ip(request)
    if not metrics_client_allowed(ip_address):
        message = "Доступ к /metrics запрещен для этого IP."
        log_json(
            logger,
            logging.WARNING,
            "metrics_access_denied",
            request_id=request_id(request),
            ip_address=ip_address,
            path=request.url.path,
        )
        audit_store.record(
            security.anonymous_context(ip_address=ip_address, request_id=request_id(request)),
            action="metrics.read",
            resource_type="metrics",
            outcome="denied",
            request_method=request.method,
            request_path=request.url.path,
            status_code=403,
            details={"message": message},
        )
        raise HTTPException(
            status_code=403,
            detail={
                "code": "metrics_access_denied",
                "message": message,
            },
        )
    return PlainTextResponse(metrics.render_prometheus(), media_type="text/plain; version=0.0.4")


@app.get("/operator")
def operator_ui() -> FileResponse:
    return ui_index_response(OPERATOR_UI_ROOT / "index.html")


@app.get("/debug")
def debug_ui() -> FileResponse:
    return ui_index_response(OPERATOR_UI_ROOT / "index.html")


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
            run_mode=request.run_mode,
            allow_llm=request.allow_llm,
            allow_readonly_integrations=request.allow_readonly_integrations,
            allow_mock_integrations=request.allow_mock_integrations,
            allow_action_with_approval=request.allow_action_with_approval,
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


@app.get("/debug/scenarios")
def debug_scenarios(
    context: SecurityContext = Depends(
        permission_dependency(
            "cases.operate",
            action="debug.scenarios.read",
            resource_type="scenario",
        )
    ),
) -> dict[str, Any]:
    _ = context
    return config_store.scenario_overview()


@app.get("/debug/scenarios/{scenario_id}")
def debug_scenario_detail(
    scenario_id: str,
    context: SecurityContext = Depends(
        permission_dependency(
            "cases.operate",
            action="debug.scenarios.detail.read",
            resource_type="scenario",
        )
    ),
) -> dict[str, Any]:
    _ = context
    try:
        return config_store.scenario_detail(scenario_id)
    except ConfigRegistryError as error:
        raise config_error_response(error) from error


@app.post("/debug/scenarios/{scenario_id}/simulate")
def debug_simulate_scenario(
    scenario_id: str,
    request: OperatorScenarioSimulationRequest,
    http_request: Request,
    context: SecurityContext = Depends(
        permission_dependency(
            "cases.operate",
            action="debug.scenarios.simulate",
            resource_type="scenario",
        )
    ),
) -> dict[str, Any]:
    try:
        result = config_store.simulate_scenario(
            scenario_id,
            text=request.text,
            provided_slots=request.provided_slots,
            run_mode=request.run_mode,
            allow_llm=request.allow_llm,
            allow_readonly_integrations=request.allow_readonly_integrations,
            allow_mock_integrations=request.allow_mock_integrations,
            allow_action_with_approval=request.allow_action_with_approval,
        )
        audit_success(
            context,
            http_request,
            action="debug.scenarios.simulate",
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


@app.get("/debug/simulations/profiles")
def debug_simulation_profiles(
    context: SecurityContext = Depends(
        permission_dependency(
            "cases.operate",
            action="debug.simulations.profiles.read",
            resource_type="debug_simulation",
        )
    ),
) -> dict[str, Any]:
    _ = context
    try:
        return debug_runtime.simulation_profiles()
    except (DebugRuntimeError, ConfigRegistryError) as error:
        raise debug_error_response(error) from error


@app.get("/debug/simulations")
def debug_simulations(
    limit: int = Query(default=50, ge=1, le=200),
    context: SecurityContext = Depends(
        permission_dependency(
            "cases.operate",
            action="debug.simulations.read",
            resource_type="debug_simulation",
        )
    ),
) -> dict[str, Any]:
    _ = context
    return debug_runtime.list_simulations(limit=limit)


@app.post("/debug/simulations/prepare")
def debug_simulation_prepare(
    request: DebugSimulationPrepareRequest,
    http_request: Request,
    context: SecurityContext = Depends(
        permission_dependency(
            "cases.operate",
            action="debug.simulations.prepare",
            resource_type="debug_simulation",
        )
    ),
) -> dict[str, Any]:
    try:
        result = debug_runtime.prepare_simulation(model_to_dict(request))
        audit_success(
            context,
            http_request,
            action="debug.simulations.prepare",
            resource_type="debug_simulation",
            resource_id=result["run"]["run_id"],
            permission="cases.operate",
            details={"item_count": len(result["items"]), "source": result["run"]["source"]},
        )
        return result
    except (DebugRuntimeError, ConfigRegistryError) as error:
        raise debug_error_response(error) from error


@app.get("/debug/simulations/{run_id}")
def debug_simulation_detail(
    run_id: str,
    context: SecurityContext = Depends(
        permission_dependency(
            "cases.operate",
            action="debug.simulations.detail.read",
            resource_type="debug_simulation",
        )
    ),
) -> dict[str, Any]:
    _ = context
    try:
        return debug_runtime.simulation_detail(run_id)
    except DebugRuntimeError as error:
        raise debug_error_response(error) from error


@app.get("/debug/simulations/{run_id}/items")
def debug_simulation_items(
    run_id: str,
    context: SecurityContext = Depends(
        permission_dependency(
            "cases.operate",
            action="debug.simulations.items.read",
            resource_type="debug_simulation_item",
        )
    ),
) -> dict[str, Any]:
    _ = context
    try:
        return debug_runtime.list_simulation_items(run_id)
    except DebugRuntimeError as error:
        raise debug_error_response(error) from error


@app.patch("/debug/simulations/{run_id}/items/{item_id}")
def debug_simulation_item_patch(
    run_id: str,
    item_id: str,
    request: DebugSimulationItemPatchRequest,
    http_request: Request,
    context: SecurityContext = Depends(
        permission_dependency(
            "cases.operate",
            action="debug.simulations.item.update",
            resource_type="debug_simulation_item",
        )
    ),
) -> dict[str, Any]:
    try:
        result = debug_runtime.patch_simulation_item(run_id, item_id, request.patch)
        audit_success(
            context,
            http_request,
            action="debug.simulations.item.update",
            resource_type="debug_simulation_item",
            resource_id=item_id,
            permission="cases.operate",
            details={"run_id": run_id},
        )
        return result
    except DebugRuntimeError as error:
        raise debug_error_response(error) from error


@app.post("/debug/simulations/{run_id}/start")
def debug_simulation_start(
    run_id: str,
    request: DebugSimulationStartRequest,
    http_request: Request,
    context: SecurityContext = Depends(
        permission_dependency(
            "cases.operate",
            action="debug.simulations.start",
            resource_type="debug_simulation",
        )
    ),
) -> dict[str, Any]:
    try:
        result = debug_runtime.start_simulation(run_id, model_to_dict(request))
        audit_success(
            context,
            http_request,
            action="debug.simulations.start",
            resource_type="debug_simulation",
            resource_id=run_id,
            permission="cases.operate",
            details={"operator_id": request.operator_id, "counters": result["run"].get("counters")},
        )
        return result
    except (DebugRuntimeError, ConfigRegistryError, ProcessingConflict, ProcessingNotFound, CaseNotFound, ValueError) as error:
        raise debug_error_response(error) from error


@app.post("/debug/simulations/{run_id}/pause")
def debug_simulation_pause(
    run_id: str,
    context: SecurityContext = Depends(
        permission_dependency(
            "cases.operate",
            action="debug.simulations.pause",
            resource_type="debug_simulation",
        )
    ),
) -> dict[str, Any]:
    _ = context
    try:
        return debug_runtime.pause_simulation(run_id)
    except DebugRuntimeError as error:
        raise debug_error_response(error) from error


@app.post("/debug/simulations/{run_id}/cancel")
def debug_simulation_cancel(
    run_id: str,
    context: SecurityContext = Depends(
        permission_dependency(
            "cases.operate",
            action="debug.simulations.cancel",
            resource_type="debug_simulation",
        )
    ),
) -> dict[str, Any]:
    _ = context
    try:
        return debug_runtime.cancel_simulation(run_id)
    except DebugRuntimeError as error:
        raise debug_error_response(error) from error


@app.get("/debug/simulations/{run_id}/trace")
def debug_simulation_trace(
    run_id: str,
    context: SecurityContext = Depends(
        permission_dependency(
            "cases.operate",
            action="debug.simulations.trace.read",
            resource_type="debug_simulation",
        )
    ),
) -> dict[str, Any]:
    _ = context
    try:
        return debug_runtime.simulation_trace(run_id)
    except (DebugRuntimeError, ProcessingConflict, ProcessingNotFound, CaseNotFound, ValueError) as error:
        raise debug_error_response(error) from error


@app.get("/debug/cases/{case_id}/trace")
def debug_case_trace(
    case_id: str,
    context: SecurityContext = Depends(
        permission_dependency(
            "cases.operate",
            action="debug.case.trace.read",
            resource_type="case",
        )
    ),
) -> dict[str, Any]:
    _ = context
    try:
        return debug_runtime.case_trace(case_id)
    except (ProcessingConflict, ProcessingNotFound, CaseNotFound, ValueError) as error:
        raise debug_error_response(error) from error


@app.get("/debug/waits")
def debug_waits(
    limit: int = Query(default=100, ge=1, le=500),
    context: SecurityContext = Depends(
        permission_dependency(
            "cases.operate",
            action="debug.waits.read",
            resource_type="wait_state",
        )
    ),
) -> dict[str, Any]:
    _ = context
    return processing_store.list_waits(limit=limit)


@app.get("/debug/integration-operations")
def debug_integration_operations(
    context: SecurityContext = Depends(
        permission_dependency(
            "tools.read",
            action="debug.integration_operations.read",
            resource_type="integration_endpoint",
        )
    ),
) -> dict[str, Any]:
    _ = context
    return config_store.active_payload("integration_endpoints")


@app.post("/debug/endpoint-captures/start")
def debug_endpoint_capture_start(
    request: DebugEndpointCaptureStartRequest,
    http_request: Request,
    context: SecurityContext = Depends(
        permission_dependency(
            "tools.manage",
            action="debug.endpoint_captures.start",
            resource_type="integration_endpoint",
        )
    ),
) -> dict[str, Any]:
    try:
        result = debug_runtime.start_capture_session(model_to_dict(request))
        audit_success(
            context,
            http_request,
            action="debug.endpoint_captures.start",
            resource_type="integration_endpoint",
            resource_id=f"{request.endpoint_id}/{request.operation_id}",
            permission="tools.manage",
            details={"operator_id": request.operator_id, "session_id": result["session"]["session_id"]},
        )
        return result
    except (DebugRuntimeError, ConfigRegistryError) as error:
        raise debug_error_response(error) from error


@app.post("/debug/endpoint-captures/stop")
def debug_endpoint_capture_stop(
    request: DebugEndpointCaptureStopRequest,
    http_request: Request,
    context: SecurityContext = Depends(
        permission_dependency(
            "tools.manage",
            action="debug.endpoint_captures.stop",
            resource_type="integration_endpoint",
        )
    ),
) -> dict[str, Any]:
    try:
        result = debug_runtime.stop_capture_session(request.session_id)
        audit_success(
            context,
            http_request,
            action="debug.endpoint_captures.stop",
            resource_type="integration_endpoint",
            resource_id=request.session_id,
            permission="tools.manage",
            details={"operator_id": request.operator_id},
        )
        return result
    except DebugRuntimeError as error:
        raise debug_error_response(error) from error


@app.get("/debug/endpoint-captures")
def debug_endpoint_captures(
    limit: int = Query(default=100, ge=1, le=200),
    context: SecurityContext = Depends(
        permission_dependency(
            "tools.read",
            action="debug.endpoint_captures.read",
            resource_type="integration_endpoint",
        )
    ),
) -> dict[str, Any]:
    _ = context
    return debug_runtime.list_captures(limit=limit)


@app.get("/debug/endpoint-captures/{capture_id}")
def debug_endpoint_capture_detail(
    capture_id: str,
    context: SecurityContext = Depends(
        permission_dependency(
            "tools.read",
            action="debug.endpoint_captures.detail.read",
            resource_type="integration_endpoint",
        )
    ),
) -> dict[str, Any]:
    _ = context
    try:
        return debug_runtime.capture_detail(capture_id)
    except DebugRuntimeError as error:
        raise debug_error_response(error) from error


@app.post("/debug/endpoint-captures/{capture_id}/sanitize")
def debug_endpoint_capture_sanitize(
    capture_id: str,
    request: DebugEndpointCaptureSanitizeRequest,
    http_request: Request,
    context: SecurityContext = Depends(
        permission_dependency(
            "tools.manage",
            action="debug.endpoint_captures.sanitize",
            resource_type="integration_endpoint",
        )
    ),
) -> dict[str, Any]:
    try:
        result = debug_runtime.sanitize_capture(capture_id)
        audit_success(
            context,
            http_request,
            action="debug.endpoint_captures.sanitize",
            resource_type="integration_endpoint",
            resource_id=capture_id,
            permission="tools.manage",
            details={"operator_id": request.operator_id},
        )
        return result
    except DebugRuntimeError as error:
        raise debug_error_response(error) from error


@app.post("/debug/endpoint-captures/{capture_id}/create-mock")
def debug_endpoint_capture_create_mock(
    capture_id: str,
    request: DebugEndpointCaptureCreateMockRequest,
    http_request: Request,
    context: SecurityContext = Depends(
        permission_dependency(
            "tools.manage",
            action="debug.endpoint_captures.create_mock",
            resource_type="integration_endpoint",
        )
    ),
) -> dict[str, Any]:
    try:
        result = debug_runtime.create_mock_from_capture(capture_id, model_to_dict(request))
        audit_success(
            context,
            http_request,
            action="debug.endpoint_captures.create_mock",
            resource_type="integration_endpoint",
            resource_id=capture_id,
            permission="tools.manage",
            details={
                "operator_id": request.operator_id,
                "version_id": result["config_version"]["version_id"],
            },
        )
        return result
    except (DebugRuntimeError, ConfigRegistryError) as error:
        raise debug_error_response(error) from error


@app.post("/debug/endpoint-captures/{capture_id}/mark-contract-broken")
def debug_endpoint_capture_mark_contract_broken(
    capture_id: str,
    request: DebugEndpointCaptureMarkBrokenRequest,
    http_request: Request,
    context: SecurityContext = Depends(
        permission_dependency(
            "tools.manage",
            action="debug.endpoint_captures.mark_contract_broken",
            resource_type="integration_endpoint",
        )
    ),
) -> dict[str, Any]:
    try:
        result = debug_runtime.mark_capture_contract_broken(capture_id, model_to_dict(request))
        audit_success(
            context,
            http_request,
            action="debug.endpoint_captures.mark_contract_broken",
            resource_type="integration_endpoint",
            resource_id=capture_id,
            permission="tools.manage",
            details={
                "operator_id": request.operator_id,
                "version_id": result["config_version"]["version_id"],
            },
        )
        return result
    except (DebugRuntimeError, ConfigRegistryError) as error:
        raise debug_error_response(error) from error


@app.get("/admin")
def admin_ui() -> FileResponse:
    return ui_index_response(ADMIN_UI_ROOT / "index.html")


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
        ticket_input = model_to_dict(request)
        analysis = workflow.analyze(ticket_input)
        processing_store.record_analysis(ticket_input, analysis)
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
    except (ProcessingConflict, ProcessingNotFound, CaseNotFound, ValueError) as error:
        raise processing_error_response(error) from error


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
        ticket_input = model_to_dict(request)
        analysis = workflow.analyze(ticket_input)
        processing_store.record_analysis(ticket_input, analysis)
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
    except (ProcessingConflict, ProcessingNotFound, CaseNotFound, ValueError) as error:
        raise processing_error_response(error) from error


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
        duplicate = existing_callback_result(payload)
        if duplicate:
            metrics.increment("callback_duplicates_total", {"endpoint_id": endpoint_id})
            audit_success(
                context,
                http_request,
                action="callbacks.receive",
                resource_type="integration_endpoint",
                resource_id=endpoint_id,
                permission="callbacks.write",
                details={
                    "case_id": duplicate["case"].get("case_id"),
                    "invocation_id": payload.get("invocation_id"),
                    "status": payload.get("status"),
                    "duplicate": True,
                },
            )
            return duplicate
        result = workflow.handle_integration_callback(payload)
        processing_store.record_integration_callback(result)
        workflow.case_store.record_callback_receipt(
            invocation_id=payload["invocation_id"],
            endpoint_id=endpoint_id,
            result=result,
        )
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


@app.post("/external-events/{source}")
def external_event(
    source: str,
    request: ExternalEventRequest,
    http_request: Request,
    context: SecurityContext = Depends(external_event_context_dependency),
) -> dict[str, Any]:
    payload = {
        key: value
        for key, value in model_to_dict(request).items()
        if value is not None
    }
    if payload.get("source") and payload["source"] != source:
        audit_error(
            context,
            http_request,
            action="external_events.receive",
            resource_type="external_event_source",
            resource_id=source,
            permission="callbacks.write",
            status_code=400,
            message="source в external event не совпадает с URL path.",
        )
        raise HTTPException(
            status_code=400,
            detail={
                "code": "source_mismatch",
                "message": "source в external event должен совпадать с URL path.",
            },
        )
    payload["source"] = source
    payload.setdefault("received_at", utc_now())
    try:
        workflow.contracts.require_valid("external_event", payload)
        if not processing_store.external_event_receipt(payload["idempotency_key"]):
            wait = processing_store.active_wait_by_correlation(
                payload["correlation_id"],
                case_id=payload.get("case_id"),
            )
            if not wait:
                raise ProcessingNotFound(payload["correlation_id"])
            config_store.validate_external_event_result_contract(wait, payload)
        result = processing_store.record_external_event(payload)
        audit_success(
            context,
            http_request,
            action="external_events.receive",
            resource_type="external_event_source",
            resource_id=source,
            permission="callbacks.write",
            details={
                "case_id": payload.get("case_id"),
                "wait_id": result.get("wait", {}).get("wait_id"),
                "correlation_id": payload.get("correlation_id"),
                "event_id": payload.get("event_id"),
                "event_type": payload.get("event_type"),
                "status": payload.get("status"),
                "duplicate": result.get("duplicate", False),
            },
        )
        return result
    except ProcessingNotFound as error:
        audit_error(
            context,
            http_request,
            action="external_events.receive",
            resource_type="external_event_source",
            resource_id=source,
            permission="callbacks.write",
            status_code=404,
            message=str(error),
        )
        raise HTTPException(
            status_code=404,
            detail={
                "code": "wait_not_found",
                "message": f"Активное ожидание не найдено: {error}",
            },
        ) from error
    except ProcessingConflict as error:
        code = "external_event_idempotency_conflict" if isinstance(error, ExternalEventIdempotencyConflict) else "external_event_conflict"
        audit_error(
            context,
            http_request,
            action="external_events.receive",
            resource_type="external_event_source",
            resource_id=source,
            permission="callbacks.write",
            status_code=409,
            message=str(error),
        )
        raise HTTPException(
            status_code=409,
            detail={
                "code": code,
                "message": str(error),
            },
        ) from error
    except ContractValidationError as error:
        audit_error(
            context,
            http_request,
            action="external_events.receive",
            resource_type="external_event_source",
            resource_id=source,
            permission="callbacks.write",
            status_code=400,
            message="External event не прошел валидацию контракта.",
        )
        raise HTTPException(
            status_code=400,
            detail={
                "contract_name": error.contract_name,
                "errors": error.errors,
            },
        ) from error


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
        processing_store.record_approval_decision(result)
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
    dashboard = workflow.admin_dashboard()
    dashboard["processing"] = processing_store.overview()
    return dashboard


@app.get("/admin/processing/overview")
def admin_processing_overview(
    context: SecurityContext = Depends(
        permission_dependency(
            "processing.read",
            action="admin.processing.overview.read",
            resource_type="processing",
        )
    ),
) -> dict[str, Any]:
    _ = context
    return processing_store.overview()


@app.get("/admin/processing/cases")
def admin_processing_cases(
    limit: int = Query(default=100, ge=1, le=500),
    context: SecurityContext = Depends(
        permission_dependency(
            "processing.read",
            action="admin.processing.cases.read",
            resource_type="processing_case",
        )
    ),
) -> dict[str, Any]:
    _ = context
    return processing_store.list_cases(limit=limit)


@app.get("/admin/processing/cases/{case_id}")
def admin_processing_case_detail(
    case_id: str,
    context: SecurityContext = Depends(
        permission_dependency(
            "processing.read",
            action="admin.processing.case.read",
            resource_type="processing_case",
        )
    ),
) -> dict[str, Any]:
    _ = context
    try:
        return processing_store.case_detail(case_id)
    except (ProcessingConflict, ProcessingNotFound, CaseNotFound, ValueError) as error:
        raise processing_error_response(error) from error


@app.get("/admin/processing/runs")
def admin_processing_runs(
    case_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    context: SecurityContext = Depends(
        permission_dependency(
            "processing.read",
            action="admin.processing.runs.read",
            resource_type="processing_run",
        )
    ),
) -> dict[str, Any]:
    _ = context
    return processing_store.list_runs(case_id=case_id, limit=limit)


@app.get("/admin/processing/tasks")
def admin_processing_tasks(
    case_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    context: SecurityContext = Depends(
        permission_dependency(
            "processing.read",
            action="admin.processing.tasks.read",
            resource_type="agent_task",
        )
    ),
) -> dict[str, Any]:
    _ = context
    return processing_store.list_tasks(case_id=case_id, limit=limit)


@app.get("/admin/processing/waits")
def admin_processing_waits(
    case_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    context: SecurityContext = Depends(
        permission_dependency(
            "processing.read",
            action="admin.processing.waits.read",
            resource_type="wait_state",
        )
    ),
) -> dict[str, Any]:
    _ = context
    return processing_store.list_waits(case_id=case_id, limit=limit)


@app.get("/admin/processing/events")
def admin_processing_events(
    case_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    context: SecurityContext = Depends(
        permission_dependency(
            "processing.read",
            action="admin.processing.events.read",
            resource_type="case_event",
        )
    ),
) -> dict[str, Any]:
    _ = context
    return processing_store.case_events(case_id=case_id, limit=limit)


@app.post("/admin/processing/runs/{run_id}/cancel")
def admin_processing_cancel_run(
    run_id: str,
    payload: AdminProcessingCommandRequest,
    request: Request,
    context: SecurityContext = Depends(
        permission_dependency(
            "processing.manage",
            action="admin.processing.run.cancel",
            resource_type="processing_run",
        )
    ),
) -> dict[str, Any]:
    try:
        run = processing_store.cancel_run(
            run_id,
            actor_id=payload.operator_id,
            reason=payload.reason,
        )
        audit_success(
            context,
            request,
            action="admin.processing.run.cancel",
            resource_type="processing_run",
            resource_id=run_id,
            permission="processing.manage",
            details={"operator_id": payload.operator_id, "status": run.get("status")},
        )
        return {"schema_version": "1.0", "run": run}
    except (ProcessingConflict, ProcessingNotFound, CaseNotFound, ValueError) as error:
        audit_error(
            context,
            request,
            action="admin.processing.run.cancel",
            resource_type="processing_run",
            resource_id=run_id,
            permission="processing.manage",
            status_code=409 if isinstance(error, ProcessingConflict) else 400,
            message=str(error),
        )
        raise processing_error_response(error) from error


@app.post("/admin/processing/tasks/{task_id}/retry")
def admin_processing_retry_task(
    task_id: str,
    payload: AdminProcessingCommandRequest,
    request: Request,
    context: SecurityContext = Depends(
        permission_dependency(
            "processing.manage",
            action="admin.processing.task.retry",
            resource_type="agent_task",
        )
    ),
) -> dict[str, Any]:
    try:
        task = processing_store.retry_task(
            task_id,
            actor_id=payload.operator_id,
            reason=payload.reason,
        )
        audit_success(
            context,
            request,
            action="admin.processing.task.retry",
            resource_type="agent_task",
            resource_id=task_id,
            permission="processing.manage",
            details={"operator_id": payload.operator_id, "status": task.get("status")},
        )
        return {"schema_version": "1.0", "task": task}
    except (ProcessingConflict, ProcessingNotFound, CaseNotFound, ValueError) as error:
        audit_error(
            context,
            request,
            action="admin.processing.task.retry",
            resource_type="agent_task",
            resource_id=task_id,
            permission="processing.manage",
            status_code=409 if isinstance(error, ProcessingConflict) else 400,
            message=str(error),
        )
        raise processing_error_response(error) from error


@app.post("/admin/processing/tasks/{task_id}/release-lease")
def admin_processing_release_task_lease(
    task_id: str,
    payload: AdminProcessingCommandRequest,
    request: Request,
    context: SecurityContext = Depends(
        permission_dependency(
            "processing.manage",
            action="admin.processing.task.release_lease",
            resource_type="agent_task",
        )
    ),
) -> dict[str, Any]:
    try:
        task = processing_store.release_task_lease(
            task_id,
            actor_id=payload.operator_id,
            reason=payload.reason,
        )
        audit_success(
            context,
            request,
            action="admin.processing.task.release_lease",
            resource_type="agent_task",
            resource_id=task_id,
            permission="processing.manage",
            details={"operator_id": payload.operator_id, "status": task.get("status")},
        )
        return {"schema_version": "1.0", "task": task}
    except (ProcessingConflict, ProcessingNotFound, CaseNotFound, ValueError) as error:
        audit_error(
            context,
            request,
            action="admin.processing.task.release_lease",
            resource_type="agent_task",
            resource_id=task_id,
            permission="processing.manage",
            status_code=409 if isinstance(error, ProcessingConflict) else 400,
            message=str(error),
        )
        raise processing_error_response(error) from error


@app.post("/admin/processing/waits/{wait_id}/force-timeout")
def admin_processing_force_wait_timeout(
    wait_id: str,
    payload: AdminProcessingCommandRequest,
    request: Request,
    context: SecurityContext = Depends(
        permission_dependency(
            "processing.manage",
            action="admin.processing.wait.force_timeout",
            resource_type="wait_state",
        )
    ),
) -> dict[str, Any]:
    try:
        wait = processing_store.force_wait_timeout(
            wait_id,
            actor_id=payload.operator_id,
            reason=payload.reason,
        )
        audit_success(
            context,
            request,
            action="admin.processing.wait.force_timeout",
            resource_type="wait_state",
            resource_id=wait_id,
            permission="processing.manage",
            details={"operator_id": payload.operator_id, "status": wait.get("status")},
        )
        return {"schema_version": "1.0", "wait": wait}
    except (ProcessingConflict, ProcessingNotFound, CaseNotFound, ValueError) as error:
        audit_error(
            context,
            request,
            action="admin.processing.wait.force_timeout",
            resource_type="wait_state",
            resource_id=wait_id,
            permission="processing.manage",
            status_code=409 if isinstance(error, ProcessingConflict) else 400,
            message=str(error),
        )
        raise processing_error_response(error) from error


@app.post("/admin/processing/cases/{case_id}/escalate")
def admin_processing_escalate_case(
    case_id: str,
    payload: AdminProcessingCommandRequest,
    request: Request,
    context: SecurityContext = Depends(
        permission_dependency(
            "processing.manage",
            action="admin.processing.case.escalate",
            resource_type="processing_case",
        )
    ),
) -> dict[str, Any]:
    try:
        detail = processing_store.escalate_case(
            case_id,
            actor_id=payload.operator_id,
            reason=payload.reason,
        )
        audit_success(
            context,
            request,
            action="admin.processing.case.escalate",
            resource_type="processing_case",
            resource_id=case_id,
            permission="processing.manage",
            details={"operator_id": payload.operator_id},
        )
        return detail
    except (ProcessingConflict, ProcessingNotFound, CaseNotFound, ValueError) as error:
        audit_error(
            context,
            request,
            action="admin.processing.case.escalate",
            resource_type="processing_case",
            resource_id=case_id,
            permission="processing.manage",
            status_code=409 if isinstance(error, ProcessingConflict) else 400,
            message=str(error),
        )
        raise processing_error_response(error) from error


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


@app.post("/admin/integration-endpoints/openapi/preview")
def admin_integration_endpoint_openapi_preview(
    payload: AdminOpenApiContractPreviewRequest,
    http_request: Request,
    context: SecurityContext = Depends(context_or_raise),
) -> dict[str, Any]:
    permission = require_config_permission(
        context,
        http_request,
        domain="integration_endpoints",
        mode="manage",
        action="admin.integration_endpoints.openapi.preview",
    )
    if not payload.endpoint_id:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "endpoint_required",
                "message": "Для preview OpenAPI передайте endpoint_id сохраненного endpoint.",
            },
        )
    active_endpoints = config_store.active_payload("integration_endpoints").get("endpoints", [])
    endpoint = next((dict(item) for item in active_endpoints if item.get("endpoint_id") == payload.endpoint_id), {})
    if not endpoint:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "endpoint_not_found",
                "message": f"Endpoint не найден: {payload.endpoint_id}. Сохраните endpoint перед импортом OpenAPI.",
            },
        )
    if payload.contract_source:
        endpoint["contract_source"] = payload.contract_source
    try:
        result = preview_openapi_contract(endpoint, endpoint.get("contract_source") or {})
    except OpenApiContractError as error:
        audit_error(
            context,
            http_request,
            action="admin.integration_endpoints.openapi.preview",
            resource_type="integration_endpoint",
            resource_id=endpoint.get("endpoint_id"),
            permission=permission,
            status_code=400,
            message=str(error),
        )
        raise HTTPException(
            status_code=400,
            detail={
                "code": "openapi_contract_error",
                "message": str(error),
            },
        ) from error
    audit_success(
        context,
        http_request,
        action="admin.integration_endpoints.openapi.preview",
        resource_type="integration_endpoint",
        resource_id=endpoint.get("endpoint_id"),
        permission=permission,
        details={
            "operator_id": payload.operator_id,
            "operation_count": len(result.get("operations", {})),
            "warning_count": len(result.get("warnings", [])),
            "source_url": result.get("source_url"),
        },
    )
    return result


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
        require_local_secret_write_allowed()
        set_local_env_value(payload.env_name, payload.secret_value)
    except RuntimeConfigurationError as error:
        audit_store.record(
            context,
            action="admin.models.secret.update",
            resource_type="model_secret",
            resource_id=payload.provider_id,
            permission="models.manage",
            outcome="denied",
            request_method=request.method,
            request_path=str(request.url.path),
            status_code=403,
            details={
                "provider_id": payload.provider_id,
                "env_name": payload.env_name,
                "error": str(error),
            },
        )
        raise HTTPException(
            status_code=403,
            detail={
                "code": "secret_write_forbidden",
                "message": str(error),
            },
        ) from error
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


@app.get("/admin/orchestration-graph")
def admin_orchestration_graph(
    scenario_id: str | None = Query(default=None),
    view: str = Query(default="scenario"),
    context: SecurityContext = Depends(
        permission_dependency(
            "workflow.read",
            action="admin.orchestration_graph.read",
            resource_type="scenario",
        )
    ),
) -> dict[str, Any]:
    _ = context
    try:
        return config_store.orchestration_graph(
            scenario_id=scenario_id,
            view=view,
        )
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
            run_mode=request.run_mode,
            allow_llm=request.allow_llm,
            allow_readonly_integrations=request.allow_readonly_integrations,
            allow_mock_integrations=request.allow_mock_integrations,
            allow_action_with_approval=request.allow_action_with_approval,
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


def assistant_slot_schema(
    *,
    slot_schema_id: str | None = None,
    scenario_id: str | None = None,
) -> dict[str, Any]:
    slot_schemas = config_store.active_payload("slot_schemas").get("slot_schemas", [])
    resolved_slot_schema_id = slot_schema_id
    if not resolved_slot_schema_id and scenario_id:
        scenarios = config_store.active_payload("service_scenarios").get("scenarios", [])
        scenario = next((item for item in scenarios if item.get("scenario_id") == scenario_id), None)
        resolved_slot_schema_id = (scenario or {}).get("slot_schema_id")
    slot_schema = next((item for item in slot_schemas if item.get("slot_schema_id") == resolved_slot_schema_id), None)
    if not slot_schema:
        raise ConfigRegistryError(f"Схема слотов не найдена: {resolved_slot_schema_id or 'не указана'}")
    return slot_schema


@app.post("/admin/config-assistant/slot-autofill/compile")
def admin_config_assistant_slot_autofill_compile(
    request: AdminSlotAutofillCompileRequest,
    http_request: Request,
    context: SecurityContext = Depends(context_or_raise),
) -> dict[str, Any]:
    permission = require_config_permission(
        context,
        http_request,
        domain="slot_autofill_profiles",
        mode="manage",
        action="admin.config_assistant.slot_autofill.compile",
    )
    try:
        result = compile_slot_autofill_profile(
            instruction=request.instruction,
            slot_schema=assistant_slot_schema(slot_schema_id=request.slot_schema_id),
            tools=config_store.active_payload("tools").get("tools", []),
            react_call=request.react_call,
            target_slots=request.target_slots,
        )
    except ConfigRegistryError as error:
        raise config_error_response(error) from error
    audit_success(
        context,
        http_request,
        action="admin.config_assistant.slot_autofill.compile",
        resource_type="config_assistant",
        resource_id=request.slot_schema_id,
        permission=permission,
        details={
            "operator_id": request.operator_id,
            "react_call": result.get("references", {}).get("react_call"),
            "validation_error_count": len(result.get("validation_errors", [])),
            "warning_count": len(result.get("warnings", [])),
        },
    )
    return result


@app.post("/admin/config-assistant/attribute-resolution-step/compile")
def admin_config_assistant_attribute_resolution_step_compile(
    request: AdminAttributeResolutionStepCompileRequest,
    http_request: Request,
    context: SecurityContext = Depends(context_or_raise),
) -> dict[str, Any]:
    permission = require_config_permission(
        context,
        http_request,
        domain="attribute_resolution_profiles",
        mode="manage",
        action="admin.config_assistant.attribute_resolution_step.compile",
    )
    try:
        slot_schema = assistant_slot_schema(
            slot_schema_id=request.slot_schema_id,
            scenario_id=request.scenario_id,
        )
        result = compile_attribute_resolution_step(
            instruction=request.instruction,
            slot_schema=slot_schema,
            tools=config_store.active_payload("tools").get("tools", []),
            react_call=request.react_call,
            step_name=request.step_name,
            previous_steps=request.previous_steps,
        )
    except ConfigRegistryError as error:
        raise config_error_response(error) from error
    audit_success(
        context,
        http_request,
        action="admin.config_assistant.attribute_resolution_step.compile",
        resource_type="config_assistant",
        resource_id=slot_schema.get("slot_schema_id"),
        permission=permission,
        details={
            "operator_id": request.operator_id,
            "react_call": result.get("references", {}).get("react_call"),
            "validation_error_count": len(result.get("validation_errors", [])),
            "warning_count": len(result.get("warnings", [])),
        },
    )
    return result


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
