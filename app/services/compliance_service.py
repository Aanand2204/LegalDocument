"""Compliance scoring, shared by the analysis workflow and the on-demand
GET /contracts/{id}/compliance endpoint."""
from __future__ import annotations

from app.agents.compliance_agent import run_compliance_check
from app.database.models import Contract
from app.governance.policies import Policy, policy_for_contract_type


async def compute_compliance(contract: Contract, found_clause_types: list[str]) -> tuple[Policy, dict]:
    policy = policy_for_contract_type(contract.contract_type)
    result = await run_compliance_check(found_clause_types, list(policy.required_clause_types))
    return policy, result
