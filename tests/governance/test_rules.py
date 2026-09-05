"""Unit tests for governance/rules.py and governance/evaluator.py.

Covers plan section 40's required governance test cases: high risk ->
human review; low confidence -> human review; AI tries to approve ->
BLOCK; missing evidence -> BLOCK; missing audit event -> BLOCK.
"""
from __future__ import annotations

from app.governance import rules
from app.governance.evaluator import evaluate


def _risk(reason="unlimited liability found", score=20, confidence=0.9):
    return {"reason": reason, "score": score, "confidence": confidence}


def test_high_risk_requires_human_review():
    decision = evaluate(risk_scores=[75], confidences=[0.9], risks=[_risk(score=75)], audit_event_logged=True)
    assert decision.requires_human_review is True
    assert decision.blocked is False


def test_low_confidence_requires_human_review():
    decision = evaluate(
        risk_scores=[10], confidences=[0.4], risks=[_risk(score=10, confidence=0.4)], audit_event_logged=True
    )
    assert decision.requires_human_review is True
    assert decision.blocked is False


def test_ai_attempting_approval_is_blocked():
    decision = evaluate(
        risk_scores=[10],
        confidences=[0.9],
        risks=[_risk()],
        audit_event_logged=True,
        ai_attempted_decision="approved",
    )
    assert decision.blocked is True
    assert decision.requires_human_review is True


def test_missing_evidence_is_blocked():
    decision = evaluate(
        risk_scores=[10],
        confidences=[0.9],
        risks=[{"reason": "", "score": 10, "confidence": 0.9}],
        audit_event_logged=True,
    )
    assert decision.blocked is True


def test_missing_audit_event_is_blocked():
    decision = evaluate(risk_scores=[10], confidences=[0.9], risks=[_risk()], audit_event_logged=False)
    assert decision.blocked is True


def test_low_risk_high_confidence_needs_no_review():
    decision = evaluate(risk_scores=[10], confidences=[0.9], risks=[_risk()], audit_event_logged=True)
    assert decision.requires_human_review is False
    assert decision.blocked is False


def test_rule_006_flags_changed_document_hash():
    assert rules.rule_006_no_document_mutation("abc", "abc").passed is True
    assert rules.rule_006_no_document_mutation("abc", "xyz").passed is False


def test_rule_007_flags_ssn_like_pattern():
    assert rules.rule_007_no_sensitive_data_in_logs("nothing sensitive here").passed is True
    assert rules.rule_007_no_sensitive_data_in_logs("SSN on file: 123-45-6789").passed is False


def test_rule_008_requires_model_version():
    assert rules.rule_008_model_version_present("mock", None).passed is False
    assert rules.rule_008_model_version_present(None, "1.0").passed is False
    assert rules.rule_008_model_version_present("mock", "1.0").passed is True


def test_evaluate_blocks_on_tampered_document_hash():
    decision = evaluate(
        risk_scores=[10],
        confidences=[0.9],
        risks=[_risk()],
        audit_event_logged=True,
        original_document_hash="abc",
        current_document_hash="xyz",
    )
    assert decision.blocked is True


def test_evaluate_blocks_on_missing_model_version():
    decision = evaluate(
        risk_scores=[10],
        confidences=[0.9],
        risks=[_risk()],
        audit_event_logged=True,
        model_name="mock",
        model_version=None,
    )
    assert decision.blocked is True


def test_evaluate_requires_review_but_does_not_block_on_sensitive_log_text():
    decision = evaluate(
        risk_scores=[10],
        confidences=[0.9],
        risks=[_risk()],
        audit_event_logged=True,
        log_text="SSN on file: 123-45-6789",
    )
    assert decision.blocked is False
    assert decision.requires_human_review is True
