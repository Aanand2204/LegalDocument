"""Registration, login, logout, and "who am I"."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_current_user, get_db
from app.database import repositories as repo
from app.governance import audit
from app.schemas.auth import LoginRequest, RegisterRequest, UserOut
from app.services import auth_service
from config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


def _issue_session(db: Session, response: Response, user_id: int) -> None:
    settings = get_settings()
    token = auth_service.generate_session_token()
    repo.create_session(
        db,
        user_id=user_id,
        token_hash=auth_service.hash_token(token),
        ttl_minutes=settings.session_inactivity_minutes,
    )
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
        path="/",  # no max_age: non-persistent cookie, cleared on browser close
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    if repo.get_user_by_email(db, body.email) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")

    user = repo.create_user(db, email=body.email, password_hash=auth_service.hash_password(body.password))
    _issue_session(db, response, user.id)
    audit.log_user_action(db, user=user.email, action="register", resource=f"user:{user.id}")
    return user


@router.post("/login", response_model=UserOut)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = repo.get_user_by_email(db, body.email)
    if user is None or not auth_service.verify_password(body.password, user.password_hash):
        logger.warning(
            "login failed for %s: %s", body.email, "no such account" if user is None else "wrong password"
        )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")

    repo.record_login(db, user)
    _issue_session(db, response, user.id)
    audit.log_user_action(db, user=user.email, action="login", resource=f"user:{user.id}")
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        repo.revoke_session(db, auth_service.hash_token(token))
    response.delete_cookie(settings.session_cookie_name, path="/")
    audit.log_user_action(db, user=current.email, action="logout", resource=f"user:{current.id}")


@router.get("/me", response_model=UserOut)
def me(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return repo.get_user(db, current.id)
