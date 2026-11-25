"""Agent D — Auditor (Day 10).

Reviews Agent C's evaluation output and applies:
  1.  Deterministic heuristic checks  (zero-latency, zero-token).
  2.  Adversarial LLM review         (semantic vigilance audit).

The auditor never trusts Agent C blindly.  It looks for:
  • Unsupported PASS verdicts with no / empty evidence.
  • Hallucinated quotes that don't appear in the raw chunks.
  • Contradictions between evidence and Agent C's reasoning.
  • Ambiguous or borderline findings that need human sign-off.
"""

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.schemas.evaluation import (
    EvaluationDecision,
    EvaluationResult,
    EvidenceChunk,
)
from app.schemas.audit import (
    AuditVerdict,
    AuditIssueType,
    AuditRecord,
    BatchAuditResult,
)
from app.services.llm import get_llm


# ---------------------------------------------------------------------------
# Adversarial system prompt
# ---------------------------------------------------------------------------

AUDITOR_SYSTEM_PROMPT = """\
You are Agent D — Chief Vigilance & Quality Auditor for CRPF government tender evaluations.

Your task: independently audit the evaluation produced by Agent C.

Operating rules
1. GROUNDING  — Verify that Agent C's reasoning is *strictly* supported
   by the supplied evidence excerpts.
2. ADVERSARIAL SCRUTINY  — Actively look for:
   • Numerical / threshold discrepancies (e.g. required Rs 5 Cr but
     evidence says 3 Cr, yet Agent C marked PASS).
   • Contradictions (e.g. reasoning mentions expiry but marks PASS).
   • Unsupported assumptions (e.g. assumed ISO cert without explicit text).
3. VERDICTS
   • "CONFIRMED"           — Agent C's decision + reasoning are correct.
   • "FLAGGED"             — Agent C made an error or hallucinated.
   • "NEEDS_HUMAN_REVIEW"  — Evidence is ambiguous or borderline.
4. RECOMMENDED DECISION  — Must be PASS, FAIL, or UNCLEAR.
   If evidence is insufficient prefer UNCLEAR; never invent compliance.

Return ONLY valid JSON matching this schema:
{
  "auditor_verdict": "CONFIRMED" | "FLAGGED" | "NEEDS_HUMAN_REVIEW",
  "recommended_decision": "PASS" | "FAIL" | "UNCLEAR",
  "confidence_score": 0.95,
  "issue_type": "NONE" | "UNSUPPORTED_ASSERTION" | "CONTRADICTION"
               | "MISSING_EVIDENCE" | "HALLUCINATED_QUOTE"
               | "NUMERICAL_MISMATCH" | "AMBIGUOUS_EVIDENCE",
  "auditor_reasoning": "...",
  "requires_human_intervention": false
}"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_audit_id(criterion_id: str) -> str:
    """Generate a short, unique audit record identifier."""
    short = uuid.uuid4().hex[:6].upper()
    return f"AUD-{criterion_id or 'CRIT'}-{short}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_json(raw: str) -> dict:
    """Extract the first JSON object from a (possibly fenced) LLM response."""
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in LLM output")
    return json.loads(cleaned[start : end + 1])


# ---------------------------------------------------------------------------
# Heuristic checks (Phase 1 — deterministic, no LLM call)
# ---------------------------------------------------------------------------

def verify_quotes(
    evaluation: EvaluationResult,
    evidence: list[EvidenceChunk],
) -> tuple[bool, str]:
    """Check whether every cited quote actually exists in the raw evidence.

    Returns (all_ok, first_error_message).
    """
    if not evaluation.evidence_references:
        return True, ""

    # Build a single normalised haystack from all chunk texts
    haystack = " ".join(c.text.lower() for c in evidence)
    haystack = re.sub(r"\s+", " ", haystack)

    for ref in evaluation.evidence_references:
        quote = (ref.quote or "").strip()
        if len(quote) < 8:
            continue  # too short to be meaningful
        needle = re.sub(r"\s+", " ", quote.lower())
        if needle not in haystack:
            return False, f"Quote not found in evidence: \"{quote[:80]}...\""

    return True, ""


def _heuristic_audit(
    evaluation: EvaluationResult,
    evidence: list[EvidenceChunk],
) -> Optional[AuditRecord]:
    """Fast deterministic checks that don't require an LLM call.

    Returns an AuditRecord if a rule fires, or None to continue to
    the LLM-based audit.
    """
    audit_id = _make_audit_id(evaluation.criterion_id)
    ts = _now_iso()
    base = dict(
        audit_id=audit_id,
        criterion_id=evaluation.criterion_id,
        requirement=evaluation.requirement,
        agent_c_decision=evaluation.decision,
        timestamp=ts,
    )

    # Rule 1 — PASS on empty evidence is impossible
    if not evidence and evaluation.decision == EvaluationDecision.PASS:
        return AuditRecord(
            **base,
            auditor_verdict=AuditVerdict.FLAGGED,
            recommended_decision=EvaluationDecision.UNCLEAR,
            confidence_score=0.99,
            issue_type=AuditIssueType.MISSING_EVIDENCE,
            auditor_reasoning=(
                "Flagged: Agent C marked PASS with zero evidence chunks."
            ),
            quotes_verified=False,
            requires_human_intervention=True,
        )

    # Rule 2 — Agent C's own guardrail already flagged it as unsupported
    if not evaluation.is_supported:
        return AuditRecord(
            **base,
            auditor_verdict=AuditVerdict.FLAGGED,
            recommended_decision=EvaluationDecision.UNCLEAR,
            confidence_score=0.95,
            issue_type=AuditIssueType.UNSUPPORTED_ASSERTION,
            auditor_reasoning=(
                "Flagged: Agent C output was previously marked as unsupported "
                "by the evaluator's own anti-hallucination guardrail."
            ),
            quotes_verified=verify_quotes(evaluation, evidence)[0],
            requires_human_intervention=True,
        )

    # Rule 3 — Hallucinated quotes
    if evidence:
        quotes_ok, quote_err = verify_quotes(evaluation, evidence)
        if not quotes_ok:
            return AuditRecord(
                **base,
                auditor_verdict=AuditVerdict.FLAGGED,
                recommended_decision=EvaluationDecision.UNCLEAR,
                confidence_score=0.92,
                issue_type=AuditIssueType.HALLUCINATED_QUOTE,
                auditor_reasoning=f"Flagged: {quote_err}",
                quotes_verified=False,
                requires_human_intervention=True,
            )

    return None  # no rule fired — proceed to LLM audit


# ---------------------------------------------------------------------------
# LLM-based audit (Phase 2 — adversarial semantic review)
# ---------------------------------------------------------------------------

def _build_audit_prompt(
    evaluation: EvaluationResult,
    evidence: list[EvidenceChunk],
) -> str:
    """Format the user prompt for the adversarial LLM audit."""
    evidence_text = "\n\n".join(
        f"--- Chunk [{c.chunk_id}] (Page {c.page}) ---\n{c.text.strip()}"
        for c in evidence
    ) or "No evidence chunks available."

    refs_text = "\n".join(
        f"  - chunk_id={r.chunk_id}, page={r.page}, quote=\"{r.quote}\""
        for r in evaluation.evidence_references
    ) or "  (none)"

    return f"""\
AUDIT TARGET
─────────────────────────────────────
Criterion ID   : {evaluation.criterion_id}
Requirement    : {evaluation.requirement}
Agent C Decision: {evaluation.decision.value}
Agent C Reasoning: {evaluation.reasoning}
Agent C References:
{refs_text}

RAW RETRIEVED EVIDENCE
─────────────────────────────────────
{evidence_text}

Perform an adversarial audit.  Did Agent C make the correct call,
strictly backed by the evidence above?  Return JSON only."""


def _llm_audit(
    evaluation: EvaluationResult,
    evidence: list[EvidenceChunk],
) -> AuditRecord:
    """Call the LLM for an adversarial review of Agent C's output."""
    audit_id = _make_audit_id(evaluation.criterion_id)
    ts = _now_iso()

    messages = [
        {"role": "system", "content": AUDITOR_SYSTEM_PROMPT},
        {"role": "user", "content": _build_audit_prompt(evaluation, evidence)},
    ]

    llm = get_llm()

    try:
        raw = llm.generate(messages=messages, temperature=0.0)
        parsed = _parse_json(raw)

        verdict_str = parsed.get("auditor_verdict", "NEEDS_HUMAN_REVIEW").upper()
        rec_dec_str = parsed.get("recommended_decision", evaluation.decision.value).upper()
        issue_str = parsed.get("issue_type", "NONE").upper()
        confidence = float(parsed.get("confidence_score", 0.85))
        reasoning = parsed.get("auditor_reasoning", "")
        human_flag = parsed.get("requires_human_intervention", False)

        # Coerce to enums (fall back to safe defaults)
        try:
            verdict = AuditVerdict(verdict_str)
        except ValueError:
            verdict = AuditVerdict.NEEDS_HUMAN_REVIEW

        try:
            rec_dec = EvaluationDecision(rec_dec_str)
        except ValueError:
            rec_dec = EvaluationDecision.UNCLEAR

        try:
            issue = AuditIssueType(issue_str)
        except ValueError:
            issue = AuditIssueType.NONE

        # If verdict isn't CONFIRMED, escalate to human
        if verdict != AuditVerdict.CONFIRMED:
            human_flag = True

        return AuditRecord(
            audit_id=audit_id,
            criterion_id=evaluation.criterion_id,
            requirement=evaluation.requirement,
            agent_c_decision=evaluation.decision,
            auditor_verdict=verdict,
            recommended_decision=rec_dec,
            confidence_score=min(max(confidence, 0.0), 1.0),
            issue_type=issue,
            auditor_reasoning=reasoning,
            quotes_verified=True,  # quote check already passed in Phase 1
            requires_human_intervention=human_flag,
            timestamp=ts,
        )

    except Exception as exc:
        # LLM formatting failure — safe fallback
        return AuditRecord(
            audit_id=audit_id,
            criterion_id=evaluation.criterion_id,
            requirement=evaluation.requirement,
            agent_c_decision=evaluation.decision,
            auditor_verdict=AuditVerdict.NEEDS_HUMAN_REVIEW,
            recommended_decision=evaluation.decision,
            confidence_score=0.50,
            issue_type=AuditIssueType.AMBIGUOUS_EVIDENCE,
            auditor_reasoning=(
                f"LLM audit parsing failed: {str(exc)[:150]}. "
                "Routed to human officer for manual review."
            ),
            quotes_verified=True,
            requires_human_intervention=True,
            timestamp=ts,
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def audit_evaluation(
    evaluation: EvaluationResult,
    raw_evidence: Optional[list[EvidenceChunk]] = None,
) -> AuditRecord:
    """Audit a single criterion evaluation (Phase 1 → Phase 2).

    Args:
        evaluation:   The ``EvaluationResult`` produced by Agent C.
        raw_evidence: Override evidence list; falls back to
                      ``evaluation.raw_evidence``.

    Returns:
        A standalone ``AuditRecord`` with the auditor's verdict.
    """
    evidence = raw_evidence or evaluation.raw_evidence or []

    # Phase 1 — fast deterministic checks
    heuristic_result = _heuristic_audit(evaluation, evidence)
    if heuristic_result is not None:
        return heuristic_result

    # Phase 2 — adversarial LLM audit (only reached when heuristics pass)
    # For trivial UNCLEAR with no evidence, skip the LLM call
    if not evidence and evaluation.decision in (
        EvaluationDecision.FAIL,
        EvaluationDecision.UNCLEAR,
    ):
        return AuditRecord(
            audit_id=_make_audit_id(evaluation.criterion_id),
            criterion_id=evaluation.criterion_id,
            requirement=evaluation.requirement,
            agent_c_decision=evaluation.decision,
            auditor_verdict=AuditVerdict.CONFIRMED,
            recommended_decision=evaluation.decision,
            confidence_score=0.95,
            issue_type=AuditIssueType.NONE,
            auditor_reasoning=(
                "Confirmed: Decision is consistent with the absence of evidence."
            ),
            quotes_verified=True,
            requires_human_intervention=False,
            timestamp=_now_iso(),
        )

    return _llm_audit(evaluation, evidence)


def audit_batch(
    bidder_document_id: str,
    evaluations: list[EvaluationResult],
) -> BatchAuditResult:
    """Audit every evaluation for a bidder and aggregate counts."""
    records: list[AuditRecord] = []
    confirmed = flagged = human_review = 0

    for ev in evaluations:
        rec = audit_evaluation(ev)
        records.append(rec)
        if rec.auditor_verdict == AuditVerdict.CONFIRMED:
            confirmed += 1
        elif rec.auditor_verdict == AuditVerdict.FLAGGED:
            flagged += 1
        else:
            human_review += 1

    return BatchAuditResult(
        bidder_document_id=bidder_document_id,
        total_audited=len(evaluations),
        confirmed_count=confirmed,
        flagged_count=flagged,
        human_review_count=human_review,
        audit_records=records,
    )
