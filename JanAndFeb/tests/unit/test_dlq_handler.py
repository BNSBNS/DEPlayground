"""Unit tests for DLQ handler."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from src.common.models import DLQMessage
from src.consumer.dlq_handler import AlertingDLQHandler, DLQHandler


class TestDLQHandler:
    """Tests for DLQHandler class."""

    def test_handler_initialization(self) -> None:
        """Test handler initialization."""
        with patch("src.consumer.dlq_handler.get_settings") as mock_settings:
            mock_settings.return_value.kafka.dlq_topic = "test-dlq"
            mock_settings.return_value.kafka.consumer_group = "test-group"
            mock_settings.return_value.kafka.bootstrap_servers = "localhost:9092"

            handler = DLQHandler()

            assert handler._messages_sent == 0

    @patch("src.consumer.dlq_handler.create_producer")
    def test_handle_failed_message_bytes(
        self,
        mock_create_producer: MagicMock,
    ) -> None:
        """Test handling failed message with bytes input."""
        mock_producer = MagicMock()
        mock_create_producer.return_value = mock_producer

        with patch("src.consumer.dlq_handler.get_settings") as mock_settings:
            mock_settings.return_value.kafka.dlq_topic = "test-dlq"
            mock_settings.return_value.kafka.consumer_group = "test-group"
            mock_settings.return_value.kafka.bootstrap_servers = "localhost:9092"

            handler = DLQHandler()
            error = ValueError("Test error")

            dlq_message = handler.handle_failed_message(
                raw_message=b'{"invalid": json}',
                error=error,
                partition=0,
                offset=123,
            )

            assert dlq_message.error_type == "ValueError"
            assert dlq_message.error_message == "Test error"
            assert dlq_message.partition == 0
            assert dlq_message.offset == 123
            assert handler._messages_sent == 1

    @patch("src.consumer.dlq_handler.create_producer")
    def test_handle_failed_message_string(
        self,
        mock_create_producer: MagicMock,
    ) -> None:
        """Test handling failed message with string input."""
        mock_producer = MagicMock()
        mock_create_producer.return_value = mock_producer

        with patch("src.consumer.dlq_handler.get_settings") as mock_settings:
            mock_settings.return_value.kafka.dlq_topic = "test-dlq"
            mock_settings.return_value.kafka.consumer_group = "test-group"
            mock_settings.return_value.kafka.bootstrap_servers = "localhost:9092"

            handler = DLQHandler()
            error = Exception("Parse error")

            dlq_message = handler.handle_failed_message(
                raw_message="malformed message",
                error=error,
                partition=2,
                offset=456,
            )

            assert dlq_message.original_message == "malformed message"
            assert dlq_message.partition == 2
            assert dlq_message.offset == 456

    @patch("src.consumer.dlq_handler.create_producer")
    def test_get_stats(
        self,
        mock_create_producer: MagicMock,
    ) -> None:
        """Test getting handler statistics."""
        mock_producer = MagicMock()
        mock_create_producer.return_value = mock_producer

        with patch("src.consumer.dlq_handler.get_settings") as mock_settings:
            mock_settings.return_value.kafka.dlq_topic = "test-dlq"
            mock_settings.return_value.kafka.consumer_group = "test-group"
            mock_settings.return_value.kafka.bootstrap_servers = "localhost:9092"

            handler = DLQHandler()

            # Send a few messages
            for i in range(3):
                handler.handle_failed_message(
                    raw_message=f"message {i}",
                    error=ValueError(f"error {i}"),
                    partition=0,
                    offset=i,
                )

            stats = handler.get_stats()
            assert stats["messages_sent"] == 3


class TestAlertingDLQHandler:
    """Tests for AlertingDLQHandler class."""

    @patch("src.consumer.dlq_handler.create_producer")
    def test_alert_triggered_on_threshold(
        self,
        mock_create_producer: MagicMock,
    ) -> None:
        """Test that alert is triggered when threshold is reached."""
        mock_producer = MagicMock()
        mock_create_producer.return_value = mock_producer
        mock_alert = MagicMock()

        with patch("src.consumer.dlq_handler.get_settings") as mock_settings:
            mock_settings.return_value.kafka.dlq_topic = "test-dlq"
            mock_settings.return_value.kafka.consumer_group = "test-group"
            mock_settings.return_value.kafka.bootstrap_servers = "localhost:9092"

            handler = AlertingDLQHandler(
                alert_callback=mock_alert,
                alert_threshold=3,
            )

            # Send 2 messages (below threshold)
            for i in range(2):
                handler.handle_failed_message(
                    raw_message=f"message {i}",
                    error=ValueError(f"error {i}"),
                    partition=0,
                    offset=i,
                )

            mock_alert.assert_not_called()

            # Send 3rd message (reaches threshold)
            handler.handle_failed_message(
                raw_message="message 2",
                error=ValueError("error 2"),
                partition=0,
                offset=2,
            )

            mock_alert.assert_called_once()

    @patch("src.consumer.dlq_handler.create_producer")
    def test_alert_callback_error_handled(
        self,
        mock_create_producer: MagicMock,
    ) -> None:
        """Test that alert callback errors are handled gracefully."""
        mock_producer = MagicMock()
        mock_create_producer.return_value = mock_producer
        mock_alert = MagicMock(side_effect=Exception("Alert failed"))

        with patch("src.consumer.dlq_handler.get_settings") as mock_settings:
            mock_settings.return_value.kafka.dlq_topic = "test-dlq"
            mock_settings.return_value.kafka.consumer_group = "test-group"
            mock_settings.return_value.kafka.bootstrap_servers = "localhost:9092"

            handler = AlertingDLQHandler(
                alert_callback=mock_alert,
                alert_threshold=1,
            )

            # Should not raise even though callback fails
            handler.handle_failed_message(
                raw_message="message",
                error=ValueError("error"),
                partition=0,
                offset=0,
            )

            mock_alert.assert_called_once()
