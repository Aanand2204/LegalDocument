"""Application-wide logging setup.

Separate from (not a replacement for) the permanent, DB-backed
compliance trail in `app/governance/audit.py` (GovernanceEvent /
AuditLog) — this is a real-time, human-readable operational trace of
what the app is doing, for monitoring/debugging, not for governance
evidence. Configured once, at process startup (see main.py); every
module logs via the standard `logging.getLogger(__name__)` pattern.
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import get_settings

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_MAX_BYTES = 5 * 1024 * 1024
_BACKUP_COUNT = 3

_configured = False


def configure_logging() -> None:
    global _configured
    if _configured:
        return  # guards our own re-entry; other libraries (pytest's log
        # capture, uvicorn's own loggers) may already hold root handlers
        # of their own, so presence-checking `root.handlers` isn't safe.
    _configured = True

    settings = get_settings()
    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())
    formatter = logging.Formatter(_LOG_FORMAT)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_dir / "app.log", maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # `uvicorn --reload`'s file watcher logs "N changes detected" for
    # every raw filesystem event in the project tree *before* deciding
    # whether to actually reload — including our own logs/app.log
    # growing on every request, which would otherwise re-log itself
    # forever. Pure dev-tooling chatter, irrelevant to monitoring the
    # app itself, so it's turned down rather than routed to our handlers.
    logging.getLogger("watchfiles").setLevel(logging.WARNING)
