import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.llm import get_llm, LLMError

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = ""
    prompt: str = ""  # backwards compatibility
    system: str | None = "You are a helpful assistant for government tender analysis."


@router.post("")
def chat(req: ChatRequest):
    user_text = req.message or req.prompt
    if not user_text:
        raise HTTPException(400, "Message cannot be empty")
    messages = []
    if req.system:
        messages.append({"role": "system", "content": req.system})
    messages.append({"role": "user", "content": user_text})
    try:
        reply = get_llm().generate(messages)
        return {
            "answer": reply,
            "reply": reply,
            "model": getattr(get_llm(), "model_name", "llm"),
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"LLM error {e.response.status_code}: {e.response.text[:300]}")
    except httpx.RequestError as e:
        raise HTTPException(504, f"Could not reach LLM: {e}")
    except LLMError as e:
        raise HTTPException(502, str(e))
