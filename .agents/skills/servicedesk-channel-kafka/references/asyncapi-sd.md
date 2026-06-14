# asyncapi_sd.yaml: Logical ServiceDesk Kafka Channel

## Meaning

`Сервисдеск` is a logical customer channel in the Admin UI. The file `../asyncapi_sd.yaml` describes the current Kafka implementation shape for that channel, but it must not force hardcoded AD/SAP/Kafka ReAct calls into ServiceDesk Agents.

## Current Topics

| Topic | Direction for ServiceDesk Agents | Meaning |
| --- | --- | --- |
| `public.ittask.ad.task` | outbound example | AD task messages in the current OПЕРУ.ИТ contract. |
| `public.ittask.sap.task` | outbound example | SAP task messages in the current OПЕРУ.ИТ contract. |
| `public.ittask.kafka.task` | outbound example | Kafka administration task messages in the current OПЕРУ.ИТ contract. |
| `public.ittask.result` | inbound | Task execution result. |
| `public.ittask.invalid` | inbound | Invalid task execution. |
| `public.ittask.temp_password` | inbound | Temporary password delivery event. |

Future logical ServiceDesk task topics should be configurable and may use:

```text
public.ittask.serviceDesk{agent_type}.task
```

The computed topic must be available as:

```text
${channel.service_desk.task_topic}
```

## Channel Parameters

Expose channel parameters to scenarios through `${channel.<channel_id>.<parameter>}`.

| Parameter | Direction | Source | Notes |
| --- | --- | --- | --- |
| `agent_type` | input | technical profile | Replaces `{agent_type}` in the topic template. |
| `task_topic` | input | computed topic | Can be used in routing and prompt text. |
| `task_key` | input | Kafka message key | By contract, contains the OПЕРУ.ИТ task number for task/result/invalid. |
| `task_number` | bidirectional | Kafka message key | Human/business name for the same correlation value. |
| `result_code` | output | `TaskResultCode` | `Выполнено` or `Не выполнено`. |
| `result_message` | output | `TaskResultMessage` | Human result message from ServiceDesk. |
| `result_topic` | input | technical profile | Usually `public.ittask.result`. |
| `invalid_payload` | output | `public.ittask.invalid` | Invalid execution payload. |
| `temp_password_personal_id` | output | `TaskTemp_PasswordMsg.personalID` | Temporary password recipient id. |

## Result Mapping

- `TaskResultCode=Выполнено` maps to `ExternalEvent.status=success`.
- `TaskResultCode=Не выполнено` maps to `ExternalEvent.status=error`.
- `TaskResultMessage` maps to `ExternalEvent.result.result_message` or `ExternalEvent.error.message`.
- `public.ittask.invalid` maps to `ExternalEvent.status=error`.
- `public.ittask.temp_password` is a secret-bearing event; password values must be masked in logs and UI.

## Security

- HMAC is a channel/adapter responsibility, not an LLM-generated value.
- Kafka transport protection is administrator-configured through broker controls such as ACLs, `SASL_SSL`, `SSL`/mTLS, signed envelopes, or equivalent infrastructure.
- Do not log temporary passwords, HMAC values, Kafka credentials, or raw secret-bearing payloads.
