import hashlib
from langchain_text_splitters import RecursiveCharacterTextSplitter

def generate_chunk_id(doc_id: str, text: str) -> str:
    """
    Creates a unique, stable ID for a chunk based on its content and document ID.
    If you process the exact same text twice, you get the same ID, preventing duplicates.
    """
    # Create an MD5 hash of the document ID + the actual text
    hash_input = f"{doc_id}_{text}".encode('utf-8')
    return hashlib.md5(hash_input).hexdigest()

def chunk_extracted_pages(extracted_pages: list, doc_id: str):
    """
    Takes a list of dictionaries [{'page': 1, 'text': '...'}, ...] 
    and returns a list of enriched chunk dictionaries.
    """
    # Initialize the LangChain splitter
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,    # Max characters per chunk
        chunk_overlap=200,  # Overlap to prevent cutting mid-sentence
        length_function=len,
        separators=["\n\n", "\n", " ", ""] # Splits by paragraph, then line, then word
    )

    all_chunks = []
    
    for page_data in extracted_pages:
        page_num = page_data["page"]
        page_text = page_data["text"]
        
        # Skip empty pages
        if not page_text.strip():
            continue
            
        # Split the specific page's text into chunks
        page_chunks = text_splitter.split_text(page_text)
        
        for i, chunk_text in enumerate(page_chunks):
            # Generate stable ID
            chunk_id = generate_chunk_id(doc_id, chunk_text)
            
            # Construct the final chunk object with traceability metadata
            all_chunks.append({
                "chunk_id": chunk_id,
                "document_id": doc_id,
                "page": page_num,
                "chunk_index": i + 1,
                "text": chunk_text
            })
            
    return all_chunks