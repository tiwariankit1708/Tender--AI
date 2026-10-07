import json
import re
from pydantic import ValidationError

from app.schemas.criteria import CriteriaResult
from app.services.llm import get_llm

QUERIES = [
    "eligibility criteria for bidders",
    "minimum annual turnover requirement",
    "past experience similar work completed projects",
    "earnest money deposit EMD",
    "bid validity period",
    "documents required to be submitted with the bid",
    "technical specifications and qualification requirements",
    "certifications registrations GST PAN ISO",
    "blacklisting declaration undertaking",
]

SYSTEM_PROMPT = """You extract bidder eligibility criteria from government tender text.
Rules:
- Use ONLY the provided excerpts. Never invent requirements.
- One criterion = one single checkable requirement (split combined requirements).
- Copy numbers, amounts, years and thresholds exactly.
- category must be one of: eligibility, technical, financial, documentation, other.
- source_page is the page number shown in the excerpt header the requirement came from.
- mandatory is true unless the text says it is optional/desirable.
- Respond with JSON ONLY, no explanation, no markdown fences, in this exact shape:
{"criteria": [{"category": "financial", "requirement": "...", "source_page": 12, "mandatory": true}]}
If nothing is found, return {"criteria": []}."""


def _retrieve(query: str, document_id: str, k: int = 4) -> list[dict]:
    """Retrieves relevant chunks from retriever.py for the given document."""
    from app.services.retriever import retrieve

    hits = retrieve(query=query, top_k=k, document_id=document_id)
    return [
        {
            "id": h.get("chunk_id") or h.get("id") or h["text"][:60],
            "text": h["text"],
            "page": h.get("page") or h.get("metadata", {}).get("page"),
        }
        for h in hits
    ]


def _gather_context(document_id: str, max_chunks: int = 14) -> list[dict]:
    seen, chunks = set(), []
    for q in QUERIES:
        for c in _retrieve(q, document_id):
            if c["id"] not in seen:
                seen.add(c["id"])
                chunks.append(c)
    chunks.sort(key=lambda c: c["page"] or 0)
    return chunks[:max_chunks]


def _parse_json(raw: str) -> dict:
    raw = re.sub(r"```(?:json)?", "", raw).strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in LLM output")
    return json.loads(raw[start : end + 1])


def extract_criteria(document_id: str) -> CriteriaResult:
    chunks = _gather_context(document_id)
    if not chunks:
        return CriteriaResult(criteria=[])

    context = "\n\n".join(f"[Page {c['page']}]\n{c['text']}" for c in chunks)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Tender excerpts:\n\n{context}\n\nExtract the criteria as JSON."},
    ]

    llm = get_llm()
    last_error = None
    for _ in range(2):  # one retry
        raw = llm.generate(messages=messages, temperature=0.0)
        try:
            result = CriteriaResult(**_parse_json(raw))
            for i, crit in enumerate(result.criteria, start=1):
                crit.criterion_id = f"C{i:03d}"
            return result
        except (ValueError, ValidationError) as e:
            last_error = e
            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role": "user",
                "content": f"Your output was invalid ({str(e)[:200]}). Return ONLY the corrected JSON.",
            })
    raise RuntimeError(f"LLM returned invalid criteria JSON after retry: {last_error}")
