from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict


class RiskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contract_id: int
    clause_id: int | None
    risk_type: str
    risk_score: int
    risk_level: str
    reason: str
    recommendation: str
    confidence: float
    requires_human_review: bool
    human_decision: str | None
    human_reason: str | None
    reviewed_by: str | None
    reviewed_at: dt.datetime | None


class RiskDecisionRequest(BaseModel):
    """Body for POST /risks/{id}/approve and /risks/{id}/reject.

    "approve" records the lawyer confirming the AI's risk finding stands;
    "reject" records the lawyer overriding it as not applicable — the
    plan section 24 example ("AI: HIGH RISK" / "Human: ACCEPTABLE,
    covered by master agreement"). human_decision is CONFIRMED or
    OVERRIDDEN respectively, never the AI's own risk_level. No
    `reviewed_by` field — that identity now comes from the authenticated
    session (see api/reviews.py), not a client-supplied string nobody
    verified.
    """

    reason: str | None = None
