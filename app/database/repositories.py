"""Thin per-entity query helpers.

Kept intentionally simple (plain functions over a `Session`, no repository
base class/ORM abstraction layer) — there's one database and one ORM here,
so an abstraction over that would add indirection without a second
implementation to justify it. This module exists to keep query logic out
of the API route handlers, not to hide SQLAlchemy.
"""
from __future__ import annotations

import datetime as dt
import uuid
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    AuditLog,
    Clause,
    Contract,
    Deadline,
    GovernanceEvent,
    Review,
    Risk,
    User,
    UserSession,
)

_Row = TypeVar("_Row")


def _persist_all(db: Session, rows: list[_Row]) -> list[_Row]:
    db.add_all(rows)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


def next_contract_number() -> str:
    """Human-friendly contract id, e.g. CNT-3F2A1B. Uniqueness is enforced
    by the `contracts.contract_number` unique constraint, not by this
    generator, so callers should handle a rare collision by retrying."""
    return f"CNT-{uuid.uuid4().hex[:6].upper()}"


def create_contract(db: Session, **fields) -> Contract:
    contract = Contract(contract_number=next_contract_number(), **fields)
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return contract


def get_contract(db: Session, contract_id: int) -> Contract | None:
    return db.get(Contract, contract_id)


def list_contracts(
    db: Session, limit: int = 100, offset: int = 0, *, uploaded_by: str | None = None
) -> list[Contract]:
    stmt = select(Contract).order_by(Contract.created_at.desc()).limit(limit).offset(offset)
    if uploaded_by is not None:
        stmt = stmt.where(Contract.uploaded_by == uploaded_by)
    return list(db.scalars(stmt))


def update_contract_status(db: Session, contract: Contract, status: str) -> Contract:
    contract.status = status
    db.commit()
    db.refresh(contract)
    return contract


def add_clauses(db: Session, contract_id: int, clauses: list[dict]) -> list[Clause]:
    return _persist_all(db, [Clause(contract_id=contract_id, **c) for c in clauses])


def list_clauses(db: Session, contract_id: int) -> list[Clause]:
    stmt = select(Clause).where(Clause.contract_id == contract_id)
    return list(db.scalars(stmt))


def add_risks(db: Session, contract_id: int, risks: list[dict]) -> list[Risk]:
    return _persist_all(db, [Risk(contract_id=contract_id, **r) for r in risks])


def list_risks(db: Session, contract_id: int) -> list[Risk]:
    stmt = select(Risk).where(Risk.contract_id == contract_id)
    return list(db.scalars(stmt))


def get_risk(db: Session, risk_id: int) -> Risk | None:
    return db.get(Risk, risk_id)


def record_risk_decision(
    db: Session, risk: Risk, *, decision: str, reason: str | None, reviewed_by: str
) -> Risk:
    risk.human_decision = decision
    risk.human_reason = reason
    risk.reviewed_by = reviewed_by
    risk.reviewed_at = dt.datetime.now(dt.UTC)
    db.commit()
    db.refresh(risk)
    return risk


def add_deadlines(db: Session, contract_id: int, deadlines: list[dict]) -> list[Deadline]:
    return _persist_all(db, [Deadline(contract_id=contract_id, **d) for d in deadlines])


def list_deadlines(
    db: Session, contract_id: int | None = None, *, contract_ids: set[int] | None = None
) -> list[Deadline]:
    if contract_ids is not None and not contract_ids:
        return []  # avoids an empty-IN warning; no ids means no rows anyway
    stmt = select(Deadline)
    if contract_id is not None:
        stmt = stmt.where(Deadline.contract_id == contract_id)
    if contract_ids is not None:
        stmt = stmt.where(Deadline.contract_id.in_(contract_ids))
    return list(db.scalars(stmt))


def update_deadline_status(db: Session, deadline: Deadline, status: str) -> Deadline:
    deadline.status = status
    db.commit()
    db.refresh(deadline)
    return deadline


def create_review(db: Session, contract_id: int, **fields) -> Review:
    review = Review(contract_id=contract_id, **fields)
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


def log_governance_event(db: Session, contract_id: int, **fields) -> GovernanceEvent:
    event = GovernanceEvent(contract_id=contract_id, **fields)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def list_governance_events(db: Session, contract_id: int) -> list[GovernanceEvent]:
    stmt = select(GovernanceEvent).where(GovernanceEvent.contract_id == contract_id)
    return list(db.scalars(stmt))


def log_audit(db: Session, *, user: str, action: str, resource: str, details: str | None = None) -> AuditLog:
    entry = AuditLog(user=user, action=action, resource=resource, details=details)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def list_audit_logs(db: Session, resource: str | None = None) -> list[AuditLog]:
    stmt = select(AuditLog)
    if resource is not None:
        stmt = stmt.where(AuditLog.resource == resource)
    return list(db.scalars(stmt).unique())


def create_user(db: Session, *, email: str, password_hash: str) -> User:
    user = User(email=email, password_hash=password_hash)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_email(db: Session, email: str) -> User | None:
    stmt = select(User).where(User.email == email)
    return db.scalars(stmt).first()


def get_user(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def record_login(db: Session, user: User) -> User:
    user.last_login_at = dt.datetime.now(dt.UTC)
    db.commit()
    db.refresh(user)
    return user


def create_session(db: Session, *, user_id: int, token_hash: str, ttl_minutes: int) -> UserSession:
    session = UserSession(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=dt.datetime.now(dt.UTC) + dt.timedelta(minutes=ttl_minutes),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_valid_session(db: Session, token_hash: str) -> UserSession | None:
    """The session for `token_hash`, or None if it doesn't exist, has
    expired, or was revoked (logged out) — callers don't need to check
    those separately."""
    stmt = select(UserSession).where(UserSession.token_hash == token_hash)
    session = db.scalars(stmt).first()
    if session is None or session.revoked_at is not None:
        return None
    if session.expires_at < dt.datetime.now(dt.UTC):
        return None
    return session


def touch_session(db: Session, session: UserSession, *, ttl_minutes: int) -> None:
    """Slide `expires_at` forward on activity — see `get_valid_session`:
    with no further activity, it simply stops being pushed out and the
    session lapses on its own `ttl_minutes` after the last request."""
    session.expires_at = dt.datetime.now(dt.UTC) + dt.timedelta(minutes=ttl_minutes)
    db.commit()


def revoke_session(db: Session, token_hash: str) -> None:
    stmt = select(UserSession).where(UserSession.token_hash == token_hash)
    session = db.scalars(stmt).first()
    if session is not None and session.revoked_at is None:
        session.revoked_at = dt.datetime.now(dt.UTC)
        db.commit()


def dashboard_counts(db: Session, *, uploaded_by: str | None = None) -> dict[str, int]:
    contract_stmt = select(Contract)
    if uploaded_by is not None:
        contract_stmt = contract_stmt.where(Contract.uploaded_by == uploaded_by)
    contracts = list(db.scalars(contract_stmt))
    contract_ids = [c.id for c in contracts]

    if not contract_ids:
        return {
            "total_contracts": 0,
            "high_risk_count": 0,
            "pending_review_count": 0,
            "upcoming_deadline_count": 0,
        }

    risks = list(db.scalars(select(Risk).where(Risk.contract_id.in_(contract_ids))))
    deadlines = list(db.scalars(select(Deadline).where(Deadline.contract_id.in_(contract_ids))))

    return {
        "total_contracts": len(contracts),
        "high_risk_count": sum(1 for r in risks if r.risk_level in ("HIGH", "CRITICAL")),
        "pending_review_count": sum(
            1 for r in risks if r.requires_human_review and r.human_decision is None
        ),
        "upcoming_deadline_count": sum(1 for d in deadlines if d.status != "passed"),
    }
