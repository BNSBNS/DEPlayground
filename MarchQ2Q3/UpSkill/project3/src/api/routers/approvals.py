from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import src.approval_store as approval_store

log = structlog.get_logger(__name__)
router = APIRouter(tags=["approvals"])


class ApprovalAction(BaseModel):
    reviewer: str = ""
    comment: str = ""


@router.post("/approvals/{proposal_id}/approve")
async def approve(proposal_id: str, action: ApprovalAction) -> dict[str, str]:
    """Approve a fix proposal."""
    approval_store.set_approval(proposal_id, "approved", action.reviewer, action.comment)
    await log.ainfo("proposal_approved", proposal_id=proposal_id, reviewer=action.reviewer)
    return {"status": "approved", "proposal_id": proposal_id}


@router.post("/approvals/{proposal_id}/reject")
async def reject(proposal_id: str, action: ApprovalAction) -> dict[str, str]:
    """Reject a fix proposal."""
    approval_store.set_approval(proposal_id, "rejected", action.reviewer, action.comment)
    await log.ainfo("proposal_rejected", proposal_id=proposal_id, reviewer=action.reviewer)
    return {"status": "rejected", "proposal_id": proposal_id}


@router.get("/approvals/{proposal_id}")
async def get_approval(proposal_id: str) -> dict:
    """Get the approval status of a proposal."""
    approval = approval_store.get_approval(proposal_id)
    if not approval:
        raise HTTPException(status_code=404, detail=f"Approval {proposal_id} not found")
    return approval
