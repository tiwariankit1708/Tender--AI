import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEndpointEmbeddings

# .env is at project root: Tender-Ai/.env (3 levels up from this file)
env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

def get_embedding_model():
    """
    Initializes the embedding model via Hugging Face Inference API.
    Using BAAI/bge-large-en-v1.5 as it is highly optimized for retrieval.
    """
    hf_token = os.getenv("HUGGINGFACEHUB_API_TOKEN")
    if not hf_token:
        raise ValueError("HUGGINGFACEHUB_API_TOKEN is missing from .env")

    # The 'model' parameter expects the Hugging Face repository ID
    embeddings = HuggingFaceEndpointEmbeddings(
        model="BAAI/bge-large-en-v1.5",
        task="feature-extraction",
        huggingfacehub_api_token=hf_token
    )
    
    return embeddings