import { useState, useCallback, useRef } from "react";
import Markdown from "react-markdown";

const GATEWAY_URL = "http://localhost:7005";

interface ConvertResponse {
  markdown: string;
  metadata: {
    processing_time_ms: number;
    actions: string[];
  };
}

type Status = "idle" | "loading" | "success" | "error";

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function App() {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [statusMessage, setStatusMessage] = useState("");
  const [result, setResult] = useState<ConvertResponse | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const convertFile = useCallback(async (f: File) => {
    setFile(f);
    setResult(null);
    setStatus("loading");
    setStatusMessage("Processing document...");

    try {
      const formData = new FormData();
      formData.append("file", f);

      const response = await fetch(`${GATEWAY_URL}/convert`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const err = await response.json().catch(() => null);
        throw new Error(err?.detail || `Server error: ${response.status}`);
      }

      const data: ConvertResponse = await response.json();
      setResult(data);
      setStatus("success");
      setStatusMessage(
        `Done in ${(data.metadata.processing_time_ms / 1000).toFixed(1)}s`
      );
    } catch (err) {
      setStatus("error");
      setStatusMessage(
        err instanceof Error ? err.message : "Something went wrong"
      );
    }
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragActive(false);
      const f = e.dataTransfer.files[0];
      if (f) convertFile(f);
    },
    [convertFile]
  );

  return (
    <>
      <header className="header">
        <h1><a href="https://canonizr.com" target="_blank" rel="noopener noreferrer">Canonizr</a></h1>
      </header>

      <main className="main">
        <div className="panel">
          <div className="panel-header">Input</div>
          <div className="panel-body">
            <div
              className={`dropzone ${dragActive ? "active" : ""}`}
              role="button"
              tabIndex={0}
              aria-label="Upload a document"
              onDragOver={(e) => {
                e.preventDefault();
                setDragActive(true);
              }}
              onDragLeave={() => setDragActive(false)}
              onDrop={handleDrop}
              onClick={() => inputRef.current?.click()}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  inputRef.current?.click();
                }
              }}
            >
              <div className="dropzone-icon">+</div>
              <div className="dropzone-label">
                Drop a document here or click to browse
              </div>
              <div className="dropzone-hint">
                PDF, DOCX, ODT, HTML, images, and more
              </div>
              <input
                ref={inputRef}
                type="file"
                hidden
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) convertFile(f);
                }}
              />
            </div>

            {file && (
              <div className="file-info">
                <span className="file-info-name">{file.name}</span>
                <span className="file-info-size">{formatSize(file.size)}</span>
              </div>
            )}

            <div role="status" aria-live="polite">
              {status !== "idle" && (
                <div className={`status status-${status}`}>
                  {statusMessage}
                  {status === "error" && file && (
                    <button
                      className="btn btn-primary"
                      onClick={() => convertFile(file)}
                    >
                      Retry
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">Output</div>
          <div className="panel-body">
            {result ? (
              <>
                <div className="markdown-output">
                  <Markdown>{result.markdown}</Markdown>
                </div>
                <div className="metadata">
                  {result.metadata.actions.map((action, i) => (
                    <span key={i}>{action}</span>
                  ))}
                </div>
              </>
            ) : (
              <div className="empty-state">
                <div className="empty-state-icon">&#8594;</div>
                <div>Converted output will appear here</div>
              </div>
            )}
          </div>
        </div>
      </main>
    </>
  );
}

export default App;
