"""Batch chaos simulators.

Provides issue generators for batch data pipelines:
- Corrupt files (truncated, invalid format)
- Schema drift (added/removed columns)
- Encoding issues (wrong character encoding)
- Empty and partial files
- Duplicate files
- Large files (memory pressure)
"""

from scripts.chaos.batch.issues import (
    BatchIssue,
    CorruptFileIssue,
    SchemaDriftIssue,
    EncodingFileIssue,
    EmptyFileIssue,
    PartialFileIssue,
    DuplicateFileIssue,
    LargeFileIssue,
    WrongFormatIssue,
    MalformedRowIssue,
)
from scripts.chaos.batch.simulator import BatchChaosSimulator

__all__ = [
    "BatchIssue",
    "CorruptFileIssue",
    "SchemaDriftIssue",
    "EncodingFileIssue",
    "EmptyFileIssue",
    "PartialFileIssue",
    "DuplicateFileIssue",
    "LargeFileIssue",
    "WrongFormatIssue",
    "MalformedRowIssue",
    "BatchChaosSimulator",
]
