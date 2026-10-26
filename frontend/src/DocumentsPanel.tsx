import { useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "./auth/AuthContext";
import { ChatApiError } from "./services/chat";
import {
  deleteDocument,
  listDocuments,
  uploadDocument,
  type TutorDocument,
} from "./services/documents";

export function DocumentsPanel() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const [documents, setDocuments] = useState<TutorDocument[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(true);
  const [action, setAction] = useState<"refresh" | "upload" | "delete" | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const requestActive = useRef(false);

  function handleUnauthorized(reason: unknown): boolean {
    if (!(reason instanceof ChatApiError) || reason.status !== 401) return false;
    logout();
    navigate("/login", { replace: true });
    return true;
  }

  async function refreshDocuments(initial = false) {
    if (requestActive.current) return;
    requestActive.current = true;
    setAction("refresh");
    setError("");
    if (initial) setLoading(true);

    try {
      setDocuments(await listDocuments());
    } catch (reason) {
      if (!handleUnauthorized(reason)) {
        setError(reason instanceof Error ? reason.message : "Could not load your documents.");
      }
    } finally {
      requestActive.current = false;
      setAction(null);
      setLoading(false);
    }
  }

  useEffect(() => {
    void refreshDocuments(true);
  }, []);

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (requestActive.current || !selectedFile) return;
    const uploadForm = event.currentTarget;
    requestActive.current = true;
    setAction("upload");
    setError("");
    setNotice("");

    try {
      const uploaded = await uploadDocument(selectedFile);
      setDocuments((current) => [uploaded, ...current.filter((item) => item.id !== uploaded.id)]);
      setSelectedFile(null);
      uploadForm.reset();
      setNotice(`${uploaded.original_filename} uploaded successfully.`);
    } catch (reason) {
      if (!handleUnauthorized(reason)) {
        setError(reason instanceof Error ? reason.message : "Could not upload this document.");
        try {
          setDocuments(await listDocuments());
        } catch {
          // Keep the upload error visible if refreshing also fails.
        }
      }
    } finally {
      requestActive.current = false;
      setAction(null);
    }
  }

  async function handleDelete(document: TutorDocument) {
    if (requestActive.current) return;
    if (!window.confirm(`Delete “${document.original_filename}”? This cannot be undone.`)) return;
    requestActive.current = true;
    setAction("delete");
    setError("");
    setNotice("");

    try {
      await deleteDocument(document.id);
      setDocuments((current) => current.filter((item) => item.id !== document.id));
      setNotice(`${document.original_filename} was deleted.`);
    } catch (reason) {
      if (!handleUnauthorized(reason)) {
        setError(reason instanceof Error ? reason.message : "Could not delete this document.");
      }
    } finally {
      requestActive.current = false;
      setAction(null);
    }
  }

  function acceptDroppedFile(file?: File) {
    if (!file || requestActive.current) return;
    setSelectedFile(file);
    setError("");
    setNotice("");
  }

  const busy = action !== null;

  return (
    <aside className="documents-sidebar" aria-labelledby="documents-title">
      <div className="documents-panel-heading">
        <div>
          <p className="eyebrow">Course materials</p>
          <h2 id="documents-title">Your documents</h2>
        </div>
        <button
          type="button"
          className="icon-button"
          onClick={() => void refreshDocuments()}
          disabled={busy}
          aria-label="Refresh documents"
          title="Refresh documents"
        >
          ↻
        </button>
      </div>
      <p className="documents-intro">Add lecture notes so your tutor can ground answers in your course.</p>

      <form className="document-upload-form" onSubmit={(event) => void handleUpload(event)}>
        <div
          className={`upload-dropzone${selectedFile ? " has-file" : ""}`}
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            acceptDroppedFile(event.dataTransfer.files[0]);
          }}
        >
          <span className="upload-icon" aria-hidden="true">↑</span>
          <strong>{selectedFile ? selectedFile.name : "Drop a file here"}</strong>
          <span>or choose from your device</span>
          <label className="browse-button" htmlFor="tutor-lecture-file">Browse files</label>
          <input
            id="tutor-lecture-file"
            className="sr-only"
            type="file"
            accept=".pdf,.docx,.pptx,.txt,.md"
            disabled={busy}
            onChange={(event) => acceptDroppedFile(event.target.files?.[0])}
          />
        </div>
        <p className="documents-help">PDF, DOCX, PPTX, TXT, or MD · up to 20 MB</p>
        <button className="upload-submit" type="submit" disabled={busy || !selectedFile}>
          {action === "upload" ? "Uploading and processing…" : "Upload material"}
        </button>
      </form>

      {error && <p className="chat-error" role="alert">{error}</p>}
      {notice && <p className="success" role="status">{notice}</p>}

      <div className="documents-list-heading">
        <h3>Library</h3>
        {documents.length > 0 && <span>{documents.length}</span>}
      </div>
      {loading ? (
        <p className="documents-state" role="status">Loading documents…</p>
      ) : documents.length === 0 ? (
        <p className="documents-state">Your uploaded materials will appear here.</p>
      ) : (
        <ul className="document-list" aria-label="Uploaded documents">
          {documents.map((document) => (
            <li className="document-item" key={document.id}>
              <span className="document-file-icon" aria-hidden="true">▤</span>
              <div className="document-details">
                <strong title={document.original_filename}>{document.original_filename}</strong>
                <span>{formatDocumentSize(document.file_size)}</span>
                <span className={`status-badge status-${document.status}`}>{document.status}</span>
                {document.processing_error && <span className="document-error">{document.processing_error}</span>}
              </div>
              <button
                type="button"
                className="delete-document-button"
                onClick={() => void handleDelete(document)}
                disabled={busy}
                aria-label={`Delete ${document.original_filename}`}
                title={`Delete ${document.original_filename}`}
              >
                {action === "delete" ? "…" : "×"}
              </button>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}

function formatDocumentSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
