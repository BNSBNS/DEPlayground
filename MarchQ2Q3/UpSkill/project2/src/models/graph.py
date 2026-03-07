"""Graph node and edge models for the knowledge graph."""

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class NodeType(StrEnum):
    database = "database"
    schema = "schema"
    table = "table"
    column = "column"
    dbt_model = "dbt_model"
    dashboard = "dashboard"
    metric = "metric"
    owner = "owner"
    document = "document"
    document_chunk = "document_chunk"


class RelationshipType(StrEnum):
    belongs_to = "belongs_to"
    depends_on = "depends_on"
    sources = "sources"
    refs = "refs"
    materializes = "materializes"
    uses = "uses"
    displays = "displays"
    derived_from = "derived_from"
    owned_by = "owned_by"
    part_of = "part_of"
    describes = "describes"


class BaseNode(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    node_type: NodeType
    properties: dict[str, Any] = {}
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class DatabaseNode(BaseNode):
    node_type: NodeType = NodeType.database


class SchemaNode(BaseNode):
    node_type: NodeType = NodeType.schema
    database: str


class TableNode(BaseNode):
    node_type: NodeType = NodeType.table
    schema_name: str
    database: str
    row_count: int | None = None
    description: str = ""


class ColumnNode(BaseNode):
    node_type: NodeType = NodeType.column
    table: str
    data_type: str
    nullable: bool = True
    description: str = ""


class DbtModelNode(BaseNode):
    node_type: NodeType = NodeType.dbt_model
    materialization: str
    schema_name: str
    description: str = ""
    depends_on: list[str] = []


class DashboardNode(BaseNode):
    node_type: NodeType = NodeType.dashboard
    tool: str = "tableau"
    url: str = ""
    owner: str = ""


class MetricNode(BaseNode):
    node_type: NodeType = NodeType.metric
    expression: str
    table: str


class OwnerNode(BaseNode):
    node_type: NodeType = NodeType.owner
    team: str
    email: str = ""
    slack_channel: str = ""


class DocumentNode(BaseNode):
    node_type: NodeType = NodeType.document
    source_path: str
    content: str


class DocumentChunkNode(BaseNode):
    node_type: NodeType = NodeType.document_chunk
    document_id: str
    content: str
    chunk_index: int


class GraphEdge(BaseModel):
    source_id: str
    target_id: str
    relationship: RelationshipType
    properties: dict[str, Any] = {}
