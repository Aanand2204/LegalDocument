"""Risk Analysis Agent (plan sections 7-8).

Evaluates extracted clauses for risk and returns a *recommendation*
only — per the plan's core principle ("AI recommends, lawyer decides"),
nothing here or in its output ever marks a contract approved or
rejected. That authority is structurally reserved to governance/human
review endpoints (see governance/evaluator.py, api/reviews.py).
"""
from __future__ import annotations

from app.agents.base import run_contract_agent

INSTRUCTIONS = """You are the LegalGuard Risk Analysis Agent.

Evaluate the contract's clauses for legal/business risk. For each risk
found, give: which clause it relates to, a severity (LOW, MEDIUM, HIGH,
or CRITICAL), a 0-100 score consistent with that severity band (LOW
0-30, MEDIUM 31-60, HIGH 61-80, CRITICAL 81-100), a reason grounded in
the contract text (never a bare conclusion), a recommendation for the
lawyer, and your confidence (0-1).

You must never recommend approving or rejecting the contract — only
describe the risk. That decision belongs to the reviewing lawyer.

Respond with a single JSON object only:
{"risks": [{"risk_type": str, "clause_type": str|null, "severity": str,
"score": int, "reason": str, "recommendation": str, "confidence": float}]}
"""

# (score_ceiling, level) bands per the plan's risk scale (section 8).
_LEVEL_BANDS: tuple[tuple[int, str], ...] = (
    (30, "LOW"),
    (60, "MEDIUM"),
    (80, "HIGH"),
    (100, "CRITICAL"),
)


def classify_risk_level(score: int) -> str:
    """Map a 0-100 risk score to LOW/MEDIUM/HIGH/CRITICAL per the plan's scale."""
    for ceiling, level in _LEVEL_BANDS:
        if score <= ceiling:
            return level
    return "CRITICAL"


async def run_risk_analysis(contract_text: str) -> dict:
    return await run_contract_agent(INSTRUCTIONS, contract_text)
