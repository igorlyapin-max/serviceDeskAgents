from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import Mock, patch

from apps.orchestrator.app import kafka_runtime


class KafkaRuntimeCliTest(unittest.TestCase):
    def run_main(self, argv: list[str]) -> dict[str, Mock]:
        contracts = Mock(name="contracts")
        config_store = Mock(name="config_store")
        processing_store = Mock(name="processing_store")
        publisher = Mock(name="publisher")
        publisher.publish_batch.return_value = {"mode": "publish-once"}
        mcp_worker = Mock(name="mcp_worker")
        mcp_worker.process_commands.return_value = {"mode": "mcp-worker"}
        event_worker = Mock(name="event_worker")
        event_worker.process_events.return_value = {"mode": "external-event-worker"}
        producer = Mock(name="producer")
        consumer = Mock(name="consumer")
        publisher.publish_forever.return_value = {"mode": "publisher"}

        with (
            patch.object(sys, "argv", ["kafka_runtime", *argv]),
            patch.object(kafka_runtime, "configure_logging"),
            patch.object(kafka_runtime, "validate_startup_environment"),
            patch.object(
                kafka_runtime,
                "build_default_runtime",
                return_value=(contracts, config_store, processing_store),
            ),
            patch.object(kafka_runtime, "JsonKafkaProducer", return_value=producer),
            patch.object(kafka_runtime, "JsonKafkaConsumer", return_value=consumer),
            patch.object(kafka_runtime, "OutboxPublisher", return_value=publisher),
            patch.object(kafka_runtime, "McpCommandWorker", return_value=mcp_worker),
            patch.object(kafka_runtime, "ExternalEventWorker", return_value=event_worker),
            patch("builtins.print"),
        ):
            kafka_runtime.main()

        return {
            "publisher": publisher,
            "mcp_worker": mcp_worker,
            "event_worker": event_worker,
        }

    def test_publish_once_without_limit_uses_default_batch_size(self) -> None:
        result = self.run_main(["publish-once"])

        result["publisher"].publish_batch.assert_called_once_with(limit=50)

    def test_publish_once_with_explicit_limit_uses_requested_batch_size(self) -> None:
        result = self.run_main(["publish-once", "--limit", "3"])

        result["publisher"].publish_batch.assert_called_once_with(limit=3)

    def test_outbox_publisher_is_long_running_by_default(self) -> None:
        result = self.run_main(["publisher"])

        result["publisher"].publish_forever.assert_called_once_with(
            limit=50,
            topics=None,
            interval_seconds=2.0,
            max_batches=None,
        )

    def test_outbox_publisher_supports_topic_interval_and_batch_limit(self) -> None:
        result = self.run_main(
            [
                "publisher",
                "--topic",
                "mcp.commands",
                "--limit",
                "3",
                "--interval-seconds",
                "0.5",
                "--max-batches",
                "2",
            ]
        )

        result["publisher"].publish_forever.assert_called_once_with(
            limit=3,
            topics=["mcp.commands"],
            interval_seconds=0.5,
            max_batches=2,
        )

    def test_mcp_worker_without_limit_is_long_running(self) -> None:
        result = self.run_main(["mcp-worker"])

        _, kwargs = result["mcp_worker"].process_commands.call_args
        self.assertIsNone(kwargs["limit"])

    def test_external_event_worker_without_limit_is_long_running(self) -> None:
        result = self.run_main(["external-event-worker"])

        _, kwargs = result["event_worker"].process_events.call_args
        self.assertIsNone(kwargs["limit"])

    def test_explicit_limit_applies_to_mcp_worker(self) -> None:
        result = self.run_main(["mcp-worker", "--limit", "3"])

        _, kwargs = result["mcp_worker"].process_commands.call_args
        self.assertEqual(kwargs["limit"], 3)

    def test_explicit_limit_applies_to_external_event_worker(self) -> None:
        result = self.run_main(["external-event-worker", "--limit", "3"])

        _, kwargs = result["event_worker"].process_events.call_args
        self.assertEqual(kwargs["limit"], 3)

    def test_kafka_security_config_defaults_to_plaintext(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            config = kafka_runtime.kafka_client_security_config()

        self.assertEqual(config, {"security_protocol": "PLAINTEXT"})

    def test_kafka_api_version_normalizes_zero_patch(self) -> None:
        with patch.dict(os.environ, {"KAFKA_API_VERSION": "2.8.0"}, clear=True):
            self.assertEqual(kafka_runtime.kafka_api_version(), (2, 8))

    def test_kafka_security_config_supports_sasl_ssl(self) -> None:
        with patch.dict(
            os.environ,
            {
                "KAFKA_SECURITY_PROTOCOL": "SASL_SSL",
                "KAFKA_SASL_MECHANISM": "SCRAM-SHA-512",
                "KAFKA_SASL_USERNAME": "svc-provider-ops",
                "KAFKA_SASL_PASSWORD": "secret",
                "KAFKA_SSL_CA_FILE": "/etc/kafka/ca.pem",
            },
            clear=True,
        ):
            config = kafka_runtime.kafka_client_security_config()

        self.assertEqual(config["security_protocol"], "SASL_SSL")
        self.assertEqual(config["sasl_mechanism"], "SCRAM-SHA-512")
        self.assertEqual(config["sasl_plain_username"], "svc-provider-ops")
        self.assertEqual(config["sasl_plain_password"], "secret")
        self.assertEqual(config["ssl_cafile"], "/etc/kafka/ca.pem")
        self.assertTrue(config["ssl_check_hostname"])

    def test_kafka_security_config_supports_mtls(self) -> None:
        with patch.dict(
            os.environ,
            {
                "KAFKA_SECURITY_PROTOCOL": "SSL",
                "KAFKA_SSL_CA_FILE": "/etc/kafka/ca.pem",
                "KAFKA_SSL_CERT_FILE": "/etc/kafka/client.pem",
                "KAFKA_SSL_KEY_FILE": "/etc/kafka/client.key",
                "KAFKA_SSL_CHECK_HOSTNAME": "false",
            },
            clear=True,
        ):
            config = kafka_runtime.kafka_client_security_config()

        self.assertEqual(config["security_protocol"], "SSL")
        self.assertEqual(config["ssl_cafile"], "/etc/kafka/ca.pem")
        self.assertEqual(config["ssl_certfile"], "/etc/kafka/client.pem")
        self.assertEqual(config["ssl_keyfile"], "/etc/kafka/client.key")
        self.assertFalse(config["ssl_check_hostname"])

    def test_kafka_security_config_requires_sasl_credentials(self) -> None:
        with patch.dict(os.environ, {"KAFKA_SECURITY_PROTOCOL": "SASL_SSL"}, clear=True):
            with self.assertRaises(kafka_runtime.KafkaRuntimeError):
                kafka_runtime.kafka_client_security_config()

    def test_outbox_publisher_publishes_payload_not_storage_envelope(self) -> None:
        processing_store = Mock(name="processing_store")
        producer = Mock(name="producer")
        outbox_message = {
            "schema_version": "1.0",
            "message_id": "msg-1",
            "topic": "external.events",
            "key": "case-123",
            "event_type": "external_event_received",
            "idempotency_key": "idem-1",
            "status": "publishing",
            "created_at": "2026-07-04T00:00:00Z",
            "attempts": 0,
            "payload": {
                "schema_version": "1.0",
                "event_id": "evt-1",
                "case_id": "case-123",
            },
        }
        processing_store.claim_outbox_batch.return_value = [outbox_message]

        result = kafka_runtime.OutboxPublisher(
            processing_store,
            producer,
            worker_id="publisher-1",
        ).publish_batch(close_producer=False)

        producer.publish.assert_called_once_with("external.events", "case-123", outbox_message["payload"])
        processing_store.mark_outbox_published.assert_called_once_with("msg-1", worker_id="publisher-1")
        self.assertEqual(result["published"], 1)


if __name__ == "__main__":
    unittest.main()
