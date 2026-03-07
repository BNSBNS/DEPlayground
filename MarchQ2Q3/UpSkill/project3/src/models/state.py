from typing import TypedDict

from src.models.diagnosis import Diagnosis
from src.models.events import PipelineFailureEvent
from src.models.fixes import FixProposal


class AgentState(TypedDict, total=False):
    """LangGraph agent state."""

    event: PipelineFailureEvent
    logs: str
    schema_diff: str
    error_classification: str
    context: dict[str, str]
    diagnosis: Diagnosis
    proposed_fixes: FixProposal
    validation_passed: bool
    validation_errors: list[str]
    pr_url: str
    notification_sent: bool
    requires_human_approval: bool
    iteration: int
    max_iterations: int
    error: str
