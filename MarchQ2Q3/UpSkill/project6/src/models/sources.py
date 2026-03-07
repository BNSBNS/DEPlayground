from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

SourceType = Literal["batch", "stream"]


class DataSource(BaseModel):
    name: str
    source_type: SourceType
    table_or_query: str | None = None
    kafka_topic: str | None = None
