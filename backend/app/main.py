import os
from pathlib import Path
import pymupdf
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.documents import Document
from app.services import vectorstore
from app.services import chunker
from app.services import retriever

app = FastAPI(title="Tender AI API")

# --- CORS middleware (from Day 1) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Upload directory ---
UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# --- Day 1: Health endpoint ---
@app.get("/health")
def health_check():
    return {"status": "Backend is running"}


# --- Day 2: PDF text extraction function ---
def extract_text_from_pdf(pdf_path):
    """
    Opens a PDF with PyMuPDF and extracts text page by page.

    Returns a dict containing:
        - page_count: total number of pages
        - text_length: total characters extracted across all pages
        - pages: list of dicts, each with page_number and text
    """
    document = pymupdf.open(pdf_path)

    pages = []

    for page_number, page in enumerate(document, start=1):
        text = page.get_text()

        pages.append({
            "page_number": page_number,
            "text": text,
        })

    page_count = len(document)

    document.close()

    total_text_length = sum(len(page["text"]) for page in pages)

    return {
        "page_count": page_count,
        "text_length": total_text_length,
        "pages": pages,
    }


# # --- Day 2: PDF upload endpoint ---
# @app.post("/upload/tender")
# async def upload_tender(file: UploadFile = File(...)):
#     if not file.filename.endswith(".pdf"):
#         raise HTTPException(status_code=400, detail="Only PDF files are allowed.")
        
#     # 1. Save the file temporarily
#     file_path = os.path.join(UPLOAD_DIR, file.filename)
#     with open(file_path, "wb") as buffer:
#         buffer.write(await file.read())
        
#     # 2. Extract Text (Day 2)
#     try:
#         extraction_result = extract_text_from_pdf(file_path)
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed to read PDF: {str(e)}")
        
#     # 3. Chunk the Text (Day 3)
#     # Map "page_number" -> "page" so the chunker gets the key it expects
#     doc_id = file.filename  # Using filename as a simple doc_id for now
#     pages_for_chunker = [
#         {"page": p["page_number"], "text": p["text"]}
#         for p in extraction_result["pages"]
#     ]
#     chunks = chunker.chunk_extracted_pages(pages_for_chunker, doc_id=doc_id)
    
#     # Return some stats and the first 3 chunks to verify
#     return {
#         "message": "Tender processed and chunked successfully",
#         "document_id": doc_id,
#         "total_pages": extraction_result["page_count"],
#         "total_chunks": len(chunks),
#     }

@app.post("/ingest/tender")
async def ingest_tender(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")
    
    # 1. Save the file temporarily
    file_path = os.path.join(UPLOAD_DIR, f"temp_{file.filename}")
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    
    # 2. Extract Text
    extraction_result = extract_text_from_pdf(file_path)
    
    # 3. Chunk the Text
    doc_id = file.filename
    pages_for_chunker = [
        {"page": p["page_number"], "text": p["text"]} 
        for p in extraction_result["pages"]
    ]
    chunks = chunker.chunk_extracted_pages(pages_for_chunker, doc_id=doc_id)
    
    # 4. Store in Vector DB
    try:
        vector_store = vectorstore.get_vector_store(collection_name="tenders")
        
        # Convert dictionary chunks into LangChain Document objects
        documents = [
            Document(
                page_content=c["text"],
                metadata={
                    "chunk_id": c["chunk_id"],
                    "document_id": c["document_id"],
                    "page": c["page"],
                    "chunk_index": c["chunk_index"],
                }
            )
            for c in chunks
        ]
        vector_store.add_documents(documents)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vector store error: {str(e)}")
    
    # 5. Clean up temporary file
    if os.path.exists(file_path):
        os.remove(file_path)
    
    return {
        "message": "Tender successfully ingested and vectorized",
        "document_id": doc_id,
        "total_chunks": len(chunks),
        "total_pages": extraction_result["page_count"]
    }


# --- Day 5: Search endpoint ---
@app.post("/search")
async def search_tenders(body: dict):
    """
    Accepts a JSON body with a 'query' field (and optional 'top_k'),
    and returns the most relevant tender chunks from the vector database.

    Example request body:
        {"query": "What is the minimum annual turnover required?", "top_k": 3}
    """
    # 1. Extract the query from the request body
    query = body.get("query")
    if not query:
        raise HTTPException(status_code=400, detail="Missing 'query' field in request body.")

    # 2. Get optional top_k (default to 3)
    top_k = body.get("top_k", 3)

    # 3. Call the retriever service
    try:
        results = retriever.search_tender_chunks(query=query, top_k=top_k)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

    # 4. Return the results
    return {
        "query": query,
        "top_k": top_k,
        "results_count": len(results),
        "results": results
    }