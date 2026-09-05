"""Aggregates governance/rules.py into one decision per analysis run."""
from __future__ import annotations

from dataclasses import dataclass

from app.governance.rules import (
    RuleResult,
    rule_001_ai_cannot_approve,
    rule_002_high_risk_requires_review,
    rule_003_evidence_required,
    rule_004_audit_logged,
    rule_005_low_confidence_requires_review,
    rule_006_no_document_mutation,
    rule_007_no_sensitive_data_in_logs,
    rule_008_model_version_present,
)


@dataclass(frozen=True)
class GovernanceDecision:
    requires_human_review: bool
    blocked: bool
    results: tuple[RuleResult, ...]

    @property
    def violations(self) -> list[str]:
        return [r.detail for r in self.results if not r.passed]


def evaluate(
    *,
    risk_scores: list[int],
    confidences: list[float],
    risks: list[dict],
    audit_event_logged: bool,
    ai_attempted_decision: str | None = None,
    original_document_hash: str | None = None,
    current_document_hash: str | None = None,
    log_text: str = "",
    model_name: str | None = None,
    model_version: str | None = None,
) -> GovernanceDecision:
    # A caller that doesn't supply hash/model info gets a trivial pass.
    document_unmutated = (
        rule_006_no_document_mutation(original_document_hash, current_document_hash)
        if original_document_hash is not None and current_document_hash is not None
        else RuleResult("RULE-006", True, "document hash not supplied for this run")
    )
    model_version_present = (
        rule_008_model_version_present(model_name, model_version)
        if model_name is not None or model_version is not None
        else RuleResult("RULE-008", True, "model identity not supplied for this run")
    )

    results = (
        rule_001_ai_cannot_approve(ai_attempted_decision),
        rule_002_high_risk_requires_review(risk_scores),
        rule_003_evidence_required(risks),
        rule_004_audit_logged(audit_event_logged),
        rule_005_low_confidence_requires_review(confidences),
        document_unmutated,
        rule_007_no_sensitive_data_in_logs(log_text),
        model_version_present,
    )

    # 001/003/004/006/008 are hard blocks; 002/005/007 route to review.
    blocked = (
        not results[0].passed
        or not results[2].passed
        or not results[3].passed
        or not results[5].passed
        or not results[7].passed
    )
    requires_human_review = blocked or not results[1].passed or not results[4].passed or not results[6].passed

    return GovernanceDecision(
        requires_human_review=requires_human_review, blocked=blocked, results=results
    )
