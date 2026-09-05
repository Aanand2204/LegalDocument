from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict

from app.schemas.review import ReviewOut


class ContractSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contract_number: str
    filename: str
    contract_type: str | None
    status: str
    created_at: dt.datetime


class ContractDetail(ContractSummary):
    parties: list[str] | None
    effective_date: dt.date | None
    expiry_date: dt.date | None
    document_hash: str
    uploaded_by: str | None
    latest_review: ReviewOut | None


class ContractUploadResponse(BaseModel):
    id: int
    contract_number: str
    filename: str
    status: str
    document_hash: str


class ContractAnalyzeResponse(BaseModel):
    contract_id: int
    status: str
    requires_human_review: bool
    clause_count: int
    risk_count: int
    high_or_critical_risk_count: int
    compliance_score: float
    compliance_violations: list[str]


class ComplianceRequirement(BaseModel):
    requirement: str
    satisfied: bool


class ComplianceResponse(BaseModel):
    policy_id: str
    policy_name: str
    results: list[ComplianceRequirement]
    violations: list[str]
    score: float
