import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.schemas.criteria import CriteriaResult
from app.services.agents.criteria_extractor import extract_criteria
from app.services.llm import LLMError

router = APIRouter(prefix="/criteria", tags=["criteria"])


class ExtractRequest(BaseModel):
    document_id: str


@router.post("/extract", response_model=CriteriaResult)
def extract(req: ExtractRequest):
    try:
        return extract_criteria(req.document_id)
    except (httpx.HTTPError, LLMError) as e:
        raise HTTPException(502, f"LLM call failed: {e}")
    except RuntimeError as e:
        raise HTTPException(500, str(e))
