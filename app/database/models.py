"""SQLAlchemy ORM models.

Mirrors the data architecture in the implementation plan (contracts,
clauses, risks, deadlines, reviews, governance_events, audit_logs) with
two intentional additions, called out where they occur:

- `Contract.document_hash` / `document_path` for the document-integrity
  requirement (plan section 30).
- `Risk.human_decision` / `human_reason` / `reviewed_by` / `reviewed_at`
  for AI-override tracking (plan section 24), beyond the minimal `risks`
  schema in section 16.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    filename: Mapped[str] = mapped_column(String(255))
    contract_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    parties: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    effective_date: Mapped[dt.date | None] = mapped_column(nullable=True)
    expiry_date: Mapped[dt.date | None] = mapped_column(nullable=True)

    # uploaded -> analyzing -> analyzed -> under_review -> approved | rejected
    status: Mapped[str] = mapped_column(String(20), default="uploaded")

    document_path: Mapped[str] = mapped_column(String(500))
    document_hash: Mapped[str] = mapped_column(String(64))  # sha256 hex digest
    uploaded_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    clauses: Mapped[list[Clause]] = relationship(
        back_populates="contract", cascade="all, delete-orphan"
    )
    risks: Mapped[list[Risk]] = relationship(back_populates="contract", cascade="all, delete-orphan")
    deadlines: Mapped[list[Deadline]] = relationship(
        back_populates="contract", cascade="all, delete-orphan"
    )
    reviews: Mapped[list[Review]] = relationship(
        back_populates="contract", cascade="all, delete-orphan"
    )

    @property
    def latest_review(self) -> Review | None:
        """Most recent human decision, if any — a contract can be
        reviewed more than once (e.g. "request changes" then a later
        "approved"), and the frontend only ever needs the latest one to
        know whether/how it was decided (see ContractDetail)."""
        return max(self.reviews, key=lambda r: r.reviewed_at, default=None)


class Clause(Base):
    __tablename__ = "clauses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id"), index=True)
    clause_type: Mapped[str] = mapped_column(String(100))
    clause_text: Mapped[str] = mapped_column(Text)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    contract: Mapped[Contract] = relationship(back_populates="clauses")


class Risk(Base):
    __tablename__ = "risks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id"), index=True)
    clause_id: Mapped[int | None] = mapped_column(ForeignKey("clauses.id"), nullable=True)
    risk_type: Mapped[str] = mapped_column(String(100))
    risk_score: Mapped[int] = mapped_column(Integer)
    risk_level: Mapped[str] = mapped_column(String(20))  # LOW / MEDIUM / HIGH / CRITICAL
    reason: Mapped[str] = mapped_column(Text)
    recommendation: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    requires_human_review: Mapped[bool] = mapped_column(default=False)

    # AI-override tracking (plan section 24) — set only via the lawyer
    # approve/reject endpoints, never by an agent.
    human_decision: Mapped[str | None] = mapped_column(String(20), nullable=True)
    human_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reviewed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    contract: Mapped[Contract] = relationship(back_populates="risks")


class Deadline(Base):
    __tablename__ = "deadlines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id"), index=True)
    deadline_type: Mapped[str] = mapped_column(String(50))
    deadline_date: Mapped[dt.date] = mapped_column()
    notice_period_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # upcoming -> notified_90 -> notified_30 -> notified_7 -> passed
    status: Mapped[str] = mapped_column(String(20), default="upcoming")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    contract: Mapped[Contract] = relationship(back_populates="deadlines")


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id"), index=True)
    lawyer_id: Mapped[str] = mapped_column(String(100))
    decision: Mapped[str] = mapped_column(String(20))  # approved / rejected / request_changes
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    contract: Mapped[Contract] = relationship(back_populates="reviews")


class GovernanceEvent(Base):
    """One row per agent execution / governance decision (plan section 11, RULE-004)."""

    __tablename__ = "governance_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(50))
    agent_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    output_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AuditLog(Base):
    """General-purpose audit trail for user-initiated actions (plan section 31)."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(100))
    resource: Mapped[str] = mapped_column(String(100))
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON-encoded string


class User(Base):
    """A real account — see app/services/auth_service.py for hashing and
    app/api/auth.py for register/login/logout. `password_hash` is a
    bcrypt hash; the plaintext password is never stored or logged."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(60))  # bcrypt hashes are always 60 chars
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_login_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    sessions: Mapped[list[UserSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserSession(Base):
    """A logged-in session, addressed by the hash of an opaque token the
    browser holds in an httpOnly cookie — the raw token is never stored,
    only ever exists in that cookie. Named `UserSession`, not `Session`,
    so it never collides with `sqlalchemy.orm.Session` imported
    everywhere else in this codebase."""

    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # sha256 hex
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")
