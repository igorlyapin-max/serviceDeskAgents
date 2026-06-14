# AGENTS.md

## Project-Local Knowledge

- Use `.agents/skills` as project-local knowledge for ServiceDesk Agents and n8n runbook workflows.
- Do not read all skills, references, memories, or knowledge files at startup.
- First choose the smallest relevant skill by `name` and `description`.
- Read only the selected `SKILL.md`, then only directly referenced `references/*.md` needed for the task.
- Keep required project rules in this `AGENTS.md`; keep long architecture, runbook, command, and payload details in skill references.

## Skill Routing

- Use `$servicedesk-n8n-runbooks` for exact repo paths, workflow/runbook conventions, operator commands, and current stand notes.
- Use `$servicedesk-channel-kafka` for the logical `Сервисдеск` channel, `asyncapi_sd.yaml`, OПЕРУ.ИТ Kafka topics, channel parameters, task keys, result messages, and ServiceDesk Kafka routing.
