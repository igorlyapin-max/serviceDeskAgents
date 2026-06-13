from __future__ import annotations

import argparse
import copy
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Iterable, Protocol

from .action_gates import utc_now
from .cases import CaseStore
from .contracts import ContractRegistry
from .integrations import IntegrationDispatcher, ToolRegistry
from .metrics import metrics
from .processing import DEFAULT_ASYNC_TOOL_COMMAND_TOPIC, ProcessingConflict, ProcessingNotFound, ProcessingStore
from .runtime_guardrails import configure_logging, log_json, validate_startup_environment


logger = logging.getLogger("servicedesk.kafka_runtime")


class KafkaRuntimeError(RuntimeError):
    pass


class MessageProducer(Protocol):
    def publish(self, topic: str, key: str, value: dict[str, Any]) -> None:
        ...


class JsonKafkaProducer:
    def __init__(self, *, bootstrap_servers: str | None = None):
        self.bootstrap_servers = bootstrap_servers or os.getenv("KAFKA_BOOTSTRAP_SERVERS", "127.0.0.1:19092")
        try:
            from kafka import KafkaProducer
        except ImportError as error:  # pragma: no cover - exercised when runtime dependency is missing
            raise KafkaRuntimeError("Установите dependency kafka-python для Kafka runtime.") from error
        self._producer = KafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            api_version=kafka_api_version(),
            key_serializer=lambda value: value.encode("utf-8"),
            value_serializer=lambda value: json.dumps(value, ensure_ascii=False).encode("utf-8"),
        )

    def publish(self, topic: str, key: str, value: dict[str, Any]) -> None:
        self._producer.send(topic, key=key, value=value).get(timeout=30)
        self._producer.flush(timeout=30)

    def close(self) -> None:
        try:
            self._producer.close(timeout=0)
        except PermissionError:
            # Some sandboxes block kafka-python's internal wakeup socket during close.
            self._producer._closed = True
            pass


class JsonKafkaConsumer:
    def __init__(
        self,
        *,
        topic: str | None = None,
        bootstrap_servers: str | None = None,
        group_id: str | None = None,
    ):
        self.topic = topic or os.getenv("TOOL_COMMAND_TOPIC", DEFAULT_ASYNC_TOOL_COMMAND_TOPIC)
        self.bootstrap_servers = bootstrap_servers or os.getenv("KAFKA_BOOTSTRAP_SERVERS", "127.0.0.1:19092")
        self.group_id = group_id or os.getenv("TOOL_COMMAND_WORKER_GROUP_ID", "servicedesk-tool-workers")
        try:
            from kafka import KafkaConsumer
        except ImportError as error:  # pragma: no cover - exercised when runtime dependency is missing
            raise KafkaRuntimeError("Установите dependency kafka-python для Kafka runtime.") from error
        self._consumer = KafkaConsumer(
            self.topic,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            api_version=kafka_api_version(),
            auto_offset_reset=os.getenv("TOOL_COMMAND_WORKER_OFFSET_RESET", "earliest"),
            enable_auto_commit=False,
            key_deserializer=lambda value: value.decode("utf-8") if value else None,
            value_deserializer=lambda value: json.loads(value.decode("utf-8")),
        )

    def __iter__(self) -> Iterable["KafkaCommandRecord"]:
        for record in self._consumer:
            yield KafkaCommandRecord(
                value=record.value,
                topic=record.topic,
                key=record.key,
                ack=self._consumer.commit,
            )


@dataclass(frozen=True)
class KafkaCommandRecord:
    value: dict[str, Any]
    topic: str | None = None
    key: str | None = None
    ack: Any | None = None

    def commit(self) -> None:
        if callable(self.ack):
            self.ack()


class OutboxPublisher:
    def __init__(
        self,
        processing_store: ProcessingStore,
        producer: MessageProducer,
        *,
        worker_id: str | None = None,
    ):
        self.processing_store = processing_store
        self.producer = producer
        self.worker_id = worker_id or f"outbox-publisher-{uuid.uuid4().hex[:8]}"

    def publish_batch(self, *, limit: int = 50, topics: list[str] | None = None) -> dict[str, Any]:
        messages = self.processing_store.claim_outbox_batch(
            worker_id=self.worker_id,
            limit=limit,
            topics=topics,
        )
        published = 0
        failed = 0
        for message in messages:
            try:
                self.producer.publish(message["topic"], message["key"], message)
                self.processing_store.mark_outbox_published(message["message_id"], worker_id=self.worker_id)
                published += 1
                metrics.increment("outbox_publish_total", {"topic": message["topic"], "status": "published"})
                log_json(
                    logger,
                    logging.INFO,
                    "outbox_message_published",
                    topic=message["topic"],
                    message_id=message["message_id"],
                    key=message["key"],
                )
            except Exception as error:  # noqa: BLE001 - publisher must keep retry context
                failed += 1
                try:
                    self.processing_store.mark_outbox_publish_failed(
                        message["message_id"],
                        str(error),
                        worker_id=self.worker_id,
                    )
                except Exception as mark_error:  # noqa: BLE001 - stale lease should not crash the batch loop
                    log_json(
                        logger,
                        logging.ERROR,
                        "outbox_message_publish_failure_mark_failed",
                        topic=message.get("topic"),
                        message_id=message.get("message_id"),
                        error=str(mark_error),
                    )
                metrics.increment("outbox_publish_total", {"topic": message.get("topic"), "status": "failed"})
                log_json(
                    logger,
                    logging.ERROR,
                    "outbox_message_publish_failed",
                    topic=message.get("topic"),
                    message_id=message.get("message_id"),
                    error=str(error),
                )
        close = getattr(self.producer, "close", None)
        if callable(close):
            close()
        return {
            "schema_version": "1.0",
            "claimed": len(messages),
            "published": published,
            "failed": failed,
        }


def kafka_api_version() -> tuple[int, ...]:
    value = os.getenv("KAFKA_API_VERSION", "2.8.0").strip()
    parts = [int(part) for part in value.split(".") if part.strip()]
    if not 2 <= len(parts) <= 3:
        raise KafkaRuntimeError("KAFKA_API_VERSION должен иметь формат major.minor или major.minor.patch.")
    return tuple(parts)


class ToolCommandWorker:
    def __init__(
        self,
        processing_store: ProcessingStore,
        dispatcher: IntegrationDispatcher,
        *,
        worker_id: str | None = None,
    ):
        self.processing_store = processing_store
        self.dispatcher = dispatcher
        self.worker_id = worker_id or f"tool-worker-{uuid.uuid4().hex[:8]}"

    def process_command(self, command: dict[str, Any]) -> dict[str, Any]:
        command = self._extract_command(command)
        self._validate_command(command)
        self.processing_store.verify_tool_command(command)
        invocation = copy.deepcopy(command["invocation"])
        self._resolve_secret_operation_parameters(invocation)
        receipt = self.processing_store.begin_tool_command(command, worker_id=self.worker_id)
        if receipt["duplicate"]:
            existing = receipt.get("receipt") or {}
            log_json(
                logger,
                logging.INFO,
                "tool_command_duplicate_skipped",
                command_id=command["command_id"],
                case_id=command["case_id"],
                receipt_status=existing.get("status"),
            )
            return {
                "schema_version": "1.0",
                "command_id": command["command_id"],
                "case_id": command["case_id"],
                "wait_id": command["wait_id"],
                "duplicate": True,
                "receipt_status": existing.get("status"),
                "tool_result": existing.get("result", {}).get("tool_result"),
            }
        invocation.setdefault("extensions", {})
        invocation["extensions"].setdefault(
            "async_callback",
            {
                "source": command["source"],
                "callback_url": command["callback_url"],
                "case_id": command["case_id"],
                "ticket_id": command.get("ticket_id"),
                "run_id": command["run_id"],
                "wait_id": command["wait_id"],
                "correlation_id": command["correlation_id"],
                "event_type": command["expected_event_type"],
                "idempotency_key": command["idempotency_key"],
            },
        )
        started_at = time.monotonic()
        result = self.dispatcher.dispatch(invocation)
        duration_seconds = time.monotonic() - started_at
        self.processing_store.record_tool_command_result(
            result,
            case_id=command["case_id"],
            idempotency_key=f"{command['idempotency_key']}:tool_result",
        )
        if result["status"] not in {"success", "dry_run_completed"}:
            external_result = self._record_dispatch_failure(command, result)
        else:
            external_result = None
        metrics.increment("tool_command_worker_total", {"status": result["status"], "tool_name": result["tool_name"]})
        metrics.observe(
            "tool_command_worker_duration_seconds",
            duration_seconds,
            {"tool_name": result["tool_name"], "status": result["status"]},
        )
        log_json(
            logger,
            logging.INFO,
            "tool_command_processed",
            command_id=command["command_id"],
            case_id=command["case_id"],
            tool_name=result["tool_name"],
            status=result["status"],
            duration_ms=int(duration_seconds * 1000),
        )
        response = {
            "schema_version": "1.0",
            "command_id": command["command_id"],
            "case_id": command["case_id"],
            "wait_id": command["wait_id"],
            "tool_result": result,
        }
        if external_result:
            response["external_event_result"] = external_result
        self.processing_store.complete_tool_command(command, response, worker_id=self.worker_id)
        return response

    def process_commands(self, commands: Iterable[dict[str, Any] | KafkaCommandRecord], *, limit: int | None = None) -> dict[str, Any]:
        processed = 0
        failed = 0
        dead_lettered = 0
        for item in commands:
            if limit is not None and processed >= limit:
                break
            command: dict[str, Any] | None = None
            try:
                command = self._extract_command(item)
                self.process_command(command)
                self._commit_record(item)
                processed += 1
            except (KafkaRuntimeError, ProcessingConflict, ProcessingNotFound) as error:
                failed += 1
                if command is None:
                    command = self._dead_letter_command(item)
                try:
                    self.processing_store.record_tool_command_dead_letter(
                        command,
                        str(error),
                        worker_id=self.worker_id,
                    )
                    self._commit_record(item)
                    dead_lettered += 1
                except Exception as dlq_error:  # noqa: BLE001 - no ack without durable failure record
                    log_json(logger, logging.ERROR, "tool_command_dead_letter_failed", error=str(dlq_error))
                metrics.increment("tool_command_worker_total", {"status": "failed", "tool_name": "unknown"})
                log_json(logger, logging.ERROR, "tool_command_failed", error=str(error))
            except Exception as error:  # noqa: BLE001 - no commit for transient/unclassified failures
                failed += 1
                metrics.increment("tool_command_worker_total", {"status": "failed", "tool_name": "unknown"})
                log_json(logger, logging.ERROR, "tool_command_failed_without_commit", error=str(error))
        return {
            "schema_version": "1.0",
            "processed": processed,
            "failed": failed,
            "dead_lettered": dead_lettered,
        }

    @staticmethod
    def _validate_command(command: dict[str, Any]) -> None:
        required = {
            "schema_version",
            "command_id",
            "command_type",
            "case_id",
            "run_id",
            "wait_id",
            "correlation_id",
            "source",
            "expected_event_type",
            "callback_url",
            "idempotency_key",
            "invocation",
        }
        missing = sorted(key for key in required if key not in command)
        if missing:
            raise KafkaRuntimeError(f"tool command misses required fields: {', '.join(missing)}")
        if command["schema_version"] != "1.0" or command["command_type"] != "async_tool_invocation":
            raise KafkaRuntimeError("tool command имеет неподдерживаемую версию или тип.")

    @staticmethod
    def _extract_command(item: dict[str, Any] | KafkaCommandRecord) -> dict[str, Any]:
        value = item.value if isinstance(item, KafkaCommandRecord) else item
        if not isinstance(value, dict):
            raise KafkaRuntimeError("Kafka message value должен быть JSON object.")
        if value.get("event_type") == "async_tool_invocation_requested" and isinstance(value.get("payload"), dict):
            command = copy.deepcopy(value["payload"])
            command.setdefault("topic", value.get("topic"))
            return command
        command = copy.deepcopy(value)
        command.setdefault("topic", DEFAULT_ASYNC_TOOL_COMMAND_TOPIC)
        return command

    @staticmethod
    def _commit_record(item: dict[str, Any] | KafkaCommandRecord) -> None:
        if isinstance(item, KafkaCommandRecord):
            item.commit()

    @staticmethod
    def _dead_letter_command(item: dict[str, Any] | KafkaCommandRecord) -> dict[str, Any]:
        value = item.value if isinstance(item, KafkaCommandRecord) else item
        return {
            "schema_version": "1.0",
            "command_id": f"invalid-{uuid.uuid4().hex[:12]}",
            "command_type": "invalid_tool_command",
            "topic": getattr(item, "topic", DEFAULT_ASYNC_TOOL_COMMAND_TOPIC),
            "case_id": "unknown",
            "wait_id": None,
            "correlation_id": None,
            "idempotency_key": f"invalid:{uuid.uuid4().hex[:12]}",
            "raw": value,
        }

    @staticmethod
    def _resolve_secret_operation_parameters(invocation: dict[str, Any]) -> None:
        extensions = invocation.get("extensions") if isinstance(invocation.get("extensions"), dict) else {}
        secret_parameters = extensions.get("secret_operation_parameters")
        if not isinstance(secret_parameters, dict):
            return
        operation_parameters = invocation.setdefault("operation_parameters", {})
        for parameter, env_name in secret_parameters.items():
            secret_value = os.getenv(str(env_name), "")
            if not secret_value:
                raise KafkaRuntimeError(f"Не задана переменная окружения для secret operation parameter: {env_name}")
            operation_parameters[parameter] = secret_value

    def _record_dispatch_failure(self, command: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
        error = result.get("error") or {
            "code": f"tool_status_{result['status']}",
            "message": f"ReAct-вызов завершился статусом {result['status']}.",
        }
        event = {
            "schema_version": "1.0",
            "event_id": f"{command['command_id']}:dispatch_error",
            "case_id": command["case_id"],
            "ticket_id": command.get("ticket_id"),
            "wait_id": command["wait_id"],
            "correlation_id": command["correlation_id"],
            "source": command["source"],
            "event_type": command["expected_event_type"],
            "status": "error",
            "received_at": utc_now(),
            "idempotency_key": f"{command['idempotency_key']}:dispatch_error",
            "error": {
                "code": str(error.get("code") or "tool_dispatch_failed"),
                "message": str(error.get("message") or "Async ReAct-вызов завершился ошибкой."),
            },
        }
        return self.processing_store.record_external_event(event)


def build_default_runtime() -> tuple[ProcessingStore, IntegrationDispatcher]:
    contracts = ContractRegistry()
    case_store = CaseStore(contracts)
    processing_store = ProcessingStore(case_store)
    registry = ToolRegistry(contracts)
    dispatcher = IntegrationDispatcher(contracts, registry)
    return processing_store, dispatcher


def main() -> None:
    parser = argparse.ArgumentParser(description="ServiceDeskAgents Kafka async runtime")
    parser.add_argument("mode", choices=["publish-once", "worker"])
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--topic", default=os.getenv("TOOL_COMMAND_TOPIC", DEFAULT_ASYNC_TOOL_COMMAND_TOPIC))
    args = parser.parse_args()

    configure_logging()
    validate_startup_environment()
    processing_store, dispatcher = build_default_runtime()
    if args.mode == "publish-once":
        result = OutboxPublisher(
            processing_store,
            JsonKafkaProducer(),
        ).publish_batch(limit=args.limit)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return

    consumer = JsonKafkaConsumer(topic=args.topic)
    result = ToolCommandWorker(processing_store, dispatcher).process_commands(consumer, limit=None)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
