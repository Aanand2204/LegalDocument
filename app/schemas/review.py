from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict

ReviewDecision = Literal["approved", "rejected", "request_changes"]


class ReviewCreateRequest(BaseModel):
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
