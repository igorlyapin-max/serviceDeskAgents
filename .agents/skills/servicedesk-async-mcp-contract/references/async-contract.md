# Async Capability Contract

## Canonical Flow

1. Scenario selects a `capability_id`.
2. `ServiceDeskAgents` resolves an active capability binding to an external MCP environment.
3. For async execution, `ServiceDeskAgents` opens `wait_state` before calling MCP.
4. `ServiceDeskAgents` sends business inputs plus `async_context`.
5. MCP returns accepted acknowledgement.
6. MCP emits `progress`, `success`, `error`, `timeout`, or `cancelled` as `ExternalEvent`.
7. `ServiceDeskAgents` validates the event, stores idempotency receipt, updates wait state, fills canonical outputs, and continues the scenario.

## Async Context

Async MCP calls must include:

- `case_id`
- `run_id`
- `wait_id`
- `correlation_id`
- `capability_id`
- `contract_version`
- `expected_event_type`
- `idempotency_key_base`
- delivery parameters selected by the wait policy, such as callback URL or event topic
- optional `async_diagnostics` for operator/debug runs. `ServiceDeskAgents` forwards only `level: basic|verbose`
  plus compact `source` and `run_mode`; unknown fields are dropped and sensitive strings are redacted.

## Accepted Acknowledgement

Async tools return only an acknowledgement:

```json
{
  "status": "accepted",
  "external_execution_id": "provider-exec-123",
  "correlation_id": "corr-123",
  "message": "Execution accepted",
  "diagnostics": {}
}
```

The acknowledgement does not fill business outputs and does not close the wait.

## Async Diagnostics

When `async_context.async_diagnostics.level` is `basic` or `verbose`, the MCP environment should emit canonical
`progress` ExternalEvent records before terminal completion. Diagnostics must be compact, redacted, and provider-neutral.
Use fields such as current stage, checked resource, iteration, last poll, next poll, match counts, and last error.

`verbose` may include richer payload shape and business/contact fields, but must still avoid tokens, passwords, auth refs,
raw secrets, and implementation-private workflow identifiers. `ServiceDeskAgents` displays diagnostics only from
wait state, receipts, and ExternalEvent payloads.

## ExternalEvent

All terminal and progress outcomes use the canonical external event contract:

```json
{
  "event_type": "provider_channel_repair_monitor.completed",
  "status": "success",
  "case_id": "case-1",
  "run_id": "run-1",
  "wait_id": "wait-1",
  "correlation_id": "corr-123",
  "source": "mcp",
  "idempotency_key": "cmd-123:success",
  "result": {}
}
```

Allowed statuses are `progress`, `success`, `error`, `timeout`, and `cancelled`.

## Idempotency

- Use one stable `idempotency_key_base` per command.
- Derive a unique event key for each progress or terminal event, for example `<idempotency_key_base>:<event_id>`.
- Re-delivery with the same key and same canonical payload is idempotent.
- Re-delivery with the same key and different payload is an error and must not mutate scenario state.

## Ownership Rules

External MCP environments must not:

- close, escalate, or change cases directly;
- fill slots directly;
- change workflow state directly;
- call ServiceDesk internal persistence APIs except the approved callback/event endpoint;
- bypass authentication or event validation.

`ServiceDeskAgents` must validate schemas before applying results to wait or slot state.
