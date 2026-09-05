"""Shared FastAPI dependencies: DB session, real session-cookie auth, and
per-account contract ownership.

Session model: an opaque token held in an httpOnly, non-persistent
(browser-close-clears-it) cookie, hashed and looked up against
app/database/models.py::UserSession — see app/services/auth_service.py
(hashing/token logic) and app/api/auth.py (register/login/logout, where
the cookie is actually issued). No signing secret anywhere, unlike a
JWT — see the auth plan's "Session model" note. `get_current_user` slides
the session's expiry forward on every call (`repo.touch_session`), so a
session dies after `session_inactivity_minutes` of no requests, not on a
fixed schedule.

No roles — every authenticated account can perform every *action*
(upload, analyze, review, ...); `get_current_user` only answers "is
there a valid session". What each account can *see*, though, is scoped
to its own contracts (`Contract.uploaded_by`) — `require_owned_contract`
below is that boundary, used by every route that takes a contract_id
(directly or via a clause/risk/deadline that belongs to one).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import repositories as repo
from app.database.database import get_db  # re-exported for `from app.api.deps import get_db`
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
    """Fetch a contract, 404ing if it doesn't exist *or* the current
    account doesn't own it — deliberately the same response either way,
    so a contract ID belonging to someone else doesn't even reveal that
    it exists."""
    contract = repo.get_contract(db, contract_id)
    if contract is None or contract.uploaded_by != user.email:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contract not found")
    return contract


def require_owned_risk(db: Session, risk_id: int, user: CurrentUser) -> Risk:
    """Same boundary as `require_owned_contract`, one level down — a risk
    is owned by whoever owns the contract it belongs to."""
    risk = repo.get_risk(db, risk_id)
    if risk is None or risk.contract.uploaded_by != user.email:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Risk not found")
    return risk
