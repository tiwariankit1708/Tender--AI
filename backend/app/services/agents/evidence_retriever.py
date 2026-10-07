import re
from typing import Union

from app.schemas.criteria import Criterion
from app.schemas.evaluation import EvidenceChunk
from app.services.retriever import search_tender_chunks


def build_focused_query(criterion: Union[Criterion, dict]) -> str:
    """
    Constructs a focused retrieval query for a given criterion.
    Strips leading noise and isolates core operational keywords.
    """
    req = criterion.requirement if isinstance(criterion, Criterion) else criterion.get("requirement", "")
    cat = criterion.category.value if isinstance(criterion, Criterion) else str(criterion.get("category", ""))

    # Clean punctuation and whitespace
    clean_req = re.sub(r"[^\w\s\.-]", " ", req).strip()
    
    # Prefix category context if helpful
    if cat and cat not in {"other", "documentation"}:
        return f"{cat} requirement {clean_req}"
    return clean_req


def retrieve_bidder_evidence(
    criterion: Union[Criterion, dict],
    bidder_document_id: str,
    collection_name: str = "bidders",
    top_k: int = 3,
) -> list[EvidenceChunk]:
    """
    Searches ChromaDB for bidder document chunks matching the criterion.
    
    Args:
        criterion: The criterion to search evidence for.
        bidder_document_id: The document_id of the bidder submission.
        collection_name: Collection storing bidder chunks (default 'bidders').
        top_k: Maximum evidence chunks to retrieve (default 3).
        
    Returns:
        List of EvidenceChunk objects with traceable metadata.
    """
    query = build_focused_query(criterion)
    if not query:
        return []

    try:
        hits = search_tender_chunks(
            query=query,
            top_k=top_k,
            collection_name=collection_name,
            document_id=bidder_document_id,
        )
    except Exception:
        # If collection doesn't exist yet or query fails, return empty list gracefully
        return []

    evidence: list[EvidenceChunk] = []
    for hit in hits:
        metadata = hit.get("metadata", {}) or {}
        chunk_id = hit.get("chunk_id") or hit.get("id") or metadata.get("chunk_id", "")
        doc_id = metadata.get("document_id") or bidder_document_id
        page = hit.get("page") or metadata.get("page")
        score = hit.get("score")
        text = hit.get("text", "")

        if text.strip():
            evidence.append(
                EvidenceChunk(
                    chunk_id=str(chunk_id),
                    document_id=str(doc_id),
                    page=page,
                    text=text,
                    score=score,
                )
            )

    return evidence
