import httpx
from fastapi import APIRouter, HTTPException

from app.schemas.evaluation import (
    EvaluateCriterionRequest,
    EvaluationResult,
    BatchEvaluateRequest,
    BatchEvaluationResult,
)
from app.services.agents.evaluator import evaluate_criterion, evaluate_bidder
from app.services.agents.criteria_extractor import extract_criteria
from app.services.llm import LLMError

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.post("/criterion", response_model=EvaluationResult)
def evaluate_single_criterion(req: EvaluateCriterionRequest):
    """
    Evaluates a single criterion against provided evidence chunks (Agent C).
    Enforces PASS, FAIL, or UNCLEAR with grounded reasoning and traceable references.
    """
    try:
        criterion_dict = {
            "criterion_id": req.criterion_id,
            "category": req.category,
            "requirement": req.requirement,
            "mandatory": req.mandatory,
            "source_page": req.source_page,
        }
        return evaluate_criterion(criterion=criterion_dict, evidence=req.evidence)
    except (httpx.HTTPError, LLMError) as e:
        raise HTTPException(502, f"LLM call failed: {e}")
    except Exception as e:
        raise HTTPException(500, f"Evaluation error: {str(e)}")


@router.post("/bidder", response_model=BatchEvaluationResult)
def evaluate_bidder_submission(req: BatchEvaluateRequest):
    """
    Runs full evaluation for a bidder against criteria.
    - If criteria are not provided, extracts them from tender_document_id (Agent A).
    - Retrieves evidence for each criterion (Agent B).
    - Evaluates each criterion against evidence (Agent C).
    """
    criteria_list = req.criteria

    if not criteria_list:
        if not req.tender_document_id:
            raise HTTPException(
                400,
                "Either 'criteria' or 'tender_document_id' must be provided."
            )
        try:
            extracted = extract_criteria(req.tender_document_id)
            criteria_list = [c.model_dump() for c in extracted.criteria]
        except Exception as e:
            raise HTTPException(500, f"Failed to extract criteria from tender: {e}")

    try:
        return evaluate_bidder(
            bidder_document_id=req.bidder_document_id,
            criteria=criteria_list,
            tender_document_id=req.tender_document_id,
        )
    except (httpx.HTTPError, LLMError) as e:
        raise HTTPException(502, f"LLM call failed during evaluation: {e}")
    except Exception as e:
        raise HTTPException(500, f"Batch evaluation error: {str(e)}")
