"""The controlled MAF workflow (plan sections 13-14): Intake -> Clause
Extraction -> Risk Analysis -> Deadline Extraction -> Compliance ->
Governance.

Uses the real `agent_framework` `Executor`/`WorkflowBuilder` API — each
pipeline stage is its own `Executor` with a single `@handler` method,
chained with `add_edge`. This is a straight sequential chain rather than
the fan-out/fan-in shown in the plan's fuller diagram (section 13); see
the implementation plan's "Workflow shape" note for why, and
`add_fan_out_edges`/`add_fan_in_edges` are the one-file change that would
parallelize Risk and Deadline later.

Governance only ever *yields a recommendation* — see GovernanceExecutor
below — never an approval/rejection; that stays with the lawyer-facing
API endpoints in api/reviews.py.

`agent_framework` deep-copies messages as they cross executors (it
supports workflow checkpointing/state history), so `PipelineState` below
carries only plain, copyable data — no SQLAlchemy `Session` or ORM
objects. Each `Executor` instead receives the `Session` through its own
constructor and keeps it as `self.db`, local to this one run.
"""
from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field

from agent_framework import Executor, Workflow, WorkflowBuilder, WorkflowContext, handler
from sqlalchemy.orm import Session

from app.agents.base import model_identity
from app.agents.clause_agent import run_clause_extraction
from app.agents.deadline_agent import run_deadline_extraction
from app.agents.intake_agent import run_intake
from app.agents.risk_agent import classify_risk_level, run_risk_analysis
from app.database import repositories as repo
from app.governance import audit
from app.governance.evaluator import evaluate
from app.services import notification_service
from app.services.compliance_service import compute_compliance
from config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class PipelineState:
    """Carried between every stage of one contract's review run.

    Deliberately plain data (ints, strings, dicts) — see the module
    docstring for why no `Session`/ORM object belongs here.
    """

    contract_id: int
    text: str
    current_document_hash: str
    clause_refs: list[dict] = field(default_factory=list)  # [{"id": int, "clause_type": str}, ...]
    risk_scores: list[int] = field(default_factory=list)
    confidences: list[float] = field(default_factory=list)
    risks_raw: list[dict] = field(default_factory=list)
    compliance_score: float = 100.0
    compliance_violations: list[str] = field(default_factory=list)


class _DbExecutor(Executor):
    """Common base: an Executor bound to one Session for this run."""

    def __init__(self, db: Session, *, id: str) -> None:
        super().__init__(id=id)
        self.db = db

    def _log_stage_start(self, state: PipelineState) -> None:
        logger.info("stage starting: %s (contract %d)", self.id, state.contract_id)


class IntakeExecutor(_DbExecutor):
    @handler
    async def run(self, state: PipelineState, ctx: WorkflowContext[PipelineState]) -> None:
        self._log_stage_start(state)
        result = await run_intake(state.text)
        model_name, model_version = model_identity()
        audit.log_agent_run(
            self.db,
            contract_id=state.contract_id,
            agent_name="intake_agent",
            model_name=model_name,
            model_version=model_version,
            input_data={"text_length": len(state.text)},
            output_data=result,
        )

        contract = repo.get_contract(self.db, state.contract_id)
        contract.contract_type = result.get("contract_type")
        contract.parties = result.get("parties") or []
        effective_date = result.get("effective_date")
        if effective_date:
            contract.effective_date = dt.date.fromisoformat(effective_date)
        self.db.commit()

        await ctx.send_message(state)


class ClauseExtractionExecutor(_DbExecutor):
    @handler
    async def run(self, state: PipelineState, ctx: WorkflowContext[PipelineState]) -> None:
        self._log_stage_start(state)
        result = await run_clause_extraction(state.text)
        model_name, model_version = model_identity()
        audit.log_agent_run(
            self.db,
            contract_id=state.contract_id,
            agent_name="clause_agent",
            model_name=model_name,
            model_version=model_version,
            input_data={"text_length": len(state.text)},
            output_data=result,
        )

        rows = repo.add_clauses(
            self.db,
            state.contract_id,
            [
                {
                    "clause_type": c["clause_type"],
                    "clause_text": c.get("text", ""),
                    "page_number": c.get("page_number"),
                    "confidence": c.get("confidence"),
                }
                for c in result.get("clauses", [])
            ],
        )
        state.clause_refs = [{"id": row.id, "clause_type": row.clause_type} for row in rows]

        await ctx.send_message(state)


def _match_clause_id(clause_refs: list[dict], clause_type: str | None) -> int | None:
    if not clause_type:
        return None
    for ref in clause_refs:
        if ref["clause_type"].lower() == clause_type.lower():
            return ref["id"]
    return None


class RiskAnalysisExecutor(_DbExecutor):
    @handler
    async def run(self, state: PipelineState, ctx: WorkflowContext[PipelineState]) -> None:
        self._log_stage_start(state)
        result = await run_risk_analysis(state.text)
        model_name, model_version = model_identity()
        audit.log_agent_run(
            self.db,
            contract_id=state.contract_id,
            agent_name="risk_agent",
            model_name=model_name,
            model_version=model_version,
            input_data={"text_length": len(state.text)},
            output_data=result,
        )

        settings = get_settings()
        rows_data = []
        for r in result.get("risks", []):
            score = int(r["score"])
            confidence = float(r.get("confidence", 0.5))
            rows_data.append(
                {
                    "clause_id": _match_clause_id(state.clause_refs, r.get("clause_type")),
                    "risk_type": r["risk_type"],
                    "risk_score": score,
                    "risk_level": classify_risk_level(score),
                    "reason": r["reason"],
                    "recommendation": r.get("recommendation", ""),
                    "confidence": confidence,
                    "requires_human_review": (
                        score >= settings.risk_review_threshold
                        or confidence < settings.confidence_review_threshold
                    ),
                }
            )
        if rows_data:
            repo.add_risks(self.db, state.contract_id, rows_data)

        state.risk_scores.extend(d["risk_score"] for d in rows_data)
        state.confidences.extend(d["confidence"] for d in rows_data)
        state.risks_raw.extend(result.get("risks", []))

        await ctx.send_message(state)


class DeadlineExtractionExecutor(_DbExecutor):
    @handler
    async def run(self, state: PipelineState, ctx: WorkflowContext[PipelineState]) -> None:
        self._log_stage_start(state)
        result = await run_deadline_extraction(state.text)
        model_name, model_version = model_identity()
        audit.log_agent_run(
            self.db,
            contract_id=state.contract_id,
            agent_name="deadline_agent",
            model_name=model_name,
            model_version=model_version,
            input_data={"text_length": len(state.text)},
            output_data=result,
        )

        rows_data = []
        expiry_date: dt.date | None = None
        for d in result.get("deadlines", []):
            date_str = d.get("date")
            if not date_str:
                continue
            deadline_date = dt.date.fromisoformat(date_str)
            if d["deadline_type"] == "expiry_date":
                expiry_date = deadline_date
            rows_data.append(
                {
                    "deadline_type": d["deadline_type"],
                    "deadline_date": deadline_date,
                    "notice_period_days": d.get("notice_period_days"),
                }
            )
        if rows_data:
            repo.add_deadlines(self.db, state.contract_id, rows_data)

        if expiry_date is not None:
            contract = repo.get_contract(self.db, state.contract_id)
            contract.expiry_date = expiry_date
            self.db.commit()

        await ctx.send_message(state)


class ComplianceExecutor(_DbExecutor):
    @handler
    async def run(self, state: PipelineState, ctx: WorkflowContext[PipelineState]) -> None:
        self._log_stage_start(state)
        contract = repo.get_contract(self.db, state.contract_id)
        found_clause_types = [ref["clause_type"] for ref in state.clause_refs]

        policy, result = await compute_compliance(contract, found_clause_types)
        model_name, model_version = model_identity()
        audit.log_agent_run(
            self.db,
            contract_id=state.contract_id,
            agent_name="compliance_agent",
            model_name=model_name,
            model_version=model_version,
            input_data={"found": found_clause_types, "required": list(policy.required_clause_types)},
            output_data=result,
        )

        state.compliance_score = float(result.get("score", 0.0))
        state.compliance_violations = list(result.get("violations", []))

        await ctx.send_message(state)


class GovernanceExecutor(_DbExecutor):
    """Terminal stage — yields a recommendation only.

    Structurally cannot approve or reject a contract (RULE-001): it has
    no code path that writes `Contract.status` to anything but
    "analyzed" or "under_review". Only api/reviews.py, driven by a
    lawyer, can set approved/rejected.
    """

    @handler
    async def run(self, state: PipelineState, ctx: WorkflowContext[None, dict]) -> None:
        self._log_stage_start(state)
        contract = repo.get_contract(self.db, state.contract_id)
        model_name, model_version = model_identity()
        # The text that ends up in the permanent audit trail / UI (see
        # riskCardHtml in frontend/app.js) — RULE-007 scans it for
        # obvious sensitive-identifier patterns before that happens.
        log_text = " ".join(
            f"{r.get('reason', '')} {r.get('recommendation', '')}" for r in state.risks_raw
        )

        decision = evaluate(
            risk_scores=state.risk_scores,
            confidences=state.confidences,
            risks=state.risks_raw,
            # Every prior stage already wrote a GovernanceEvent via
            # audit.log_agent_run, so RULE-004 is satisfied for this run.
            audit_event_logged=True,
            original_document_hash=contract.document_hash,
            current_document_hash=state.current_document_hash,
            log_text=log_text,
            model_name=model_name,
            model_version=model_version,
        )
        audit.log_governance_decision(self.db, contract_id=state.contract_id, decision=decision)

        new_status = "under_review" if decision.requires_human_review else "analyzed"
        repo.update_contract_status(self.db, contract, new_status)

        high_or_critical = sum(1 for s in state.risk_scores if s >= get_settings().risk_review_threshold)
        if decision.requires_human_review:
            notification_service.notify_human_review_required(contract=contract, risk_count=high_or_critical)

        await ctx.yield_output(
            {
                "contract_id": state.contract_id,
                "status": new_status,
                "requires_human_review": decision.requires_human_review,
                "clause_count": len(state.clause_refs),
                "risk_count": len(state.risk_scores),
                "high_or_critical_risk_count": high_or_critical,
                "compliance_score": state.compliance_score,
                "compliance_violations": state.compliance_violations,
            }
        )


def build_workflow(db: Session) -> Workflow:
    intake = IntakeExecutor(db, id="intake")
    clause = ClauseExtractionExecutor(db, id="clause_extraction")
    risk = RiskAnalysisExecutor(db, id="risk_analysis")
    deadline = DeadlineExtractionExecutor(db, id="deadline_extraction")
    compliance = ComplianceExecutor(db, id="compliance")
    governance = GovernanceExecutor(db, id="governance")

    return (
        WorkflowBuilder(start_executor=intake)
        .add_edge(intake, clause)
        .add_edge(clause, risk)
        .add_edge(risk, deadline)
        .add_edge(deadline, compliance)
        .add_edge(compliance, governance)
        .build()
    )


async def run_contract_review(
    db: Session, contract_id: int, text: str, *, current_document_hash: str
) -> dict:
    """Run the full Intake -> ... -> Governance chain for one contract.

    `current_document_hash` is the SHA-256 of the file bytes read right
    before this run (see api/contracts.py::analyze_contract) — compared
    against the contract's stored `document_hash` by GovernanceExecutor
    (RULE-006: the AI must not be analyzing a document that's been
    swapped out since upload).

    Returns the single dict GovernanceExecutor yields (see above) —
    everything the API needs to answer `POST /contracts/{id}/analyze`.
    """
    workflow = build_workflow(db)
    state = PipelineState(contract_id=contract_id, text=text, current_document_hash=current_document_hash)
    result = await workflow.run(state)
    outputs = result.get_outputs()
    if not outputs:
        raise RuntimeError("Contract review workflow produced no output")
    return outputs[0]
