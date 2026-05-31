from __future__ import annotations

import logging
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .metrics import metrics
from .runtime_guardrails import log_json


logger = logging.getLogger("servicedesk.http")


def urlopen_with_retry(
    request: Request,
    *,
    timeout: int | float,
    operation_name: str,
    attempts: int = 3,
    backoff_seconds: float = 0.2,
) -> bytes:
    last_error: Exception | None = None
    safe_attempts = max(1, attempts)
    for attempt in range(1, safe_attempts + 1):
        started = time.perf_counter()
        try:
            with urlopen(request, timeout=timeout) as response:
                body = response.read()
            log_json(
                logger,
                logging.INFO,
                "http_integration_call",
                operation=operation_name,
                attempt=attempt,
                status="success",
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
            metrics.increment("integration_calls_total", {"operation": operation_name, "status": "success"})
            metrics.observe(
                "integration_call_duration_seconds",
                time.perf_counter() - started,
                {"operation": operation_name, "status": "success"},
            )
            return body
        except HTTPError as error:
            last_error = error
            retryable = error.code in {408, 425, 429, 500, 502, 503, 504}
            log_json(
                logger,
                logging.WARNING,
                "http_integration_call",
                operation=operation_name,
                attempt=attempt,
                status="http_error",
                status_code=error.code,
                retryable=retryable,
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
            metrics.increment("integration_calls_total", {"operation": operation_name, "status": f"http_{error.code}"})
            metrics.observe(
                "integration_call_duration_seconds",
                time.perf_counter() - started,
                {"operation": operation_name, "status": f"http_{error.code}"},
            )
            if not retryable or attempt >= safe_attempts:
                raise
        except (URLError, TimeoutError) as error:
            last_error = error
            log_json(
                logger,
                logging.WARNING,
                "http_integration_call",
                operation=operation_name,
                attempt=attempt,
                status="network_error",
                error_type=type(error).__name__,
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
            metrics.increment("integration_calls_total", {"operation": operation_name, "status": "network_error"})
            metrics.observe(
                "integration_call_duration_seconds",
                time.perf_counter() - started,
                {"operation": operation_name, "status": "network_error"},
            )
            if attempt >= safe_attempts:
                raise
        time.sleep(backoff_seconds * attempt)
    if last_error:
        raise last_error
    raise RuntimeError(f"HTTP operation failed without explicit error: {operation_name}")
