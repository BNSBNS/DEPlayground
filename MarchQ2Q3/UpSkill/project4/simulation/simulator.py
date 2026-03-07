"""Configurable event simulator producing to Kafka topics.

Usage:
    python -m simulation.simulator --scenario normal --rate 50
"""
from __future__ import annotations

import argparse
import asyncio
import random
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from src.config import settings
from src.logging import get_logger, setup_logging
from src.models.events import (
    ClickAction,
    ClickstreamEvent,
    InventoryEvent,
    InventoryReason,
    OrderEvent,
    OrderStatus,
    PaymentEvent,
    PaymentStatus,
)
from src.producers.base import EventProducer

log = get_logger(__name__)

# Scenario profiles: (order_weight, click_weight, payment_weight, inv_weight, failure_rate)
SCENARIOS: dict[str, dict[str, float]] = {
    "normal": {
        "order_weight": 0.3,
        "click_weight": 0.4,
        "payment_weight": 0.2,
        "inventory_weight": 0.1,
        "failure_rate": 0.05,
    },
    "flash_sale": {
        "order_weight": 0.5,
        "click_weight": 0.3,
        "payment_weight": 0.15,
        "inventory_weight": 0.05,
        "failure_rate": 0.02,
    },
    "fraud_spike": {
        "order_weight": 0.25,
        "click_weight": 0.25,
        "payment_weight": 0.4,
        "inventory_weight": 0.1,
        "failure_rate": 0.30,
    },
    "outage_recovery": {
        "order_weight": 0.4,
        "click_weight": 0.2,
        "payment_weight": 0.3,
        "inventory_weight": 0.1,
        "failure_rate": 0.15,
    },
}

REGIONS = ["us-east", "us-west", "eu-west", "eu-central", "ap-southeast", "ap-northeast"]


def _random_order(scenario: dict[str, float]) -> OrderEvent:
    cust = f"cust-{random.randint(0, 499):04d}"
    prod = f"prod-{random.randint(0, 99):04d}"
    qty = random.randint(1, 5)
    price = Decimal(str(round(random.uniform(10.0, 300.0), 2)))
    total = price * qty

    # In flash_sale, bias toward CREATED status
    statuses = list(OrderStatus)
    if scenario.get("order_weight", 0) > 0.4:
        statuses = [OrderStatus.CREATED] * 5 + [OrderStatus.CONFIRMED] * 3 + list(OrderStatus)

    return OrderEvent(
        order_id=str(uuid.uuid4()),
        customer_id=cust,
        product_id=prod,
        quantity=qty,
        unit_price=price,
        total_amount=total,
        status=random.choice(statuses),
        region=random.choice(REGIONS),
        timestamp=datetime.now(tz=timezone.utc),
    )


def _random_click() -> ClickstreamEvent:
    return ClickstreamEvent(
        session_id=f"sess-{random.randint(0, 999):04d}",
        customer_id=f"cust-{random.randint(0, 499):04d}",
        action=random.choice(list(ClickAction)),
        page_url=f"/products/prod-{random.randint(0, 99):04d}",
        product_id=f"prod-{random.randint(0, 99):04d}" if random.random() > 0.3 else None,
        timestamp=datetime.now(tz=timezone.utc),
    )


def _random_payment(scenario: dict[str, float]) -> PaymentEvent:
    failure_rate = scenario.get("failure_rate", 0.05)
    if random.random() < failure_rate:
        status = PaymentStatus.FAILED
    else:
        status = random.choice([PaymentStatus.AUTHORIZED, PaymentStatus.CAPTURED])

    return PaymentEvent(
        payment_id=str(uuid.uuid4()),
        order_id=str(uuid.uuid4()),
        customer_id=f"cust-{random.randint(0, 499):04d}",
        amount=Decimal(str(round(random.uniform(10.0, 1500.0), 2))),
        status=status,
        failure_reason="Insufficient funds" if status == PaymentStatus.FAILED else None,
        timestamp=datetime.now(tz=timezone.utc),
    )


def _random_inventory() -> InventoryEvent:
    return InventoryEvent(
        product_id=f"prod-{random.randint(0, 99):04d}",
        warehouse_id=random.choice(["warehouse-us", "warehouse-eu", "warehouse-ap"]),
        quantity_change=random.randint(-10, 50),
        reason=random.choice(list(InventoryReason)),
        current_stock=random.randint(0, 1000),
        timestamp=datetime.now(tz=timezone.utc),
    )


async def simulate(rate: int, scenario_name: str) -> None:
    """Main simulation loop."""
    setup_logging(json_output=False)
    scenario = SCENARIOS.get(scenario_name, SCENARIOS["normal"])
    producer = EventProducer()
    await producer.start()

    weights = [
        scenario["order_weight"],
        scenario["click_weight"],
        scenario["payment_weight"],
        scenario["inventory_weight"],
    ]

    log.info("simulator_started", rate=rate, scenario=scenario_name)
    interval = 1.0 / rate

    try:
        while True:
            choice = random.choices(
                ["order", "click", "payment", "inventory"],
                weights=weights,
                k=1,
            )[0]

            if choice == "order":
                event = _random_order(scenario)
                await producer.produce("orders", event.kafka_key, event)
            elif choice == "click":
                event = _random_click()
                await producer.produce("clickstream", event.kafka_key, event)
            elif choice == "payment":
                event = _random_payment(scenario)
                await producer.produce("payments", event.kafka_key, event)
            else:
                event = _random_inventory()
                await producer.produce("inventory", event.kafka_key, event)

            await asyncio.sleep(interval)
    except (KeyboardInterrupt, asyncio.CancelledError):
        log.info("simulator_stopping")
    finally:
        await producer.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Event Simulator")
    parser.add_argument("--rate", type=int, default=50, help="Events per second")
    parser.add_argument(
        "--scenario",
        choices=list(SCENARIOS.keys()),
        default="normal",
        help="Simulation scenario",
    )
    args = parser.parse_args()
    asyncio.run(simulate(rate=args.rate, scenario_name=args.scenario))


if __name__ == "__main__":
    main()
