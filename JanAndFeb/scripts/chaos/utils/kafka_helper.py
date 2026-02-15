"""Kafka helper utilities for chaos testing.

Provides a clean interface for producing test messages to Kafka,
including poison pills and malformed data.
"""

import json
import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from confluent_kafka import Producer, Consumer, KafkaError
from confluent_kafka.admin import AdminClient, NewTopic


@dataclass
class MessageResult:
    """Result of sending a message to Kafka."""

    topic: str
    partition: int | None = None
    offset: int | None = None
    error: str | None = None
    success: bool = True
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class KafkaHelper:
    """Helper class for Kafka operations in chaos testing.

    Provides methods to:
    - Produce valid and invalid messages
    - Consume messages from topics
    - Inspect topic state
    - Create/delete topics

    Example:
        helper = KafkaHelper()

        # Send a poison pill
        result = helper.send_raw("trades", b"not valid json")

        # Send valid trade
        result = helper.send_trade("AAPL", 150.50, 100)
    """

    def __init__(
        self,
        bootstrap_servers: str | None = None,
        topic: str = "trades",
        dlq_topic: str = "trades-dlq",
    ):
        """Initialize Kafka helper.

        Args:
            bootstrap_servers: Kafka broker addresses
            topic: Main topic name
            dlq_topic: DLQ topic name
        """
        self.bootstrap_servers = bootstrap_servers or os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
        )
        self.topic = topic
        self.dlq_topic = dlq_topic

        self._producer: Producer | None = None
        self._consumer: Consumer | None = None
        self._admin: AdminClient | None = None

        # Track sent messages
        self._sent_messages: list[MessageResult] = []
        self._delivery_errors: list[str] = []

    @property
    def producer(self) -> Producer:
        """Get or create Kafka producer."""
        if self._producer is None:
            self._producer = Producer({
                "bootstrap.servers": self.bootstrap_servers,
                "client.id": "chaos-test-producer",
                "acks": "all",
            })
        return self._producer

    @property
    def admin(self) -> AdminClient:
        """Get or create Kafka admin client."""
        if self._admin is None:
            self._admin = AdminClient({
                "bootstrap.servers": self.bootstrap_servers,
            })
        return self._admin

    def _delivery_callback(self, err: Any, msg: Any) -> None:
        """Handle delivery confirmation."""
        if err is not None:
            self._delivery_errors.append(str(err))
        else:
            result = MessageResult(
                topic=msg.topic(),
                partition=msg.partition(),
                offset=msg.offset(),
            )
            self._sent_messages.append(result)

    def send_raw(
        self,
        topic: str | None = None,
        value: bytes | str = b"",
        key: bytes | str | None = None,
    ) -> MessageResult:
        """Send a raw message to Kafka.

        Use this to inject poison pills and malformed data.

        Args:
            topic: Target topic (defaults to main topic)
            value: Raw message value
            key: Optional message key

        Returns:
            MessageResult with delivery info
        """
        topic = topic or self.topic

        if isinstance(value, str):
            value = value.encode("utf-8")
        if isinstance(key, str):
            key = key.encode("utf-8")

        try:
            self.producer.produce(
                topic=topic,
                value=value,
                key=key,
                callback=self._delivery_callback,
            )
            self.producer.flush(timeout=5.0)

            if self._delivery_errors:
                error = self._delivery_errors.pop()
                return MessageResult(topic=topic, error=error, success=False)

            if self._sent_messages:
                return self._sent_messages.pop()

            return MessageResult(topic=topic)

        except Exception as e:
            return MessageResult(topic=topic, error=str(e), success=False)

    def send_json(
        self,
        data: dict[str, Any],
        topic: str | None = None,
        key: str | None = None,
    ) -> MessageResult:
        """Send a JSON message to Kafka.

        Args:
            data: Dictionary to serialize as JSON
            topic: Target topic
            key: Optional message key

        Returns:
            MessageResult with delivery info
        """
        value = json.dumps(data).encode("utf-8")
        return self.send_raw(topic, value, key)

    def send_trade(
        self,
        symbol: str = "TEST_SYM",
        price: float = 100.0,
        volume: float = 10.0,
        side: str = "BUY",
        trader_id: str = "CHAOS_TEST",
        event_timestamp: datetime | None = None,
        trade_id: str | None = None,
    ) -> MessageResult:
        """Send a valid trade event.

        Args:
            symbol: Trading symbol
            price: Trade price
            volume: Trade volume
            side: BUY or SELL
            trader_id: Trader identifier
            event_timestamp: Event time (defaults to now)
            trade_id: Trade UUID (auto-generated if not provided)

        Returns:
            MessageResult with delivery info
        """
        if event_timestamp is None:
            event_timestamp = datetime.now(UTC)
        if trade_id is None:
            trade_id = str(uuid4())

        trade = {
            "trade_id": trade_id,
            "symbol": symbol,
            "price": str(Decimal(str(price))),
            "volume": str(Decimal(str(volume))),
            "side": side,
            "trader_id": trader_id,
            "event_timestamp": event_timestamp.isoformat(),
        }

        return self.send_json(trade, key=symbol)

    def consume_messages(
        self,
        topic: str | None = None,
        max_messages: int = 100,
        timeout: float = 5.0,
        from_beginning: bool = True,
    ) -> list[dict[str, Any]]:
        """Consume messages from a topic.

        Args:
            topic: Topic to consume from
            max_messages: Maximum messages to consume
            timeout: Polling timeout in seconds
            from_beginning: Start from earliest offset

        Returns:
            List of message dictionaries
        """
        topic = topic or self.topic

        consumer = Consumer({
            "bootstrap.servers": self.bootstrap_servers,
            "group.id": f"chaos-test-consumer-{uuid4().hex[:8]}",
            "auto.offset.reset": "earliest" if from_beginning else "latest",
            "enable.auto.commit": False,
        })

        messages = []
        try:
            consumer.subscribe([topic])

            start_time = time.time()
            eof_partitions: set[int] = set()
            assigned_partitions: set[int] | None = None

            while len(messages) < max_messages:
                if time.time() - start_time > timeout:
                    break

                msg = consumer.poll(timeout=1.0)
                if msg is None:
                    if assigned_partitions is None:
                        assignment = consumer.assignment()
                        if assignment:
                            assigned_partitions = {tp.partition for tp in assignment}
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        eof_partitions.add(msg.partition())
                        if assigned_partitions and eof_partitions >= assigned_partitions:
                            break
                    continue

                try:
                    value = json.loads(msg.value().decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    value = {"_raw": msg.value().hex()}

                messages.append({
                    "partition": msg.partition(),
                    "offset": msg.offset(),
                    "key": msg.key().decode("utf-8") if msg.key() else None,
                    "value": value,
                    "timestamp": msg.timestamp()[1],
                })
        finally:
            consumer.close()

        return messages

    def get_topic_info(self, topic: str | None = None) -> dict[str, Any]:
        """Get topic metadata.

        Args:
            topic: Topic name

        Returns:
            Dictionary with topic info
        """
        topic = topic or self.topic

        metadata = self.admin.list_topics(timeout=10)
        if topic in metadata.topics:
            topic_metadata = metadata.topics[topic]
            return {
                "name": topic,
                "partitions": len(topic_metadata.partitions),
                "error": str(topic_metadata.error) if topic_metadata.error else None,
            }
        return {"name": topic, "error": "Topic not found"}

    def count_messages(self, topic: str | None = None) -> int:
        """Count messages in a topic.

        Args:
            topic: Topic name

        Returns:
            Approximate message count
        """
        topic = topic or self.topic

        consumer = Consumer({
            "bootstrap.servers": self.bootstrap_servers,
            "group.id": f"chaos-count-{uuid4().hex[:8]}",
            "auto.offset.reset": "earliest",
        })

        try:
            # Get partition info
            metadata = consumer.list_topics(topic, timeout=10)
            if topic not in metadata.topics:
                return 0

            partitions = metadata.topics[topic].partitions
            total = 0

            for partition_id in partitions:
                from confluent_kafka import TopicPartition
                tp = TopicPartition(topic, partition_id)
                low, high = consumer.get_watermark_offsets(tp, timeout=10)
                total += high - low

            return total
        finally:
            consumer.close()

    def clear_topic(self, topic: str | None = None) -> bool:
        """Clear all messages from a topic by deleting and recreating.

        Args:
            topic: Topic to clear

        Returns:
            True if successful
        """
        topic = topic or self.topic

        try:
            # Get current config
            metadata = self.admin.list_topics(timeout=10)
            if topic not in metadata.topics:
                return True

            num_partitions = len(metadata.topics[topic].partitions)

            # Delete topic
            self.admin.delete_topics([topic])
            time.sleep(2)  # Wait for deletion

            # Recreate topic
            new_topic = NewTopic(topic, num_partitions=num_partitions, replication_factor=1)
            self.admin.create_topics([new_topic])
            time.sleep(2)  # Wait for creation

            return True
        except Exception:
            return False

    def close(self) -> None:
        """Close all connections."""
        if self._producer:
            self._producer.flush()
            self._producer = None
        if self._consumer:
            self._consumer.close()
            self._consumer = None
