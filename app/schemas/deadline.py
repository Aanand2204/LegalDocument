from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict


class DeadlineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contract_id: int
    deadline_type: str
    deadline_date: dt.date
    notice_period_days: int | None
    status: str


class DeadlineAlert(BaseModel):
    """One entry in a deadline-check run (plan section 27/28)."""

    contract_id: int
    contract_number: str
    deadline_id: int
    deadline_type: str
    deadline_date: dt.date
    days_remaining: int
    window: Literal["90_day", "30_day", "7_day"]
