from __future__ import annotations

from typing import Any

from aiokafka import AIOKafkaConsumer
from fastapi import APIRouter

from src.config import settings
from src.logging import get_logger

router = APIRouter(prefix="/topics", tags=["topics"])
log = get_logger(__name__)

TOPICS = ["orders", "clickstream", "payments", "inventory"]


@router.get("")
async def get_topics() -> list[dict[str, Any]]:
    """Get Kafka topic info and consumer group lag."""
    consumer = AIOKafkaConsumer(
        bootstrap_servers=settings.kafka.bootstrap_servers,
        group_id=settings.kafka.consumer_group,
    )
    try:
        await consumer.start()
        cluster_topics = await consumer.topics()

        results: list[dict[str, Any]] = []
        for topic in TOPICS:
            info: dict[str, Any] = {
                "topic": topic,
                "exists": topic in cluster_topics,
                "partitions": [],
            }

            if topic in cluster_topics:
                partitions = consumer.partitions_for_topic(topic)
                if partitions:
                    info["partition_count"] = len(partitions)

            results.append(info)

        return results
    except Exception:
        log.exception("topics_query_error")
        return [{"topic": t, "exists": False, "error": "Unable to connect"} for t in TOPICS]
    finally:
        await consumer.stop()
