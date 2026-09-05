"""Registration, login, logout, and session-protected access."""
from __future__ import annotations

import uuid


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


def _register(client, *, email=None, password="supersecret1"):
    return client.post("/auth/register", json={"email": email or _email("user"), "password": password})


def test_registration_creates_and_logs_in_the_account(client):
    email = _email("new")
    response = _register(client, email=email)

    assert response.status_code == 201
    assert response.json()["email"] == email
    assert client.get("/auth/me").status_code == 200


def test_duplicate_email_registration_rejected(client):
    email = _email("dup")
    assert _register(client, email=email).status_code == 201
    second = _register(client, email=email, password="differentpassword")
    assert second.status_code == 409


def test_registration_rejects_short_password(client):
    response = client.post("/auth/register", json={"email": _email("short"), "password": "short"})
    assert response.status_code == 422


def test_registration_rejects_invalid_email(client):
    response = client.post("/auth/register", json={"email": "not-an-email", "password": "supersecret1"})
    assert response.status_code == 422


def test_login_with_wrong_password_rejected(client):
    email = _email("wrongpw")
    _register(client, email=email, password="correcthorsebattery")
    client.post("/auth/logout")

    response = client.post("/auth/login", json={"email": email, "password": "wrongpassword"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_with_unknown_email_gets_same_generic_message(client):
    response = client.post("/auth/login", json={"email": _email("unknown"), "password": "whatever123"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_succeeds_with_correct_credentials(client):
    email = _email("correct")
    _register(client, email=email, password="correcthorsebattery")
    client.post("/auth/logout")

    response = client.post("/auth/login", json={"email": email, "password": "correcthorsebattery"})

    assert response.status_code == 200
    assert response.json()["email"] == email


def test_me_reflects_logged_in_user(client):
    email = _email("me")
    registered = _register(client, email=email).json()

    me = client.get("/auth/me")

    assert me.status_code == 200
    assert me.json() == registered


def test_me_without_a_session_cookie_is_401(client):
    assert client.get("/auth/me").status_code == 401


def test_logout_invalidates_the_session(client):
    email = _email("logout")
    _register(client, email=email)
    assert client.get("/auth/me").status_code == 200

    assert client.post("/auth/logout").status_code == 204
    assert client.get("/auth/me").status_code == 401


def test_protected_endpoint_rejects_no_cookie_at_all(client):
    assert client.get("/contracts").status_code == 401
