from app.services.vectorstore import get_vector_store


def search_tender_chunks(
    query: str,
    top_k: int = 5,
    collection_name: str = "tenders",
    document_id: str | None = None,
):
    """
    Searches the ChromaDB vector store for chunks most relevant to the query.

    Args:
        query:           The user's natural language question
        top_k:           Number of top matching chunks to return (default: 5)
        collection_name: Name of the ChromaDB collection to search (default: "tenders")
        document_id:     Optional document ID to filter chunks by

    Returns:
        List of dicts, each containing:
            - id:       Chunk ID
            - text:     The chunk content
            - metadata: Original metadata (document_id, page, chunk_index, etc.)
            - page:     Source page number
            - score:    Similarity score (higher = more relevant)
    """
    # 1. Get the vector store instance
    vector_store = get_vector_store(collection_name=collection_name)

    # 2. Perform similarity search with scores (filtered by document_id if provided)
    search_kwargs = {"query": query, "k": top_k}
    if document_id:
        search_kwargs["filter"] = {"document_id": document_id}

    results_with_scores = vector_store.similarity_search_with_relevance_scores(
        **search_kwargs
    )

    # 3. Format the results into a clean list of dicts
    formatted_results = []
    for document, score in results_with_scores:
        metadata = document.metadata or {}
        formatted_results.append({
            "id": metadata.get("chunk_id", ""),
            "chunk_id": metadata.get("chunk_id", ""),
            "text": document.page_content,
            "metadata": metadata,
            "page": metadata.get("page"),
            "score": round(score, 4),
        })

    return formatted_results


# Alias matching Day 7 agent expectations
retrieve = search_tender_chunks
