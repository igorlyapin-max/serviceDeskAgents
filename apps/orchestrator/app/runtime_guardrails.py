from __future__ import annotations

import ipaddress
import json
import logging
import logging.handlers
import os
import re
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
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
    "LITELLM_MASTER_KEY": {"sk-dev-litellm-master-key", "change_me_litellm_master_key"},
    "INTEGRATION_CALLBACK_TOKEN": {"dev-callback-token", "change_me_integration_callback_token"},
    "MCP_PROVIDER_OPS_TOKEN": {"change_me_mcp_provider_ops_token"},
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

LOG_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
LOG_PHONE_RE = re.compile(r"(?<![\w+])(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")


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
    callback_auth_mode = os.getenv("SECURITY_CALLBACK_AUTH_MODE", "source_token").strip().lower()
    if callback_auth_mode not in {"oidc_jwks", "oidc_proxy_jwt"}:
        errors.append("SECURITY_CALLBACK_AUTH_MODE=oidc_jwks/oidc_proxy_jwt обязателен для shared/staging/production callbacks.")
    else:
        if not os.getenv("CALLBACK_OIDC_ISSUER", "").strip():
            errors.append("CALLBACK_OIDC_ISSUER обязателен для OIDC callbacks.")
        if not os.getenv("CALLBACK_OIDC_AUDIENCE", "").strip():
            errors.append("CALLBACK_OIDC_AUDIENCE обязателен для OIDC callbacks.")
        if not os.getenv("CALLBACK_OIDC_ALLOWED_CLIENT_IDS", "").strip():
            errors.append("CALLBACK_OIDC_ALLOWED_CLIENT_IDS обязателен для OIDC callbacks.")
        if callback_auth_mode == "oidc_jwks" and not os.getenv("CALLBACK_OIDC_JWKS_URL", "").strip():
            errors.append("CALLBACK_OIDC_JWKS_URL обязателен для oidc_jwks callbacks.")
        if callback_auth_mode == "oidc_proxy_jwt":
            has_trusted_ip = bool(os.getenv("CALLBACK_OIDC_PROXY_TRUSTED_IPS", "").strip())
            has_trusted_header = bool(os.getenv("CALLBACK_OIDC_PROXY_TRUST_HEADER", "").strip()) and bool(
                os.getenv("CALLBACK_OIDC_PROXY_TRUST_HEADER_VALUE", "").strip()
            )
            if not has_trusted_ip and not has_trusted_header:
                errors.append(
                    "oidc_proxy_jwt требует CALLBACK_OIDC_PROXY_TRUSTED_IPS или "
                    "CALLBACK_OIDC_PROXY_TRUST_HEADER/CALLBACK_OIDC_PROXY_TRUST_HEADER_VALUE."
                )

    for env_name, weak_values in WEAK_SECRET_DEFAULTS.items():
        if env_name == "INTEGRATION_CALLBACK_TOKEN":
            if callback_auth_mode in {"oidc_jwks", "oidc_proxy_jwt"}:
                continue
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

    kafka_protocol = os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT").strip().upper() or "PLAINTEXT"
    if kafka_protocol not in {"SSL", "SASL_SSL"}:
        errors.append(
            "Для Kafka external.events в shared/staging/production нужен KAFKA_SECURITY_PROTOCOL=SSL/SASL_SSL."
        )

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
    model_config: dict[str, Any] = {}
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
    def model_probe() -> dict[str, Any]:
        nonlocal model_config
        model_config = workflow.model_config()
        return model_config

    checks.append(_check("model_routing", model_probe))
    if model_config:
        checks.append(_model_gateway_check(model_config))
    checks.append(_check("knowledge_index", lambda: workflow.knowledge_status()))
    processing_overview: dict[str, Any] = {}

    def processing_probe() -> dict[str, Any]:
        nonlocal processing_overview
        processing_overview = processing_store.overview()
        return processing_overview

    checks.append(_check("processing_store", processing_probe))
    checks.append(_kafka_bootstrap_check())
    checks.append(_integration_auth_check(config_store))
    checks.append(_mcp_health_check(config_store))
    if processing_overview:
        checks.append(_async_runtime_check(processing_overview))

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
    if isinstance(value, str):
        return _sanitize_log_string(value)
    return value


def _sanitize_log_string(value: str) -> str:
    redacted = LOG_EMAIL_RE.sub("персональные данные скрыты", value)
    redacted = LOG_PHONE_RE.sub("персональные данные скрыты", redacted)
    return redacted


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


def _readiness_network_timeout() -> float:
    try:
        return float(os.getenv("READYZ_NETWORK_TIMEOUT_SECONDS", "1.5"))
    except ValueError:
        return 1.5


def _kafka_bootstrap_check() -> dict[str, Any]:
    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "127.0.0.1:19092")
    timeout = _readiness_network_timeout()
    errors: list[str] = []
    for server in [item.strip() for item in bootstrap.split(",") if item.strip()]:
        host, _, port_text = server.rpartition(":")
        if not host or not port_text.isdigit():
            errors.append(f"{server}: некорректный формат host:port")
            continue
        try:
            with socket.create_connection((host, int(port_text)), timeout=timeout):
                return {
                    "name": "kafka_bootstrap",
                    "status": "ok",
                    "message": server,
                }
        except OSError as error:
            errors.append(f"{server}: {error}")
    return {
        "name": "kafka_bootstrap",
        "status": "error",
        "message": "; ".join(errors) or "KAFKA_BOOTSTRAP_SERVERS не задан.",
    }


def _model_gateway_check(model_config: dict[str, Any]) -> dict[str, Any]:
    gateway = model_config.get("gateway") if isinstance(model_config, dict) else {}
    providers = model_config.get("providers") if isinstance(model_config, dict) else {}
    routing = model_config.get("routing") if isinstance(model_config, dict) else {}
    if not isinstance(gateway, dict):
        gateway = {}
    if not isinstance(providers, dict):
        providers = {}
    if not isinstance(routing, dict):
        routing = {}

    alias = routing.get("slot_resolution") or model_config.get("default_model_alias")
    provider = _model_provider_for_alias(providers, alias)
    base_url = str(gateway.get("base_url") or provider.get("base_url") or "").strip()
    if not base_url:
        return {
            "name": "model_gateway",
            "status": "error",
            "message": "Не задан URL model gateway.",
        }

    headers: dict[str, str] = {}
    if gateway.get("type") == "litellm":
        api_key = os.getenv("LITELLM_MASTER_KEY", "").strip()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
    else:
        api_key_env = str(provider.get("api_key_env") or "").strip()
        api_key = os.getenv(api_key_env, "").strip() if api_key_env else ""
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

    url = f"{base_url.rstrip('/')}/models"
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=_readiness_network_timeout()) as response:
            status_code = int(getattr(response, "status", 0) or 0)
    except (OSError, urllib.error.URLError) as error:
        return {
            "name": "model_gateway",
            "status": "error",
            "message": f"{url}: {error}",
        }
    if 200 <= status_code < 300:
        return {
            "name": "model_gateway",
            "status": "ok",
            "message": url,
        }
    return {
        "name": "model_gateway",
        "status": "error",
        "message": f"{url}: HTTP {status_code}",
    }


def _model_provider_for_alias(providers: dict[str, Any], alias: Any) -> dict[str, Any]:
    for provider_id, provider in providers.items():
        if not isinstance(provider, dict):
            continue
        if provider_id == alias or provider.get("model_alias") == alias:
            return provider
    return {}


def _integration_auth_check(config_store: Any) -> dict[str, Any]:
    try:
        payload = config_store.active_payload("mcp_environments")
    except Exception as error:  # noqa: BLE001 - readiness must report dependency failures
        return {
            "name": "mcp_auth",
            "status": "error",
            "message": f"Не удалось прочитать mcp_environments: {error}",
        }

    missing: list[str] = []
    checked = 0
    for environment in payload.get("environments", []) if isinstance(payload, dict) else []:
        if not isinstance(environment, dict) or environment.get("status") in {"disabled", "deprecated"}:
            continue
        auth_mode = environment.get("auth_mode")
        if auth_mode in {None, "", "none", "signed_event"}:
            continue
        auth_ref = str(environment.get("auth_ref") or "").strip()
        checked += 1
        if not auth_ref:
            missing.append(f"{environment.get('environment_id') or 'unknown'} требует auth_ref для {auth_mode}")
            continue
        prefix, separator, env_name = auth_ref.partition(":")
        if prefix == "env" and separator == ":" and not os.getenv(env_name):
            missing.append(
                f"{environment.get('environment_id') or 'unknown'} требует env {env_name} для {auth_mode}"
            )

    if missing:
        return {
            "name": "mcp_auth",
            "status": "error",
            "message": "; ".join(missing),
        }
    return {
        "name": "mcp_auth",
        "status": "ok",
        "message": f"Проверено MCP auth: {checked}",
    }


def _mcp_health_check(config_store: Any) -> dict[str, Any]:
    try:
        payload = config_store.active_payload("mcp_environments")
    except Exception as error:  # noqa: BLE001 - readiness must report dependency failures
        return {
            "name": "mcp_health",
            "status": "error",
            "message": f"Не удалось прочитать mcp_environments: {error}",
        }

    checked = 0
    skipped = 0
    degraded: list[str] = []
    for environment in payload.get("environments", []) if isinstance(payload, dict) else []:
        if not isinstance(environment, dict) or environment.get("status") in {"disabled", "deprecated"}:
            continue
        environment_id = str(environment.get("environment_id") or "unknown")
        health_check = environment.get("health_check") if isinstance(environment.get("health_check"), dict) else {}
        mode = str(health_check.get("mode") or "disabled")
        if mode == "disabled":
            skipped += 1
            continue
        try:
            if mode == "http_get":
                _check_mcp_http_health(environment, health_check)
            elif mode == "mcp_ping":
                from .mcp_execution import invoke_mcp_tools_list

                invoke_mcp_tools_list(
                    environment=_environment_with_resolved_mcp_base_url(environment),
                    secret_resolver=os.getenv,
                    request_id=f"{environment_id}.ready",
                    timeout_seconds=_health_check_timeout(health_check),
                    attempts=1,
                )
            else:
                degraded.append(f"{environment_id}: unsupported health_check.mode={mode}")
                continue
        except Exception as error:  # noqa: BLE001 - readiness reports dependency failures
            degraded.append(f"{environment_id}: {type(error).__name__}: {error}")
            continue
        checked += 1

    if degraded:
        return {
            "name": "mcp_health",
            "status": "degraded",
            "message": "; ".join(degraded),
            "checked": checked,
            "skipped": skipped,
        }
    return {
        "name": "mcp_health",
        "status": "ok",
        "message": f"Проверено MCP health: {checked}, пропущено: {skipped}",
        "checked": checked,
        "skipped": skipped,
    }


def _check_mcp_http_health(environment: dict[str, Any], health_check: dict[str, Any]) -> None:
    base_url = _resolve_mcp_base_url(environment)
    path = str(health_check.get("path") or "/health")
    if not path.startswith("/"):
        path = f"/{path}"
    parsed = urllib.parse.urlsplit(base_url)
    origin = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
    url = urllib.parse.urljoin(f"{origin}/", path.lstrip("/"))
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=_health_check_timeout(health_check)) as response:
        status_code = int(getattr(response, "status", 0) or 0)
    if not 200 <= status_code < 300:
        raise OSError(f"{url}: HTTP {status_code}")


def _resolve_mcp_base_url(environment: dict[str, Any]) -> str:
    value = str(environment.get("base_url") or "").strip()
    prefix, separator, env_name = value.partition(":")
    if prefix == "env" and separator == ":":
        value = os.getenv(env_name, "").strip()
    if not value:
        raise OSError(f"{environment.get('environment_id') or 'unknown'} base_url пустой")
    return value


def _environment_with_resolved_mcp_base_url(environment: dict[str, Any]) -> dict[str, Any]:
    resolved = dict(environment)
    resolved["base_url"] = _resolve_mcp_base_url(environment)
    return resolved


def _health_check_timeout(health_check: dict[str, Any]) -> float:
    value = health_check.get("timeout_seconds")
    try:
        return float(value)
    except (TypeError, ValueError):
        return _readiness_network_timeout()


def _async_runtime_check(processing_overview: dict[str, Any]) -> dict[str, Any]:
    runtime = processing_overview.get("runtime") if isinstance(processing_overview, dict) else None
    recovery = processing_overview.get("recovery") if isinstance(processing_overview, dict) else None
    if not isinstance(runtime, dict):
        return {
            "name": "async_runtime",
            "status": "error",
            "message": "ProcessingStore не вернул блок runtime.",
        }
    issues = [str(item) for item in runtime.get("issues") or []]
    recovery_issues = []
    if isinstance(recovery, dict) and recovery.get("status") not in {None, "ok"}:
        recovery_issues = [str(item) for item in recovery.get("issues") or []]
    status = runtime.get("status")
    if status == "ok" and not issues and not recovery_issues:
        return {
            "name": "async_runtime",
            "status": "ok",
            "message": "Async runtime компоненты работают.",
            "components": runtime.get("required_components", []),
        }
    if status == "ok" and recovery_issues:
        return {
            "name": "async_runtime",
            "status": "degraded",
            "message": "; ".join(recovery_issues),
            "components": runtime.get("required_components", []),
            "recovery": recovery,
        }
    return {
        "name": "async_runtime",
        "status": "error",
        "message": "; ".join(issues) or "Async runtime не готов.",
        "components": runtime.get("required_components", []),
        "stale_mcp_outbox": runtime.get("stale_mcp_outbox"),
        "recovery": recovery,
    }


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
