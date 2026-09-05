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
    reason: str | None = None
