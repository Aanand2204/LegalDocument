"""Deadline Agent — extracts dates and notice periods for deadline_service."""
from __future__ import annotations

from app.agents.base import run_contract_agent

INSTRUCTIONS = """You are the LegalGuard Deadline Agent.

Extract every date-driven obligation from the contract text: effective
date, expiration date, renewal date, termination notice period, payment
deadlines, review dates, insurance renewal, compliance deadlines. Where a
notice period is stated (e.g. "90 days"), compute the corresponding
deadline_type "termination_notice" date as (expiry date - notice period).

Respond with a single JSON object only:
{"deadlines": [{"deadline_type": str, "date": str, "notice_period_days": int|null}]}
Dates must be ISO 8601 (YYYY-MM-DD).
"""


async def run_deadline_extraction(contract_text: str) -> dict:
    return await run_contract_agent(INSTRUCTIONS, contract_text)
