"""SQLAlchemy engine/session setup.

SQLite by default (see config.py); DATABASE_URL swaps to Postgres later
with no code changes elsewhere, since every other module only imports
`Base`, `get_db`, or `SessionLocal` from here.
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine():
    settings = get_settings()
    connect_args = {}
    if settings.database_url.startswith("sqlite"):
        # Needed because FastAPI can hand the same connection to different
        # threads within one request lifecycle.
        connect_args["check_same_thread"] = False
    return create_engine(settings.database_url, connect_args=connect_args)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    """Create all tables that don't exist yet.

    A plain create-all is enough for this stage (no alembic migrations
    yet — see the implementation plan's deferred-scope list).
    """
    from app.database import models  # noqa: F401  (registers models on Base.metadata)

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a session, always closed after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
