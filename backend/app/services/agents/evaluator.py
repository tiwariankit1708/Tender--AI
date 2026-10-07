import json
import re
from typing import Union, Optional
from pydantic import ValidationError

from app.schemas.criteria import Criterion
from app.schemas.evaluation import (
    EvaluationDecision,
    EvidenceChunk,
    EvidenceReference,
    EvaluationResult,
    BatchEvaluationResult,
)
from app.services.llm import get_llm
from app.services.agents.evidence_retriever import retrieve_bidder_evidence


SYSTEM_PROMPT = """You are an expert government tender auditor (Agent C - Evaluator).
Your sole task is to evaluate whether a bidder meets a specific tender criterion based EXCLUSIVELY on the provided retrieved evidence chunks.

Core Rules:
1. Grounding: Rely ONLY on the facts explicitly stated in the supplied evidence. Never assume, extrapolate, or invent information.
2. Anti-Hallucination: An unsupported assertion is NEVER proof. If the evidence does not contain clear, factual proof of compliance, you MUST choose "UNCLEAR" or "FAIL".
3. Force One Decision:
   - "PASS": The evidence provides explicit, unambiguous factual proof that the requirement is fully met (e.g. required figure is met or exceeded, required document is confirmed present).
   - "FAIL": The evidence explicitly shows non-compliance (e.g. turnover is below threshold, disqualification disclosed, expired credential).
   - "UNCLEAR": The evidence is missing, incomplete, inconclusive, or lacks the necessary data/numbers to verify compliance.
4. Reasoning: Provide concise, professional reasoning (1-3 sentences) directly citing facts from the excerpts.
5. Evidence References: For every cited finding, reference the chunk_id, page, and an exact verbatim quote from the evidence text.
6. Format: Output ONLY valid JSON, with no markdown code fences, matching this schema:
{
  "decision": "PASS" | "FAIL" | "UNCLEAR",
  "reasoning": "...",
  "evidence_references": [
    {
      "chunk_id": "...",
      "page": 1,
      "quote": "..."
    }
  ]
}"""


def _parse_json(raw: str) -> dict:
    """Extract and parse JSON object from LLM response string."""
    raw = re.sub(r"```(?:json)?", "", raw).strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in LLM output")
    return json.loads(raw[start : end + 1])


def _format_evidence_context(evidence: list[EvidenceChunk]) -> str:
    """Formats retrieved evidence chunks into structured text for Agent C."""
    if not evidence:
        return "No evidence was found in the bidder's submitted documents."

    formatted_parts = []
    for i, chunk in enumerate(evidence, start=1):
        page_str = f"Page {chunk.page}" if chunk.page is not None else "Page Unknown"
        formatted_parts.append(
            f"--- Evidence Chunk {i} [Chunk ID: {chunk.chunk_id}] [{page_str}] ---\n"
            f"{chunk.text.strip()}"
        )
    return "\n\n".join(formatted_parts)


def _validate_and_sanitize_result(
    result: EvaluationResult,
    evidence: list[EvidenceChunk],
) -> EvaluationResult:
    """
    Programmatic guardrail:
    Enforces the rule 'Never treat an unsupported LLM answer as proof'.
    - If no evidence was provided, decision cannot be PASS.
    - If decision is PASS, evidence_references must point to actual supplied chunk IDs.
    - Demotes unsupported PASS to UNCLEAR.
    """
    valid_chunk_ids = {c.chunk_id for c in evidence if c.chunk_id}

    if not evidence:
        if result.decision == EvaluationDecision.PASS:
            result.decision = EvaluationDecision.UNCLEAR
            result.is_supported = False
            result.reasoning = (
                "Demoted to UNCLEAR: No evidence chunks were provided, "
                "so compliance cannot be proven."
            )
            result.evidence_references = []
        return result

    if result.decision == EvaluationDecision.PASS:
        # Check if references exist and reference real chunks
        referenced_valid = [
            ref for ref in result.evidence_references
            if ref.chunk_id in valid_chunk_ids or not ref.chunk_id
        ]
        
        # If the LLM passed without any valid evidence citation or references
        if not result.evidence_references or not referenced_valid:
            result.decision = EvaluationDecision.UNCLEAR
            result.is_supported = False
            result.reasoning = (
                f"Demoted to UNCLEAR: Model asserted PASS but failed to provide "
                f"valid citations to the supplied evidence chunks. "
                f"Original reasoning: {result.reasoning}"
            )

    return result


def evaluate_criterion(
    criterion: Union[Criterion, dict],
    evidence: list[Union[EvidenceChunk, dict]],
) -> EvaluationResult:
    """
    Agent C — Evaluator:
    Evaluates a single tender criterion strictly against retrieved evidence chunks.
    
    Args:
        criterion: The tender requirement to evaluate.
        evidence: Top retrieved evidence chunks from bidder documents.
        
    Returns:
        Structured, auditable EvaluationResult (PASS / FAIL / UNCLEAR).
    """
    # Normalize criterion data
    if isinstance(criterion, dict):
        crit_id = criterion.get("criterion_id", "")
        category = criterion.get("category", "other")
        requirement = criterion.get("requirement", "")
        mandatory = criterion.get("mandatory", True)
    else:
        crit_id = criterion.criterion_id
        category = criterion.category.value if hasattr(criterion.category, "value") else str(criterion.category)
        requirement = criterion.requirement
        mandatory = criterion.mandatory

    # Normalize evidence chunks
    normalized_evidence: list[EvidenceChunk] = []
    for item in evidence:
        if isinstance(item, dict):
            normalized_evidence.append(EvidenceChunk(**item))
        elif isinstance(item, EvidenceChunk):
            normalized_evidence.append(item)

    # Fast-path: When zero evidence was retrieved, never hallucinate compliance
    if not normalized_evidence:
        return EvaluationResult(
            criterion_id=crit_id,
            category=category,
            requirement=requirement,
            decision=EvaluationDecision.UNCLEAR,
            reasoning="No evidence retrieved from bidder submission for this requirement.",
            evidence_references=[],
            is_supported=True,
            raw_evidence=[],
        )

    evidence_text = _format_evidence_context(normalized_evidence)

    user_prompt = f"""EVALUATION TASK:
Criterion ID: {crit_id or 'N/A'}
Category: {category}
Mandatory: {'Yes' if mandatory else 'No'}
Requirement: {requirement}

RETRIEVED EVIDENCE FROM BIDDER:
{evidence_text}

Evaluate this requirement strictly using the evidence above. Return ONLY JSON."""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    llm = get_llm()
    last_error = None

    for attempt in range(2):
        raw = llm.generate(messages=messages, temperature=0.0)
        try:
            parsed = _parse_json(raw)
            eval_result = EvaluationResult(
                criterion_id=crit_id,
                category=category,
                requirement=requirement,
                decision=parsed.get("decision", EvaluationDecision.UNCLEAR),
                reasoning=parsed.get("reasoning", "").strip(),
                evidence_references=[
                    EvidenceReference(**ref)
                    for ref in parsed.get("evidence_references", [])
                ],
                raw_evidence=normalized_evidence,
            )

            # Apply auditable verification guardrail
            return _validate_and_sanitize_result(eval_result, normalized_evidence)

        except (ValueError, ValidationError) as e:
            last_error = e
            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role": "user",
                "content": (
                    f"Your output was invalid ({str(e)[:180]}). "
                    f"Return ONLY valid JSON with keys: decision, reasoning, evidence_references."
                ),
            })

    # Fallback safe response if LLM failed JSON formatting twice
    return EvaluationResult(
        criterion_id=crit_id,
        category=category,
        requirement=requirement,
        decision=EvaluationDecision.UNCLEAR,
        reasoning=f"Evaluation failed due to LLM response format error: {str(last_error)[:150]}",
        evidence_references=[],
        is_supported=False,
        raw_evidence=normalized_evidence,
    )


def evaluate_bidder(
    bidder_document_id: str,
    criteria: list[Union[Criterion, dict]],
    tender_document_id: Optional[str] = None,
    collection_name: str = "bidders",
    top_k: int = 3,
) -> BatchEvaluationResult:
    """
    Coordinates Agent B (Retriever) and Agent C (Evaluator) across all criteria
    for a given bidder document.
    """
    evaluations: list[EvaluationResult] = []
    passed = 0
    failed = 0
    unclear = 0

    for crit in criteria:
        # 1. Agent B: Retrieve evidence for this criterion from bidder's documents
        evidence = retrieve_bidder_evidence(
            criterion=crit,
            bidder_document_id=bidder_document_id,
            collection_name=collection_name,
            top_k=top_k,
        )

        # 2. Agent C: Evaluate criterion against evidence
        result = evaluate_criterion(criterion=crit, evidence=evidence)
        evaluations.append(result)

        if result.decision == EvaluationDecision.PASS:
            passed += 1
        elif result.decision == EvaluationDecision.FAIL:
            failed += 1
        else:
            unclear += 1

    return BatchEvaluationResult(
        bidder_document_id=bidder_document_id,
        tender_document_id=tender_document_id,
        total_criteria=len(criteria),
        passed=passed,
        failed=failed,
        unclear=unclear,
        evaluations=evaluations,
    )
