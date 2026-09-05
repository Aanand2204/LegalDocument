from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict


class ClauseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contract_id: int
    clause_type: str
    clause_text: str
    page_number: int | None
    confidence: float | None
    created_at: dt.datetime
