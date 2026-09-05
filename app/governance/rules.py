"""RULE-001..008 (plan section 11) as pure, independently testable functions.

Each rule takes plain data — never a database session or the LLM — and
returns a RuleResult. `governance/evaluator.py` aggregates them into one
GovernanceDecision. Keeping every rule a pure function is what makes the
governance test cases in plan section 40 ("AI tries to approve -> BLOCK",
etc.) testable without a running app.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from config import get_settings

_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_LONG_DIGIT_RUN_RE = re.compile(r"\b\d{13,19}\b")


@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    passed: bool
    detail: str


def rule_001_ai_cannot_approve(ai_attempted_decision: str | None) -> RuleResult:
    """RULE-001: AI cannot approve contracts.

    `ai_attempted_decision` should always be None in this codebase — no
    agent output includes a decision field. This rule is an explicit,
    testable guard against that ever changing silently.
    """
    if ai_attempted_decision is not None:
        return RuleResult("RULE-001", False, f"AI attempted decision {ai_attempted_decision!r}; blocked")
    return RuleResult("RULE-001", True, "AI made no approval/rejection attempt")


def rule_002_high_risk_requires_review(risk_scores: list[int]) -> RuleResult:
    """RULE-002: High-risk contracts require lawyer approval."""
    threshold = get_settings().risk_review_threshold
    offending = [s for s in risk_scores if s >= threshold]
    if offending:
        return RuleResult("RULE-002", False, f"{len(offending)} risk(s) scored >= {threshold}")
    return RuleResult("RULE-002", True, "no risk at or above the review threshold")


def rule_003_evidence_required(risks: list[dict]) -> RuleResult:
    """RULE-003: AI-generated risk must contain evidence (a non-empty reason)."""
    missing = [r for r in risks if not (r.get("reason") or "").strip()]
    if missing:
        return RuleResult("RULE-003", False, f"{len(missing)} risk(s) missing a reason/evidence")
    return RuleResult("RULE-003", True, "every risk has a reason")


def rule_004_audit_logged(audit_event_logged: bool) -> RuleResult:
    """RULE-004: Every AI decision must be logged."""
    if not audit_event_logged:
        return RuleResult("RULE-004", False, "no governance/audit event recorded for this run")
    return RuleResult("RULE-004", True, "governance event recorded")


def rule_005_low_confidence_requires_review(confidences: list[float]) -> RuleResult:
    """RULE-005: AI confidence below threshold requires manual review."""
    threshold = get_settings().confidence_review_threshold
    offending = [c for c in confidences if c < threshold]
    if offending:
        return RuleResult("RULE-005", False, f"{len(offending)} finding(s) below {threshold:.2f} confidence")
    return RuleResult("RULE-005", True, "all findings meet the confidence threshold")


def rule_006_no_document_mutation(original_hash: str, current_hash: str) -> RuleResult:
    """RULE-006: AI cannot modify original contracts (SHA-256 check, plan section 30)."""
    if original_hash != current_hash:
        return RuleResult("RULE-006", False, "document hash changed since upload")
    return RuleResult("RULE-006", True, "document hash unchanged")


def rule_007_no_sensitive_data_in_logs(log_text: str) -> RuleResult:
    """RULE-007: Sensitive information must not appear in logs.

    A lightweight heuristic guard (not a full PII/DLP scanner) that flags
    obvious sensitive-looking patterns — SSNs and long digit runs that
    look like account/card numbers — in text about to be logged.
    """
    if _SSN_RE.search(log_text) or _LONG_DIGIT_RUN_RE.search(log_text):
        return RuleResult("RULE-007", False, "log text appears to contain sensitive identifiers")
    return RuleResult("RULE-007", True, "no obvious sensitive identifiers detected")


def rule_008_model_version_present(model_name: str | None, model_version: str | None) -> RuleResult:
    """RULE-008: Every model execution must have a version."""
    if not model_name or not model_version:
        return RuleResult("RULE-008", False, "model execution missing name/version")
    return RuleResult("RULE-008", True, f"{model_name} {model_version}")
