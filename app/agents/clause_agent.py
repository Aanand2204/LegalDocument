"""Clause Extraction Agent — identifies standard clause types with their
source text so a lawyer can trace a finding back to the wording."""
from __future__ import annotations

from app.agents.base import run_contract_agent

INSTRUCTIONS = """You are the LegalGuard Clause Extraction Agent.

Identify clauses in the contract text from this list: Payment Terms,
Termination, Renewal, Liability, Indemnification, Confidentiality, Data
Protection, Intellectual Property, Non-compete, Non-solicitation,
Governing Law, Dispute Resolution, Insurance, Audit Rights, Force Majeure.

For each clause found, include the source text so it can be traced back
to the original contract.

Respond with a single JSON object only:
{"clauses": [{"clause_type": str, "text": str, "page_number": int|null, "confidence": float}]}
"""


async def run_clause_extraction(contract_text: str) -> dict:
    return await run_contract_agent(INSTRUCTIONS, contract_text)
