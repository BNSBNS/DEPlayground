from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class FixType(StrEnum):
    SQL_ALTER = "sql_alter"
    SQL_UPDATE = "sql_update"
    DBT_MODEL_PATCH = "dbt_model_patch"
    DBT_TEST_ADD = "dbt_test_add"
    CONFIG_CHANGE = "config_change"
    MANUAL = "manual"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class GeneratedFix(BaseModel):
    """A single generated fix (SQL, dbt patch, etc.)."""

    fix_type: FixType
    file_path: str = ""
    content: str
    description: str
    risk_level: RiskLevel = RiskLevel.MEDIUM


class FixProposal(BaseModel):
    """A complete fix proposal with one or more fixes."""

    proposal_id: UUID = Field(default_factory=uuid4)
    fixes: list[GeneratedFix] = Field(default_factory=list)
    pr_title: str = ""
    pr_body: str = ""
    requires_approval: bool = False
    approved: bool = False
