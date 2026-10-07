from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class EvaluationDecision(str, Enum):
    """Auditable decision for a tender criterion."""
    PASS = "PASS"
    FAIL = "FAIL"
    UNCLEAR = "UNCLEAR"

    @classmethod
    def _missing_(cls, value: object):
        if isinstance(value, str):
            val = value.strip().upper()
            for member in cls:
                if member.value == val:
                    return member
        return cls.UNCLEAR


class EvidenceReference(BaseModel):
    """Traceable citation to an evidence chunk used in evaluation."""
    chunk_id: str = ""
    page: Optional[int] = None
    document_id: Optional[str] = None
    quote: str = Field(
        default="",
        description="Exact phrase or sentence from the evidence that supports the finding."
    )


class EvidenceChunk(BaseModel):
    """A retrieved chunk from bidder documents."""
    chunk_id: str
    document_id: str = ""
    page: Optional[int] = None
    text: str
    score: Optional[float] = None


class EvaluationResult(BaseModel):
    """Structured, auditable evaluation output produced by Agent C."""
    criterion_id: str = ""
    category: str = "other"
    requirement: str
    decision: EvaluationDecision
    reasoning: str = Field(
        description="Concise reasoning strictly grounded in the supplied evidence."
    )
    evidence_references: list[EvidenceReference] = Field(
        default_factory=list,
        description="List of cited evidence chunks supporting the decision."
    )
    is_supported: bool = Field(
        default=True,
        description="False if the verdict lacked factual backing in the retrieved evidence."
    )
    raw_evidence: list[EvidenceChunk] = Field(
        default_factory=list,
        description="Original evidence chunks provided to the evaluator."
    )

    @field_validator("decision", mode="before")
    @classmethod
    def normalize_decision(cls, v):
        if isinstance(v, str):
            val = v.strip().upper()
            if val in {"PASS", "PASSED", "MET", "COMPLIANT"}:
                return EvaluationDecision.PASS
            if val in {"FAIL", "FAILED", "NOT MET", "NON-COMPLIANT"}:
                return EvaluationDecision.FAIL
            return EvaluationDecision.UNCLEAR
        return v


class EvaluateCriterionRequest(BaseModel):
    """Request payload to evaluate a single criterion against retrieved evidence."""
    criterion_id: str = ""
    category: str = "other"
    requirement: str
    mandatory: bool = True
    source_page: Optional[int] = None
    evidence: list[EvidenceChunk] = Field(default_factory=list)


class BatchEvaluateRequest(BaseModel):
    """Request payload to evaluate all criteria for a bidder."""
    bidder_document_id: str
    tender_document_id: Optional[str] = None
    criteria: Optional[list[dict]] = None


class BatchEvaluationResult(BaseModel):
    """Aggregated evaluation results across all criteria for a bidder."""
    bidder_document_id: str
    tender_document_id: Optional[str] = None
    total_criteria: int
    passed: int
    failed: int
    unclear: int
    evaluations: list[EvaluationResult]
