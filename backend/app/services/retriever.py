from app.services.vectorstore import get_vector_store


def search_tender_chunks(query: str, top_k: int = 5, collection_name: str = "tenders"):
    """
    Searches the ChromaDB vector store for chunks most relevant to the query.

    Args:
        query:           The user's natural language question
        top_k:           Number of top matching chunks to return (default: 5)
        collection_name: Name of the ChromaDB collection to search (default: "tenders")

    Returns:
        List of dicts, each containing:
            - text:     The chunk content
            - metadata: Original metadata (document_id, page, chunk_index, etc.)
            - score:    Similarity score (higher = more relevant)
    """
    # 1. Get the vector store instance
    vector_store = get_vector_store(collection_name=collection_name)

    # 2. Perform similarity search with scores
    results_with_scores = vector_store.similarity_search_with_relevance_scores(
        query=query,
        k=top_k
    )

    # 3. Format the results into a clean list of dicts
    formatted_results = []
    for document, score in results_with_scores:
        formatted_results.append({
            "text": document.page_content,
            "metadata": document.metadata,
            "score": round(score, 4)
        })

    return formatted_results
