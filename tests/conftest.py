"""Shared test fixtures.

LLM_PROVIDER is pinned to "mock" before any app module is imported, so
every test runs fully offline as far as the LLM goes. The database is
NOT mocked or swapped for a local file, though — per the Aiven-Postgres
plan, tests run against the exact same database the app itself uses
(`settings.database_url`). Isolation instead comes from wrapping every
test in an outer transaction that's always rolled back at the end
(SQLAlchemy's documented external-transaction pattern,
`join_transaction_mode="create_savepoint"`): application code's own
`session.commit()` calls (throughout app/database/repositories.py) only
commit to a SAVEPOINT under that outer transaction, so the rollback
undoes everything regardless of what got "committed" along the way.
This means every test run needs network access to Aiven.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import uuid

os.environ.setdefault("LLM_PROVIDER", "mock")
# Uploaded-file writes (app/api/contracts.py::upload_contract) land on
# real disk regardless of the DB-transaction rollback below — without
# this, every test run permanently orphans a file under the real
# documents/ dir. Redirect it to a throwaway temp dir instead, removed
# by _cleanup_test_documents_dir once the whole suite finishes.
os.environ.setdefault("DOCUMENTS_DIR", tempfile.mkdtemp(prefix="legalguard_test_documents_"))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_db
from app.database.database import Base, engine
from app.database.models import User
from config import get_settings


def make_minimal_pdf(text: str) -> bytes:
    """Build a tiny valid one-page PDF containing `text`, for tests that
    exercise real PDF parsing without adding a heavyweight PDF-writing
    dependency just for fixtures."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
        b"/MediaBox [0 0 612 792] /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    stream = f"BT /F1 24 Tf 72 700 Td ({text}) Tj ET".encode()
    objects.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"

    xref_start = len(out)
    n = len(objects) + 1
    out += f"xref\n0 {n}\n".encode() + b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode()
    out += b"trailer\n" + f"<< /Size {n} /Root 1 0 R >>\n".encode()
    out += b"startxref\n" + f"{xref_start}\n".encode() + b"%%EOF"
    return bytes(out)


@pytest.fixture(scope="session", autouse=True)
def _tables_exist():
    """Runs once per test session: creates any tables that don't already
    exist on the real database. Autouse so a test file that never spins
    up the FastAPI app (and so never runs its `lifespan`/`init_db()`)
    still has a schema to work with."""
    Base.metadata.create_all(bind=engine)


@pytest.fixture(scope="session", autouse=True)
def _cleanup_test_documents_dir():
    yield
    shutil.rmtree(get_settings().documents_dir, ignore_errors=True)


@pytest.fixture()
def db_session():
    connection = engine.connect()
    outer_transaction = connection.begin()
    test_session_local = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")
    session = test_session_local()
    try:
        yield session
    finally:
        session.close()
        outer_transaction.rollback()
        connection.close()


@pytest.fixture()
def client(db_session) -> TestClient:
    """A TestClient whose every request is served through `db_session`'s
    connection — so a user/contract/etc. seeded directly via `db_session`
    in a test is visible to the API calls that test makes, and it all
    rolls back together when the test ends."""
    from main import app

    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


def login_as(client: TestClient, db_session, *, email: str | None = None) -> User:
    """Test-only helper: seed a user directly and authenticate `client`
    as them via a real session row — the same session mechanism
    api/auth.py's own login issues, just skipping the HTTP round trip and
    password hashing/checking (tests that need to exercise login itself
    go through the real /auth/login endpoint instead — see test_auth.py).
    """
    from app.database import repositories as repo
    from app.services import auth_service

    # example.com is RFC 2606-reserved for documentation/testing —
    # unlike .local/.test/.invalid it passes email-validator's
    # special-use-domain check, which real login/register emails go
    # through too (see app/schemas/auth.py).
    email = email or f"user-{uuid.uuid4().hex[:8]}@example.com"
    user = repo.create_user(db_session, email=email, password_hash=auth_service.hash_password("Testpass123!"))
    switch_to(client, db_session, user)
    return user


def switch_to(client: TestClient, db_session, user) -> None:
    """Re-authenticate `client` as an *already-created* user (e.g. one a
    prior `login_as` call returned) — a fresh session, no new user row.
    Calling `login_as` again with that user's email would violate the
    `users.email` unique constraint, since it always creates a new user."""
    from app.database import repositories as repo
    from app.services import auth_service

    token = auth_service.generate_session_token()
    repo.create_session(
        db_session, user_id=user.id, token_hash=auth_service.hash_token(token), ttl_minutes=60
    )
    client.cookies.set(get_settings().session_cookie_name, token)
