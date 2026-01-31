"""Batch issue definitions using Strategy pattern.

Each issue type generates a problematic file that tests
batch pipeline resilience.
"""

import csv
import io
import json
import os
import random
import string
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass
class FileResult:
    """Result of generating a problematic file."""

    issue_type: str
    filename: str
    filepath: Path | None = None
    content: bytes = b""
    expected_error: str = ""
    description: str = ""
    should_fail: bool = True
    row_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class BatchIssue(ABC):
    """Base class for batch file issues (Strategy pattern).

    Each subclass generates a specific type of problematic file
    that can occur in batch data pipelines.
    """

    name: str = "base_issue"
    description: str = "Base batch issue"
    expected_error: str = "Unknown"
    file_extension: str = ".csv"

    @abstractmethod
    def generate(self, output_dir: Path | None = None) -> FileResult:
        """Generate a problematic file.

        Args:
            output_dir: Directory to write file (optional)

        Returns:
            FileResult with file content and metadata
        """
        pass

    def _write_file(
        self,
        output_dir: Path,
        filename: str,
        content: bytes,
    ) -> Path:
        """Write content to file.

        Args:
            output_dir: Output directory
            filename: File name
            content: File content

        Returns:
            Path to written file
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        filepath = output_dir / filename
        with open(filepath, "wb") as f:
            f.write(content)
        return filepath

    def _generate_valid_row(self) -> dict[str, str]:
        """Generate a valid trade row."""
        return {
            "trade_id": str(uuid4()),
            "symbol": random.choice(["AAPL", "GOOGL", "MSFT", "AMZN"]),
            "price": str(Decimal(str(random.uniform(100, 500)))),
            "volume": str(Decimal(str(random.uniform(1, 1000)))),
            "side": random.choice(["BUY", "SELL"]),
            "trader_id": f"TRADER_{random.randint(1, 100)}",
            "event_timestamp": datetime.now(UTC).isoformat(),
        }

    def _generate_csv(self, rows: list[dict[str, str]]) -> bytes:
        """Generate CSV content from rows."""
        if not rows:
            return b""

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue().encode("utf-8")


class CorruptFileIssue(BatchIssue):
    """Generate corrupted files.

    Common causes:
    - Incomplete uploads
    - Disk errors
    - Transfer interruptions
    """

    name = "corrupt_file"
    description = "Corrupted/truncated file"
    expected_error = "CSV parsing error or unexpected EOF"

    def __init__(self, variant: str = "random"):
        """Initialize corrupt file generator.

        Args:
            variant: Type of corruption
                - "truncated": File cut off mid-row
                - "binary_garbage": Random bytes inserted
                - "null_bytes": Null bytes in file
                - "random": Random variant
        """
        self.variant = variant
        self._variants = ["truncated", "binary_garbage", "null_bytes"]

    def generate(self, output_dir: Path | None = None) -> FileResult:
        variant = self.variant
        if variant == "random":
            variant = random.choice(self._variants)

        # Generate valid data first
        rows = [self._generate_valid_row() for _ in range(10)]
        valid_csv = self._generate_csv(rows)

        if variant == "truncated":
            # Cut file in half
            content = valid_csv[:len(valid_csv) // 2]
            desc = "File truncated mid-content"

        elif variant == "binary_garbage":
            # Insert random bytes
            garbage = bytes(random.randint(0, 255) for _ in range(100))
            insert_pos = len(valid_csv) // 2
            content = valid_csv[:insert_pos] + garbage + valid_csv[insert_pos:]
            desc = "Random binary data inserted"

        else:  # null_bytes
            # Insert null bytes
            nulls = b"\x00" * 50
            insert_pos = len(valid_csv) // 3
            content = valid_csv[:insert_pos] + nulls + valid_csv[insert_pos:]
            desc = "Null bytes inserted"

        filename = f"corrupt_{variant}_{uuid4().hex[:8]}.csv"

        result = FileResult(
            issue_type=self.name,
            filename=filename,
            content=content,
            expected_error=self.expected_error,
            description=desc,
            should_fail=True,
            row_count=len(rows),
            metadata={"variant": variant},
        )

        if output_dir:
            result.filepath = self._write_file(output_dir, filename, content)

        return result


class SchemaDriftIssue(BatchIssue):
    """Generate files with schema changes.

    Common causes:
    - Upstream system changes
    - Different data sources with different schemas
    - Version mismatches
    """

    name = "schema_drift"
    description = "File with different schema than expected"
    expected_error = "Missing columns or type mismatch"

    def __init__(self, variant: str = "random"):
        """Initialize schema drift generator.

        Args:
            variant: Type of schema drift
                - "missing_column": Required column missing
                - "extra_column": Unexpected column added
                - "renamed_column": Column renamed
                - "reordered": Columns in different order
                - "random": Random variant
        """
        self.variant = variant
        self._variants = ["missing_column", "extra_column", "renamed_column", "reordered"]

    def generate(self, output_dir: Path | None = None) -> FileResult:
        variant = self.variant
        if variant == "random":
            variant = random.choice(self._variants)

        rows = [self._generate_valid_row() for _ in range(10)]

        if variant == "missing_column":
            # Remove a required column
            for row in rows:
                del row["price"]
            desc = "Missing required column: price"

        elif variant == "extra_column":
            # Add unexpected column
            for row in rows:
                row["extra_field"] = "unexpected_data"
            desc = "Extra unexpected column: extra_field"

        elif variant == "renamed_column":
            # Rename a column
            for row in rows:
                row["trade_price"] = row.pop("price")
            desc = "Column renamed: price -> trade_price"

        else:  # reordered
            # Reorder columns
            reordered_rows = []
            for row in rows:
                keys = list(row.keys())
                random.shuffle(keys)
                reordered_rows.append({k: row[k] for k in keys})
            rows = reordered_rows
            desc = "Columns in different order"

        content = self._generate_csv(rows)
        filename = f"schema_drift_{variant}_{uuid4().hex[:8]}.csv"

        result = FileResult(
            issue_type=self.name,
            filename=filename,
            content=content,
            expected_error=self.expected_error,
            description=desc,
            should_fail=variant == "missing_column",  # Only missing required fails
            row_count=len(rows),
            metadata={"variant": variant},
        )

        if output_dir:
            result.filepath = self._write_file(output_dir, filename, content)

        return result


class EncodingFileIssue(BatchIssue):
    """Generate files with encoding issues.

    Common causes:
    - Different systems with different default encodings
    - Legacy data exports
    - Cross-platform file transfers
    """

    name = "encoding_issue"
    description = "File with wrong character encoding"
    expected_error = "UnicodeDecodeError"

    def __init__(self, encoding: str = "random"):
        """Initialize encoding issue generator.

        Args:
            encoding: Target encoding
                - "latin1": ISO-8859-1
                - "cp1252": Windows-1252
                - "utf16": UTF-16 without BOM
                - "random": Random encoding
        """
        self.encoding = encoding
        self._encodings = ["latin1", "cp1252", "utf16"]

    def generate(self, output_dir: Path | None = None) -> FileResult:
        encoding = self.encoding
        if encoding == "random":
            encoding = random.choice(self._encodings)

        rows = [self._generate_valid_row() for _ in range(10)]

        # Add some non-ASCII characters
        rows[0]["trader_id"] = "Müller"
        rows[1]["trader_id"] = "Øresund"
        rows[2]["trader_id"] = "Café Trading"

        # Generate CSV and encode with wrong encoding
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        csv_str = output.getvalue()

        content = csv_str.encode(encoding)
        filename = f"encoding_{encoding}_{uuid4().hex[:8]}.csv"

        result = FileResult(
            issue_type=self.name,
            filename=filename,
            content=content,
            expected_error=self.expected_error,
            description=f"File encoded as {encoding} (not UTF-8)",
            should_fail=True,
            row_count=len(rows),
            metadata={"encoding": encoding},
        )

        if output_dir:
            result.filepath = self._write_file(output_dir, filename, content)

        return result


class EmptyFileIssue(BatchIssue):
    """Generate empty files.

    Common causes:
    - Failed data extraction
    - No data for period
    - Process errors
    """

    name = "empty_file"
    description = "Empty file or header-only"
    expected_error = "No data to process"

    def __init__(self, variant: str = "random"):
        """Initialize empty file generator.

        Args:
            variant: Type of empty file
                - "zero_bytes": Completely empty
                - "header_only": Only header row
                - "whitespace": Only whitespace
                - "random": Random variant
        """
        self.variant = variant
        self._variants = ["zero_bytes", "header_only", "whitespace"]

    def generate(self, output_dir: Path | None = None) -> FileResult:
        variant = self.variant
        if variant == "random":
            variant = random.choice(self._variants)

        if variant == "zero_bytes":
            content = b""
            desc = "Zero-byte file"

        elif variant == "header_only":
            header = "trade_id,symbol,price,volume,side,trader_id,event_timestamp\n"
            content = header.encode("utf-8")
            desc = "Header row only, no data"

        else:  # whitespace
            content = b"\n\n   \n\t\n"
            desc = "Only whitespace characters"

        filename = f"empty_{variant}_{uuid4().hex[:8]}.csv"

        result = FileResult(
            issue_type=self.name,
            filename=filename,
            content=content,
            expected_error=self.expected_error,
            description=desc,
            should_fail=False,  # Should be handled gracefully, not error
            row_count=0,
            metadata={"variant": variant},
        )

        if output_dir:
            result.filepath = self._write_file(output_dir, filename, content)

        return result


class PartialFileIssue(BatchIssue):
    """Generate partially complete files.

    Common causes:
    - Upload still in progress
    - Writer crashed mid-file
    - Disk full during write
    """

    name = "partial_file"
    description = "File with incomplete data"
    expected_error = "Incomplete row at end of file"

    def __init__(self, complete_rows: int = 5, partial_bytes: int = 50):
        """Initialize partial file generator.

        Args:
            complete_rows: Number of complete rows
            partial_bytes: Bytes of partial last row
        """
        self.complete_rows = complete_rows
        self.partial_bytes = partial_bytes

    def generate(self, output_dir: Path | None = None) -> FileResult:
        # Generate complete rows
        rows = [self._generate_valid_row() for _ in range(self.complete_rows)]
        complete_csv = self._generate_csv(rows)

        # Add partial row
        partial_row = self._generate_valid_row()
        partial_csv = self._generate_csv([partial_row])
        # Take only part of the last row (skip header)
        partial_line = partial_csv.split(b"\n")[1][:self.partial_bytes]

        content = complete_csv + partial_line

        filename = f"partial_{uuid4().hex[:8]}.csv"

        result = FileResult(
            issue_type=self.name,
            filename=filename,
            content=content,
            expected_error=self.expected_error,
            description=f"{self.complete_rows} complete rows + partial row",
            should_fail=True,
            row_count=self.complete_rows,
            metadata={
                "complete_rows": self.complete_rows,
                "partial_bytes": self.partial_bytes,
            },
        )

        if output_dir:
            result.filepath = self._write_file(output_dir, filename, content)

        return result


class DuplicateFileIssue(BatchIssue):
    """Generate duplicate files for idempotency testing.

    Common causes:
    - Retry after timeout
    - Multiple file deliveries
    - Backup file copied to input
    """

    name = "duplicate_file"
    description = "Same file processed multiple times"
    expected_error = "None (tests idempotency)"

    def __init__(self):
        """Initialize duplicate file generator."""
        self._last_content: bytes | None = None
        self._last_filename: str | None = None

    def generate(self, output_dir: Path | None = None) -> FileResult:
        # First call generates new file, subsequent calls return same content
        if self._last_content is None:
            rows = [self._generate_valid_row() for _ in range(10)]
            self._last_content = self._generate_csv(rows)
            self._last_filename = f"duplicate_source_{uuid4().hex[:8]}.csv"

        # Generate with timestamp suffix for unique filename
        timestamp = datetime.now(UTC).strftime("%H%M%S%f")
        filename = f"dup_{timestamp}.csv"

        result = FileResult(
            issue_type=self.name,
            filename=filename,
            content=self._last_content,
            expected_error="None",
            description="Duplicate content (tests idempotent processing)",
            should_fail=False,
            row_count=10,
            metadata={"original_filename": self._last_filename},
        )

        if output_dir:
            result.filepath = self._write_file(output_dir, filename, self._last_content)

        return result

    def reset(self) -> None:
        """Reset to generate new content on next call."""
        self._last_content = None
        self._last_filename = None


class LargeFileIssue(BatchIssue):
    """Generate large files for memory/performance testing.

    Tests:
    - Memory consumption
    - Processing time
    - Batch size limits
    """

    name = "large_file"
    description = "Large file for stress testing"
    expected_error = "None (tests performance)"

    def __init__(self, row_count: int = 100000):
        """Initialize large file generator.

        Args:
            row_count: Number of rows to generate
        """
        self.row_count = row_count

    def generate(self, output_dir: Path | None = None) -> FileResult:
        # Generate rows in batches to avoid memory issues
        output = io.BytesIO()

        # Write header
        header = "trade_id,symbol,price,volume,side,trader_id,event_timestamp\n"
        output.write(header.encode("utf-8"))

        # Generate rows
        symbols = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"]
        for i in range(self.row_count):
            row = (
                f"{uuid4()},"
                f"{random.choice(symbols)},"
                f"{random.uniform(100, 500):.8f},"
                f"{random.uniform(1, 1000):.8f},"
                f"{random.choice(['BUY', 'SELL'])},"
                f"TRADER_{random.randint(1, 100)},"
                f"{datetime.now(UTC).isoformat()}\n"
            )
            output.write(row.encode("utf-8"))

        content = output.getvalue()
        filename = f"large_{self.row_count}rows_{uuid4().hex[:8]}.csv"

        result = FileResult(
            issue_type=self.name,
            filename=filename,
            content=content,
            expected_error="None",
            description=f"Large file with {self.row_count:,} rows",
            should_fail=False,
            row_count=self.row_count,
            metadata={
                "row_count": self.row_count,
                "size_bytes": len(content),
                "size_mb": len(content) / (1024 * 1024),
            },
        )

        if output_dir:
            result.filepath = self._write_file(output_dir, filename, content)

        return result


class WrongFormatIssue(BatchIssue):
    """Generate files in wrong format.

    Common causes:
    - Wrong file extension
    - Format detection failure
    - Misconfigured export
    """

    name = "wrong_format"
    description = "File format doesn't match extension"
    expected_error = "Format parsing error"

    def __init__(self, actual_format: str = "random"):
        """Initialize wrong format generator.

        Args:
            actual_format: Actual file format
                - "json_as_csv": JSON content with .csv extension
                - "xml_as_csv": XML content with .csv extension
                - "parquet_as_csv": Binary Parquet as .csv
                - "random": Random variant
        """
        self.actual_format = actual_format
        self._formats = ["json_as_csv", "xml_as_csv"]

    def generate(self, output_dir: Path | None = None) -> FileResult:
        actual_format = self.actual_format
        if actual_format == "random":
            actual_format = random.choice(self._formats)

        rows = [self._generate_valid_row() for _ in range(10)]

        if actual_format == "json_as_csv":
            content = json.dumps(rows, indent=2).encode("utf-8")
            desc = "JSON content with .csv extension"

        else:  # xml_as_csv
            xml = ['<?xml version="1.0"?>', "<trades>"]
            for row in rows:
                xml.append("  <trade>")
                for k, v in row.items():
                    xml.append(f"    <{k}>{v}</{k}>")
                xml.append("  </trade>")
            xml.append("</trades>")
            content = "\n".join(xml).encode("utf-8")
            desc = "XML content with .csv extension"

        filename = f"wrong_format_{actual_format}_{uuid4().hex[:8]}.csv"

        result = FileResult(
            issue_type=self.name,
            filename=filename,
            content=content,
            expected_error=self.expected_error,
            description=desc,
            should_fail=True,
            row_count=len(rows),
            metadata={"actual_format": actual_format},
        )

        if output_dir:
            result.filepath = self._write_file(output_dir, filename, content)

        return result


class MalformedRowIssue(BatchIssue):
    """Generate files with malformed rows.

    Common causes:
    - Data corruption in specific rows
    - Inconsistent quoting
    - Wrong delimiters
    """

    name = "malformed_row"
    description = "File with some malformed rows"
    expected_error = "Row parsing error"

    def __init__(self, malformed_count: int = 3, total_rows: int = 20):
        """Initialize malformed row generator.

        Args:
            malformed_count: Number of bad rows
            total_rows: Total row count
        """
        self.malformed_count = malformed_count
        self.total_rows = total_rows

    def generate(self, output_dir: Path | None = None) -> FileResult:
        lines = ["trade_id,symbol,price,volume,side,trader_id,event_timestamp"]

        # Generate rows, some malformed
        malformed_positions = random.sample(
            range(1, self.total_rows + 1),
            self.malformed_count
        )

        for i in range(1, self.total_rows + 1):
            if i in malformed_positions:
                # Generate malformed row
                variant = random.choice([
                    "too_few_columns",
                    "too_many_columns",
                    "unquoted_comma",
                    "unclosed_quote",
                ])

                if variant == "too_few_columns":
                    lines.append(f"{uuid4()},AAPL,100.50")  # Missing columns

                elif variant == "too_many_columns":
                    lines.append(
                        f"{uuid4()},AAPL,100.50,10,BUY,TRADER,2024-01-01,EXTRA,MORE"
                    )

                elif variant == "unquoted_comma":
                    lines.append(
                        f'{uuid4()},Price, with comma,100.50,10,BUY,TRADER,2024-01-01'
                    )

                else:  # unclosed_quote
                    lines.append(
                        f'{uuid4()},"AAPL,100.50,10,BUY,TRADER,2024-01-01'
                    )
            else:
                row = self._generate_valid_row()
                lines.append(",".join(str(v) for v in row.values()))

        content = "\n".join(lines).encode("utf-8")
        filename = f"malformed_rows_{uuid4().hex[:8]}.csv"

        result = FileResult(
            issue_type=self.name,
            filename=filename,
            content=content,
            expected_error=self.expected_error,
            description=f"{self.malformed_count} malformed rows in {self.total_rows} total",
            should_fail=True,  # Depends on error handling strategy
            row_count=self.total_rows,
            metadata={
                "malformed_count": self.malformed_count,
                "malformed_positions": malformed_positions,
            },
        )

        if output_dir:
            result.filepath = self._write_file(output_dir, filename, content)

        return result


# Factory for creating issues by name
BATCH_ISSUES: dict[str, type[BatchIssue]] = {
    "corrupt_file": CorruptFileIssue,
    "schema_drift": SchemaDriftIssue,
    "encoding_issue": EncodingFileIssue,
    "empty_file": EmptyFileIssue,
    "partial_file": PartialFileIssue,
    "duplicate_file": DuplicateFileIssue,
    "large_file": LargeFileIssue,
    "wrong_format": WrongFormatIssue,
    "malformed_row": MalformedRowIssue,
}


def create_issue(name: str, **kwargs) -> BatchIssue:
    """Factory function to create batch issues by name.

    Args:
        name: Issue type name
        **kwargs: Issue-specific parameters

    Returns:
        BatchIssue instance

    Raises:
        ValueError: If issue type not found
    """
    if name not in BATCH_ISSUES:
        raise ValueError(
            f"Unknown issue type: {name}. "
            f"Available: {list(BATCH_ISSUES.keys())}"
        )
    return BATCH_ISSUES[name](**kwargs)
