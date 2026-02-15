"""Batch connector - processes historical/bulk data files (hourly/daily).

Handles file-based data imports with checkpointing.
"""

import asyncio
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, AsyncIterator
from uuid import uuid4

import pandas as pd

from src.ingestion.adapters.connectors.base import BaseConnector
from src.ingestion.domain.models import SourceType
from src.ingestion.ports import MetricsPort
from src.ingestion.resilience import CircuitBreaker, RetryPolicy


class BatchConnector(BaseConnector):
    """Batch connector for file-based data processing.

    Monitors a directory for new files and processes them.
    Supports CSV, JSON, and Parquet formats.

    Example:
        ```python
        connector = BatchConnector(
            name="historical_import",
            input_path="/data/batch",
            file_pattern="*.csv",
            poll_interval=60,  # Check for new files every minute
        )

        async for batch in connector.stream_events():
            for event in batch.get("_batch", []):
                process(event)
        ```
    """

    SUPPORTED_FORMATS = {".csv", ".json", ".parquet", ".pq"}

    def __init__(
        self,
        name: str,
        input_path: Path | str,
        file_pattern: str = "*.csv",
        poll_interval: int = 60,
        batch_size: int = 10000,
        archive_path: Path | str | None = None,
        delete_after_processing: bool = False,
        checkpoint_file: Path | str | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        retry_policy: RetryPolicy | None = None,
        metrics: MetricsPort | None = None,
    ):
        """Initialize batch connector.

        Args:
            name: Connector identifier
            input_path: Directory to monitor for files
            file_pattern: Glob pattern for files (e.g., "*.csv")
            poll_interval: Seconds between directory checks
            batch_size: Rows per batch when reading large files
            archive_path: Directory to move processed files to
            delete_after_processing: Delete files after processing
            checkpoint_file: File to track processed files
            circuit_breaker: Optional circuit breaker
            retry_policy: Optional retry policy
            metrics: Optional metrics port
        """
        super().__init__(
            name=name,
            source_type=SourceType.BATCH,
            expected_latency_ms=poll_interval * 1000,
            circuit_breaker=circuit_breaker,
            retry_policy=retry_policy,
            metrics=metrics,
        )

        self._input_path = Path(input_path)
        self._file_pattern = file_pattern
        self._poll_interval = poll_interval
        self._batch_size = batch_size
        self._archive_path = Path(archive_path) if archive_path else None
        self._delete_after_processing = delete_after_processing
        self._checkpoint_file = Path(checkpoint_file) if checkpoint_file else None

        self._processed_files: set[str] = set()
        self._file_count = 0
        self._row_count = 0
        self._current_file: str | None = None

    async def connect(self) -> None:
        """Verify input path and load checkpoint."""
        self._logger.info(
            "Initializing batch connector",
            input_path=str(self._input_path),
            file_pattern=self._file_pattern,
        )

        if not self._input_path.exists():
            raise FileNotFoundError(f"Input path not found: {self._input_path}")

        if not self._input_path.is_dir():
            raise NotADirectoryError(f"Input path is not a directory: {self._input_path}")

        # Create archive directory if needed
        if self._archive_path:
            self._archive_path.mkdir(parents=True, exist_ok=True)

        # Load checkpoint
        self._load_checkpoint()

    async def disconnect(self) -> None:
        """Save checkpoint on disconnect."""
        self._save_checkpoint()

    def _load_checkpoint(self) -> None:
        """Load processed files from checkpoint."""
        if self._checkpoint_file and self._checkpoint_file.exists():
            try:
                with open(self._checkpoint_file) as f:
                    self._processed_files = set(f.read().splitlines())
                self._logger.info(
                    "Checkpoint loaded",
                    processed_count=len(self._processed_files),
                )
            except Exception as e:
                self._logger.warning("Failed to load checkpoint", error=str(e))

    def _save_checkpoint(self) -> None:
        """Save processed files to checkpoint."""
        if self._checkpoint_file:
            try:
                self._checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self._checkpoint_file, "w") as f:
                    f.write("\n".join(sorted(self._processed_files)))
                self._logger.debug("Checkpoint saved")
            except Exception as e:
                self._logger.warning("Failed to save checkpoint", error=str(e))

    def _get_unprocessed_files(self) -> list[Path]:
        """Get list of files not yet processed."""
        all_files = sorted(self._input_path.glob(self._file_pattern))
        return [
            f for f in all_files
            if str(f) not in self._processed_files
            and f.suffix.lower() in self.SUPPORTED_FORMATS
        ]

    def _read_file(self, file_path: Path) -> pd.DataFrame:
        """Read file into DataFrame based on extension.

        Handles common issues:
        - Encoding detection and fallback
        - Empty files
        - Malformed rows (on_bad_lines='warn')
        """
        suffix = file_path.suffix.lower()

        # Check for empty file
        if file_path.stat().st_size == 0:
            self._logger.warning("Empty file detected", file=file_path.name)
            return pd.DataFrame()

        if suffix == ".csv":
            # Try UTF-8 first, fallback to other encodings
            encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
            last_error = None

            for encoding in encodings:
                try:
                    return pd.read_csv(
                        file_path,
                        encoding=encoding,
                        on_bad_lines="warn",  # Log bad rows instead of failing
                    )
                except UnicodeDecodeError as e:
                    last_error = e
                    self._logger.debug(
                        "Encoding failed, trying next",
                        encoding=encoding,
                        error=str(e),
                    )
                    continue
                except pd.errors.EmptyDataError:
                    self._logger.warning("File has no data", file=file_path.name)
                    return pd.DataFrame()
                except pd.errors.ParserError as e:
                    self._logger.error("CSV parsing error", file=file_path.name, error=str(e))
                    raise ValueError(f"CSV parsing error: {e}") from e

            # If all encodings failed
            raise ValueError(f"Failed to decode file with any encoding: {last_error}")

        elif suffix == ".json":
            try:
                return pd.read_json(file_path)
            except ValueError as e:
                self._logger.error("JSON parsing error", file=file_path.name, error=str(e))
                raise ValueError(f"JSON parsing error: {e}") from e

        elif suffix in (".parquet", ".pq"):
            return pd.read_parquet(file_path)

        else:
            raise ValueError(f"Unsupported file format: {suffix}")

    def _archive_file(self, file_path: Path) -> None:
        """Move file to archive directory."""
        if self._archive_path:
            dest = self._archive_path / file_path.name
            file_path.rename(dest)
            self._logger.debug("File archived", source=str(file_path), dest=str(dest))

    def _delete_file(self, file_path: Path) -> None:
        """Delete processed file."""
        file_path.unlink()
        self._logger.debug("File deleted", path=str(file_path))

    async def _process_file(self, file_path: Path) -> AsyncIterator[dict[str, Any]]:
        """Process a single file and yield batches."""
        self._current_file = str(file_path)
        self._file_count += 1

        self._logger.info(
            "Processing file",
            file=file_path.name,
            file_count=self._file_count,
        )

        try:
            # Read file
            df = self._read_file(file_path)
            total_rows = len(df)

            # Process in batches
            for start_idx in range(0, total_rows, self._batch_size):
                if not self._running:
                    break

                end_idx = min(start_idx + self._batch_size, total_rows)
                batch_df = df.iloc[start_idx:end_idx]
                batch_records = batch_df.to_dict("records")

                batch_id = f"{self._name}-{file_path.stem}-{start_idx}-{uuid4().hex[:8]}"
                self._row_count += len(batch_records)

                yield {
                    "_batch": batch_records,
                    "_batch_id": batch_id,
                    "_batch_size": len(batch_records),
                    "_batch_timestamp": datetime.now(UTC).isoformat(),
                    "_file": file_path.name,
                    "_file_total_rows": total_rows,
                    "_batch_start_row": start_idx,
                    "_batch_end_row": end_idx,
                }

            # Mark as processed
            self._processed_files.add(str(file_path))
            self._save_checkpoint()

            # Archive or delete
            if self._delete_after_processing:
                self._delete_file(file_path)
            elif self._archive_path:
                self._archive_file(file_path)

            self._logger.info(
                "File processed",
                file=file_path.name,
                rows=total_rows,
            )

        except pd.errors.EmptyDataError:
            self._logger.warning("Empty or header-only file", file=str(file_path))
            # Mark as processed but yield nothing
            self._processed_files.add(str(file_path))
            self._save_checkpoint()
            if self._archive_path:
                self._archive_file(file_path)

        except ValueError as e:
            # Schema or format errors - log and mark for DLQ
            self._logger.error(
                "File format/schema error",
                file=str(file_path),
                error=str(e),
            )
            # Yield error event for DLQ handling
            yield {
                "_error": True,
                "_error_type": "FileFormatError",
                "_error_message": str(e),
                "_file": file_path.name,
            }
            # Still mark as processed to avoid retry loop
            self._processed_files.add(str(file_path))
            self._save_checkpoint()

        except Exception as e:
            self._logger.error(
                "Unexpected error processing file",
                file=str(file_path),
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

        finally:
            self._current_file = None

    async def _fetch_events(self) -> AsyncIterator[dict[str, Any]]:
        """Monitor directory and process new files."""
        while self._running:
            files = self._get_unprocessed_files()

            if files:
                self._logger.info(
                    "Found unprocessed files",
                    count=len(files),
                )

                for file_path in files:
                    if not self._running:
                        break

                    async for batch in self._process_file(file_path):
                        yield batch

            # Wait before next check
            if self._running:
                await asyncio.sleep(self._poll_interval)

    async def process_single_file(self, file_path: Path | str) -> AsyncIterator[dict[str, Any]]:
        """Process a specific file immediately.

        Args:
            file_path: Path to the file to process

        Yields:
            Batch dictionaries
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        async for batch in self._process_file(path):
            yield batch

    def get_stats(self) -> dict[str, Any]:
        """Get connector statistics."""
        stats = super().get_stats()
        stats.update({
            "input_path": str(self._input_path),
            "file_pattern": self._file_pattern,
            "poll_interval": self._poll_interval,
            "batch_size": self._batch_size,
            "file_count": self._file_count,
            "row_count": self._row_count,
            "processed_files": len(self._processed_files),
            "pending_files": len(self._get_unprocessed_files()),
            "current_file": self._current_file,
            "archive_path": str(self._archive_path) if self._archive_path else None,
        })
        return stats
