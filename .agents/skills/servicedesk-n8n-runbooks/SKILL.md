---
name: servicedesk-n8n-runbooks
description: "Use in /home/lsk/projects/serviceDeskAgents only when a ServiceDesk capability is implemented inside the separate ../n8n project; n8n is external MCP implementation detail, not a ServiceDeskAgents endpoint."
---

# ServiceDeskAgents n8n Runbooks

Use this skill only after `servicedesk-async-mcp-contract`.

`ServiceDeskAgents` no longer owns n8n workflows, n8n webhook endpoints, `tool.commands`, ReAct operation bindings, or `n8n_*` scenario contracts. New scenario/profile work must use:

- `capabilities`;
- `mcp_environments`;
- `capability_bindings`;
- `mcp.commands`;
- `external.events`;
- `agent.tasks`.

If a capability is physically implemented in n8n, that n8n workflow belongs to the separate project `../n8n`. Changes to actual workflow JSON, publish/import helpers, credentials, and n8n runtime checks must be made there, not by reintroducing n8n domains into this repository.

## Rules

- Do not add `integration_endpoints`, `tools`, `n8n_workflows`, `/tools/dispatch`, `/integrations/callbacks/{endpoint_id}`, `paramReAct`, or `ReAct.n8n_*` back to ServiceDeskAgents.
- Do not expose n8n workflow ids, webhook paths, node names, or `email_result.body` style fields to ServiceDesk scenarios.
- Express runbook behavior as a capability contract with canonical input/output schemas and `async_event_contracts`.
- External MCP must return accepted ack for async execution and terminal/progress `ExternalEvent` results.
- For local/dev auth, use MCP environment token references. For production, use OIDC as described by `servicedesk-async-mcp-contract`.

## When Editing Runbooks

1. Update ServiceDesk capability/binding schemas in this repository only if the public contract changes.
2. Update the actual n8n workflow in `../n8n`.
3. Keep n8n-specific fields mapped inside the external MCP implementation.
4. Validate ServiceDesk with MCP/capability tests; validate n8n with the `../n8n` project tooling.

## Source Of Truth

- ServiceDesk async contract: `.agents/skills/servicedesk-async-mcp-contract/references/async-contract.md`.
- MCP execution environment contract: `.agents/skills/servicedesk-async-mcp-contract/references/mcp-execution-environment.md`.
- Runbook developer guide: `docs/runbooks/ASYNC_MCP_RUNBOOK_DEVELOPER_GUIDE.md`.
