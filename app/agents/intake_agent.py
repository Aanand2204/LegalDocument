"""Agent 1 — Document Intake Agent (plan section 5).

Identifies contract type, parties, and the effective date from the raw
extracted document text. Page counting and file-level metadata come
directly from services/document_service.py (no LLM needed for that), so
this agent's job is exactly the natural-language part.
"""
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
