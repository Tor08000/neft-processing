import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  downloadClientDocumentFile,
  getClientDocument,
  getClientDocumentEdoState,
  getClientDocumentTimeline,
  sendClientDocument,
  signClientDocument,
  listClientDocumentSignatures,
  submitClientDocument,
  uploadClientDocumentFile,
  type ClientDocumentDetails,
  type ClientDocumentEdoState,
  type ClientDocumentTimelineEvent,
  type ClientDocumentSignature,
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
  const [edoState, setEdoState] = useState<ClientDocumentEdoState | null>(null);
  const [signatures, setSignatures] = useState<ClientDocumentSignature[]>([]);
  const [signing, setSigning] = useState(false);
  const [confirmChecked, setConfirmChecked] = useState(false);
  const [signerFullName, setSignerFullName] = useState("");
  const [signerPosition, setSignerPosition] = useState("");
  const [sendingToEdo, setSendingToEdo] = useState(false);
  const [activeTab, setActiveTab] = useState<"files" | "history">("files");
  const { toast, showToast } = useToast();

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    Promise.all([
      getClientDocument(id, user),
      getClientDocumentTimeline(id, user),
      getClientDocumentEdoState(id, user),
      listClientDocumentSignatures(id, user),
    ])
      .then(([d, events, edo, signs]) => {
        setDocument(d);
        setTimeline(events);
        setEdoState(edo);
        setSignatures(signs);
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



  useEffect(() => {
    if (!id || !edoState) return;
    const terminal = new Set(["DELIVERED", "SIGNED", "REJECTED"]);
    if (terminal.has(edoState.edo_status)) return;
    const interval = window.setInterval(() => {
      void getClientDocumentEdoState(id, user)
        .then((state) => {
          setEdoState(state);
        })
        .catch(() => undefined);
    }, 15000);
    return () => window.clearInterval(interval);
  }, [id, user, edoState?.edo_status]);

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


  const onSign = async () => {
    if (!id) return;
    setSigning(true);
    try {
      await signClientDocument(
        id,
        {
          consent_text_version: "v1",
          checkbox_confirmed: confirmChecked,
          signer_full_name: signerFullName || undefined,
          signer_position: signerPosition || undefined,
        },
        user,
      );
      const [updated, events, signs] = await Promise.all([
        getClientDocument(id, user),
        getClientDocumentTimeline(id, user),
        listClientDocumentSignatures(id, user),
      ]);
      setDocument(updated);
      setTimeline(events);
      setSignatures(signs);
      showToast({ kind: "success", text: "Документ подписан" });
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409 && err.detail === "DOC_NOT_READY_TO_SIGN") {
          showToast({ kind: "error", text: "Документ ещё не готов к подписи" });
        } else if (err.status === 409 && err.detail === "SIGN_NOT_ALLOWED_FOR_OUTBOUND") {
          showToast({ kind: "error", text: "Подписание доступно только для входящих документов" });
        } else {
          showToast({ kind: "error", text: "Не удалось подписать документ" });
        }
      }
    } finally {
      setSigning(false);
    }
  };

  const currentStatus = document?.status;
  const statusLabel =
    currentStatus === "READY_TO_SEND"
      ? "Готов к отправке"
      : currentStatus === "READY_TO_SIGN"
        ? "Готов к подписи"
        : currentStatus === "SIGNED_CLIENT" || currentStatus === "CLOSED"
          ? "Подписан"
          : "Черновик";

  const onSendToEdo = async () => {
    if (!id) return;
    setSendingToEdo(true);
    try {
      const state = await sendClientDocument(id, user);
      setEdoState(state);
      const refreshed = await getClientDocument(id, user);
      setDocument(refreshed);
    } catch (err) {
      if (err instanceof ApiError) {
        const payload = err.detail as { error_code?: string } | string;
        const code = typeof payload === "string" ? payload : payload?.error_code;
        if (code === "EDO_NOT_CONFIGURED") {
          showToast({ kind: "error", text: "ЭДО не настроен для production. Свяжитесь с менеджером." });
        } else {
          showToast({ kind: "error", text: "Не удалось отправить документ в ЭДО" });
        }
      }
    } finally {
      setSendingToEdo(false);
    }
  };

  const canSubmit = document?.direction === "OUTBOUND" && document?.status === "DRAFT";
  const canSign = document?.direction === "INBOUND" && document?.status === "READY_TO_SIGN";
  const isSigned = document?.status === "SIGNED_CLIENT" || document?.status === "CLOSED";

  const describeEvent = (event: ClientDocumentTimelineEvent): string => {
    if (event.event_type === "DOCUMENT_CREATED") return "Документ создан";
    if (event.event_type === "FILE_UPLOADED") return `Файл загружен: ${String(event.meta.filename ?? "—")}`;
    if (event.event_type === "STATUS_CHANGED") {
      return `Статус изменён: ${String(event.meta.from ?? "—")} → ${String(event.meta.to ?? "—")}`;
    }
    if (event.event_type === "SIGNED_CLIENT") return "Документ подписан клиентом";
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



      {canSign ? (
        <div style={{ margin: "12px 0", border: "1px solid #e5e7eb", borderRadius: 8, padding: 12 }}>
          <h3>Подпись</h3>
          <label style={{ display: "block", marginBottom: 8 }}>
            <input type="checkbox" checked={confirmChecked} onChange={(e) => setConfirmChecked(e.target.checked)} />
            {" "}Подтверждаю, что ознакомился и принимаю условия документа
          </label>
          <input
            placeholder="ФИО"
            value={signerFullName}
            onChange={(e) => setSignerFullName(e.target.value)}
            style={{ marginBottom: 8, width: "100%" }}
          />
          <input
            placeholder="Должность (опционально)"
            value={signerPosition}
            onChange={(e) => setSignerPosition(e.target.value)}
            style={{ marginBottom: 8, width: "100%" }}
          />
          <button type="button" disabled={!confirmChecked || signing} onClick={() => void onSign()}>
            {signing ? "Подписание…" : "Подписать"}
          </button>
        </div>
      ) : null}

      {isSigned ? (
        <div style={{ margin: "12px 0" }}>
          <strong>Подписано</strong>
          <div className="muted small">
            {signatures[0]?.signed_at ? new Date(signatures[0].signed_at).toLocaleString() : "—"}
            {signatures[0]?.signer_user_id ? ` · ${signatures[0].signer_user_id}` : ""}
          </div>
        </div>
      ) : null}

      {document.direction === "OUTBOUND" ? (
        <div style={{ margin: "12px 0" }}>
          <button type="button" onClick={() => void onSendToEdo()} disabled={sendingToEdo || document.status !== "READY_TO_SEND"}>
            {sendingToEdo ? "Отправка…" : "Отправить"}
          </button>
        </div>
      ) : null}

      <div style={{ margin: "12px 0", borderTop: "1px solid #eee", paddingTop: 12 }}>
        <h3>Статус ЭДО</h3>
        {edoState ? (
          <>
            <p>Провайдер: {edoState.provider ?? "—"} ({edoState.provider_mode})</p>
            <p>Статус: {edoState.edo_status}</p>
            <p>Обновлён: {edoState.last_status_at ? new Date(edoState.last_status_at).toLocaleString() : "—"}</p>
            {edoState.last_error_message ? <p className="muted">Ошибка: {edoState.last_error_message}</p> : null}
          </>
        ) : (
          <p className="muted">Ещё не отправлялся в ЭДО.</p>
        )}
      </div>

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
