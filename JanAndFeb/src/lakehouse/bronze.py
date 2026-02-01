"""Bronze Layer - Raw data ingestion.

The Bronze layer stores raw data exactly as received from sources:
- No transformations
- Append-only writes
- Preserves original format for debugging
- Includes metadata (source, ingestion time, etc.)

Data flows:
- Kafka (trades topic) → Bronze table
- Batch files (CSV/Parquet) → Bronze table

Schema:
- All original fields from source
- _ingested_at: When data was ingested
- _source: Where data came from
- _kafka_offset: Kafka offset (for streaming)
- _file_name: Source file (for batch)
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class BronzeRecord:
    """A record in the Bronze layer.

    Contains the raw trade data plus ingestion metadata.
    """

    # Original trade data (as JSON dict)
    data: dict[str, Any]

    # Ingestion metadata
    ingested_at: datetime
    source: str
    kafka_partition: int | None = None
    kafka_offset: int | None = None
    file_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            **self.data,
            "_ingested_at": self.ingested_at.isoformat(),
            "_source": self.source,
            "_kafka_partition": self.kafka_partition,
            "_kafka_offset": self.kafka_offset,
            "_file_name": self.file_name,
        }


class BronzeLayer:
    """Bronze layer for raw data storage.

    Stores raw trade events with minimal processing:
    - Adds ingestion metadata
    - Writes to Delta Lake format (or Parquet for simplicity)
    - Partitions by date for efficient queries

    Example usage:
        >>> bronze = BronzeLayer(storage_path="s3://bucket/bronze/trades")
        >>> bronze.write_batch(records)
        >>> bronze.write_streaming(kafka_message)
    """

    def __init__(
        self,
        storage_path: str | Path,
        partition_by: str = "date",
    ):
        """Initialize the Bronze layer.

        Args:
            storage_path: Path to store Bronze data (local or S3)
            partition_by: Partition column (date, hour, etc.)
        """
        self.storage_path = Path(storage_path)
        self.partition_by = partition_by
        self._buffer: list[BronzeRecord] = []
        self._buffer_size = 1000  # Flush after this many records

        logger.info(
            "Bronze layer initialized",
            storage_path=str(self.storage_path),
            partition_by=partition_by,
        )

    def write_record(self, record: BronzeRecord) -> None:
        """Write a single record to the Bronze layer.

        Records are buffered and flushed in batches for efficiency.

        Args:
            record: Bronze record to write
        """
        self._buffer.append(record)
        if len(self._buffer) >= self._buffer_size:
            self.flush()

    def write_batch(self, records: list[BronzeRecord]) -> int:
        """Write a batch of records to the Bronze layer.

        Args:
            records: List of Bronze records

        Returns:
            Number of records written
        """
        self._buffer.extend(records)
        self.flush()
        return len(records)

    def write_from_kafka(
        self,
        message: dict[str, Any],
        partition: int,
        offset: int,
        source: str = "kafka",
    ) -> BronzeRecord:
        """Write a Kafka message to the Bronze layer.

        Args:
            message: Kafka message value (parsed JSON)
            partition: Kafka partition number
            offset: Kafka offset
            source: Source name

        Returns:
            The created BronzeRecord
        """
        record = BronzeRecord(
            data=message,
            ingested_at=datetime.now(UTC),
            source=source,
            kafka_partition=partition,
            kafka_offset=offset,
        )
        self.write_record(record)
        return record

    def write_from_file(
        self,
        records: list[dict[str, Any]],
        file_name: str,
        source: str = "batch",
    ) -> int:
        """Write records from a batch file to the Bronze layer.

        Args:
            records: List of records from the file
            file_name: Name of the source file
            source: Source name

        Returns:
            Number of records written
        """
        now = datetime.now(UTC)
        bronze_records = [
            BronzeRecord(
                data=rec,
                ingested_at=now,
                source=source,
                file_name=file_name,
            )
            for rec in records
        ]
        return self.write_batch(bronze_records)

    def flush(self) -> None:
        """Flush buffered records to storage.

        In a real implementation, this would:
        1. Convert records to Parquet/Delta format
        2. Write to partitioned storage
        3. Update Delta transaction log (if using Delta Lake)
        """
        if not self._buffer:
            return

        # Group by partition
        partitions: dict[str, list[dict]] = {}
        for record in self._buffer:
            # Extract partition value (date from ingested_at)
            partition_value = record.ingested_at.strftime("%Y-%m-%d")
            if partition_value not in partitions:
                partitions[partition_value] = []
            partitions[partition_value].append(record.to_dict())

        # Write each partition
        for partition_value, records in partitions.items():
            partition_path = self.storage_path / f"{self.partition_by}={partition_value}"
            partition_path.mkdir(parents=True, exist_ok=True)

            # Generate unique file name
            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
            file_path = partition_path / f"part_{timestamp}.parquet"

            # Write using pyarrow/pandas (in production, use Delta Lake)
            self._write_parquet(file_path, records)

            logger.info(
                "Bronze layer flushed",
                partition=partition_value,
                records=len(records),
                file=str(file_path),
            )

        self._buffer.clear()

    def _write_parquet(self, path: Path, records: list[dict]) -> None:
        """Write records as Parquet file.

        Args:
            path: Output file path
            records: Records to write
        """
        try:
            import pandas as pd

            df = pd.DataFrame(records)
            df.to_parquet(path, index=False)
        except ImportError:
            # Fallback to JSON if pandas not available
            import json

            json_path = path.with_suffix(".json")
            with open(json_path, "w") as f:
                json.dump(records, f)

    def read_partition(
        self,
        date: str,
    ) -> Iterator[dict[str, Any]]:
        """Read records from a partition.

        Args:
            date: Partition date (YYYY-MM-DD)

        Yields:
            Records from the partition
        """
        partition_path = self.storage_path / f"{self.partition_by}={date}"
        if not partition_path.exists():
            return

        try:
            import pandas as pd

            for file_path in partition_path.glob("*.parquet"):
                df = pd.read_parquet(file_path)
                for _, row in df.iterrows():
                    yield row.to_dict()
        except ImportError:
            # Fallback to JSON
            for file_path in partition_path.glob("*.json"):
                import json

                with open(file_path) as f:
                    records = json.load(f)
                    yield from records

    def get_stats(self) -> dict[str, Any]:
        """Get Bronze layer statistics.

        Returns:
            Dictionary with storage stats
        """
        total_files = 0
        total_size = 0
        partitions = []

        if self.storage_path.exists():
            for partition_dir in self.storage_path.iterdir():
                if partition_dir.is_dir():
                    partitions.append(partition_dir.name)
                    for file_path in partition_dir.glob("*"):
                        total_files += 1
                        total_size += file_path.stat().st_size

        return {
            "storage_path": str(self.storage_path),
            "partition_by": self.partition_by,
            "partitions": len(partitions),
            "total_files": total_files,
            "total_size_bytes": total_size,
            "buffer_size": len(self._buffer),
        }
