# Changelog

## Unreleased

- Added production startup guardrails for dev auth mode and default secrets.
- Added security headers and request id propagation for FastAPI responses.
- Added `/readyz` readiness checks alongside the lightweight `/healthz` liveness endpoint.
- Restricted Admin UI secret writes to local/dev environments.
- Added duplicate callback detection by `invocation_id`.
- Added retry/backoff logging wrapper for outbound HTTP integration and model calls.
- Added minimal PII/secret redaction before LLM slot extraction and exposed redaction markers in dry-run trace.
- Added `/metrics` Prometheus-compatible MVP metrics for HTTP, integration calls and duplicate callbacks.
- Persisted callback receipts by `invocation_id` to make duplicate callbacks idempotent across process restarts.
- Added stdlib unit tests and a GitHub Actions CI workflow that runs backend, UI, contract, documentation and test checks.
