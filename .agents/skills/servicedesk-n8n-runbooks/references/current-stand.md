# n8n As External MCP Implementation

`ServiceDeskAgents` treats n8n as an implementation detail behind an external MCP environment. There is no in-repo n8n service, no `async-tool-worker`, no `tool.commands`, and no ServiceDesk `n8n_workflows` config domain.

## ServiceDesk Runtime

- Outbound MCP command topic: `mcp.commands`.
- Inbound external result topic: `external.events`.
- Continuation topic: `agent.tasks`.
- Runtime workers: `async-outbox-publisher`, `async-mcp-worker`, `async-external-event-worker`, `async-agent-task-worker`.
- Public callback/event endpoint is source-based, normally `POST /external-events/mcp` for the configured MCP environment source.

## n8n Project Boundary

- Actual n8n workflow JSON and publish/import helpers live in `../n8n`.
- Do not copy n8n webhook paths, workflow ids, node names, or raw result structures into ServiceDesk profiles.
- If n8n emits fields such as `email_result.body`, map them inside the MCP implementation to canonical capability outputs such as `provider_mail_body`.

## Contract Boundary

ServiceDesk scenarios see only:

- `Capability.<capability_id>`;
- `paramCapability.<capability_id>.input.<field>`;
- `paramCapability.<capability_id>.output.<field>`;
- `step.<step_id>.capability.<capability_id>.output.<field>`.

Legacy `ReAct.n8n_*`, `paramReAct.*`, `endpoint_id`, `operation_id`, and `n8n_workflows` are removed.
