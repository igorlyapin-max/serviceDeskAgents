from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], int] = defaultdict(int)
        self._sums: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)

    def increment(self, name: str, labels: dict[str, Any] | None = None, value: int = 1) -> None:
        key = self._key(name, labels)
        with self._lock:
            self._counters[key] += value

    def observe(self, name: str, value: float, labels: dict[str, Any] | None = None) -> None:
        labels = labels or {}
        with self._lock:
            self._counters[self._key(f"{name}_count", labels)] += 1
            self._sums[self._key(f"{name}_sum", labels)] += value

    def render_prometheus(self) -> str:
        lines = [
            "# HELP servicedesk_http_requests_total HTTP requests by method, path and status.",
            "# TYPE servicedesk_http_requests_total counter",
        ]
        with self._lock:
            for key, value in sorted(self._counters.items()):
                metric_name, labels = key
                lines.append(f"{metric_name}{self._format_labels(labels)} {value}")
            for key, value in sorted(self._sums.items()):
                metric_name, labels = key
                lines.append(f"{metric_name}{self._format_labels(labels)} {value:.6f}")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _key(name: str, labels: dict[str, Any] | None) -> tuple[str, tuple[tuple[str, str], ...]]:
        normalized = tuple(
            sorted((str(key), str(value)) for key, value in (labels or {}).items() if value not in (None, ""))
        )
        return f"servicedesk_{name}", normalized

    @staticmethod
    def _format_labels(labels: tuple[tuple[str, str], ...]) -> str:
        if not labels:
            return ""
        escaped = ",".join(f'{key}="{MetricsRegistry._escape_label_value(value)}"' for key, value in labels)
        return "{" + escaped + "}"

    @staticmethod
    def _escape_label_value(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


metrics = MetricsRegistry()
