"""Load PacketRecord lists from JSON fixture files."""

from __future__ import annotations

import json
import pathlib

from src.models import PacketRecord


def load_packets(path: str | pathlib.Path) -> list[PacketRecord]:
    """Load a list of PacketRecord objects from a JSON file."""
    data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    return [PacketRecord.model_validate(record) for record in data]


def load_packets_from_list(data: list[dict[str, object]]) -> list[PacketRecord]:
    """Parse PacketRecord objects from an in-memory list of dicts."""
    return [PacketRecord.model_validate(record) for record in data]
