"""Silver Layer - Cleaned and validated data.

The Silver layer contains:
- Validated records (passed quality checks)
- Deduplicated data
- Standardized schema
- Type-safe fields (Decimal, datetime, etc.)

Transformations from Bronze:
1. Parse and validate JSON fields
2. Deduplicate by trade_id
3. Apply quality checks
4. Standardize timestamps to UTC
5. Reject invalid records to quarantine

This layer is suitable for:
- Ad-hoc analysis
- Training ML models
- Feeding Gold layer aggregations
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator
from uuid import UUID

import structlog

from src.common.models import TradeEvent, TradeSide
from src.quality.checks import QualityChecker, QualityReport

logger = structlog.get_logger(__name__)


@dataclass
class SilverRecord:
    """A validated record in the Silver layer."""

    # Core trade fields (validated and typed)
    trade_id: UUID
    symbol: str
    price: Decimal
    volume: Decimal
    side: TradeSide
    trader_id: str
    event_timestamp: datetime

    # Lineage metadata
    bronze_file: str | None = None
    processed_at: datetime | None = None
    quality_score: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "trade_id": str(self.trade_id),
            "symbol": self.symbol,
            "price": str(self.price),
            "volume": str(self.volume),
            "side": self.side.value,
            "trader_id": self.trader_id,
            "event_timestamp": self.event_timestamp.isoformat(),
            "_bronze_file": self.bronze_file,
            "_processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "_quality_score": self.quality_score,
        }

    def to_trade_event(self) -> TradeEvent:
        """Convert to TradeEvent model."""
        return TradeEvent(
            trade_id=self.trade_id,
            symbol=self.symbol,
            price=self.price,
            volume=self.volume,
            side=self.side,
            trader_id=self.trader_id,
            event_timestamp=self.event_timestamp,
        )


class SilverLayer:
    """Silver layer for cleaned, validated data.

    Processes Bronze records:
    1. Validates schema and data types
    2. Runs quality checks
    3. Deduplicates by trade_id
    4. Writes valid records to Silver
    5. Routes invalid records to quarantine

    Example usage:
        >>> silver = SilverLayer(
        ...     storage_path="s3://bucket/silver/trades",
        ...     quarantine_path="s3://bucket/quarantine/trades"
        ... )
        >>> stats = silver.process_bronze_partition("2024-01-15")
    """

    def __init__(
        self,
        storage_path: str | Path,
        quarantine_path: str | Path | None = None,
        quality_threshold: float = 0.5,
    ):
        """Initialize the Silver layer.

        Args:
            storage_path: Path to store Silver data
            quarantine_path: Path for invalid records
            quality_threshold: Minimum quality score to pass
        """
        self.storage_path = Path(storage_path)
        self.quarantine_path = Path(quarantine_path) if quarantine_path else None
        self.quality_threshold = quality_threshold
        self.quality_checker = QualityChecker(source="silver")

        # Deduplication cache (in production, use external store)
        self._seen_ids: set[str] = set()
        self._buffer: list[SilverRecord] = []
        self._quarantine_buffer: list[dict] = []

        logger.info(
            "Silver layer initialized",
            storage_path=str(self.storage_path),
            quality_threshold=quality_threshold,
        )

    def process_record(
        self,
        bronze_record: dict[str, Any],
        bronze_file: str | None = None,
    ) -> tuple[SilverRecord | None, QualityReport]:
        """Process a single Bronze record.

        Args:
            bronze_record: Raw record from Bronze layer
            bronze_file: Source file name

        Returns:
            Tuple of (SilverRecord or None if invalid, QualityReport)
        """
        now = datetime.now(UTC)

        # Try to parse and validate
        try:
            # Extract trade data (skip metadata fields)
            trade_data = {
                k: v for k, v in bronze_record.items()
                if not k.startswith("_")
            }

            # Parse to TradeEvent for validation
            trade = TradeEvent.from_kafka_value(trade_data)

            # Check for duplicates
            trade_id_str = str(trade.trade_id)
            if trade_id_str in self._seen_ids:
                logger.debug("Duplicate record skipped", trade_id=trade_id_str)
                return None, QualityReport(
                    is_valid=False,
                    score=0,
                    issues=[],
                    checks_performed=["deduplication"],
                )
            self._seen_ids.add(trade_id_str)

            # Run quality checks
            report = self.quality_checker.check(trade)

            # Check if passes threshold
            if report.score < self.quality_threshold:
                self._quarantine_record(bronze_record, report, bronze_file)
                return None, report

            # Create Silver record
            silver_record = SilverRecord(
                trade_id=trade.trade_id,
                symbol=trade.symbol,
                price=trade.price,
                volume=trade.volume,
                side=trade.side,
                trader_id=trade.trader_id,
                event_timestamp=trade.event_timestamp,
                bronze_file=bronze_file,
                processed_at=now,
                quality_score=report.score,
            )

            self._buffer.append(silver_record)
            return silver_record, report

        except Exception as e:
            logger.warning(
                "Failed to process Bronze record",
                error=str(e),
            )
            self._quarantine_record(
                bronze_record,
                QualityReport(is_valid=False, score=0),
                bronze_file,
                error=str(e),
            )
            return None, QualityReport(
                is_valid=False,
                score=0,
                checks_performed=["parsing"],
            )

    def _quarantine_record(
        self,
        record: dict[str, Any],
        report: QualityReport,
        bronze_file: str | None,
        error: str | None = None,
    ) -> None:
        """Send invalid record to quarantine.

        Args:
            record: Original Bronze record
            report: Quality report explaining why it failed
            bronze_file: Source file name
            error: Optional error message
        """
        quarantine_record = {
            "original_record": record,
            "quality_score": report.score,
            "issues": [i.issue for i in report.issues],
            "quarantined_at": datetime.now(UTC).isoformat(),
            "bronze_file": bronze_file,
            "error": error,
        }
        self._quarantine_buffer.append(quarantine_record)

    def process_batch(
        self,
        bronze_records: Iterator[dict[str, Any]],
        bronze_file: str | None = None,
    ) -> dict[str, int]:
        """Process a batch of Bronze records.

        Args:
            bronze_records: Iterator of Bronze records
            bronze_file: Source file name

        Returns:
            Statistics: valid_count, invalid_count, duplicate_count
        """
        stats = {
            "valid": 0,
            "invalid": 0,
            "duplicate": 0,
            "total": 0,
        }

        for record in bronze_records:
            stats["total"] += 1
            silver_record, report = self.process_record(record, bronze_file)

            if silver_record:
                stats["valid"] += 1
            elif "deduplication" in report.checks_performed:
                stats["duplicate"] += 1
            else:
                stats["invalid"] += 1

        self.flush()
        return stats

    def flush(self) -> None:
        """Flush buffered records to storage."""
        if self._buffer:
            # Write Silver records
            self._write_records(self._buffer, self.storage_path)
            logger.info(
                "Silver records flushed",
                count=len(self._buffer),
            )
            self._buffer.clear()

        if self._quarantine_buffer and self.quarantine_path:
            # Write quarantine records
            self._write_quarantine(self._quarantine_buffer)
            logger.info(
                "Quarantine records flushed",
                count=len(self._quarantine_buffer),
            )
            self._quarantine_buffer.clear()

    def _write_records(self, records: list[SilverRecord], path: Path) -> None:
        """Write Silver records to storage."""
        path.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
        file_path = path / f"part_{timestamp}.parquet"

        try:
            import pandas as pd

            df = pd.DataFrame([r.to_dict() for r in records])
            df.to_parquet(file_path, index=False)
        except ImportError:
            import json

            json_path = file_path.with_suffix(".json")
            with open(json_path, "w") as f:
                json.dump([r.to_dict() for r in records], f)

    def _write_quarantine(self, records: list[dict]) -> None:
        """Write quarantine records."""
        if not self.quarantine_path:
            return

        self.quarantine_path.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
        file_path = self.quarantine_path / f"quarantine_{timestamp}.json"

        import json

        with open(file_path, "w") as f:
            json.dump(records, f, indent=2)

    def read_records(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> Iterator[SilverRecord]:
        """Read Silver records.

        Args:
            start_date: Start date filter (YYYY-MM-DD)
            end_date: End date filter (YYYY-MM-DD)

        Yields:
            SilverRecord objects
        """
        try:
            import pandas as pd

            for file_path in self.storage_path.glob("**/*.parquet"):
                df = pd.read_parquet(file_path)
                for _, row in df.iterrows():
                    yield SilverRecord(
                        trade_id=UUID(row["trade_id"]),
                        symbol=row["symbol"],
                        price=Decimal(str(row["price"])),
                        volume=Decimal(str(row["volume"])),
                        side=TradeSide(row["side"]),
                        trader_id=row["trader_id"],
                        event_timestamp=datetime.fromisoformat(row["event_timestamp"]),
                        bronze_file=row.get("_bronze_file"),
                        quality_score=row.get("_quality_score", 1.0),
                    )
        except ImportError:
            pass  # No pandas available

    def get_stats(self) -> dict[str, Any]:
        """Get Silver layer statistics."""
        return {
            "storage_path": str(self.storage_path),
            "quality_threshold": self.quality_threshold,
            "seen_ids_count": len(self._seen_ids),
            "buffer_size": len(self._buffer),
            "quarantine_buffer_size": len(self._quarantine_buffer),
        }
