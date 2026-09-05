"""Writes GovernanceEvent + AuditLog rows.

Called by every agent stage in the workflow (workflows/contract_review.py)
and by the review/decision API endpoints — this is the single place that
touches the audit tables, so RULE-004 ("every AI decision must be
logged") has one implementation to verify rather than one per caller.
"""
from __future__ import annotations

import hashlib
import json
import logging

from sqlalchemy.orm import Session

from app.database import repositories as repo
from app.governance.evaluator import GovernanceDecision

logger = logging.getLogger(__name__)


def _hash(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def log_agent_run(
    db: Session,
    *,
    contract_id: int,
    agent_name: str,
    model_name: str,
    model_version: str,
    input_data: object,
    output_data: object,
) -> None:
    logger.info("agent run: %s on contract %d (%s %s)", agent_name, contract_id, model_name, model_version)
    repo.log_governance_event(
        db,
        contract_id=contract_id,
        event_type="agent_run",
        agent_name=agent_name,
        model_name=model_name,
        model_version=model_version,
        input_hash=_hash(input_data),
        output_hash=_hash(output_data),
    )


def log_governance_decision(db: Session, *, contract_id: int, decision: GovernanceDecision) -> None:
    logger.info(
        "governance decision on contract %d: blocked=%s requires_human_review=%s%s",
        contract_id,
        decision.blocked,
        decision.requires_human_review,
        f" violations={decision.violations}" if decision.violations else "",
    )
    repo.log_governance_event(
        db,
        contract_id=contract_id,
        event_type="governance_decision",
        agent_name="governance",
        model_name=None,
        model_version=None,
        input_hash=None,
        output_hash=_hash([r.__dict__ for r in decision.results]),
    )


def log_user_action(
    db: Session, *, user: str, action: str, resource: str, details: dict | None = None
) -> None:
    logger.info("user action: %s by %s on %s", action, user, resource)
    repo.log_audit(
        db,
        user=user,
        action=action,
        resource=resource,
        details=json.dumps(details) if details is not None else None,
    )
