import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.schemas.evaluation import (
    EvaluationDecision,
    EvidenceChunk,
    EvidenceReference,
    EvaluationResult,
)
from app.services.agents.evaluator import (
    _parse_json,
    _validate_and_sanitize_result,
    evaluate_criterion,
)


def test_parse_evaluator_json():
    raw = '''```json
    {
      "decision": "PASS",
      "reasoning": "The bidder demonstrated an annual turnover of 12 Crores in FY 2022-23 exceeding the required 5 Crores.",
      "evidence_references": [
        {
          "chunk_id": "chunk_turnover_01",
          "page": 4,
          "quote": "Audited turnover for FY 22-23 is Rs. 12.4 Crores."
        }
      ]
    }
    ```'''
    parsed = _parse_json(raw)
    assert parsed["decision"] == "PASS"
    assert len(parsed["evidence_references"]) == 1
    assert parsed["evidence_references"][0]["chunk_id"] == "chunk_turnover_01"


def test_decision_normalization():
    res_pass = EvaluationResult(
        requirement="Min turnover 5 Cr",
        decision="compliant",
        reasoning="Compliant.",
    )
    assert res_pass.decision == EvaluationDecision.PASS

    res_fail = EvaluationResult(
        requirement="Min turnover 5 Cr",
        decision="Failed",
        reasoning="Turnover is only 2 Cr.",
    )
    assert res_fail.decision == EvaluationDecision.FAIL

    res_unclear = EvaluationResult(
        requirement="Min turnover 5 Cr",
        decision="unknown",
        reasoning="No data found.",
    )
    assert res_unclear.decision == EvaluationDecision.UNCLEAR


def test_unsupported_pass_demoted_to_unclear():
    """Anti-hallucination check: If LLM claims PASS without evidence chunks, demote to UNCLEAR."""
    unsupported = EvaluationResult(
        criterion_id="C001",
        requirement="Annual turnover Rs 5 Cr",
        decision=EvaluationDecision.PASS,
        reasoning="Bidder seems to meet the requirement.",
        evidence_references=[],
    )
    sanitized = _validate_and_sanitize_result(unsupported, evidence=[])
    assert sanitized.decision == EvaluationDecision.UNCLEAR
    assert sanitized.is_supported is False


def test_pass_with_unmatched_chunk_id_demoted():
    """Anti-hallucination check: If cited chunk ID was not supplied, demote to UNCLEAR."""
    hallucinated_ref = EvaluationResult(
        criterion_id="C001",
        requirement="Annual turnover Rs 5 Cr",
        decision=EvaluationDecision.PASS,
        reasoning="Meets criteria.",
        evidence_references=[
            EvidenceReference(
                chunk_id="fake_invented_chunk",
                page=99,
                quote="Turnover is 10 Cr",
            )
        ],
    )
    real_evidence = [
        EvidenceChunk(
            chunk_id="real_chunk_01",
            text="General company profile...",
            page=1,
        )
    ]
    sanitized = _validate_and_sanitize_result(hallucinated_ref, evidence=real_evidence)
    assert sanitized.decision == EvaluationDecision.UNCLEAR
    assert sanitized.is_supported is False


def test_empty_evidence_fast_path():
    """When evidence is empty, evaluate_criterion immediately returns UNCLEAR without calling LLM."""
    crit = {
        "criterion_id": "C002",
        "category": "technical",
        "requirement": "Must have ISO 9001:2015 certification",
        "mandatory": True,
    }
    result = evaluate_criterion(criterion=crit, evidence=[])
    assert result.decision == EvaluationDecision.UNCLEAR
    assert len(result.evidence_references) == 0
    assert "No evidence retrieved" in result.reasoning
