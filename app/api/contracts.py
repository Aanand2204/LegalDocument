"""Contract upload, listing, retrieval, and analysis endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_current_user, get_db, require_owned_contract
from app.database import repositories as repo
from app.governance import audit
from app.schemas.contract import (
    ComplianceResponse,
    ContractAnalyzeResponse,
    ContractDetail,
    ContractSummary,
    ContractUploadResponse,
)
from app.services import document_service
from app.services.compliance_service import compute_compliance
from app.workflows.contract_review import run_contract_review
from config import get_settings

router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.post("/upload", response_model=ContractUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_contract(
    file: UploadFile,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Uploaded file has no filename")

    data = await file.read()
    try:
        extracted = document_service.extract_document(file.filename, data)
    except document_service.UnsupportedDocumentType as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    settings = get_settings()
    dest_path = settings.documents_path / f"{extracted.sha256}_{file.filename}"
    dest_path.write_bytes(data)

    contract = repo.create_contract(
        db,
        filename=file.filename,
        document_path=str(dest_path),
        document_hash=extracted.sha256,
        uploaded_by=user.email,
        status="uploaded",
    )
    audit.log_user_action(db, user=user.email, action="upload_contract", resource=f"contract:{contract.id}")

    return ContractUploadResponse(
        id=contract.id,
        contract_number=contract.contract_number,
        filename=contract.filename,
        status=contract.status,
        document_hash=contract.document_hash,
    )


@router.get("", response_model=list[ContractSummary])
def list_contracts(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    return repo.list_contracts(db, uploaded_by=user.email)


@router.get("/{contract_id}", response_model=ContractDetail)
def get_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    return require_owned_contract(db, contract_id, user)


@router.post("/{contract_id}/analyze", response_model=ContractAnalyzeResponse)
async def analyze_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    contract = require_owned_contract(db, contract_id, user)

    with open(contract.document_path, "rb") as fh:
        data = fh.read()
    extracted = document_service.extract_document(contract.filename, data)

    repo.update_contract_status(db, contract, "analyzing")
    result = await run_contract_review(
        db, contract_id, extracted.text, current_document_hash=extracted.sha256
    )

    audit.log_user_action(
        db, user=user.email, action="analyze_contract", resource=f"contract:{contract_id}"
    )

    return ContractAnalyzeResponse(**result)


@router.get("/{contract_id}/compliance", response_model=ComplianceResponse)
async def get_contract_compliance(
    contract_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    contract = require_owned_contract(db, contract_id, user)

    clauses = repo.list_clauses(db, contract_id)
    found_clause_types = [c.clause_type for c in clauses]

    policy, result = await compute_compliance(contract, found_clause_types)

    return ComplianceResponse(
        policy_id=policy.policy_id,
        policy_name=policy.name,
        results=result.get("results", []),
        violations=result.get("violations", []),
        score=float(result.get("score", 100.0)),
    )
