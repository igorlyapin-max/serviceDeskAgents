from __future__ import annotations

import ipaddress
import json
import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Any

from .action_gates import DEFAULT_STATE_DB_PATH


LOCAL_ENVIRONMENTS = {"local", "dev", "development", "test", "testing"}
PRODUCTION_ENVIRONMENTS = {"prod", "production"}
SHARED_ENVIRONMENTS = {"staging", "stage", "uat", "shared", "preprod", "preproduction"}
KNOWN_ENVIRONMENTS = LOCAL_ENVIRONMENTS | PRODUCTION_ENVIRONMENTS | SHARED_ENVIRONMENTS

DEFAULT_LOG_SINKS = "stdout,jsonl"
DEFAULT_LOG_JSONL_PATH = "state/logs/servicedesk-events.jsonl"
DEBUG_LEVELS = {"Basic", "Verbose"}

WEAK_SECRET_DEFAULTS = {
    "POSTGRES_PASSWORD": {"servicedesk_dev_password", "change_me_postgres_password"},
    "N8N_DB_PASSWORD": {"n8n_dev_password", "change_me_n8n_db_password"},
    "N8N_ENCRYPTION_KEY": {"replace_with_32_plus_chars_dev_key", "change_me_n8n_encryption_key_32_chars_min"},
    "N8N_WEBHOOK_TOKEN": {"replace_with_dev_webhook_token", "change_me_n8n_webhook_token"},
    "LITELLM_MASTER_KEY": {"sk-dev-litellm-master-key", "change_me_litellm_master_key"},
    "INTEGRATION_CALLBACK_TOKEN": {"dev-callback-token", "change_me_integration_callback_token"},
}

DEFAULT_METRICS_ALLOWED_IPS = "127.0.0.1,::1"

SENSITIVE_LOG_KEYWORDS = (
    "token",
    "password",
    "passwd",
    "pwd",
    "secret",
    "key",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "session",
    "credential",
    "bearer",
    "токен",
    "пароль",
    "секрет",
    "ключ",
    "авторизация",
    "куки",
    "сессия",
    "учетные_данные",
    "учётные_данные",
)


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


def is_shared_environment() -> bool:
    return app_environment() in SHARED_ENVIRONMENTS


def is_local_environment() -> bool:
    return app_environment() in LOCAL_ENVIRONMENTS


def is_non_local_environment() -> bool:
    return app_environment() in PRODUCTION_ENVIRONMENTS | SHARED_ENVIRONMENTS


def validate_startup_environment() -> None:
    environment = app_environment()
    errors: list[str] = []
    if environment not in KNOWN_ENVIRONMENTS:
        errors.append(
            f"APP_ENV={environment} не поддерживается. Разрешены: {', '.join(sorted(KNOWN_ENVIRONMENTS))}."
        )
        raise RuntimeConfigurationError("Runtime guardrails failed: " + "; ".join(errors))

    try:
        debug_logging_level()
    except RuntimeConfigurationError as error:
        errors.append(str(error))

    if not operational_log_sink_configured() and environment in (PRODUCTION_ENVIRONMENTS | SHARED_ENVIRONMENTS):
        errors.append(
            "Для shared/staging/production нужен второй log sink: включите jsonl или syslog в LOG_SINKS."
        )

    if not is_non_local_environment():
        if errors:
            raise RuntimeConfigurationError("Runtime guardrails failed: " + "; ".join(errors))
        return

    auth_mode = os.getenv("SECURITY_AUTH_MODE", "dev_header").strip().lower()
    if auth_mode in {"dev_header", "disabled"}:
        errors.append("SECURITY_AUTH_MODE=dev_header/disabled запрещен для shared/staging/production.")

    for env_name, weak_values in WEAK_SECRET_DEFAULTS.items():
        if env_name == "INTEGRATION_CALLBACK_TOKEN":
            source_specific_tokens = [
                value
                for key, value in os.environ.items()
                if key.startswith("INTEGRATION_CALLBACK_TOKEN__") and value
            ]
            value = os.getenv(env_name, "")
            if not value and not source_specific_tokens:
                errors.append("Задайте INTEGRATION_CALLBACK_TOKEN__<SOURCE> для callback endpoints.")
            elif value and value in weak_values:
                errors.append(f"{env_name} содержит dev/default значение.")
            continue
        value = os.getenv(env_name, "")
        if not value:
            errors.append(f"{env_name} не задан для shared/staging/production.")
        elif value in weak_values:
            errors.append(f"{env_name} содержит dev/default значение.")

    if errors:
        raise RuntimeConfigurationError("Runtime guardrails failed: " + "; ".join(errors))


def local_security_warnings() -> list[str]:
    if not is_local_environment():
        return []

    warnings: list[str] = []
    auth_mode = os.getenv("SECURITY_AUTH_MODE", "dev_header").strip().lower()
    if auth_mode in {"dev_header", "disabled"}:
        warnings.append(f"SECURITY_AUTH_MODE={auth_mode} предназначен только для local/dev.")

    for env_name, weak_values in WEAK_SECRET_DEFAULTS.items():
        value = os.getenv(env_name, "")
        if value and value in weak_values:
            warnings.append(f"{env_name} содержит dev/default значение; замените перед shared/prod окружением.")
    return warnings


def require_local_secret_write_allowed() -> None:
    if is_non_local_environment():
        raise RuntimeConfigurationError(
            "Запись секретов в .env запрещена для shared/staging/production. "
            "Используйте переменные окружения или внешний secret store."
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
    formatter = logging.Formatter("%(message)s")
    handlers: list[logging.Handler] = []
    sinks = log_sinks()

    if not ({"stdout", "stderr"} & sinks):
        sinks.add("stdout")
    if "stdout" in sinks:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        handlers.append(handler)
    if "stderr" in sinks:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(formatter)
        handlers.append(handler)
    if "jsonl" in sinks:
        jsonl_path = Path(os.getenv("LOG_JSONL_PATH", DEFAULT_LOG_JSONL_PATH))
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(jsonl_path, encoding="utf-8")
        handler.setFormatter(formatter)
        handlers.append(handler)
    if "syslog" in sinks:
        address = os.getenv("SYSLOG_ADDRESS", "/dev/log")
        handler = logging.handlers.SysLogHandler(address=address)
        handler.setFormatter(formatter)
        handlers.append(handler)

    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(message)s",
        handlers=handlers,
        force=True,
    )


def log_sinks() -> set[str]:
    return {
        item.strip().lower()
        for item in os.getenv("LOG_SINKS", DEFAULT_LOG_SINKS).split(",")
        if item.strip()
    }


def operational_log_sink_configured() -> bool:
    sinks = log_sinks()
    return bool(sinks & {"jsonl", "syslog"})


def debug_logging_enabled() -> bool:
    return os.getenv("DEBUG_LOGGING_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def debug_logging_level() -> str:
    value = os.getenv("DEBUG_LOGGING_LEVEL", "Basic").strip() or "Basic"
    normalized = value[:1].upper() + value[1:].lower()
    if normalized not in DEBUG_LEVELS:
        raise RuntimeConfigurationError("DEBUG_LOGGING_LEVEL должен быть Basic или Verbose.")
    return normalized


def log_debug_event(
    logger: logging.Logger,
    event: str,
    *,
    verbose_fields: dict[str, Any] | None = None,
    **fields: Any,
) -> bool:
    if not debug_logging_enabled():
        return False
    level = debug_logging_level()
    payload = {
        "debug_level": level,
        **fields,
    }
    if level == "Verbose":
        payload.update(verbose_fields or {})
    log_json(logger, logging.INFO, f"diagnostic_{event}", **payload)
    return True


def readiness_http_status(report: dict[str, Any]) -> int:
    status = report.get("status")
    if status == "error":
        return 503
    strict = os.getenv("READYZ_STRICT", "false").strip().lower() in {"1", "true", "yes", "on"}
    if status == "degraded" and strict:
        return 503
    return 200


def log_json(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    payload = {
        "event": event,
        **{
            key: sanitize_log_value(str(key), value)
            for key, value in fields.items()
            if value not in (None, "", [], {})
        },
    }
    logger.log(level, json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str))


def sanitize_log_value(key: str, value: Any) -> Any:
    normalized_key = str(key).lower()
    if any(keyword in normalized_key for keyword in SENSITIVE_LOG_KEYWORDS):
        return "параметр скрыт"
    if isinstance(value, dict):
        return {
            item_key: sanitize_log_value(str(item_key), item_value)
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [sanitize_log_value(key, item) for item in value]
    return value


def log_local_security_warnings(logger: logging.Logger) -> None:
    for message in local_security_warnings():
        log_json(
            logger,
            logging.WARNING,
            "local_security_warning",
            environment=app_environment(),
            message=message,
        )


def metrics_allowed_ips() -> list[str]:
    return [
        item.strip()
        for item in os.getenv("METRICS_ALLOWED_IPS", DEFAULT_METRICS_ALLOWED_IPS).split(",")
        if item.strip()
    ]


def metrics_client_allowed(ip_address: str | None, allowed_ips: list[str] | None = None) -> bool:
    if not ip_address:
        return False
    try:
        client = ipaddress.ip_address(ip_address)
    except ValueError:
        return False

    for item in allowed_ips if allowed_ips is not None else metrics_allowed_ips():
        try:
            if "/" in item:
                if client in ipaddress.ip_network(item, strict=False):
                    return True
            elif client == ipaddress.ip_address(item):
                return True
        except ValueError:
            continue
    return False


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
