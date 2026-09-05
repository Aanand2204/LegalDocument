"""Deadline endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_current_user, get_db, require_owned_contract
from app.database import repositories as repo
from app.schemas.deadline import DeadlineAlert, DeadlineOut
from app.services.deadline_service import check_deadlines

router = APIRouter(tags=["deadlines"])

# Translates deadline_service's internal status labels to the API's shape.
_WINDOW_LABELS = {"notified_90": "90_day", "notified_30": "30_day", "notified_7": "7_day"}


@router.get("/contracts/{contract_id}/deadlines", response_model=list[DeadlineOut])
def list_contract_deadlines(
    contract_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    require_owned_contract(db, contract_id, user)
    return repo.list_deadlines(db, contract_id)


@router.post("/deadlines/check", response_model=list[DeadlineAlert])
def run_deadline_check(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    owned_ids = {c.id for c in repo.list_contracts(db, uploaded_by=user.email)}
    results = check_deadlines(db, contract_ids=owned_ids)
    return [
        DeadlineAlert(
            contract_id=r.contract.id,
            contract_number=r.contract.contract_number,
            deadline_id=r.deadline.id,
            deadline_type=r.deadline.deadline_type,
            deadline_date=r.deadline.deadline_date,
            days_remaining=r.days_remaining,
            window=_WINDOW_LABELS[r.window],
        )
        for r in results
    ]
