from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from .action_gates import DEFAULT_STATE_DB_PATH


LOCAL_ENVIRONMENTS = {"local", "dev", "development", "test", "testing"}
PRODUCTION_ENVIRONMENTS = {"prod", "production"}

WEAK_SECRET_DEFAULTS = {
    "POSTGRES_PASSWORD": {"servicedesk_dev_password"},
    "N8N_DB_PASSWORD": {"n8n_dev_password"},
    "N8N_ENCRYPTION_KEY": {"replace_with_32_plus_chars_dev_key"},
    "N8N_WEBHOOK_TOKEN": {"replace_with_dev_webhook_token"},
    "LITELLM_MASTER_KEY": {"sk-dev-litellm-master-key"},
    "INTEGRATION_CALLBACK_TOKEN": {"dev-callback-token"},
}


class RuntimeConfigurationError(RuntimeError):
    pass


def app_environment() -> str:
    return (
        os.getenv("APP_ENV")
        or os.getenv("SERVICE_DESK_ENV")
        or os.getenv("ENVIRONMENT")
        or os.getenv("ENV")
        or "local"
    ).strip().lower()


def is_production_environment() -> bool:
    return app_environment() in PRODUCTION_ENVIRONMENTS


def is_local_environment() -> bool:
    environment = app_environment()
    return environment in LOCAL_ENVIRONMENTS or environment not in PRODUCTION_ENVIRONMENTS


def validate_startup_environment() -> None:
    if not is_production_environment():
        return

    errors: list[str] = []
    auth_mode = os.getenv("SECURITY_AUTH_MODE", "dev_header").strip().lower()
    if auth_mode in {"dev_header", "disabled"}:
        errors.append("SECURITY_AUTH_MODE=dev_header/disabled запрещен для APP_ENV=production.")

    for env_name, weak_values in WEAK_SECRET_DEFAULTS.items():
        value = os.getenv(env_name, "")
        if not value:
            errors.append(f"{env_name} не задан для production.")
        elif value in weak_values:
            errors.append(f"{env_name} содержит dev/default значение.")

    if errors:
        raise RuntimeConfigurationError("Production guardrails failed: " + "; ".join(errors))


def require_local_secret_write_allowed() -> None:
    if is_production_environment():
        raise RuntimeConfigurationError(
            "Запись секретов в .env запрещена для production. Используйте переменные окружения или внешний secret store."
        )


def readiness_report(*, config_store: Any, workflow: Any, processing_store: Any) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    checks.append(_state_db_check())
    if is_production_environment():
        checks.append(
            {
                "name": "production_storage",
                "status": "degraded",
                "message": "SQLite state DB используется только как MVP-хранилище и не является production-ready.",
            }
        )
    checks.append(_check("config_registry", lambda: config_store.active_payload("service_scenarios")))
    checks.append(_check("model_routing", lambda: workflow.model_config()))
    checks.append(_check("knowledge_index", lambda: workflow.knowledge_status()))
    checks.append(_check("processing_store", lambda: processing_store.overview()))

    status = "ok"
    if any(check["status"] == "error" for check in checks):
        status = "error"
    elif any(check["status"] == "degraded" for check in checks):
        status = "degraded"
    return {
        "schema_version": "1.0",
        "status": status,
        "environment": app_environment(),
        "production_ready": is_production_environment() and status == "ok",
        "checks": checks,
    }


def configure_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=getattr(logging, level, logging.INFO), format="%(message)s")


def log_json(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    payload = {
        "event": event,
        **{key: value for key, value in fields.items() if value not in (None, "", [], {})},
    }
    logger.log(level, json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str))


def security_headers(*, https_enabled: bool = False) -> dict[str, str]:
    headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Content-Security-Policy": (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'"
        ),
    }
    if https_enabled:
        headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return headers


def _state_db_check() -> dict[str, Any]:
    configured_path = os.getenv("ORCHESTRATOR_STATE_DB")
    db_path = Path(configured_path) if configured_path else DEFAULT_STATE_DB_PATH
    parent = db_path.parent
    if not parent.exists():
        return {
            "name": "state_db",
            "status": "error",
            "message": f"Каталог state DB не существует: {parent}",
        }
    if not os.access(parent, os.W_OK):
        return {
            "name": "state_db",
            "status": "error",
            "message": f"Каталог state DB недоступен для записи: {parent}",
        }
    return {
        "name": "state_db",
        "status": "ok" if db_path.exists() else "degraded",
        "message": str(db_path),
    }


def _check(name: str, probe: Any) -> dict[str, Any]:
    try:
        result = probe()
    except Exception as error:  # noqa: BLE001 - readiness must report dependency failures
        return {"name": name, "status": "error", "message": str(error)}
    status = result.get("status") if isinstance(result, dict) else None
    if status in {"failed", "unavailable", "error"}:
        return {"name": name, "status": "degraded", "message": str(status)}
    return {"name": name, "status": "ok"}
