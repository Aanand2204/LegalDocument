"""Organizational policy definitions (plan section 10).

Kept as plain Python data for now — the plan's RAG architecture (section
15, Azure AI Search) is deferred (see the implementation plan's
"Explicitly deferred" list). This module is the seam: a retrieval-backed
policy store would still resolve to the same `Policy` shape the
Compliance Agent consumes, so swapping it in later doesn't touch the
agent.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Policy:
    policy_id: str
    name: str
    applies_to: tuple[str, ...]  # contract_type values this policy governs
    required_clause_types: tuple[str, ...]


# POLICY-001 (plan section 10). The plan's example requirement "Liability
# Cap" is represented here as "Liability" — clause extraction currently
# detects clause *presence*, not whether liability is capped vs
# unlimited (that distinction is a Risk Agent finding; see
# agents/risk_agent.py's "unlimited liability" signal). Tightening this
# to a true liability-cap check is a documented follow-up, not a bug.
VENDOR_CONTRACT_POLICY = Policy(
    policy_id="POLICY-001",
    name="Vendor Contract Baseline",
    applies_to=("Vendor Agreement", "Service Agreement"),
    required_clause_types=(
        "Data Protection",
        "Confidentiality",
        "Liability",
        "Termination",
        "Governing Law",
    ),
)

DEFAULT_POLICY = Policy(
    policy_id="POLICY-000",
    name="General Baseline",
    applies_to=(),
    required_clause_types=("Confidentiality", "Termination", "Governing Law"),
)

_POLICIES: tuple[Policy, ...] = (VENDOR_CONTRACT_POLICY, DEFAULT_POLICY)


def policy_for_contract_type(contract_type: str | None) -> Policy:
    """Return the most specific policy that applies to `contract_type`, else the default."""
    for policy in _POLICIES:
        if contract_type in policy.applies_to:
            return policy
    return DEFAULT_POLICY
