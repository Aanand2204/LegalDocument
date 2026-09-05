"""Shared test fixtures. Runs against the real DATABASE_URL, isolated by
wrapping each test in a transaction that's always rolled back."""
from __future__ import annotations

import os
import shutil
import tempfile
import uuid

os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("DOCUMENTS_DIR", tempfile.mkdtemp(prefix="legalguard_test_documents_"))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_db
from app.database.database import Base, engine
from app.database.models import User
from config import get_settings


def make_minimal_pdf(text: str) -> bytes:
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
    from main import app

    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


def login_as(client: TestClient, db_session, *, email: str | None = None) -> User:
    from app.database import repositories as repo
    from app.services import auth_service

    email = email or f"user-{uuid.uuid4().hex[:8]}@example.com"
    user = repo.create_user(db_session, email=email, password_hash=auth_service.hash_password("Testpass123!"))
    switch_to(client, db_session, user)
    return user


def switch_to(client: TestClient, db_session, user) -> None:
    from app.database import repositories as repo
    from app.services import auth_service

    token = auth_service.generate_session_token()
    repo.create_session(
        db_session, user_id=user.id, token_hash=auth_service.hash_token(token), ttl_minutes=60
    )
    client.cookies.set(get_settings().session_cookie_name, token)
