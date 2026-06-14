---
name: servicedesk-channel-kafka
description: "Use in /home/lsk/projects/serviceDeskAgents when working with the logical ServiceDesk channel, asyncapi_sd.yaml, OПЕРУ.ИТ Kafka topics, channel parameters, task keys, result messages, or ServiceDesk Kafka routing."
---

# ServiceDeskAgents ServiceDesk Kafka Channel

Use this project-local skill when the task touches the logical UI channel `Сервисдеск` or the `asyncapi_sd.yaml` Kafka contract.

## Working Rules

- `Сервисдеск` in the Admin UI is a customer-facing logical channel, not a single hardcoded topic.
- `asyncapi_sd.yaml` is the current Kafka implementation example for that channel.
- Do not import AD/SAP/Kafka commands from `asyncapi_sd.yaml` as mandatory ReAct calls.
- Keep topic names configurable. Future task topics can follow `public.ittask.serviceDesk{agent_type}.task`.
- Channel parameters such as `task_topic`, `agent_type`, `task_key`, `result_code`, and `result_message` must remain available to scenario prompts, routing text, escalation messages, and slot-resolution rules through `${channel.<channel_id>.<parameter>}` references.
- External ServiceDesk systems return events/results; they must not close, escalate, or otherwise own internal case business state directly.

## Source Of Truth

Read `references/asyncapi-sd.md` for the topic table, parameter mapping, result mapping, and security notes before changing channel behavior or documentation.
