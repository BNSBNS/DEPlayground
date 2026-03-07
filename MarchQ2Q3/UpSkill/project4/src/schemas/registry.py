from __future__ import annotations

import json
from typing import Any

import httpx

from src.config import settings
from src.logging import get_logger
from src.models.events import ClickstreamEvent, InventoryEvent, OrderEvent, PaymentEvent

log = get_logger(__name__)

# Map topic names to their Pydantic models
TOPIC_SCHEMAS: dict[str, type] = {
    "orders": OrderEvent,
    "clickstream": ClickstreamEvent,
    "payments": PaymentEvent,
    "inventory": InventoryEvent,
}


def _pydantic_to_json_schema(model: type) -> dict[str, Any]:
    """Extract JSON Schema from a Pydantic v2 model."""
    return model.model_json_schema()


async def register_schemas() -> None:
    """Register JSON schemas with Redpanda Schema Registry."""
    base_url = settings.schema_registry.url

    async with httpx.AsyncClient(timeout=10.0) as client:
        for topic, model in TOPIC_SCHEMAS.items():
            subject = f"{topic}-value"
            schema = _pydantic_to_json_schema(model)

            payload = {
                "schema": json.dumps(schema),
                "schemaType": "JSON",
            }

            try:
                resp = await client.post(
                    f"{base_url}/subjects/{subject}/versions",
                    json=payload,
                    headers={"Content-Type": "application/vnd.schemaregistry.v1+json"},
                )
                if resp.status_code in (200, 409):
                    log.info(
                        "schema_registered",
                        subject=subject,
                        status=resp.status_code,
                    )
                else:
                    log.warning(
                        "schema_registration_failed",
                        subject=subject,
                        status=resp.status_code,
                        body=resp.text,
                    )
            except httpx.HTTPError:
                log.exception("schema_registry_error", subject=subject)


async def get_schema(topic: str) -> dict[str, Any] | None:
    """Retrieve the latest schema for a topic from the registry."""
    base_url = settings.schema_registry.url
    subject = f"{topic}-value"

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(
                f"{base_url}/subjects/{subject}/versions/latest"
            )
            if resp.status_code == 200:
                data = resp.json()
                return json.loads(data["schema"])
        except httpx.HTTPError:
            log.exception("schema_fetch_error", subject=subject)

    return None
