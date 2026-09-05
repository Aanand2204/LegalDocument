"""Each agent run against the mock chat client — no network, no API key.

Asserts the structured JSON shape each agent module promises, since
workflows/contract_review.py and the mock client (llm/mock_client.py)
both depend on that shape staying stable.
"""
from __future__ import annotations

import pytest

from app.agents.clause_agent import run_clause_extraction
from app.agents.compliance_agent import run_compliance_check
from app.agents.deadline_agent import run_deadline_extraction
from app.agents.intake_agent import run_intake
from app.agents.risk_agent import classify_risk_level, run_risk_analysis

SAMPLE_TEXT = (
    "This Vendor Agreement is between ABC Ltd and XYZ Corp. "
    "The effective date is 01 January 2026. Company liability is unlimited liability. "
    "The Agreement expires 31 December 2027. Confidentiality: both parties shall keep terms confidential. "
    "Data Protection: personal data will be handled per applicable law. "
    "Governing Law: this Agreement is governed by the laws of Delaware. "
    "Termination: either party may terminate for cause."
)


async def test_intake_agent_identifies_type_and_parties():
    result = await run_intake(SAMPLE_TEXT)

    assert result["contract_type"] == "Vendor Agreement"
    assert result["parties"] == ["ABC Ltd", "XYZ Corp"]
    assert result["effective_date"] == "2026-01-01"


async def test_clause_agent_finds_expected_clause_types():
    result = await run_clause_extraction(SAMPLE_TEXT)
    found_types = {c["clause_type"] for c in result["clauses"]}

    assert {"Liability", "Confidentiality", "Data Protection", "Governing Law", "Termination"} <= found_types
    assert all(c["text"] for c in result["clauses"]), "every clause must carry source text as evidence"


async def test_clause_agent_returns_the_complete_numbered_paragraph():
    """Regression test: clause extraction used to grab a fixed 240-char
    window around the matched keyword, which routinely started and ended
    mid-word. Real contracts are almost always organized into numbered
    sections ("12. Insurance and Indemnification. ..."), which is a
    reliable boundary to extract the *complete* clause instead."""
    text = (
        "11. Non-Solicitation. For a period of six months following any termination, "
        "the Contractor shall not, directly or indirectly hire, solicit, or encourage "
        "to leave the Company's employment, any employee, consultant, or contractor "
        "of the Company.\n"
        "12. Insurance and Indemnification. The Contractor shall maintain comprehensive "
        "liability, professional, cyber, and other insurance as determined by the "
        "Company and shall fully indemnify, defend, and hold harmless the Company from "
        "any claims arising out of the Contractor's performance of services.\n"
        "13. Confidentiality. All confidential information disclosed shall remain the "
        "property of the Company."
    )

    result = await run_clause_extraction(text)
    by_type = {c["clause_type"]: c["text"] for c in result["clauses"]}

    assert by_type["Liability"].startswith("12. Insurance and Indemnification.")
    assert by_type["Liability"].endswith("performance of services.")
    assert by_type["Non-solicitation"].startswith("11. Non-Solicitation.")
    assert by_type["Non-solicitation"].endswith("of the Company.")


async def test_risk_agent_flags_unlimited_liability_as_critical():
    result = await run_risk_analysis(SAMPLE_TEXT)

    assert result["risks"]
    top = result["risks"][0]
    assert top["severity"] == "CRITICAL"
    assert classify_risk_level(top["score"]) == "CRITICAL"
    assert top["reason"], "risk findings must carry evidence (RULE-003)"


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0, "LOW"),
        (30, "LOW"),
        (31, "MEDIUM"),
        (60, "MEDIUM"),
        (61, "HIGH"),
        (80, "HIGH"),
        (81, "CRITICAL"),
        (100, "CRITICAL"),
    ],
)
def test_classify_risk_level_bands(score, expected):
    assert classify_risk_level(score) == expected


async def test_deadline_agent_computes_termination_notice_from_expiry_and_notice_period():
    text = SAMPLE_TEXT + " Either party may terminate by giving 90 days notice."
    result = await run_deadline_extraction(text)
    by_type = {d["deadline_type"]: d for d in result["deadlines"]}

    assert by_type["expiry_date"]["date"] == "2027-12-31"
    assert by_type["termination_notice"]["notice_period_days"] == 90
    assert by_type["termination_notice"]["date"] == "2027-10-02"  # 90 days before expiry


async def test_deadline_agent_survives_pdf_line_wrapping():
    """Regression test: pypdf's extract_text() emits one \\n per rendered
    PDF line, not per sentence — a real contract routinely wraps a
    keyword and its date onto separate lines. This reproduces exactly
    that shape; before the whitespace-normalization fix in
    llm/mock_client.py, this returned zero deadlines."""
    text = (
        "This Agreement is made and entered into as of the 1st day of\n"
        "January, 2026 (the \"Effective Date\") by and between ABC Ltd and XYZ\n"
        "Corp. This Agreement shall remain in effect for an initial term expiring\n"
        "on December 31, 2028, unless earlier terminated as provided herein.\n"
        "Either party may terminate this Agreement by providing ninety (90) days\n"
        "prior written notice to the other party."
    )

    result = await run_deadline_extraction(text)
    by_type = {d["deadline_type"]: d for d in result["deadlines"]}

    assert by_type["effective_date"]["date"] == "2026-01-01"
    assert by_type["expiry_date"]["date"] == "2028-12-31"
    assert by_type["termination_notice"]["notice_period_days"] == 90
    assert by_type["termination_notice"]["date"] == "2028-10-02"


async def test_deadline_agent_falls_back_to_duration_from_effective_date():
    text = (
        "This Agreement shall commence on the Effective Date of March 15, 2026 "
        "and shall continue in force for a period of three (3) years from such date, "
        "unless earlier terminated."
    )

    result = await run_deadline_extraction(text)
    by_type = {d["deadline_type"]: d for d in result["deadlines"]}

    assert by_type["effective_date"]["date"] == "2026-03-15"
    assert by_type["expiry_date"]["date"] == "2029-03-15"


async def test_compliance_agent_reports_violations_for_missing_requirements():
    result = await run_compliance_check(
        found_clause_types=["Confidentiality", "Termination"],
        required_clause_types=["Confidentiality", "Termination", "Governing Law", "Data Protection"],
    )

    assert result["violations"] == ["Governing Law", "Data Protection"]
    assert result["score"] == 50.0


async def test_compliance_agent_full_score_when_everything_satisfied():
    result = await run_compliance_check(
        found_clause_types=["Confidentiality", "Termination"],
        required_clause_types=["Confidentiality", "Termination"],
    )

    assert result["violations"] == []
    assert result["score"] == 100.0
