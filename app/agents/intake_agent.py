"""Intake Agent — identifies contract type, parties, and effective date."""
from __future__ import annotations

from app.agents.base import run_contract_agent

INSTRUCTIONS = """You are the LegalGuard Intake Agent.

Read the contract text and identify:
- contract_type (e.g. "Vendor Agreement", "NDA", "Employment Contract")
- parties (list of party names)
- effective_date (ISO 8601 date, or null if not stated)

Respond with a single JSON object only:
{"contract_type": str, "parties": [str, ...], "effective_date": str|null}
"""


async def run_intake(contract_text: str) -> dict:
    return await run_contract_agent(INSTRUCTIONS, contract_text)
