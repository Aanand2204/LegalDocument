"""Notification stub — logs what would be sent instead of delivering it."""
from __future__ import annotations

import logging

from app.database.models import Contract, Deadline

logger = logging.getLogger("legalguard.notifications")


def notify_deadline_approaching(*, contract: Contract, deadline: Deadline, days_remaining: int) -> None:
    logger.info(
        "NOTIFICATION (would send email): contract=%s (%s) deadline_type=%s date=%s days_remaining=%s",
        contract.contract_number,
        contract.filename,
        deadline.deadline_type,
        deadline.deadline_date,
        days_remaining,
    )


def notify_human_review_required(*, contract: Contract, risk_count: int) -> None:
    logger.info(
        "NOTIFICATION (would send email): contract=%s requires lawyer review (%s risk(s) flagged)",
        contract.contract_number,
        risk_count,
    )
