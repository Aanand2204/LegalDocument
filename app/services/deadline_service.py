"""Deadline monitoring (plan section 27).

`check_deadlines` is the logic a scheduled job would call every morning;
this slice exposes it via a plain function reachable from an API endpoint
(`POST /deadlines/check`) instead of wrapping it in an Azure Function —
see the implementation plan's "Explicitly deferred" list. The scheduling
*mechanism* is what's deferred; this is the real check logic.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.database import repositories as repo
from app.database.models import Contract, Deadline
from app.services import notification_service

# (max_days_remaining, status_label), closest-due window first.
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
    """Find deadlines due within 90/30/7 days, notify, and advance their status.

    Idempotent: a deadline already at (or past) a given window's status
    is not re-notified for that window on a later call. `contract_ids`
    restricts the sweep to those contracts — the API route uses this to
    scope the check to the caller's own contracts (see app/api/deadlines.py).
    """
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
