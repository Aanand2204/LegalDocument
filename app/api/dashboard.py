"""Dashboard statistics and audit-trail read endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_current_user, get_db, require_owned_contract
from app.database import repositories as repo

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/statistics")
def dashboard_statistics(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    return repo.dashboard_counts(db, uploaded_by=user.email)


@router.get("/audit/{contract_id}")
def contract_audit_trail(
    contract_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    require_owned_contract(db, contract_id, user)
    events = repo.list_governance_events(db, contract_id)
    logs = repo.list_audit_logs(db, resource=f"contract:{contract_id}")
    return {
        "governance_events": [
            {
                "event_type": e.event_type,
                "agent_name": e.agent_name,
                "model_name": e.model_name,
                "model_version": e.model_version,
                "timestamp": e.timestamp,
            }
            for e in events
        ],
        "audit_logs": [
            {"user": a.user, "action": a.action, "timestamp": a.timestamp, "details": a.details}
            for a in logs
        ],
    }
