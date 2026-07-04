from __future__ import annotations

import argparse
import copy
import hashlib
import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Iterable, Protocol

from .action_gates import utc_now
from .cases import CaseStore
from .config_registry import ConfigStore
from .contracts import ContractValidationError
from .contracts import ContractRegistry
from .mcp_execution import McpExecutionError, invoke_mcp_tool_request, validate_async_ack, validate_sync_result
from .metrics import metrics
from .processing import (
    DEFAULT_ASYNC_MCP_COMMAND_TOPIC,
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
SERVICEDESK_RESULT_CODES = {"Выполнено", "Не выполнено"}


class RuntimeHeartbeat:
    def __init__(
        self,
        processing_store: ProcessingStore,
        *,
        role: str,
        display_name: str,
        worker_id: str,
        topic: str | None = None,
        interval_seconds: float | None = None,
    ):
        self.processing_store = processing_store
        self.role = role
        self.display_name = display_name
        self.worker_id = worker_id
        self.topic = topic
        self.interval_seconds = interval_seconds or float(os.getenv("ASYNC_RUNTIME_HEARTBEAT_INTERVAL_SECONDS", "5"))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self) -> "RuntimeHeartbeat":
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc: BaseException | None, traceback: Any) -> None:
        if exc is None:
            self.stop(status="stopped")
        else:
            self.stop(status="error", error=str(exc))

    def start(self) -> None:
        self.beat(status="ok")
        self._thread = threading.Thread(
            target=self._run,
            name=f"{self.role}-heartbeat",
            daemon=True,
        )
        self._thread.start()

    def stop(self, *, status: str = "stopped", error: str | None = None) -> None:
        self._stop.set()
        self.beat(status=status, error=error)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def beat(
        self,
        *,
        status: str = "ok",
        details: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        self.processing_store.record_runtime_heartbeat(
            role=self.role,
            display_name=self.display_name,
            worker_id=self.worker_id,
            topic=self.topic,
            status=status,
            details=details,
            error=error,
        )

    def _run(self) -> None:
        while not self._stop.wait(max(1.0, self.interval_seconds)):
            self.beat(status="ok")


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
        offset_reset_env: str = "MCP_COMMAND_WORKER_OFFSET_RESET",
    ):
        self.topic = topic or os.getenv("MCP_COMMAND_TOPIC", DEFAULT_ASYNC_MCP_COMMAND_TOPIC)
        self.bootstrap_servers = bootstrap_servers or os.getenv("KAFKA_BOOTSTRAP_SERVERS", "127.0.0.1:19092")
        self.group_id = group_id or os.getenv("MCP_COMMAND_WORKER_GROUP_ID", "servicedesk-mcp-workers")
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
        topic: str | None = None,
    ):
        self.processing_store = processing_store
        self.producer = producer
        self.worker_id = worker_id or f"outbox-publisher-{uuid.uuid4().hex[:8]}"
        self.topic = topic or "*"

    def publish_batch(
        self,
        *,
        limit: int = 50,
        topics: list[str] | None = None,
        close_producer: bool = True,
    ) -> dict[str, Any]:
        messages = self.processing_store.claim_outbox_batch(
            worker_id=self.worker_id,
            limit=limit,
            topics=topics,
        )
        published = 0
        failed = 0
        for message in messages:
            try:
                wire_payload = self._wire_payload(message)
                self.producer.publish(message["topic"], message["key"], wire_payload)
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
        if close_producer:
            close = getattr(self.producer, "close", None)
            if callable(close):
                close()
        return {
            "schema_version": "1.0",
            "claimed": len(messages),
            "published": published,
            "failed": failed,
        }

    @staticmethod
    def _wire_payload(message: dict[str, Any]) -> dict[str, Any]:
        payload = message.get("payload")
        if not isinstance(payload, dict):
            raise KafkaRuntimeError("Outbox message payload должен быть JSON object.")
        return copy.deepcopy(payload)

    def publish_forever(
        self,
        *,
        limit: int = 50,
        topics: list[str] | None = None,
        interval_seconds: float = 2.0,
        max_batches: int | None = None,
    ) -> dict[str, Any]:
        totals = {
            "schema_version": "1.0",
            "mode": "publisher",
            "batches": 0,
            "claimed": 0,
            "published": 0,
            "failed": 0,
        }
        heartbeat_topic = ",".join(topics) if topics else self.topic
        heartbeat = RuntimeHeartbeat(
            self.processing_store,
            role="outbox_publisher",
            display_name="Outbox publisher",
            worker_id=self.worker_id,
            topic=heartbeat_topic,
        )
        try:
            with heartbeat:
                while True:
                    result = self.publish_batch(limit=limit, topics=topics, close_producer=False)
                    totals["batches"] += 1
                    totals["claimed"] += int(result.get("claimed") or 0)
                    totals["published"] += int(result.get("published") or 0)
                    totals["failed"] += int(result.get("failed") or 0)
                    heartbeat.beat(status="ok", details=totals)
                    log_json(
                        logger,
                        logging.INFO,
                        "outbox_publisher_batch_completed",
                        claimed=result.get("claimed"),
                        published=result.get("published"),
                        failed=result.get("failed"),
                        batch=totals["batches"],
                    )
                    if max_batches is not None and totals["batches"] >= max_batches:
                        return totals
                    if int(result.get("claimed") or 0) == 0:
                        time.sleep(max(0.1, interval_seconds))
        finally:
            close = getattr(self.producer, "close", None)
            if callable(close):
                close()


def kafka_api_version() -> tuple[int, ...]:
    value = os.getenv("KAFKA_API_VERSION", "2.3.0").strip()
    parts = [int(part) for part in value.split(".") if part.strip()]
    if not 2 <= len(parts) <= 3:
        raise KafkaRuntimeError("KAFKA_API_VERSION должен иметь формат major.minor или major.minor.patch.")
    if len(parts) == 3 and parts[2] == 0:
        parts = parts[:2]
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


class McpCommandWorker:
    def __init__(
        self,
        processing_store: ProcessingStore,
        config_store: ConfigStore,
        *,
        worker_id: str | None = None,
        topic: str | None = None,
    ):
        self.processing_store = processing_store
        self.config_store = config_store
        self.worker_id = worker_id or f"mcp-worker-{uuid.uuid4().hex[:8]}"
        self.topic = topic or os.getenv("MCP_COMMAND_TOPIC", DEFAULT_ASYNC_MCP_COMMAND_TOPIC)

    def process_command(self, command: dict[str, Any]) -> dict[str, Any]:
        command = self._extract_command(command)
        self._validate_command(command)
        command = self.processing_store.verify_tool_command(command)
        self._validate_command(command)
        capability, environment = self._resolve_command_context(command)
        receipt = self.processing_store.begin_tool_command(command, worker_id=self.worker_id)
        if receipt["duplicate"]:
            existing = receipt.get("receipt") or {}
            log_json(
                logger,
                logging.INFO,
                "mcp_command_duplicate_skipped",
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
                "mcp_result": existing.get("result", {}).get("mcp_result"),
            }

        started_at = time.monotonic()
        external_result = None
        try:
            self.processing_store.mark_tool_command_dispatch_started(command, worker_id=self.worker_id)
            ack_or_result = invoke_mcp_tool_request(
                environment=environment,
                mcp_request=command["mcp_request"],
                secret_resolver=os.getenv,
                request_id=command["command_id"],
            )
            if command["mcp_request"].get("execution_mode") == "async":
                validate_async_ack(ack_or_result, correlation_id=command["correlation_id"])
            else:
                validate_sync_result(ack_or_result, capability)
            result = self._success_result(
                command,
                ack_or_result,
                duration_ms=int((time.monotonic() - started_at) * 1000),
            )
        except McpExecutionError as error:
            result = self._failure_result(
                command,
                str(error),
                duration_ms=int((time.monotonic() - started_at) * 1000),
            )
            external_result = self._record_dispatch_failure(command, result)

        duration_seconds = time.monotonic() - started_at
        self.processing_store.record_tool_command_result(
            result,
            case_id=command["case_id"],
            idempotency_key=f"{command['idempotency_key']}:mcp_result",
        )
        metrics.increment(
            "mcp_command_worker_total",
            {"status": result["status"], "capability_id": command["capability_id"]},
        )
        metrics.observe(
            "mcp_command_worker_duration_seconds",
            duration_seconds,
            {"capability_id": command["capability_id"], "status": result["status"]},
        )
        log_json(
            logger,
            logging.INFO,
            "mcp_command_processed",
            command_id=command["command_id"],
            case_id=command["case_id"],
            capability_id=command["capability_id"],
            mcp_environment_id=command["mcp_environment_id"],
            status=result["status"],
            duration_ms=int(duration_seconds * 1000),
        )
        response = {
            "schema_version": "1.0",
            "command_id": command["command_id"],
            "case_id": command["case_id"],
            "wait_id": command["wait_id"],
            "mcp_result": result,
            "tool_result": result,
        }
        if external_result:
            response["external_event_result"] = external_result
        self.processing_store.complete_tool_command(command, response, worker_id=self.worker_id)
        return response

    def process_commands(
        self,
        commands: Iterable[dict[str, Any] | KafkaCommandRecord],
        *,
        limit: int | None = None,
    ) -> dict[str, Any]:
        processed = 0
        failed = 0
        dead_lettered = 0
        handled = 0
        with RuntimeHeartbeat(
            self.processing_store,
            role="mcp_worker",
            display_name="MCP command worker",
            worker_id=self.worker_id,
            topic=self.topic,
        ) as heartbeat:
            for item in commands:
                if limit is not None and handled >= limit:
                    break
                command: dict[str, Any] | None = None
                heartbeat.beat(status="ok", details={"handled": handled, "processed": processed, "failed": failed})
                try:
                    command = self._extract_command(item)
                    self.process_command(command)
                    self._commit_record(item)
                    processed += 1
                    handled += 1
                except (KafkaRuntimeError, McpExecutionError, ProcessingConflict, ProcessingNotFound) as error:
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
                            "mcp_command_dead_letter_failed",
                            error=ProcessingStore._sanitize_error_text(str(dlq_error)),
                        )
                    metrics.increment("mcp_command_worker_total", {"status": "failed", "capability_id": "unknown"})
                    log_json(
                        logger,
                        logging.ERROR,
                        "mcp_command_failed",
                        error=ProcessingStore._sanitize_error_text(str(error)),
                    )
                except Exception as error:  # noqa: BLE001 - no commit for transient/unclassified failures
                    failed += 1
                    handled += 1
                    metrics.increment("mcp_command_worker_total", {"status": "failed", "capability_id": "unknown"})
                    log_json(
                        logger,
                        logging.ERROR,
                        "mcp_command_failed_without_commit",
                        error=ProcessingStore._sanitize_error_text(str(error)),
                    )
            heartbeat.beat(
                status="ok",
                details={"handled": handled, "processed": processed, "failed": failed, "dead_lettered": dead_lettered},
            )
        return {
            "schema_version": "1.0",
            "processed": processed,
            "failed": failed,
            "dead_lettered": dead_lettered,
        }

    def _resolve_command_context(self, command: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        capability = command.get("capability_snapshot")
        if not isinstance(capability, dict) or capability.get("capability_id") != command.get("capability_id"):
            capability = self._find_config_item(
                self.config_store.active_payload("capabilities").get("capabilities", []),
                "capability_id",
                command["capability_id"],
            )
        environment = command.get("mcp_environment_snapshot")
        if not isinstance(environment, dict) or environment.get("environment_id") != command.get("mcp_environment_id"):
            environment = self._find_config_item(
                self.config_store.active_payload("mcp_environments").get("environments", []),
                "environment_id",
                command["mcp_environment_id"],
            )
        return capability, environment

    @staticmethod
    def _find_config_item(items: Iterable[dict[str, Any]], key: str, value: str) -> dict[str, Any]:
        for item in items:
            if item.get(key) == value:
                return copy.deepcopy(item)
        raise McpExecutionError(f"MCP command ссылается на неизвестный {key}: {value}.")

    @classmethod
    def _success_result(cls, command: dict[str, Any], mcp_result: dict[str, Any], *, duration_ms: int) -> dict[str, Any]:
        return {
            **cls._tool_result_base(command, duration_ms=duration_ms),
            "schema_version": "1.0",
            "tool_name": command["mcp_tool_name"],
            "adapter_type": "mcp_tool",
            "endpoint_id": command["mcp_environment_id"],
            "operation_id": command["mcp_tool_name"],
            "status": "success",
            "output": copy.deepcopy(mcp_result),
            "extensions": {
                "capability_id": command["capability_id"],
                "mcp_environment_id": command["mcp_environment_id"],
                "mcp_tool_name": command["mcp_tool_name"],
                "external_execution_id": mcp_result.get("external_execution_id"),
                "diagnostics": copy.deepcopy(mcp_result.get("diagnostics") or {}),
            },
        }

    @classmethod
    def _failure_result(cls, command: dict[str, Any], message: str, *, duration_ms: int) -> dict[str, Any]:
        return {
            **cls._tool_result_base(command, duration_ms=duration_ms),
            "schema_version": "1.0",
            "tool_name": command["mcp_tool_name"],
            "adapter_type": "mcp_tool",
            "endpoint_id": command["mcp_environment_id"],
            "operation_id": command["mcp_tool_name"],
            "status": "error",
            "output": {},
            "error": {
                "code": "mcp_execution_failed",
                "message": ProcessingStore._sanitize_error_text(message),
            },
            "extensions": {
                "capability_id": command["capability_id"],
                "mcp_environment_id": command["mcp_environment_id"],
                "mcp_tool_name": command["mcp_tool_name"],
            },
        }

    @staticmethod
    def _tool_result_base(command: dict[str, Any], *, duration_ms: int) -> dict[str, Any]:
        invocation = command.get("invocation") if isinstance(command.get("invocation"), dict) else {}
        extensions = invocation.get("extensions") if isinstance(invocation.get("extensions"), dict) else {}
        invocation_id = str(invocation.get("invocation_id") or command["command_id"])
        action_id = str(invocation.get("action_id") or invocation.get("launch_id") or command["capability_id"])
        policy_rule_id = str(
            invocation.get("policy_rule_id")
            or extensions.get("policy_rule_id")
            or f"capability.{command['capability_id']}.mcp_dispatch"
        )
        return {
            "invocation_id": invocation_id,
            "action_id": action_id,
            "policy_rule_id": policy_rule_id,
            "duration_ms": max(0, int(duration_ms)),
            "attempts": int(command.get("attempts") or 1),
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
            "capability_id",
            "mcp_environment_id",
            "mcp_tool_name",
            "mcp_request",
            "invocation",
        }
        missing = sorted(key for key in required if key not in command)
        if missing:
            raise KafkaRuntimeError(f"MCP command misses required fields: {', '.join(missing)}")
        if command["schema_version"] != "1.0" or command["command_type"] != "async_mcp_capability_invocation":
            raise KafkaRuntimeError("MCP command имеет неподдерживаемую версию или тип.")
        if not isinstance(command.get("mcp_request"), dict):
            raise KafkaRuntimeError("MCP command mcp_request должен быть object.")

    @staticmethod
    def _extract_command(item: dict[str, Any] | KafkaCommandRecord) -> dict[str, Any]:
        value = item.value if isinstance(item, KafkaCommandRecord) else item
        value = decode_kafka_json_object(value)
        if value.get("event_type") == "async_mcp_capability_invocation_requested" and isinstance(value.get("payload"), dict):
            command = copy.deepcopy(value["payload"])
            command["topic"] = value.get("topic") or command.get("topic") or DEFAULT_ASYNC_MCP_COMMAND_TOPIC
            return command
        command = copy.deepcopy(value)
        command.setdefault("topic", DEFAULT_ASYNC_MCP_COMMAND_TOPIC)
        return command

    @staticmethod
    def _commit_record(item: dict[str, Any] | KafkaCommandRecord) -> None:
        if isinstance(item, KafkaCommandRecord):
            item.commit()

    @staticmethod
    def _dead_letter_command(item: dict[str, Any] | KafkaCommandRecord) -> dict[str, Any]:
        value = item.value if isinstance(item, KafkaCommandRecord) else item
        record_key = (
            f"{getattr(item, 'topic', DEFAULT_ASYNC_MCP_COMMAND_TOPIC)}:"
            f"{getattr(item, 'partition', 'unknown')}:"
            f"{getattr(item, 'offset', uuid.uuid4().hex[:12])}"
        )
        return {
            "schema_version": "1.0",
            "command_id": f"invalid-{uuid.uuid4().hex[:12]}",
            "command_type": "invalid_mcp_command",
            "topic": getattr(item, "topic", DEFAULT_ASYNC_MCP_COMMAND_TOPIC),
            "case_id": "unknown",
            "wait_id": None,
            "correlation_id": None,
            "idempotency_key": f"invalid:{record_key}",
            "raw": value,
        }

    def _record_dispatch_failure(self, command: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
        error = result.get("error") or {
            "code": f"mcp_status_{result['status']}",
            "message": f"MCP-вызов завершился статусом {result['status']}.",
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
                "code": str(error.get("code") or "mcp_dispatch_failed"),
                "message": str(error.get("message") or "Async MCP-вызов завершился ошибкой."),
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
        topic: str | None = None,
    ):
        self.processing_store = processing_store
        self.config_store = config_store
        self.contracts = contracts
        self.worker_id = worker_id or f"external-event-worker-{uuid.uuid4().hex[:8]}"
        self.topic = topic or os.getenv("EXTERNAL_EVENT_TOPIC", DEFAULT_EXTERNAL_EVENT_TOPIC)

    def process_event(
        self,
        event: dict[str, Any] | KafkaCommandRecord,
        *,
        received_transport: str = "kafka_event",
        source_topic: str | None = None,
    ) -> dict[str, Any]:
        event = self._extract_event(event)
        event.setdefault("received_at", utc_now())
        event = self._enrich_event_from_receipt_or_wait(event)
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
        with RuntimeHeartbeat(
            self.processing_store,
            role="external_event_worker",
            display_name="External event worker",
            worker_id=self.worker_id,
            topic=self.topic,
        ) as heartbeat:
            for item in events:
                if limit is not None and handled >= limit:
                    break
                event: dict[str, Any] | None = None
                heartbeat.beat(status="ok", details={"handled": handled, "processed": processed, "failed": failed})
                try:
                    event = self._extract_event(item)
                    self.process_event(
                        item,
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
            heartbeat.beat(
                status="ok",
                details={"handled": handled, "processed": processed, "failed": failed, "dead_lettered": dead_lettered},
            )
        return {
            "schema_version": "1.0",
            "processed": processed,
            "failed": failed,
            "dead_lettered": dead_lettered,
        }

    def _enrich_event_from_receipt_or_wait(self, event: dict[str, Any]) -> dict[str, Any]:
        event = copy.deepcopy(event)
        receipt = self.processing_store.external_event_receipt(str(event.get("idempotency_key") or ""))
        if receipt:
            for key in ("case_id", "ticket_id", "wait_id", "correlation_id", "source", "event_type", "status"):
                if receipt.get(key) and not event.get(key):
                    event[key] = receipt[key]
            return event

        correlation_id = event.get("correlation_id")
        if not correlation_id:
            return event
        wait = self.processing_store.active_wait_by_correlation(
            str(correlation_id),
            case_id=event.get("case_id"),
        )
        if not wait:
            return event
        event.setdefault("case_id", wait.get("case_id"))
        event.setdefault("ticket_id", wait.get("ticket_id"))
        event.setdefault("wait_id", wait.get("wait_id"))
        return event

    @classmethod
    def _extract_event(cls, item: dict[str, Any] | KafkaCommandRecord) -> dict[str, Any]:
        value = item.value if isinstance(item, KafkaCommandRecord) else item
        value = decode_kafka_json_object(value)
        if value.get("event_type") == "external_event_received" and isinstance(value.get("payload"), dict):
            payload = value["payload"]
            if isinstance(payload.get("external_event"), dict):
                return copy.deepcopy(payload["external_event"])
        if value.get("event_type") == "external_event" and isinstance(value.get("payload"), dict):
            return copy.deepcopy(value["payload"])
        service_desk_event = cls._service_desk_event_from_kafka_record(item, value)
        if service_desk_event:
            return service_desk_event
        return copy.deepcopy(value)

    @classmethod
    def _service_desk_event_from_kafka_record(
        cls,
        item: dict[str, Any] | KafkaCommandRecord,
        value: dict[str, Any],
    ) -> dict[str, Any] | None:
        topic = getattr(item, "topic", None) if isinstance(item, KafkaCommandRecord) else None
        key = getattr(item, "key", None) if isinstance(item, KafkaCommandRecord) else None
        has_task_result = "TaskResultCode" in value
        has_temp_password = "personalID" in value and "password" in value
        is_invalid_topic = bool(topic and str(topic).endswith(".invalid"))
        if not has_task_result and not has_temp_password and not is_invalid_topic:
            return None

        correlation_id = cls._service_desk_correlation_id(key, value)
        record_ref = cls._record_reference(item, value)
        metadata = {
            "adapter": "operu_it_servicedesk",
            "source_topic": topic,
            "message_key": key,
        }
        metadata = {name: item for name, item in metadata.items() if item is not None}
        business_ref = cls._service_desk_business_reference(
            "task-result",
            correlation_id,
            value,
        )
        event: dict[str, Any] = {
            "schema_version": "1.0",
            "event_id": f"servicedesk-{business_ref}",
            "correlation_id": correlation_id,
            "source": "service_desk",
            "event_type": "servicedesk_task_result",
            "status": "success",
            "received_at": utc_now(),
            "idempotency_key": f"servicedesk:{business_ref}",
            "metadata": metadata,
        }

        for field in ("case_id", "ticket_id", "wait_id"):
            if value.get(field):
                event[field] = value[field]

        if has_temp_password:
            explicit_correlation_id = cls._service_desk_explicit_correlation_id(value)
            if not explicit_correlation_id:
                raise KafkaRuntimeError(
                    "ServiceDesk temp_password требует явный correlation_id, task_number, TaskNumber или task_key."
                )
            business_ref = cls._service_desk_business_reference(
                "temp-password",
                explicit_correlation_id,
                {"personalID": value.get("personalID"), "source_topic": topic},
            )
            event["event_id"] = f"servicedesk-{business_ref}"
            event["correlation_id"] = explicit_correlation_id
            event["idempotency_key"] = f"servicedesk:{business_ref}"
            event["event_type"] = "servicedesk_temp_password"
            event["result"] = {
                "personal_id": value.get("personalID"),
                "password": value.get("password"),
                "task_key": explicit_correlation_id,
                "source_topic": topic,
            }
            return event

        if is_invalid_topic and not has_task_result:
            business_ref = cls._service_desk_business_reference(
                "task-invalid",
                correlation_id,
                value,
            )
            event["event_id"] = f"servicedesk-{business_ref}"
            event["idempotency_key"] = f"servicedesk:{business_ref}"
            event["event_type"] = "servicedesk_task_result"
            event["status"] = "error"
            event["result"] = {
                "task_key": correlation_id,
                "task_number": correlation_id,
                "invalid_payload": copy.deepcopy(value),
                "source_topic": topic,
            }
            event["error"] = {
                "code": "servicedesk_invalid_task",
                "message": "Сервисдеск вернул сообщение в invalid topic.",
            }
            return event

        result_code = str(value.get("TaskResultCode") or "").strip()
        result_message = str(value.get("TaskResultMessage") or "").strip()
        if result_code not in SERVICEDESK_RESULT_CODES:
            raise KafkaRuntimeError(
                "ServiceDesk TaskResultCode должен быть одним из: Выполнено, Не выполнено."
            )
        event["status"] = "success" if result_code == "Выполнено" else "error"
        event["result"] = {
            "result_code": result_code,
            "result_message": result_message,
            "task_key": correlation_id,
            "task_number": correlation_id,
            "source_topic": topic,
        }
        if event["status"] == "error":
            event["error"] = {
                "code": "servicedesk_task_failed",
                "message": result_message or result_code or "Сервисдеск вернул неуспешный результат.",
            }
        return event

    @staticmethod
    def _service_desk_correlation_id(key: str | None, value: dict[str, Any]) -> str:
        candidates = (
            key,
            value.get("correlation_id"),
            value.get("CorrelationId"),
            value.get("task_number"),
            value.get("TaskNumber"),
            value.get("task_key"),
        )
        for candidate in candidates:
            if candidate:
                return str(candidate)
        serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        return f"servicedesk-{hashlib.sha256(serialized.encode('utf-8')).hexdigest()[:16]}"

    @staticmethod
    def _service_desk_explicit_correlation_id(value: dict[str, Any]) -> str | None:
        for candidate in (
            value.get("correlation_id"),
            value.get("CorrelationId"),
            value.get("task_number"),
            value.get("TaskNumber"),
            value.get("task_key"),
        ):
            if candidate:
                return str(candidate)
        return None

    @classmethod
    def _service_desk_business_reference(
        cls,
        event_kind: str,
        correlation_id: str,
        payload: dict[str, Any],
    ) -> str:
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]
        return cls._safe_event_token(f"{event_kind}-{correlation_id}-{digest}")

    @staticmethod
    def _record_reference(item: dict[str, Any] | KafkaCommandRecord, value: dict[str, Any]) -> str:
        if isinstance(item, KafkaCommandRecord) and item.topic is not None and item.offset is not None:
            parts = [str(item.topic), str(item.partition if item.partition is not None else "p"), str(item.offset)]
            return "-".join(ExternalEventWorker._safe_event_token(part) for part in parts)
        serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]
        return f"payload-{digest}"

    @staticmethod
    def _safe_event_token(value: str) -> str:
        token = "".join(char if char.isalnum() or char in "_.:-" else "-" for char in str(value))
        return token[:120] or "unknown"

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


class AgentTaskWorker:
    def __init__(
        self,
        processing_store: ProcessingStore,
        *,
        worker_id: str | None = None,
        topic: str | None = None,
        lease_seconds: int | None = None,
    ):
        self.processing_store = processing_store
        self.worker_id = worker_id or f"agent-task-worker-{uuid.uuid4().hex[:8]}"
        self.topic = topic or os.getenv("AGENT_TASK_TOPIC", "agent.tasks")
        self.lease_seconds = lease_seconds or int(os.getenv("AGENT_TASK_LEASE_SECONDS", "60"))

    def process_batch(self, *, limit: int = 50, heartbeat: RuntimeHeartbeat | None = None) -> dict[str, Any]:
        if heartbeat is None:
            with RuntimeHeartbeat(
                self.processing_store,
                role="agent_task_worker",
                display_name="Agent task worker",
                worker_id=self.worker_id,
                topic=self.topic,
            ) as batch_heartbeat:
                return self._process_batch(limit=limit, heartbeat=batch_heartbeat)
        return self._process_batch(limit=limit, heartbeat=heartbeat)

    def _process_batch(self, *, limit: int = 50, heartbeat: RuntimeHeartbeat) -> dict[str, Any]:
        processed = 0
        failed = 0
        handled = 0
        while handled < max(1, limit):
            heartbeat.beat(status="ok", details={"handled": handled, "processed": processed, "failed": failed})
            task = self.processing_store.claim_next_task(
                task_type="langgraph_resume",
                worker_id=self.worker_id,
                lease_seconds=self.lease_seconds,
            )
            if not task:
                break
            handled += 1
            try:
                result = self.processing_store.process_external_event_resume_task(
                    task,
                    worker_id=self.worker_id,
                )
                processed += 1
                metrics.increment("agent_task_worker_total", {"task_type": task.get("task_type"), "status": "completed"})
                log_json(
                    logger,
                    logging.INFO,
                    "agent_task_processed",
                    task_id=task.get("task_id"),
                    task_type=task.get("task_type"),
                    run_id=task.get("run_id"),
                    case_id=task.get("case_id"),
                    result=result,
                )
            except Exception as error:  # noqa: BLE001 - durable task failure is better than silent queue buildup
                failed += 1
                self.processing_store.fail_task(
                    task["task_id"],
                    worker_id=self.worker_id,
                    error=str(error),
                )
                metrics.increment("agent_task_worker_total", {"task_type": task.get("task_type"), "status": "failed"})
                log_json(
                    logger,
                    logging.ERROR,
                    "agent_task_failed",
                    task_id=task.get("task_id"),
                    task_type=task.get("task_type"),
                    run_id=task.get("run_id"),
                    case_id=task.get("case_id"),
                    error=ProcessingStore._sanitize_error_text(str(error)),
                )
        heartbeat.beat(status="ok", details={"handled": handled, "processed": processed, "failed": failed})
        return {
            "schema_version": "1.0",
            "processed": processed,
            "failed": failed,
            "handled": handled,
        }

    def process_forever(
        self,
        *,
        limit: int = 50,
        interval_seconds: float = 2.0,
        max_batches: int | None = None,
    ) -> dict[str, Any]:
        totals = {"schema_version": "1.0", "processed": 0, "failed": 0, "handled": 0, "batches": 0}
        with RuntimeHeartbeat(
            self.processing_store,
            role="agent_task_worker",
            display_name="Agent task worker",
            worker_id=self.worker_id,
            topic=self.topic,
        ) as heartbeat:
            while max_batches is None or totals["batches"] < max_batches:
                result = self.process_batch(limit=limit, heartbeat=heartbeat)
                totals["processed"] += int(result.get("processed") or 0)
                totals["failed"] += int(result.get("failed") or 0)
                totals["handled"] += int(result.get("handled") or 0)
                totals["batches"] += 1
                heartbeat.beat(status="ok", details=totals)
                if result.get("handled"):
                    log_json(
                        logger,
                        logging.INFO,
                        "agent_task_worker_batch_completed",
                        processed=result.get("processed"),
                        failed=result.get("failed"),
                        handled=result.get("handled"),
                    )
                time.sleep(max(0.2, interval_seconds))
        return totals


def build_default_runtime() -> tuple[ContractRegistry, ConfigStore, ProcessingStore]:
    contracts = ContractRegistry()
    case_store = CaseStore(contracts)
    config_store = ConfigStore(contracts)
    processing_store = ProcessingStore(case_store, config_store=config_store)
    from .workflow import TicketWorkflow

    workflow = TicketWorkflow(
        contracts=contracts,
        case_store=case_store,
        config_store=config_store,
        processing_store=processing_store,
    )
    processing_store.attach_workflow(workflow)
    return contracts, config_store, processing_store


def main() -> None:
    parser = argparse.ArgumentParser(description="ServiceDeskAgents Kafka async runtime")
    parser.add_argument(
        "mode",
        choices=["publish-once", "publisher", "mcp-worker", "external-event-worker", "agent-task-worker"],
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--topic")
    parser.add_argument("--interval-seconds", type=float, default=2.0)
    parser.add_argument("--max-batches", type=int)
    args = parser.parse_args()

    configure_logging()
    validate_startup_environment()
    contracts, config_store, processing_store = build_default_runtime()
    if args.mode == "publish-once":
        publish_limit = args.limit if args.limit is not None else 50
        result = OutboxPublisher(
            processing_store,
            JsonKafkaProducer(),
            topic="*",
        ).publish_batch(limit=publish_limit)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return

    if args.mode == "publisher":
        publish_limit = args.limit if args.limit is not None else 50
        topics = [args.topic] if args.topic else None
        result = OutboxPublisher(
            processing_store,
            JsonKafkaProducer(),
            topic=args.topic or "*",
        ).publish_forever(
            limit=publish_limit,
            topics=topics,
            interval_seconds=args.interval_seconds,
            max_batches=args.max_batches,
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return

    if args.mode == "mcp-worker":
        topic = args.topic or os.getenv("MCP_COMMAND_TOPIC", DEFAULT_ASYNC_MCP_COMMAND_TOPIC)
        consumer = JsonKafkaConsumer(
            topic=topic,
            group_id=os.getenv("MCP_COMMAND_WORKER_GROUP_ID", "servicedesk-mcp-workers"),
            offset_reset_env="MCP_COMMAND_WORKER_OFFSET_RESET",
        )
        result = McpCommandWorker(processing_store, config_store, topic=topic).process_commands(consumer, limit=args.limit)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return

    if args.mode == "agent-task-worker":
        task_limit = args.limit if args.limit is not None else 50
        result = AgentTaskWorker(
            processing_store,
            topic=args.topic or os.getenv("AGENT_TASK_TOPIC", "agent.tasks"),
        ).process_forever(
            limit=task_limit,
            interval_seconds=args.interval_seconds,
            max_batches=args.max_batches,
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return

    topic = args.topic or os.getenv("EXTERNAL_EVENT_TOPIC", DEFAULT_EXTERNAL_EVENT_TOPIC)
    consumer = JsonKafkaConsumer(
        topic=topic,
        group_id=os.getenv("EXTERNAL_EVENT_WORKER_GROUP_ID", "servicedesk-external-event-workers"),
        offset_reset_env="EXTERNAL_EVENT_WORKER_OFFSET_RESET",
    )
    result = ExternalEventWorker(processing_store, config_store, contracts, topic=topic).process_events(
        consumer,
        limit=args.limit,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
