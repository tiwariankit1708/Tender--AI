import { useEffect, useState, useRef } from "react";
import "./App.css";

function App() {
  const [status, setStatus] = useState("Checking backend...");
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch("http://127.0.0.1:8000/health")
      .then((response) => response.json())
      .then((data) => {
        setStatus(data.status);
      })
      .catch((err) => {
        console.error(err);
        setStatus("Backend connection failed");
      });
  }, []);

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
    setResult(null);
    setError(null);
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("http://127.0.0.1:8000/upload/tender", {
        method: "POST",
        body: formData,
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Upload failed");
      }
      const data = await res.json();
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div style={{ maxWidth: 700, margin: "0 auto", padding: "2rem" }}>
      <h1>Tender AI</h1>
      <p>Backend status: {status}</p>

      <hr />

      <h2>Upload Tender PDF</h2>
      <input type="file" accept=".pdf" onChange={handleFileChange} />
      <br />
      <button onClick={handleUpload} disabled={!file || uploading} style={{ marginTop: "0.5rem" }}>
        {uploading ? "Processing..." : "Upload & Process"}
      </button>

      {error && <p style={{ color: "red" }}>⚠️ {error}</p>}

      {result && (
        <div style={{ marginTop: "1rem" }}>
          <p>✅ {result.message}</p>
          <p>Document: {result.document_id}</p>
          <p>Pages: {result.total_pages} | Chunks: {result.total_chunks}</p>

          {result.sample_chunks?.length > 0 && (
            <>
              <h3>Sample Chunks</h3>
              {result.sample_chunks.map((chunk, i) => (
                <div key={i} style={{ border: "1px solid #ccc", padding: "0.5rem", marginBottom: "0.5rem", borderRadius: 4 }}>
                  <small>Page {chunk.page} · Chunk #{chunk.chunk_index} · ID: {chunk.chunk_id?.slice(0, 8)}…</small>
                  <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.85rem" }}>{chunk.text}</pre>
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default App;