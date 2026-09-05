"""Compliance Agent (plan section 10).

Checks the contract's already-extracted clauses against an
organizational policy checklist (see governance/policies.py) and reports
pass/fail per requirement plus an overall compliance score.
"""
from __future__ import annotations

from app.agents.base import build_agent, run_agent_json

INSTRUCTIONS = """You are the LegalGuard Compliance Agent.

You are given the clause types already found in the contract
(CLAUSES_FOUND) and the clause types a policy requires (REQUIRED_CLAUSES).
For each required clause, decide whether it is satisfied.

Respond with a single JSON object only:
{"results": [{"requirement": str, "satisfied": bool}], "violations": [str], "score": float}
score is the percentage of requirements satisfied (0-100).
"""


async def run_compliance_check(
    found_clause_types: list[str], required_clause_types: list[str]
) -> dict:
    agent = build_agent(INSTRUCTIONS)
    prompt = (
        f"CLAUSES_FOUND: {', '.join(found_clause_types)}\n"
        f"REQUIRED_CLAUSES: {', '.join(required_clause_types)}"
    )
    return await run_agent_json(agent, prompt)
