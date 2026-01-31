"""Streaming chaos simulators.

Provides issue generators for streaming data pipelines:
- Poison pills (malformed JSON, invalid encoding)
- Schema violations (missing fields, wrong types)
- Duplicates and out-of-order events
- Late arriving events
- High volume bursts
"""

from scripts.chaos.streaming.issues import (
    StreamingIssue,
    PoisonPillIssue,
    SchemaViolationIssue,
    DuplicateEventIssue,
    LateEventIssue,
    OutOfOrderIssue,
    HighVolumeIssue,
    EncodingIssue,
    NullFieldIssue,
)
from scripts.chaos.streaming.simulator import StreamingChaosSimulator

__all__ = [
    "StreamingIssue",
    "PoisonPillIssue",
    "SchemaViolationIssue",
    "DuplicateEventIssue",
    "LateEventIssue",
    "OutOfOrderIssue",
    "HighVolumeIssue",
    "EncodingIssue",
    "NullFieldIssue",
    "StreamingChaosSimulator",
]
