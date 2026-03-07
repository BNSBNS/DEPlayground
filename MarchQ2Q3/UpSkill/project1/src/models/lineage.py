"""Lineage graph node and edge models."""

from enum import StrEnum

from pydantic import BaseModel, Field


class NodeType(StrEnum):
    TABLE = "table"
    VIEW = "view"
    DBT_MODEL = "dbt_model"
    DASHBOARD = "dashboard"
    METRIC = "metric"
    PIPELINE = "pipeline"


class RelationshipType(StrEnum):
    DEPENDS_ON = "depends_on"
    DERIVED_FROM = "derived_from"
    FEEDS_INTO = "feeds_into"


class LineageNode(BaseModel):
    """A node in the data lineage graph."""

    id: str  # fully qualified name
    name: str
    node_type: NodeType
    owner: str | None = None
    tags: list[str] = Field(default_factory=list)


class LineageEdge(BaseModel):
    """A directed edge in the data lineage graph."""

    source_id: str
    target_id: str
    relationship: RelationshipType
    transformation: str | None = None
