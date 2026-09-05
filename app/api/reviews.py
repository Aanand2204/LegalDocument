"""Lawyer review endpoints (plan sections 12, 20, 24).

This is the ONLY place `Contract.status` can become "approved" or
"rejected", and the only place a `Risk.human_decision` is set — matching
the plan's core principle, AI recommends and a human decides (RULE-001).
No agent or workflow code writes these fields. Any logged-in account can
call these (no roles — see app/api/deps.py); the point is AI-vs-human,
not which human.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_current_user, get_db, require_owned_contract, require_owned_risk
from app.database import repositories as repo
from app.governance import audit
from app.schemas.review import ReviewCreateRequest, ReviewOut
from app.schemas.risk import RiskDecisionRequest, RiskOut

router = APIRouter(tags=["reviews"])


@router.post(
    "/contracts/{contract_id}/review", response_model=ReviewOut, status_code=status.HTTP_201_CREATED
)
def submit_review(
    contract_id: int,
    body: ReviewCreateRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    contract = require_owned_contract(db, contract_id, user)

    review = repo.create_review(
        db,
        contract_id=contract_id,
        lawyer_id=user.email,
        decision=body.decision,
        comments=body.comments,
    )
    new_status = "under_review" if body.decision == "request_changes" else body.decision
    repo.update_contract_status(db, contract, new_status)

    audit.log_user_action(
        db,
        user=user.email,
        action=f"review_{body.decision}",
        resource=f"contract:{contract_id}",
        details={"comments": body.comments},
    )
    return review


def _decide_risk(
    db: Session, risk_id: int, *, decision: str, body: RiskDecisionRequest, user: CurrentUser
) -> RiskOut:
    risk = require_owned_risk(db, risk_id, user)

    repo.record_risk_decision(db, risk, decision=decision, reason=body.reason, reviewed_by=user.email)
    audit.log_user_action(
        db,
        user=user.email,
        action=f"risk_{decision.lower()}",
        resource=f"risk:{risk_id}",
        details={"reason": body.reason},
    )
    return risk


@router.post("/risks/{risk_id}/approve", response_model=RiskOut)
def approve_risk(
    risk_id: int,
    body: RiskDecisionRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Lawyer confirms the AI's risk finding stands (human_decision=CONFIRMED)."""
    return _decide_risk(db, risk_id, decision="CONFIRMED", body=body, user=user)


@router.post("/risks/{risk_id}/reject", response_model=RiskOut)
def reject_risk(
    risk_id: int,
    body: RiskDecisionRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Lawyer overrides the AI's risk finding as not applicable (plan
    section 24's override example; human_decision=OVERRIDDEN)."""
    return _decide_risk(db, risk_id, decision="OVERRIDDEN", body=body, user=user)
