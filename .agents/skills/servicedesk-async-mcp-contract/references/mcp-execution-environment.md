# MCP Execution Environment Rules

## Capability Metadata

An external MCP environment should publish enough metadata for discovery or manual binding:

- capability or tool name
- contract version
- supported execution mode: `sync` or `async`
- input schema
- sync output schema or async acknowledgement schema
- async event type and result schemas
- auth requirements
- health status

JSON Schema descriptions are part of the operator-facing contract. Fill `inputSchema.properties.*.description`,
`_meta.servicedesk.output_schema.properties.*.description`, and capability/tool descriptions with business wording.
`ServiceDeskAgents` passes these descriptions into the capability-step LLM assistant so it can map scenario slots to
inputs and outputs. Do not expose n8n workflow names, webhook paths, node names, tokens, or other private implementation
details in those descriptions.

## Sync Execution

Sync tools return a canonical result immediately. `ServiceDeskAgents` validates the result against the capability `output_schema` and then fills outputs.

## Async Execution

Async tools must accept `async_context` and return accepted acknowledgement. They must later deliver canonical `ExternalEvent` payloads for progress and terminal states.

## Authentication

Development environments may use static Bearer token authentication through secret references. Production environments must use OIDC or an approved signed-event equivalent.

OIDC validation must cover issuer, audience, expiry, subject or client id, and capability permission.

For inbound HTTP callbacks in shared/staging/production, use `SECURITY_CALLBACK_AUTH_MODE=oidc_jwks`: `ServiceDeskAgents` verifies the JWT signature against `CALLBACK_OIDC_JWKS_URL` and validates issuer, audience, expiry, subject/client id, allowed client ids, and required scope. `SECURITY_CALLBACK_AUTH_MODE=oidc_proxy_jwt` is allowed only behind a trusted gateway/proxy that has already verified the JWT signature.

## Diagnostics

MCP diagnostics should include stable identifiers and compact state:

- `environment_id`
- `capability_id`
- `external_execution_id`
- `correlation_id`
- current phase
- last checked resource
- next poll time when polling
- non-sensitive error summary

Diagnostics must not include secret values.

## Internal Implementations

The MCP environment may internally use n8n, Temporal, scripts, HTTP APIs, or manual systems. Those details are outside the `ServiceDeskAgents` scenario contract and must be hidden behind the MCP capability surface.
