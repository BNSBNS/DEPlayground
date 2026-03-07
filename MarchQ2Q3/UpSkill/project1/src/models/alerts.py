"""Alert models with state machine lifecycle."""

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class AlertSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertState(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


# Valid state transitions
ALERT_TRANSITIONS: dict[AlertState, set[AlertState]] = {
    AlertState.OPEN: {AlertState.ACKNOWLEDGED, AlertState.RESOLVED, AlertState.SUPPRESSED},
    AlertState.ACKNOWLEDGED: {AlertState.RESOLVED, AlertState.SUPPRESSED},
    AlertState.RESOLVED: set(),
    AlertState.SUPPRESSED: {AlertState.OPEN},
}


class Alert(BaseModel):
    """A data quality alert with lifecycle management."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    title: str
    description: str
    severity: AlertSeverity
    state: AlertState = AlertState.OPEN
    source_table: str
    source_metric_type: str
    root_cause: str | None = None
    suggested_remediation: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None

    def can_transition_to(self, new_state: AlertState) -> bool:
        """Check if transition to new_state is valid."""
        return new_state in ALERT_TRANSITIONS.get(self.state, set())

    def transition_to(self, new_state: AlertState) -> None:
        """Transition alert to a new state. Raises ValueError if invalid."""
        if not self.can_transition_to(new_state):
            msg = f"Cannot transition from {self.state} to {new_state}"
            raise ValueError(msg)
        self.state = new_state
        now = datetime.utcnow()
        if new_state == AlertState.ACKNOWLEDGED:
            self.acknowledged_at = now
        elif new_state == AlertState.RESOLVED:
            self.resolved_at = now
