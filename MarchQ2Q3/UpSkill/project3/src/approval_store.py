"""Shared in-memory approval store.

Both the REST API (approvals router) and the agent's await_approval_node read/write here,
so a decision posted via the API is immediately visible to the polling node.
"""
from __future__ import annotations

_approvals: dict[str, dict] = {}


def set_approval(
    proposal_id: str,
    action: str,
    reviewer: str = "",
    comment: str = "",
) -> None:
    """Record an approval decision (approved | rejected)."""
    _approvals[proposal_id] = {
        "proposal_id": proposal_id,
        "action": action,
        "reviewer": reviewer,
        "comment": comment,
    }


def get_approval(proposal_id: str) -> dict | None:
    """Return the approval record, or None if no decision has been made yet."""
    return _approvals.get(proposal_id)
