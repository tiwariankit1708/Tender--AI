"""Day 2 test: Upload a PDF to POST /upload/tender and inspect the response."""
import urllib.request
import json

# Read the sample PDF

#we open the file using rb and it is read and write
with open("data/uploads/sample_tender.pdf", "rb") as f:
    pdf_data = f.read()

# Build multipart form data
boundary = b"----PythonBoundary12345"
body = (
    b"------PythonBoundary12345\r\n"
    b'Content-Disposition: form-data; name="file"; filename="sample_tender.pdf"\r\n'
    b"Content-Type: application/pdf\r\n\r\n"
    + pdf_data
    + b"\r\n------PythonBoundary12345--\r\n"
)

req = urllib.request.Request(
    "http://127.0.0.1:8000/upload/tender",
    data=body,
    headers={"Content-Type": "multipart/form-data; boundary=----PythonBoundary12345"},
    method="POST",
)

response = urllib.request.urlopen(req)
result = json.loads(response.read())

print("=== UPLOAD RESPONSE ===")
print(f"Filename:    {result['filename']}")
print(f"Page Count:  {result['page_count']}")
print(f"Text Length: {result['text_length']}")
print()

for page in result["pages"]:
    print(f"--- Page {page['page_number']} ---")
    preview = page["text"][:200].strip()
    print(preview)
    print()
