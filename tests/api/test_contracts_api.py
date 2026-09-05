"""End-to-end API test: upload -> analyze -> risks/clauses/deadlines/audit."""
from __future__ import annotations

import datetime as dt

from app.database.models import Deadline
from tests.conftest import login_as, make_minimal_pdf

SAMPLE_TEXT = (
    "This Vendor Agreement is between ABC Ltd and XYZ Corp. "
    "The effective date is 01 January 2026. Company liability is unlimited liability. "
    "The Agreement expires 31 December 2027. Either party may terminate by giving 90 days notice. "
    "Confidentiality: both parties shall keep terms confidential. "
    "Data Protection: personal data will be handled per applicable law. "
    "Governing Law: this Agreement is governed by the laws of Delaware. "
    "Termination: either party may terminate for cause."
)


def _upload(client, db_session):
    login_as(client, db_session)
    pdf_bytes = make_minimal_pdf(SAMPLE_TEXT)
    response = client.post(
        "/contracts/upload",
        files={"file": ("vendor_agreement.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 201
    return response.json()


def test_upload_returns_uploaded_contract(client, db_session):
    contract = _upload(client, db_session)

    assert contract["status"] == "uploaded"
    assert contract["contract_number"].startswith("CNT-")

    listed = client.get("/contracts").json()
    assert any(c["id"] == contract["id"] for c in listed)


def test_analyze_persists_clauses_risks_and_flags_review(client, db_session):
    contract = _upload(client, db_session)
    contract_id = contract["id"]

    analyze_response = client.post(f"/contracts/{contract_id}/analyze")
    assert analyze_response.status_code == 200
    result = analyze_response.json()

    assert result["contract_id"] == contract_id
    assert result["clause_count"] > 0
    assert result["risk_count"] > 0
    assert result["requires_human_review"] is True
    assert result["status"] == "under_review"

    risks = client.get(f"/contracts/{contract_id}/risks").json()
    assert len(risks) == result["risk_count"]
    assert any(r["risk_level"] == "CRITICAL" for r in risks)

    clauses = client.get(f"/contracts/{contract_id}/clauses").json()
    assert len(clauses) == result["clause_count"]

    deadlines = client.get(f"/contracts/{contract_id}/deadlines").json()
    assert {"expiry_date", "termination_notice"} <= {d["deadline_type"] for d in deadlines}


def test_compliance_endpoint_matches_analyze_and_survives_reload(client, db_session):
    contract = _upload(client, db_session)
    contract_id = contract["id"]
    analyzed = client.post(f"/contracts/{contract_id}/analyze").json()

    compliance = client.get(f"/contracts/{contract_id}/compliance").json()

    assert compliance["policy_id"] == "POLICY-001"  # Vendor Agreement
    assert compliance["score"] == analyzed["compliance_score"]
    assert compliance["violations"] == analyzed["compliance_violations"]
    assert all("requirement" in r and "satisfied" in r for r in compliance["results"])

    audit_after_analyze = client.get(f"/audit/{contract_id}").json()
    client.get(f"/contracts/{contract_id}/compliance")
    audit_after_reload = client.get(f"/audit/{contract_id}").json()
    assert len(audit_after_reload["governance_events"]) == len(audit_after_analyze["governance_events"])

    contract_detail = client.get(f"/contracts/{contract_id}").json()
    assert contract_detail["contract_type"] == "Vendor Agreement"
    assert contract_detail["parties"] == ["ABC Ltd", "XYZ Corp"]


def test_analyze_writes_governance_and_audit_trail(client, db_session):
    contract = _upload(client, db_session)
    contract_id = contract["id"]
    client.post(f"/contracts/{contract_id}/analyze")

    audit = client.get(f"/audit/{contract_id}").json()

    agent_names = {e["agent_name"] for e in audit["governance_events"]}
    expected_agents = {
        "intake_agent",
        "clause_agent",
        "risk_agent",
        "deadline_agent",
        "compliance_agent",
        "governance",
    }
    assert expected_agents <= agent_names

    agent_events = [e for e in audit["governance_events"] if e["agent_name"] != "governance"]
    assert all(e["model_name"] and e["model_version"] for e in agent_events)
    assert any(log["action"] == "analyze_contract" for log in audit["audit_logs"])


def test_can_override_a_risk_finding(client, db_session):
    contract = _upload(client, db_session)
    contract_id = contract["id"]
    client.post(f"/contracts/{contract_id}/analyze")
    risk_id = client.get(f"/contracts/{contract_id}/risks").json()[0]["id"]

    response = client.post(
        f"/risks/{risk_id}/reject",
        json={"reason": "Covered by master agreement."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["human_decision"] == "OVERRIDDEN"
    assert body["reviewed_by"]


def test_review_sets_contract_status(client, db_session):
    contract = _upload(client, db_session)
    contract_id = contract["id"]
    client.post(f"/contracts/{contract_id}/analyze")

    response = client.post(
        f"/contracts/{contract_id}/review",
        json={"decision": "approved", "comments": "Acceptable risk."},
    )
    assert response.status_code == 201
    assert response.json()["lawyer_id"]

    detail = client.get(f"/contracts/{contract_id}").json()
    assert detail["status"] == "approved"


def test_upload_rejects_unsupported_file_type(client, db_session):
    login_as(client, db_session)
    response = client.post(
        "/contracts/upload",
        files={"file": ("notes.txt", b"plain text", "text/plain")},
    )
    assert response.status_code == 400


def test_accounts_cannot_see_each_others_contracts(client, db_session):
    uploader_contract = _upload(client, db_session)

    login_as(client, db_session)
    assert client.get(f"/contracts/{uploader_contract['id']}").status_code == 404
    listed = client.get("/contracts").json()
    assert not any(c["id"] == uploader_contract["id"] for c in listed)


def test_protected_endpoints_reject_no_session(client):
    assert client.get("/contracts").status_code == 401
    assert client.get("/dashboard/statistics").status_code == 401


def test_deadline_check_returns_a_schema_valid_alert_for_a_due_soon_deadline(client, db_session):
    contract = _upload(client, db_session)
    client.post(f"/contracts/{contract['id']}/analyze")

    deadline = db_session.query(Deadline).filter(Deadline.contract_id == contract["id"]).first()
    deadline.deadline_date = dt.date.today() + dt.timedelta(days=20)
    db_session.commit()

    response = client.post("/deadlines/check")
    assert response.status_code == 200
    alerts = response.json()
    assert any(a["deadline_id"] == deadline.id and a["window"] == "30_day" for a in alerts)
