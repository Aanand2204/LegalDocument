"""Deadline monitoring — the 90/30/7-day sweep behind POST /deadlines/check."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.database import repositories as repo
from app.database.models import Contract, Deadline
from app.services import notification_service

_WINDOWS: tuple[tuple[int, str], ...] = (
    (7, "notified_7"),
    (30, "notified_30"),
    (90, "notified_90"),
)
_STATUS_ORDER = ("upcoming", "notified_90", "notified_30", "notified_7", "passed")


@dataclass(frozen=True)
class DeadlineCheckResult:
    deadline: Deadline
    contract: Contract
    days_remaining: int
    window: str


def _window_for(days_remaining: int) -> str | None:
    for max_days, label in _WINDOWS:
        if days_remaining <= max_days:
            return label
    return None


def check_deadlines(
    db: Session, *, today: dt.date | None = None, contract_ids: set[int] | None = None
) -> list[DeadlineCheckResult]:
    today = today or dt.date.today()
    results: list[DeadlineCheckResult] = []

    for deadline in repo.list_deadlines(db, contract_ids=contract_ids):
        if deadline.status == "passed":
            continue

        days_remaining = (deadline.deadline_date - today).days
        if days_remaining < 0:
            repo.update_deadline_status(db, deadline, "passed")
            continue

        window = _window_for(days_remaining)
        if window is None:
            continue

        already_at_or_past = _STATUS_ORDER.index(deadline.status) >= _STATUS_ORDER.index(window)
        if not already_at_or_past:
            repo.update_deadline_status(db, deadline, window)
            notification_service.notify_deadline_approaching(
                contract=deadline.contract, deadline=deadline, days_remaining=days_remaining
            )

        results.append(
            DeadlineCheckResult(
                deadline=deadline,
                contract=deadline.contract,
                days_remaining=days_remaining,
                window=window,
            )
        )

    return results
