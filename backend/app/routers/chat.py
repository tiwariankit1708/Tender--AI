from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.llm import LLMError, get_llm

router = APIRouter(prefix="/llm", tags=["LLM"])


# ---------- Schemas ----------
class ChatRequest(BaseModel):
    prompt: str
    system: Optional[str] = None
    temperature: Optional[float] = None
    json_mode: bool = False


class ChatResponse(BaseModel):
    model: str
    reply: str


# ---------- Endpoints ----------
@router.get("/health")
def llm_health():
    """Quick check: can we reach the configured model?"""
    llm = get_llm()
    return {"model": llm.model_name, "available": llm.is_available()}


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest):
    """Send a prompt to the LLM and return its reply."""
    llm = get_llm()
    try:
        reply = llm.generate(
            prompt=body.prompt,
            system=body.system,
            temperature=body.temperature,
            json_mode=body.json_mode,
        )
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return ChatResponse(model=llm.model_name, reply=reply)
