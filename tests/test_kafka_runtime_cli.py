from __future__ import annotations

import sys
import unittest
from unittest.mock import Mock, patch

from apps.orchestrator.app import kafka_runtime


class KafkaRuntimeCliTest(unittest.TestCase):
    def run_main(self, argv: list[str]) -> dict[str, Mock]:
        contracts = Mock(name="contracts")
        config_store = Mock(name="config_store")
        processing_store = Mock(name="processing_store")
        dispatcher = Mock(name="dispatcher")
        publisher = Mock(name="publisher")
        publisher.publish_batch.return_value = {"mode": "publish-once"}
        tool_worker = Mock(name="tool_worker")
        tool_worker.process_commands.return_value = {"mode": "worker"}
        event_worker = Mock(name="event_worker")
        event_worker.process_events.return_value = {"mode": "external-event-worker"}
        producer = Mock(name="producer")
        consumer = Mock(name="consumer")

        with (
            patch.object(sys, "argv", ["kafka_runtime", *argv]),
            patch.object(kafka_runtime, "configure_logging"),
            patch.object(kafka_runtime, "validate_startup_environment"),
            patch.object(
                kafka_runtime,
                "build_default_runtime",
                return_value=(contracts, config_store, processing_store, dispatcher),
            ),
            patch.object(kafka_runtime, "JsonKafkaProducer", return_value=producer),
            patch.object(kafka_runtime, "JsonKafkaConsumer", return_value=consumer),
            patch.object(kafka_runtime, "OutboxPublisher", return_value=publisher),
            patch.object(kafka_runtime, "ToolCommandWorker", return_value=tool_worker),
            patch.object(kafka_runtime, "ExternalEventWorker", return_value=event_worker),
            patch("builtins.print"),
        ):
            kafka_runtime.main()

        return {
            "publisher": publisher,
            "tool_worker": tool_worker,
            "event_worker": event_worker,
        }

    def test_publish_once_without_limit_uses_default_batch_size(self) -> None:
        result = self.run_main(["publish-once"])

        result["publisher"].publish_batch.assert_called_once_with(limit=50)

    def test_publish_once_with_explicit_limit_uses_requested_batch_size(self) -> None:
        result = self.run_main(["publish-once", "--limit", "3"])

        result["publisher"].publish_batch.assert_called_once_with(limit=3)

    def test_tool_worker_without_limit_is_long_running(self) -> None:
        result = self.run_main(["worker"])

        _, kwargs = result["tool_worker"].process_commands.call_args
        self.assertIsNone(kwargs["limit"])

    def test_external_event_worker_without_limit_is_long_running(self) -> None:
        result = self.run_main(["external-event-worker"])

        _, kwargs = result["event_worker"].process_events.call_args
        self.assertIsNone(kwargs["limit"])

    def test_explicit_limit_applies_to_tool_worker(self) -> None:
        result = self.run_main(["worker", "--limit", "3"])

        _, kwargs = result["tool_worker"].process_commands.call_args
        self.assertEqual(kwargs["limit"], 3)

    def test_explicit_limit_applies_to_external_event_worker(self) -> None:
        result = self.run_main(["external-event-worker", "--limit", "3"])

        _, kwargs = result["event_worker"].process_events.call_args
        self.assertEqual(kwargs["limit"], 3)


if __name__ == "__main__":
    unittest.main()
