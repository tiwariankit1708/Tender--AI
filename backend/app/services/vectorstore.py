import os
from langchain_chroma import Chroma
from app.services.embeddings import get_embedding_model

# Define where the database will live on your local machine
CHROMA_PATH = os.path.join(os.path.dirname(__file__), "../data/chroma_db")

def get_vector_store(collection_name: str = "tenders"):
    """
    Returns a Chroma vector store instance. 
    If it doesn't exist, it will be created at CHROMA_PATH.
    """
    embedding_model = get_embedding_model()
    
    vector_store = Chroma(
        collection_name=collection_name,
        embedding_function=embedding_model,
        persist_directory=CHROMA_PATH
    )
    return vector_store