"""Application configuration.

All settings are environment-driven (see .env.example) with safe,
zero-cost local defaults: SQLite database, mock LLM provider, local
filesystem document storage. Read via `get_settings()` everywhere else
in the codebase rather than instantiating `Settings` directly, so the
whole app shares one (cached) instance.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "LegalGuard AI"

    database_url: str = "sqlite:///./legalguard.db"

    # See llm/client.py for the provider seam. Only "mock" is implemented.
    llm_provider: str = "mock"

    documents_dir: str = "./documents"

    # Governance thresholds — see governance/rules.py RULE-002 / RULE-005.
    # Risk scale per the implementation plan: 0-30 LOW, 31-60 MEDIUM,
    # 61-80 HIGH, 81-100 CRITICAL. HIGH and above requires human review.
    risk_review_threshold: int = 61
    confidence_review_threshold: float = 0.75

    # Session cookies (see services/auth_service.py, api/auth.py). No
    # signing secret to configure — sessions are opaque tokens looked up
    # in the database, not JWTs, by design (see the auth plan's "Session
    # model" note). session_cookie_secure should be true in any real
    # deployment behind HTTPS; false here so local http://localhost dev
    # still gets the cookie set.
    #
    # The cookie itself carries no Max-Age (see api/auth.py::_issue_session)
    # so it's a non-persistent "session cookie" — browsers clear it when
    # the browser itself closes. Server-side, UserSession.expires_at is a
    # sliding inactivity deadline, not a fixed lifetime: every
    # authenticated request pushes it forward by session_inactivity_minutes
    # (see api/deps.py::get_current_user, repositories.py::touch_session);
    # go quiet for that long and the next request's session lookup fails
    # on its own, no separate "idle" check needed.
    session_cookie_name: str = "legalguard_session"
    session_inactivity_minutes: int = 180
    session_cookie_secure: bool = False

    # See app/logging_config.py::configure_logging.
    log_level: str = "INFO"

    @property
    def documents_path(self) -> Path:
        path = Path(self.documents_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
