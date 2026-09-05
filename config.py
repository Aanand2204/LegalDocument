"""Application configuration."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "LegalGuard AI"

    database_url: str = "sqlite:///./legalguard.db"

    llm_provider: str = "mock"

    documents_dir: str = "./documents"

    risk_review_threshold: int = 61
    confidence_review_threshold: float = 0.75

    # No signing secret: sessions are opaque tokens, not JWTs. The cookie
    # has no Max-Age (cleared on browser close); session_inactivity_minutes
    # is a sliding server-side deadline pushed forward on each request.
    session_cookie_name: str = "legalguard_session"
    session_inactivity_minutes: int = 180
    session_cookie_secure: bool = False

    log_level: str = "INFO"

    @property
    def documents_path(self) -> Path:
        path = Path(self.documents_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
