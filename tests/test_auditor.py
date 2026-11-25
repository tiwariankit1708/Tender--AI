"""Tests for Agent D — Auditor (Day 10).

Covers the five core failure modes that the auditor must handle:
  1. PASS on empty evidence  → FLAGGED / UNCLEAR
  2. Hallucinated quote      → detected by verify_quotes
  3. Legitimate PASS         → quote verification succeeds
  4. Pre-guardrail flagged   → FLAGGED / UNSUPPORTED_ASSERTION
  5. No-evidence UNCLEAR     → CONFIRMED (consistent with absence)
"""

import sys
from pathlib import Path

# Ensure the backend package is importable when running from repo root
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.schemas.evaluation import (
    EvaluationDecision,
    EvaluationResult,
    EvidenceChunk,
    EvidenceReference,
)
from app.schemas.audit import AuditVerdict, AuditIssueType
from app.services.agents.auditor import audit_evaluation, verify_quotes


# ── Test 1: PASS with zero evidence must be flagged ─────────────────────

def test_pass_on_empty_evidence_is_flagged():
    ev = EvaluationResult(
        criterion_id="C001",
        requirement="Annual turnover Rs 10 Crores",
        decision=EvaluationDecision.PASS,
        reasoning="Bidder appears compliant.",
        raw_evidence=[],
    )
    audit = audit_evaluation(ev)

    assert audit.auditor_verdict == AuditVerdict.FLAGGED
    assert audit.recommended_decision == EvaluationDecision.UNCLEAR
    assert audit.issue_type == AuditIssueType.MISSING_EVIDENCE
    assert audit.requires_human_intervention is True


# ── Test 2: Fabricated quote is detected ────────────────────────────────

def test_hallucinated_quote_detected():
    chunk = EvidenceChunk(
        chunk_id="chunk_1",
        text="Company registered under MSME Act 2006. Annual revenue 2 Crores.",
    )
    ev = EvaluationResult(
        criterion_id="C002",
        requirement="ISO 9001 certified",
        decision=EvaluationDecision.PASS,
        reasoning="Bidder holds ISO 9001:2015 certification.",
        evidence_references=[
            EvidenceReference(
                chunk_id="chunk_1",
                quote="Certified under ISO 9001:2015 standards.",
            )
        ],
        raw_evidence=[chunk],
    )

    quotes_ok, err = verify_quotes(ev, [chunk])
    assert quotes_ok is False
    assert "not found" in err.lower()

    # Full audit should also flag it
    audit = audit_evaluation(ev)
    assert audit.auditor_verdict == AuditVerdict.FLAGGED
    assert audit.issue_type == AuditIssueType.HALLUCINATED_QUOTE


# ── Test 3: Real quote passes verification ──────────────────────────────

def test_real_quote_passes_verification():
    chunk = EvidenceChunk(
        chunk_id="chunk_2",
        text="The audited turnover for FY 2023-24 is Rs. 14.5 Crores.",
    )
    ev = EvaluationResult(
        criterion_id="C003",
        requirement="Min turnover Rs 5 Crores",
        decision=EvaluationDecision.PASS,
        reasoning="Turnover of Rs. 14.5 Crores exceeds requirement.",
        evidence_references=[
            EvidenceReference(
                chunk_id="chunk_2",
                quote="audited turnover for FY 2023-24 is Rs. 14.5 Crores",
            )
        ],
        raw_evidence=[chunk],
    )

    quotes_ok, _ = verify_quotes(ev, [chunk])
    assert quotes_ok is True


# ── Test 4: Pre-guardrail unsupported flag ──────────────────────────────

def test_unsupported_preguardrail_is_flagged():
    ev = EvaluationResult(
        criterion_id="C004",
        requirement="Must have Class-1 contractor license",
        decision=EvaluationDecision.UNCLEAR,
        reasoning="Model asserted PASS but citations were invalid.",
        is_supported=False,
        raw_evidence=[EvidenceChunk(chunk_id="c3", text="General company info.")],
    )
    audit = audit_evaluation(ev)

    assert audit.auditor_verdict == AuditVerdict.FLAGGED
    assert audit.issue_type == AuditIssueType.UNSUPPORTED_ASSERTION
    assert audit.requires_human_intervention is True


# ── Test 5: UNCLEAR with no evidence is simply confirmed ────────────────

def test_unclear_no_evidence_confirmed():
    ev = EvaluationResult(
        criterion_id="C005",
        requirement="Blacklisting declaration",
        decision=EvaluationDecision.UNCLEAR,
        reasoning="No evidence retrieved from bidder submission.",
        raw_evidence=[],
    )
    audit = audit_evaluation(ev)

    assert audit.auditor_verdict == AuditVerdict.CONFIRMED
    assert audit.recommended_decision == EvaluationDecision.UNCLEAR
    assert audit.requires_human_intervention is False
