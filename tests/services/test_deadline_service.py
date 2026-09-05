"""Tests for services/deadline_service.py."""
from __future__ import annotations

import datetime as dt

from app.database import repositories as repo
from app.services.deadline_service import check_deadlines


def _make_contract(db_session):
    return repo.create_contract(
        db_session,
        filename="sample.pdf",
        document_path="/tmp/sample.pdf",
        document_hash="hash",
        status="analyzed",
    )


def test_deadline_within_30_days_triggers_notification(db_session, monkeypatch):
    notified = []
    monkeypatch.setattr(
        "app.services.deadline_service.notification_service.notify_deadline_approaching",
        lambda **kwargs: notified.append(kwargs),
    )

    contract = _make_contract(db_session)
    today = dt.date(2026, 1, 1)
    repo.add_deadlines(
        db_session,
        contract.id,
        [{"deadline_type": "renewal_date", "deadline_date": today + dt.timedelta(days=20)}],
    )

    results = check_deadlines(db_session, today=today)

    assert len(results) == 1
    assert results[0].window == "notified_30"
    assert len(notified) == 1


def test_deadline_not_renotified_once_already_at_window(db_session, monkeypatch):
    notified = []
    monkeypatch.setattr(
        "app.services.deadline_service.notification_service.notify_deadline_approaching",
        lambda **kwargs: notified.append(kwargs),
    )

    contract = _make_contract(db_session)
    today = dt.date(2026, 1, 1)
    [deadline] = repo.add_deadlines(
        db_session,
        contract.id,
        [{"deadline_type": "renewal_date", "deadline_date": today + dt.timedelta(days=5)}],
    )
    repo.update_deadline_status(db_session, deadline, "notified_7")

    results = check_deadlines(db_session, today=today)

    assert len(results) == 1
    assert len(notified) == 0


def test_past_deadline_marked_passed_and_not_alerted(db_session):
    contract = _make_contract(db_session)
    today = dt.date(2026, 1, 1)
    repo.add_deadlines(
        db_session,
        contract.id,
        [{"deadline_type": "expiry_date", "deadline_date": today - dt.timedelta(days=1)}],
    )

    results = check_deadlines(db_session, today=today)

    assert results == []
    [deadline] = repo.list_deadlines(db_session, contract.id)
    assert deadline.status == "passed"


def test_deadline_beyond_90_days_produces_no_alert(db_session):
    contract = _make_contract(db_session)
    today = dt.date(2026, 1, 1)
    repo.add_deadlines(
        db_session,
        contract.id,
        [{"deadline_type": "expiry_date", "deadline_date": today + dt.timedelta(days=200)}],
    )

    assert check_deadlines(db_session, today=today) == []
