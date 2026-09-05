"""Organizational policy definitions, kept as plain Python data."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Policy:
    policy_id: str
    name: str
    applies_to: tuple[str, ...]
    required_clause_types: tuple[str, ...]


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
    for policy in _POLICIES:
        if contract_type in policy.applies_to:
            return policy
    return DEFAULT_POLICY
