"""Console + rotating-file logging, separate from the DB-backed audit trail
in app/governance/audit.py."""
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
        return
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

    # Quiet uvicorn's reload-watcher chatter (it logs every fs event,
    # including our own log file growing).
    logging.getLogger("watchfiles").setLevel(logging.WARNING)
