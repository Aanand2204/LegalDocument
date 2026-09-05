# POLICY-001 — Vendor Contract Baseline

**Applies to:** Vendor Agreement, Service Agreement

All vendor and service contracts must contain:

- ✓ Data Protection clause
- ✓ Confidentiality clause
- ✓ Liability terms (with a cap — see note below)
- ✓ Termination clause
- ✓ Governing Law clause

A contract missing any of the above fails compliance and the missing
item(s) are reported as violations (plan section 10).

## Note on "Liability Cap"

The Compliance Agent currently checks for the *presence* of a Liability
clause, not specifically whether it caps liability — clause extraction
detects clause types, not clause terms. Whether liability is capped or
unlimited is instead surfaced by the Risk Agent (an "unlimited liability"
finding is scored CRITICAL — see `agents/risk_agent.py`). This is a
documented simplification for this implementation slice, not a policy
change: enforcing the cap itself compliance-side is a natural next step
once clause extraction can classify clause *terms*, not just presence.

## Machine-readable form

This policy's `required_clause_types` list is defined in
[`app/governance/policies.py`](../app/governance/policies.py) as
`VENDOR_CONTRACT_POLICY` — that module, not this file, is what the
Compliance Agent actually reads. This document exists so the policy is
also reviewable by a lawyer/compliance officer in plain language, per
the plan's "Company Policy Documents" input to the (currently deferred)
RAG pipeline (plan section 15).
