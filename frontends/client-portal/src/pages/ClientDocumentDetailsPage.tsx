import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  downloadClientDocumentFile,
  getClientDocument,
  getClientDocumentTimeline,
  submitClientDocument,
  uploadClientDocumentFile,
  type ClientDocumentDetails,
  type ClientDocumentTimelineEvent,
} from "../api/client/documents";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { Toast } from "../components/Toast/Toast";
import { useToast } from "../components/Toast/useToast";

function formatSize(size: number): string {
  if (size > 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  if (size > 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${size} B`;
}

export function ClientDocumentDetailsPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [document, setDocument] = useState<ClientDocumentDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorCode, setErrorCode] = useState<number | null>(null);
  const [uploading, setUploading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [timeline, setTimeline] = useState<ClientDocumentTimelineEvent[]>([]);
  const [activeTab, setActiveTab] = useState<"files" | "history">("files");
  const { toast, showToast } = useToast();

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    Promise.all([getClientDocument(id, user), getClientDocumentTimeline(id, user)])
      .then(([d, events]) => {
        setDocument(d);
        setTimeline(events);
        setErrorCode(null);
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError) {
          if (err.status === 401) {
            navigate("/login", { replace: true });
            return;
          }
          setErrorCode(err.status);
          return;
        }
        setErrorCode(500);
      })
      .finally(() => setLoading(false));
  }, [id, user, navigate]);

  const onUpload = async (file: File | null) => {
    if (!file || !id) return;
    setUploading(true);
    try {
      const created = await uploadClientDocumentFile(id, file, user);
      setDocument((prev) => (prev ? { ...prev, files: [created, ...prev.files] } : prev));
      const events = await getClientDocumentTimeline(id, user);
      setTimeline(events);
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorCode(err.status);
      } else {
        setErrorCode(500);
      }
    } finally {
      setUploading(false);
    }
  };

  const onSubmit = async () => {
    if (!id) return;
    setSubmitting(true);
    try {
      const updated = await submitClientDocument(id, user);
      const events = await getClientDocumentTimeline(id, user);
      setDocument(updated);
      setTimeline(events);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        if (err.detail === "missing_files") {
          showToast({ kind: "error", text: "Сначала загрузите файл" });
        } else if (err.detail === "already_submitted") {
          showToast({ kind: "error", text: "Уже подготовлен" });
        }
      }
    } finally {
      setSubmitting(false);
    }
  };

  const statusLabel = document.status === "READY_TO_SEND" ? "Готов к отправке" : "Черновик";
  const canSubmit = document.direction === "OUTBOUND" && document.status === "DRAFT";

  const describeEvent = (event: ClientDocumentTimelineEvent): string => {
    if (event.event_type === "DOCUMENT_CREATED") return "Документ создан";
    if (event.event_type === "FILE_UPLOADED") return `Файл загружен: ${String(event.meta.filename ?? "—")}`;
    if (event.event_type === "STATUS_CHANGED") {
      return `Статус изменён: ${String(event.meta.from ?? "—")} → ${String(event.meta.to ?? "—")}`;
    }
    return event.event_type;
  };

  if (!id) return <div className="card">Документ не найден</div>;
  if (loading) return <div className="card">Загрузка…</div>;
  if (errorCode === 404) return <div className="card">Документ не найден</div>;
  if (errorCode) return <div className="card">Не удалось загрузить документ</div>;
  if (!document) return <div className="card">Документ не найден</div>;

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <h2>{document.title}</h2>
        <Link to="/client/documents">Назад</Link>
      </div>
      <p>Направление: {document.direction}</p>
      <p>
        Статус:{" "}
        <span className="pill" style={{ background: document.status === "READY_TO_SEND" ? "#dcfce7" : "#fef3c7" }}>
          {statusLabel}
        </span>
      </p>
      <p>Тип: {document.doc_type ?? "—"}</p>
      <p>Описание: {document.description ?? "—"}</p>

      {canSubmit ? (
        <div style={{ margin: "12px 0" }}>
          <button type="button" onClick={() => void onSubmit()} disabled={submitting || document.files.length === 0}>
            Подготовить к отправке
          </button>
          {document.files.length === 0 ? <span className="muted small"> Загрузите хотя бы один файл</span> : null}
        </div>
      ) : null}

      <div style={{ margin: "12px 0", display: "flex", gap: 8 }}>
        <button type="button" className={activeTab === "files" ? "secondary" : "ghost"} onClick={() => setActiveTab("files")}>
          Файлы
        </button>
        <button type="button" className={activeTab === "history" ? "secondary" : "ghost"} onClick={() => setActiveTab("history")}>
          История
        </button>
      </div>

      {activeTab === "files" ? <div style={{ margin: "12px 0" }}>
        <label htmlFor="file-upload">Загрузить файл</label>
        <input
          id="file-upload"
          type="file"
          onChange={(e) => void onUpload(e.target.files?.[0] ?? null)}
          disabled={uploading}
        />
        {uploading ? <p>Загрузка файла…</p> : null}
      </div> : null}

      {activeTab === "files" ? <table>
        <thead>
          <tr>
            <th>Файл</th>
            <th>Размер</th>
            <th>Создан</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {document.files.map((file) => (
            <tr key={file.id}>
              <td>{file.filename}</td>
              <td>{formatSize(file.size)}</td>
              <td>{new Date(file.created_at).toLocaleString()}</td>
              <td>
                <button type="button" onClick={() => void downloadClientDocumentFile(file.id, user)}>Download</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table> : null}

      {activeTab === "history" ? (
        <ul>
          {timeline.map((event) => (
            <li key={event.id}>
              <strong>{describeEvent(event)}</strong>
              <div className="muted small">{new Date(event.created_at).toLocaleString()}</div>
            </li>
          ))}
        </ul>
      ) : null}
      <Toast toast={toast} onClose={() => showToast(null)} />
    </div>
  );
}
