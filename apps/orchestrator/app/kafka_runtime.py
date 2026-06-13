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
from .config_registry import ConfigStore
from .contracts import ContractValidationError
from .contracts import ContractRegistry
from .integrations import IntegrationDispatcher, ToolRegistry
from .metrics import metrics
from .processing import (
    DEFAULT_ASYNC_TOOL_COMMAND_TOPIC,
    DEFAULT_EXTERNAL_EVENT_TOPIC,
    ProcessingConflict,
    ProcessingNotFound,
    ProcessingStore,
)
from .runtime_guardrails import configure_logging, log_json, validate_startup_environment


logger = logging.getLogger("servicedesk.kafka_runtime")


class KafkaRuntimeError(RuntimeError):
    pass


KAFKA_SECURITY_PROTOCOLS = {"PLAINTEXT", "SSL", "SASL_PLAINTEXT", "SASL_SSL"}
KAFKA_SASL_MECHANISMS = {"PLAIN", "SCRAM-SHA-256", "SCRAM-SHA-512"}


class MessageProducer(Protocol):
    def publish(self, topic: str, key: str, value: dict[str, Any]) -> None:
        ...


def kafka_client_security_config() -> dict[str, Any]:
    protocol = os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT").strip().upper() or "PLAINTEXT"
    if protocol not in KAFKA_SECURITY_PROTOCOLS:
        raise KafkaRuntimeError(
            "KAFKA_SECURITY_PROTOCOL должен быть PLAINTEXT, SSL, SASL_PLAINTEXT или SASL_SSL."
        )

    config: dict[str, Any] = {"security_protocol": protocol}
    if protocol.startswith("SASL_"):
        mechanism = os.getenv("KAFKA_SASL_MECHANISM", "PLAIN").strip().upper() or "PLAIN"
        if mechanism not in KAFKA_SASL_MECHANISMS:
            raise KafkaRuntimeError(
                "KAFKA_SASL_MECHANISM должен быть PLAIN, SCRAM-SHA-256 или SCRAM-SHA-512."
            )
        username = os.getenv("KAFKA_SASL_USERNAME", "")
        password = os.getenv("KAFKA_SASL_PASSWORD", "")
        if not username or not password:
            raise KafkaRuntimeError("KAFKA_SASL_USERNAME и KAFKA_SASL_PASSWORD обязательны для SASL Kafka.")
        config.update(
            sasl_mechanism=mechanism,
            sasl_plain_username=username,
            sasl_plain_password=password,
        )

    if protocol in {"SSL", "SASL_SSL"}:
        ssl_options = {
            "ssl_cafile": os.getenv("KAFKA_SSL_CA_FILE", ""),
            "ssl_certfile": os.getenv("KAFKA_SSL_CERT_FILE", ""),
            "ssl_keyfile": os.getenv("KAFKA_SSL_KEY_FILE", ""),
        }
        config.update({key: value for key, value in ssl_options.items() if value})
        check_hostname = os.getenv("KAFKA_SSL_CHECK_HOSTNAME", "true").strip().lower()
        config["ssl_check_hostname"] = check_hostname not in {"0", "false", "no", "off"}

    return config


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
            **kafka_client_security_config(),
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
        offset_reset_env: str = "TOOL_COMMAND_WORKER_OFFSET_RESET",
    ):
        self.topic = topic or os.getenv("TOOL_COMMAND_TOPIC", DEFAULT_ASYNC_TOOL_COMMAND_TOPIC)
        self.bootstrap_servers = bootstrap_servers or os.getenv("KAFKA_BOOTSTRAP_SERVERS", "127.0.0.1:19092")
        self.group_id = group_id or os.getenv("TOOL_COMMAND_WORKER_GROUP_ID", "servicedesk-tool-workers")
        self.offset_reset_env = offset_reset_env
        try:
            from kafka import KafkaConsumer
        except ImportError as error:  # pragma: no cover - exercised when runtime dependency is missing
            raise KafkaRuntimeError("Установите dependency kafka-python для Kafka runtime.") from error
        self._consumer = KafkaConsumer(
            self.topic,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            api_version=kafka_api_version(),
            auto_offset_reset=os.getenv(self.offset_reset_env, "earliest"),
            enable_auto_commit=False,
            key_deserializer=lambda value: value.decode("utf-8") if value else None,
            **kafka_client_security_config(),
        )

    def __iter__(self) -> Iterable["KafkaCommandRecord"]:
        for record in self._consumer:
            yield KafkaCommandRecord(
                value=record.value,
                topic=record.topic,
                key=record.key,
                partition=getattr(record, "partition", None),
                offset=getattr(record, "offset", None),
                ack=self._consumer.commit,
            )


@dataclass(frozen=True)
class KafkaCommandRecord:
    value: Any
    topic: str | None = None
    key: str | None = None
    partition: int | None = None
    offset: int | None = None
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


def decode_kafka_json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return copy.deepcopy(value)
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except UnicodeDecodeError as error:
            raise KafkaRuntimeError("Kafka message value должен быть UTF-8 JSON object.") from error
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as error:
            raise KafkaRuntimeError("Kafka message value должен быть валидным JSON object.") from error
        if not isinstance(decoded, dict):
            raise KafkaRuntimeError("Kafka message value должен быть JSON object.")
        return decoded
    raise KafkaRuntimeError("Kafka message value должен быть JSON object.")


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
                "idempotency_key_base": command["idempotency_key"],
                "result_transport": command.get("result_transport", "http_callback"),
                "result_topic": command.get("result_topic", DEFAULT_EXTERNAL_EVENT_TOPIC),
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
        handled = 0
        for item in commands:
            if limit is not None and handled >= limit:
                break
            command: dict[str, Any] | None = None
            try:
                command = self._extract_command(item)
                self.process_command(command)
                self._commit_record(item)
                processed += 1
                handled += 1
            except (KafkaRuntimeError, ProcessingConflict, ProcessingNotFound) as error:
                failed += 1
                handled += 1
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
                    log_json(
                        logger,
                        logging.ERROR,
                        "tool_command_dead_letter_failed",
                        error=ProcessingStore._sanitize_error_text(str(dlq_error)),
                    )
                metrics.increment("tool_command_worker_total", {"status": "failed", "tool_name": "unknown"})
                log_json(
                    logger,
                    logging.ERROR,
                    "tool_command_failed",
                    error=ProcessingStore._sanitize_error_text(str(error)),
                )
            except Exception as error:  # noqa: BLE001 - no commit for transient/unclassified failures
                failed += 1
                handled += 1
                metrics.increment("tool_command_worker_total", {"status": "failed", "tool_name": "unknown"})
                log_json(
                    logger,
                    logging.ERROR,
                    "tool_command_failed_without_commit",
                    error=ProcessingStore._sanitize_error_text(str(error)),
                )
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
        value = decode_kafka_json_object(value)
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
        record_key = (
            f"{getattr(item, 'topic', DEFAULT_ASYNC_TOOL_COMMAND_TOPIC)}:"
            f"{getattr(item, 'partition', 'unknown')}:"
            f"{getattr(item, 'offset', uuid.uuid4().hex[:12])}"
        )
        return {
            "schema_version": "1.0",
            "command_id": f"invalid-{uuid.uuid4().hex[:12]}",
            "command_type": "invalid_tool_command",
            "topic": getattr(item, "topic", DEFAULT_ASYNC_TOOL_COMMAND_TOPIC),
            "case_id": "unknown",
            "wait_id": None,
            "correlation_id": None,
            "idempotency_key": f"invalid:{record_key}",
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


class ExternalEventWorker:
    def __init__(
        self,
        processing_store: ProcessingStore,
        config_store: ConfigStore,
        contracts: ContractRegistry,
        *,
        worker_id: str | None = None,
    ):
        self.processing_store = processing_store
        self.config_store = config_store
        self.contracts = contracts
        self.worker_id = worker_id or f"external-event-worker-{uuid.uuid4().hex[:8]}"

    def process_event(
        self,
        event: dict[str, Any],
        *,
        received_transport: str = "kafka_event",
        source_topic: str | None = None,
    ) -> dict[str, Any]:
        event = self._extract_event(event)
        event.setdefault("received_at", utc_now())
        self.contracts.require_valid("external_event", event)
        if not self.processing_store.external_event_receipt(event["idempotency_key"]):
            wait = self.processing_store.active_wait_by_correlation(
                event["correlation_id"],
                case_id=event.get("case_id"),
            )
            if not wait:
                raise ProcessingNotFound(event["correlation_id"])
            self.config_store.validate_external_event_result_contract(wait, event)
        result = self.processing_store.record_external_event(
            event,
            received_transport=received_transport,
            source_topic=source_topic,
        )
        metrics.increment(
            "external_event_worker_total",
            {"source": event["source"], "status": event["status"]},
        )
        log_json(
            logger,
            logging.INFO,
            "external_event_processed",
            case_id=event.get("case_id"),
            wait_id=event.get("wait_id"),
            correlation_id=event.get("correlation_id"),
            source=event.get("source"),
            event_type=event.get("event_type"),
            status=event.get("status"),
            duplicate=result.get("duplicate", False),
        )
        return result

    def process_events(
        self,
        events: Iterable[dict[str, Any] | KafkaCommandRecord],
        *,
        limit: int | None = None,
    ) -> dict[str, Any]:
        processed = 0
        failed = 0
        dead_lettered = 0
        handled = 0
        for item in events:
            if limit is not None and handled >= limit:
                break
            event: dict[str, Any] | None = None
            try:
                event = self._extract_event(item)
                self.process_event(
                    event,
                    received_transport="kafka_event" if isinstance(item, KafkaCommandRecord) else "internal",
                    source_topic=getattr(item, "topic", None),
                )
                self._commit_record(item)
                processed += 1
                handled += 1
            except (ContractValidationError, KafkaRuntimeError, ProcessingConflict, ProcessingNotFound) as error:
                failed += 1
                handled += 1
                if event is None:
                    event = self._dead_letter_event(item)
                try:
                    self.processing_store.record_external_event_dead_letter(
                        event,
                        str(error),
                        worker_id=self.worker_id,
                        source_topic=getattr(item, "topic", DEFAULT_EXTERNAL_EVENT_TOPIC),
                    )
                    self._commit_record(item)
                    dead_lettered += 1
                except Exception as dlq_error:  # noqa: BLE001 - no ack without durable failure record
                    log_json(
                        logger,
                        logging.ERROR,
                        "external_event_dead_letter_failed",
                        error=ProcessingStore._sanitize_error_text(str(dlq_error)),
                    )
                metrics.increment("external_event_worker_total", {"source": "unknown", "status": "failed"})
                log_json(
                    logger,
                    logging.ERROR,
                    "external_event_failed",
                    error=ProcessingStore._sanitize_error_text(str(error)),
                )
            except Exception as error:  # noqa: BLE001 - no commit for transient/unclassified failures
                failed += 1
                handled += 1
                metrics.increment("external_event_worker_total", {"source": "unknown", "status": "failed"})
                log_json(
                    logger,
                    logging.ERROR,
                    "external_event_failed_without_commit",
                    error=ProcessingStore._sanitize_error_text(str(error)),
                )
        return {
            "schema_version": "1.0",
            "processed": processed,
            "failed": failed,
            "dead_lettered": dead_lettered,
        }

    @staticmethod
    def _extract_event(item: dict[str, Any] | KafkaCommandRecord) -> dict[str, Any]:
        value = item.value if isinstance(item, KafkaCommandRecord) else item
        value = decode_kafka_json_object(value)
        if value.get("event_type") == "external_event_received" and isinstance(value.get("payload"), dict):
            payload = value["payload"]
            if isinstance(payload.get("external_event"), dict):
                return copy.deepcopy(payload["external_event"])
        if value.get("event_type") == "external_event" and isinstance(value.get("payload"), dict):
            return copy.deepcopy(value["payload"])
        return copy.deepcopy(value)

    @staticmethod
    def _commit_record(item: dict[str, Any] | KafkaCommandRecord) -> None:
        if isinstance(item, KafkaCommandRecord):
            item.commit()

    @staticmethod
    def _dead_letter_event(item: dict[str, Any] | KafkaCommandRecord) -> dict[str, Any]:
        value = item.value if isinstance(item, KafkaCommandRecord) else item
        record_key = (
            f"{getattr(item, 'topic', DEFAULT_EXTERNAL_EVENT_TOPIC)}:"
            f"{getattr(item, 'partition', 'unknown')}:"
            f"{getattr(item, 'offset', uuid.uuid4().hex[:12])}"
        )
        return {
            "schema_version": "1.0",
            "event_id": f"invalid-{uuid.uuid4().hex[:12]}",
            "source": "unknown",
            "event_type": "invalid_external_event",
            "status": "error",
            "received_at": utc_now(),
            "idempotency_key": f"invalid:{record_key}",
            "topic": getattr(item, "topic", DEFAULT_EXTERNAL_EVENT_TOPIC),
            "raw": value,
        }


def build_default_runtime() -> tuple[ContractRegistry, ConfigStore, ProcessingStore, IntegrationDispatcher]:
    contracts = ContractRegistry()
    case_store = CaseStore(contracts)
    config_store = ConfigStore(contracts)
    processing_store = ProcessingStore(case_store)
    for domain, attribute in (
        ("tools", "tool_catalog"),
        ("integration_endpoints", "integration_endpoint_catalog"),
        ("n8n_workflows", "n8n_workflow_catalog"),
    ):
        setattr(contracts, attribute, copy.deepcopy(config_store.active_payload(domain)))
    registry = ToolRegistry(contracts)
    dispatcher = IntegrationDispatcher(contracts, registry)
    return contracts, config_store, processing_store, dispatcher


def main() -> None:
    parser = argparse.ArgumentParser(description="ServiceDeskAgents Kafka async runtime")
    parser.add_argument("mode", choices=["publish-once", "worker", "external-event-worker"])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--topic")
    args = parser.parse_args()

    configure_logging()
    validate_startup_environment()
    contracts, config_store, processing_store, dispatcher = build_default_runtime()
    if args.mode == "publish-once":
        publish_limit = args.limit if args.limit is not None else 50
        result = OutboxPublisher(
            processing_store,
            JsonKafkaProducer(),
        ).publish_batch(limit=publish_limit)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return

    if args.mode == "worker":
        topic = args.topic or os.getenv("TOOL_COMMAND_TOPIC", DEFAULT_ASYNC_TOOL_COMMAND_TOPIC)
        consumer = JsonKafkaConsumer(topic=topic)
        result = ToolCommandWorker(processing_store, dispatcher).process_commands(consumer, limit=args.limit)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return

    topic = args.topic or os.getenv("EXTERNAL_EVENT_TOPIC", DEFAULT_EXTERNAL_EVENT_TOPIC)
    consumer = JsonKafkaConsumer(
        topic=topic,
        group_id=os.getenv("EXTERNAL_EVENT_WORKER_GROUP_ID", "servicedesk-external-event-workers"),
        offset_reset_env="EXTERNAL_EVENT_WORKER_OFFSET_RESET",
    )
    result = ExternalEventWorker(processing_store, config_store, contracts).process_events(consumer, limit=args.limit)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
