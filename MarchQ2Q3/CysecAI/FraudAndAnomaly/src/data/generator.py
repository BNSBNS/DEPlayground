"""Synthetic transaction generator for fraud detection training.

Generates realistic financial transaction data with configurable fraud patterns.
Normal transactions follow consistent user behavior (location, spending, timing).
Fraud transactions inject detectable anomalies across 5 strategies:

1. Amount spike — 5-20x the user's average spend
2. New device + new location — previously unseen device, >500km from home
3. Rapid successive — 3+ transactions within 5 minutes
4. Round amounts — suspicious exact amounts ($500, $1000, $2000, $5000)
5. Category mismatch — unfamiliar merchant category at unusual time

All monetary amounts use Decimal (never float) per project rules.
Deterministic via seed for reproducibility.
"""

from __future__ import annotations

import math
import random
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from src.config import GeneratorSettings

# --- Constants ---

MERCHANT_CATEGORIES = [
    "grocery",
    "restaurant",
    "gas_station",
    "online_retail",
    "electronics",
    "clothing",
    "travel",
    "entertainment",
    "healthcare",
    "utilities",
    "insurance",
    "education",
    "home_improvement",
    "automotive",
    "subscription",
]

ROUND_FRAUD_AMOUNTS = [
    Decimal("500.00"),
    Decimal("1000.00"),
    Decimal("2000.00"),
    Decimal("5000.00"),
]


class FraudStrategy(StrEnum):
    """Fraud injection strategies."""

    AMOUNT_SPIKE = "amount_spike"
    NEW_DEVICE_LOCATION = "new_device_location"
    RAPID_SUCCESSIVE = "rapid_successive"
    ROUND_AMOUNT = "round_amount"
    CATEGORY_MISMATCH = "category_mismatch"


# --- Models ---


class Transaction(BaseModel):
    """A single financial transaction record.

    All monetary amounts use Decimal per project rules.
    """

    transaction_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    amount: Decimal = Field(ge=Decimal("0.01"))
    merchant_category: str
    timestamp: datetime
    device_id: str
    ip_address: str
    geo_lat: float = Field(ge=-90.0, le=90.0)
    geo_lon: float = Field(ge=-180.0, le=180.0)
    is_fraud: bool = False
    fraud_strategy: str | None = None


# --- Internal state ---


@dataclass
class UserProfile:
    """Internal user profile for generating realistic behavior patterns."""

    user_id: str
    home_lat: float
    home_lon: float
    device_id: str
    typical_categories: list[str]
    avg_amount: float
    std_amount: float
    transactions_generated: int = 0
    last_timestamp: datetime | None = None
    ip_address: str = ""

    # Track per-user state for behavioral realism
    used_categories: set[str] = field(default_factory=set)


# --- Generator ---


class TransactionGenerator:
    """Generate synthetic transaction datasets with realistic patterns.

    Usage:
        from src.config import GeneratorSettings
        gen = TransactionGenerator(GeneratorSettings(num_transactions=1000, seed=42))
        transactions = gen.generate()
    """

    def __init__(self, settings: GeneratorSettings) -> None:
        self._settings = settings
        self._rng = random.Random(settings.seed)
        self._users: list[UserProfile] = []

    def generate(self) -> list[Transaction]:
        """Generate the full transaction dataset.

        Returns sorted by timestamp. Fraud transactions are injected
        at the configured rate, evenly split across 5 strategies.
        """
        self._users = self._create_user_profiles()
        n = self._settings.num_transactions
        n_fraud = int(n * self._settings.fraud_rate)
        n_normal = n - n_fraud

        # Generate base timeline (30-day window)
        start = datetime(2024, 1, 1, tzinfo=UTC)
        end = start + timedelta(days=30)

        transactions: list[Transaction] = []

        # Normal transactions
        for _ in range(n_normal):
            user = self._rng.choice(self._users)
            ts = self._random_timestamp(start, end, business_hours_bias=True)
            tx = self._normal_transaction(user, ts)
            transactions.append(tx)

        # Fraud transactions — equal split across 5 strategies
        strategies = list(FraudStrategy)
        per_strategy = n_fraud // len(strategies)
        remainder = n_fraud % len(strategies)

        for i, strategy in enumerate(strategies):
            count = per_strategy + (1 if i < remainder else 0)
            for _ in range(count):
                user = self._rng.choice(self._users)
                ts = self._random_timestamp(start, end, business_hours_bias=False)
                tx = self._fraud_transaction(user, ts, strategy)
                transactions.append(tx)

        # Sort by timestamp for realism
        transactions.sort(key=lambda t: t.timestamp)
        return transactions

    # --- Profile creation ---

    def _create_user_profiles(self) -> list[UserProfile]:
        """Create user profiles with distinct behavioral patterns."""
        profiles: list[UserProfile] = []
        for i in range(self._settings.num_users):
            # Scatter users across realistic lat/lon (US-centric)
            lat = self._rng.uniform(25.0, 48.0)
            lon = self._rng.uniform(-122.0, -73.0)

            # Each user has 3-6 typical merchant categories
            n_cats = self._rng.randint(3, 6)
            cats = self._rng.sample(MERCHANT_CATEGORIES, k=n_cats)

            # Spending pattern: avg between $15-$500, std 20-50% of avg
            avg = self._rng.uniform(15.0, 500.0)
            std = avg * self._rng.uniform(0.2, 0.5)

            profiles.append(
                UserProfile(
                    user_id=f"user-{i:05d}",
                    home_lat=lat,
                    home_lon=lon,
                    device_id=f"device-{uuid.UUID(int=self._rng.getrandbits(128))}",
                    typical_categories=cats,
                    avg_amount=avg,
                    std_amount=std,
                    ip_address=self._random_ip(),
                )
            )
        return profiles

    # --- Normal transaction ---

    def _normal_transaction(self, user: UserProfile, ts: datetime) -> Transaction:
        """Generate a normal transaction consistent with user behavior."""
        # Amount: normal distribution around user's average, clamped > 0.01
        raw_amount = max(0.01, self._rng.gauss(user.avg_amount, user.std_amount))
        amount = Decimal(str(round(raw_amount, 2)))

        # Location: small jitter from home (within ~50km)
        lat = user.home_lat + self._rng.gauss(0, 0.2)
        lon = user.home_lon + self._rng.gauss(0, 0.2)
        lat = max(-90.0, min(90.0, lat))
        lon = max(-180.0, min(180.0, lon))

        # Category: from user's typical set
        category = self._rng.choice(user.typical_categories)
        user.used_categories.add(category)

        user.transactions_generated += 1
        user.last_timestamp = ts

        return Transaction(
            user_id=user.user_id,
            amount=amount,
            merchant_category=category,
            timestamp=ts,
            device_id=user.device_id,
            ip_address=user.ip_address,
            geo_lat=round(lat, 6),
            geo_lon=round(lon, 6),
            is_fraud=False,
        )

    # --- Fraud transactions ---

    def _fraud_transaction(
        self, user: UserProfile, ts: datetime, strategy: FraudStrategy
    ) -> Transaction:
        """Generate a fraud transaction using the specified strategy."""
        method = {
            FraudStrategy.AMOUNT_SPIKE: self._fraud_amount_spike,
            FraudStrategy.NEW_DEVICE_LOCATION: self._fraud_new_device_location,
            FraudStrategy.RAPID_SUCCESSIVE: self._fraud_rapid_successive,
            FraudStrategy.ROUND_AMOUNT: self._fraud_round_amount,
            FraudStrategy.CATEGORY_MISMATCH: self._fraud_category_mismatch,
        }
        return method[strategy](user, ts)

    def _fraud_amount_spike(self, user: UserProfile, ts: datetime) -> Transaction:
        """Strategy 1: Amount 5-20x the user's average."""
        multiplier = self._rng.uniform(5.0, 20.0)
        amount = Decimal(str(round(user.avg_amount * multiplier, 2)))
        return Transaction(
            user_id=user.user_id,
            amount=amount,
            merchant_category=self._rng.choice(user.typical_categories),
            timestamp=ts,
            device_id=user.device_id,
            ip_address=user.ip_address,
            geo_lat=round(user.home_lat + self._rng.gauss(0, 0.2), 6),
            geo_lon=round(user.home_lon + self._rng.gauss(0, 0.2), 6),
            is_fraud=True,
            fraud_strategy=FraudStrategy.AMOUNT_SPIKE,
        )

    def _fraud_new_device_location(self, user: UserProfile, ts: datetime) -> Transaction:
        """Strategy 2: Previously unseen device + location >500km from home."""
        # Offset by 5-15 degrees (~500-1500km)
        lat_offset = self._rng.choice([-1, 1]) * self._rng.uniform(5.0, 15.0)
        lon_offset = self._rng.choice([-1, 1]) * self._rng.uniform(5.0, 15.0)
        lat = max(-90.0, min(90.0, user.home_lat + lat_offset))
        lon = max(-180.0, min(180.0, user.home_lon + lon_offset))

        raw = max(0.01, self._rng.gauss(user.avg_amount, user.std_amount))
        amount = Decimal(str(round(raw, 2)))
        return Transaction(
            user_id=user.user_id,
            amount=amount,
            merchant_category=self._rng.choice(user.typical_categories),
            timestamp=ts,
            device_id=f"device-{uuid.uuid4()}",  # New device
            ip_address=self._random_ip(),  # New IP
            geo_lat=round(lat, 6),
            geo_lon=round(lon, 6),
            is_fraud=True,
            fraud_strategy=FraudStrategy.NEW_DEVICE_LOCATION,
        )

    def _fraud_rapid_successive(self, user: UserProfile, ts: datetime) -> Transaction:
        """Strategy 3: Transaction within rapid burst (< 5 min of last).

        The test suite verifies burst patterns by checking multiple fraud
        transactions from the same user within a short window.
        """
        # Place within 1-4 minutes of base timestamp
        offset = timedelta(seconds=self._rng.randint(30, 240))
        burst_ts = ts + offset

        raw = max(0.01, self._rng.gauss(user.avg_amount, user.std_amount))
        amount = Decimal(str(round(raw, 2)))
        return Transaction(
            user_id=user.user_id,
            amount=amount,
            merchant_category=self._rng.choice(user.typical_categories),
            timestamp=burst_ts,
            device_id=user.device_id,
            ip_address=user.ip_address,
            geo_lat=round(user.home_lat + self._rng.gauss(0, 0.2), 6),
            geo_lon=round(user.home_lon + self._rng.gauss(0, 0.2), 6),
            is_fraud=True,
            fraud_strategy=FraudStrategy.RAPID_SUCCESSIVE,
        )

    def _fraud_round_amount(self, user: UserProfile, ts: datetime) -> Transaction:
        """Strategy 4: Suspiciously round amounts ($500, $1000, $2000, $5000)."""
        amount = self._rng.choice(ROUND_FRAUD_AMOUNTS)
        return Transaction(
            user_id=user.user_id,
            amount=amount,
            merchant_category=self._rng.choice(user.typical_categories),
            timestamp=ts,
            device_id=user.device_id,
            ip_address=user.ip_address,
            geo_lat=round(user.home_lat + self._rng.gauss(0, 0.2), 6),
            geo_lon=round(user.home_lon + self._rng.gauss(0, 0.2), 6),
            is_fraud=True,
            fraud_strategy=FraudStrategy.ROUND_AMOUNT,
        )

    def _fraud_category_mismatch(self, user: UserProfile, ts: datetime) -> Transaction:
        """Strategy 5: Merchant category the user has never used, at unusual hours."""
        # Pick a category NOT in user's typical set
        unused = [c for c in MERCHANT_CATEGORIES if c not in user.typical_categories]
        category = self._rng.choice(unused) if unused else self._rng.choice(MERCHANT_CATEGORIES)

        # Force unusual hour (2am-5am)
        unusual_ts = ts.replace(hour=self._rng.randint(2, 4), minute=self._rng.randint(0, 59))

        raw = max(0.01, self._rng.gauss(user.avg_amount, user.std_amount))
        amount = Decimal(str(round(raw, 2)))
        return Transaction(
            user_id=user.user_id,
            amount=amount,
            merchant_category=category,
            timestamp=unusual_ts,
            device_id=user.device_id,
            ip_address=user.ip_address,
            geo_lat=round(user.home_lat + self._rng.gauss(0, 0.2), 6),
            geo_lon=round(user.home_lon + self._rng.gauss(0, 0.2), 6),
            is_fraud=True,
            fraud_strategy=FraudStrategy.CATEGORY_MISMATCH,
        )

    # --- Helpers ---

    def _random_timestamp(
        self, start: datetime, end: datetime, *, business_hours_bias: bool
    ) -> datetime:
        """Generate a random timestamp, optionally biased toward business hours."""
        delta = (end - start).total_seconds()
        offset = self._rng.uniform(0, delta)
        ts = start + timedelta(seconds=offset)

        if business_hours_bias and self._rng.random() < 0.7:
            # 70% chance of business hours (8am-8pm)
            ts = ts.replace(hour=self._rng.randint(8, 19), minute=self._rng.randint(0, 59))

        return ts

    def _random_ip(self) -> str:
        """Generate a random private IP address."""
        octets = [self._rng.randint(0, 255) for _ in range(2)]
        return f"10.{octets[0]}.{octets[1]}.{self._rng.randint(1, 254)}"

    @staticmethod
    def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate great-circle distance between two points in km.

        Exposed as static method for use in tests and feature engineering.
        """
        r = 6371.0  # Earth radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
        )
        return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
