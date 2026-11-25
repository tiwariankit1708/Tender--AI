"""Audit router — Day 10.

Endpoints:
  POST /audit/criterion   — Audit a single Agent C evaluation.
  POST /audit/batch       — Audit all evaluations for a bidder (persists).
  GET  /audit/records/{id} — Retrieve saved audit findings.
"""

from fastapi import APIRouter, HTTPException

from app.schemas.audit import (
    AuditSingleRequest,
    AuditRecord,
    BatchAuditRequest,
    BatchAuditResult,
)
from app.services.agents.auditor import audit_evaluation, audit_batch
from app.services.audit_store import save_batch_audit, load_batch_audit
from app.services.llm import LLMError

router = APIRouter(prefix="/audit", tags=["audit"])


@router.post("/criterion", response_model=AuditRecord)
def audit_single_criterion(req: AuditSingleRequest):
    """Audit one evaluation result produced by Agent C."""
    try:
        return audit_evaluation(
            evaluation=req.evaluation,
            raw_evidence=req.raw_evidence,
        )
    except LLMError as exc:
        raise HTTPException(502, f"LLM call failed during audit: {exc}")
    except Exception as exc:
        raise HTTPException(500, f"Audit error: {exc}")


@router.post("/batch", response_model=BatchAuditResult)
def audit_bidder_batch(req: BatchAuditRequest):
    """Audit every evaluation for a bidder, persist findings separately."""
    try:
        result = audit_batch(
            bidder_document_id=req.bidder_document_id,
            evaluations=req.evaluations,
        )
        save_batch_audit(result)
        return result
    except LLMError as exc:
        raise HTTPException(502, f"LLM call failed during batch audit: {exc}")
    except Exception as exc:
        raise HTTPException(500, f"Batch audit error: {exc}")


@router.get("/records/{bidder_document_id}", response_model=BatchAuditResult)
def get_audit_records(bidder_document_id: str):
    """Retrieve previously saved audit findings for a bidder."""
    result = load_batch_audit(bidder_document_id)
    if result is None:
        raise HTTPException(404, "No audit records found for this bidder.")
    return result
