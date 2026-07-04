---
name: servicedesk-async-mcp-contract
description: "Use in /home/lsk/projects/serviceDeskAgents when designing, implementing, reviewing, or diagnosing ServiceDesk async capability contracts executed by external MCP environments, including wait_state, async_context, accepted acknowledgements, ExternalEvent callbacks, idempotency, auth, and capability bindings."
---

# ServiceDesk Async MCP Contract

Use this skill for the canonical async execution contract. It is the source of truth for capability-level execution through external MCP environments.

## Core Rules

- `ServiceDeskAgents` owns scenario state, `wait_state`, timeout, retries, idempotency receipts, slot filling, workflow transitions, and continuation.
- Execution environments are external MCP services. They execute capabilities and return sync results or async events; they do not mutate case business state directly.
- Scenario/profile language must use `Capability.<capability_id>` and canonical input/output fields. Do not expose n8n workflow names, webhook paths, operation ids, or internal payload fields as scenario contract.
- Async execution must open a durable wait before calling the external MCP tool.
- Async MCP tools return an accepted acknowledgement only. Progress and terminal outcomes must return as canonical `ExternalEvent`.
- Every async command and event must carry correlation identifiers and stable idempotency keys.
- Dev MCP authentication may use configured static Bearer token refs. Production MCP authentication must use OIDC or an approved signed-event equivalent.
- Do not log tokens, passwords, resolved secret refs, or fields explicitly marked secret-bearing by a contract. `Verbose` diagnostics may include payload shape, correlation ids, and business/contact fields after secret redaction; do not treat personal/contact data as secret by default.

## Reference Loading

- Read `references/async-contract.md` when changing runtime, schemas, wait handling, external-event handling, or validation.
- Read `references/mcp-execution-environment.md` when writing docs for external implementers, MCP binding/discovery code, auth behavior, or conformance tests.

## n8n Boundary

If an external MCP service uses n8n internally, treat n8n as private implementation detail of that MCP environment. `ServiceDeskAgents` must depend only on capability contracts, MCP bindings, accepted acknowledgements, and canonical `ExternalEvent` results.
