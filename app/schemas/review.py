from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict

ReviewDecision = Literal["approved", "rejected", "request_changes"]


class ReviewCreateRequest(BaseModel):
    """No `lawyer_id` field — that identity now comes from the
    authenticated session (see api/reviews.py), not a client-supplied
    string nobody verified."""

    decision: ReviewDecision
    comments: str | None = None


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contract_id: int
    lawyer_id: str
    decision: str
    comments: str | None
    reviewed_at: dt.datetime
