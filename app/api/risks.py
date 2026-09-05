"""Read-only risk and clause endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_current_user, get_db, require_owned_contract
from app.database import repositories as repo
from app.schemas.clause import ClauseOut
from app.schemas.risk import RiskOut

router = APIRouter(tags=["risks"])


@router.get("/contracts/{contract_id}/risks", response_model=list[RiskOut])
def list_risks(
    contract_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    require_owned_contract(db, contract_id, user)
    return repo.list_risks(db, contract_id)


@router.get("/contracts/{contract_id}/clauses", response_model=list[ClauseOut])
def list_clauses(
    contract_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    require_owned_contract(db, contract_id, user)
    return repo.list_clauses(db, contract_id)
