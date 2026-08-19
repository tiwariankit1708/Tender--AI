from pathlib import Path

import pymupdf
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware

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


# --- Day 2: PDF upload endpoint ---
@app.post("/upload/tender")
async def upload_tender(file: UploadFile = File(...)):
    """
    Accepts a PDF file upload, saves it to data/uploads/,
    extracts text page by page using PyMuPDF, and returns
    the extracted content as JSON.
    """
    pdf_path = UPLOAD_DIR / file.filename

    with open(pdf_path, "wb") as buffer:
        buffer.write(await file.read())

    result = extract_text_from_pdf(pdf_path)

    return {
        "filename": file.filename,
        **result,
    }