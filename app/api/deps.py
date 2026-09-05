"""Shared FastAPI dependencies: DB session, session-cookie auth, and
per-account contract ownership (no roles — every account can act on
anything it owns; require_owned_* is the ownership boundary)."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import repositories as repo
from app.database.database import get_db  # re-exported
from app.database.models import Contract, Risk
from app.services import auth_service
from config import get_settings

__all__ = [
    "get_db",
    "CurrentUser",
    "get_current_user",
    "require_owned_contract",
    "require_owned_risk",
]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CurrentUser:
    id: int
    email: str


def get_current_user(request: Request, db: Session = Depends(get_db)) -> CurrentUser:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    session = repo.get_valid_session(db, auth_service.hash_token(token))
    if session is None:
        logger.info("rejected request: session missing, expired, or revoked")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired or invalid")

    repo.touch_session(db, session, ttl_minutes=settings.session_inactivity_minutes)
    user = session.user
    return CurrentUser(id=user.id, email=user.email)


def require_owned_contract(db: Session, contract_id: int, user: CurrentUser) -> Contract:
    # 404, not 403, either way — a contract ID belonging to someone else
    # shouldn't reveal that it exists.
    contract = repo.get_contract(db, contract_id)
    if contract is None or contract.uploaded_by != user.email:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contract not found")
    return contract


def require_owned_risk(db: Session, risk_id: int, user: CurrentUser) -> Risk:
    risk = repo.get_risk(db, risk_id)
    if risk is None or risk.contract.uploaded_by != user.email:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Risk not found")
    return risk
