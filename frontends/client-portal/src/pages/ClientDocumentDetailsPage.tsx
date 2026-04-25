import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { downloadDocumentFile as downloadLegacyDocumentFile, fetchDocumentDetails } from "../api/documents";
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
  type ClientDocumentAckDetails as CanonicalClientDocumentAckDetails,
  type ClientDocumentDetails as CanonicalClientDocumentDetails,
  type ClientDocumentEdoState,
  type ClientDocumentRiskExplain,
  type ClientDocumentTimelineEvent,
  type ClientDocumentSignature,
} from "../api/client/documents";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { Toast } from "../components/Toast/Toast";
import { useToast } from "../components/Toast/useToast";
import { AppEmptyState, AppErrorState, AppLoadingState } from "../components/states";
import type {
  ClientDocumentAckDetails as LegacyClientDocumentAckDetails,
  ClientDocumentDetails as LegacyClientDocumentDetails,
  ClientDocumentEvent as LegacyClientDocumentEvent,
  ClientDocumentFile as LegacyClientDocumentFile,
} from "../types/documents";
import { getDocumentStatusLabel, getDocumentStatusTone, getDocumentTypeLabel } from "../utils/documents";

function formatSize(size: number): string {
  if (size > 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  if (size > 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${size} B`;
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString();
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function canDownloadLegacyFile(fileType: string): fileType is "PDF" | "XLSX" {
  return fileType === "PDF" || fileType === "XLSX";
}

function describeCanonicalAction(actionCode: string | null | undefined): string {
  if (actionCode === "SIGN") return "Подписать";
  if (actionCode === "SEND_TO_EDO") return "Отправить";
  if (actionCode === "UPLOAD_OR_SUBMIT") return "Подготовить";
  return "Требует действия";
}

function describeCanonicalFileKind(kind: string | null | undefined, mime: string): string {
  if (kind) return kind;
  if (mime === "application/pdf") return "PDF";
  if (mime === "application/vnd.ms-excel" || mime === "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet") {
    return "XLSX";
  }
  if (mime === "application/msword" || mime === "application/vnd.openxmlformats-officedocument.wordprocessingml.document") {
    return "DOC";
  }
  if (mime.startsWith("image/")) return "IMAGE";
  return "OTHER";
}

function describeLegacyEvent(event: LegacyClientDocumentEvent): string {
  if (event.action) {
    return `${event.event_type} · ${event.action}`;
  }
  return event.event_type;
}

function LegacyAckDetailsSection({ details }: { details: LegacyClientDocumentAckDetails | CanonicalClientDocumentAckDetails | null | undefined }) {
  if (!details) return null;
  return (
    <div style={{ margin: "12px 0", borderTop: "1px solid #eee", paddingTop: 12 }}>
      <h3>Acknowledgement</h3>
      <p>Acknowledged: {formatDateTime(details.ack_at)}</p>
      <p>Email: {details.ack_by_email ?? "?"}</p>
      <p>User: {details.ack_by_user_id ?? "?"}</p>
      <p>Method: {details.ack_method ?? "?"}</p>
    </div>
  );
}

function RiskExplainSection({ explain }: { explain: ClientDocumentRiskExplain | null | undefined }) {
  if (!explain) return null;
  return (
    <details style={{ margin: "12px 0" }}>
      <summary>Risk explain</summary>
      <pre style={{ marginTop: 8, whiteSpace: "pre-wrap", overflowX: "auto" }}>{JSON.stringify(explain, null, 2)}</pre>
    </details>
  );
}

// The same screen serves two owned contours on purpose:
// - legacy mode -> /documents* final closing-doc compatibility tail for detail/file/history UX
// - canonical mode -> /client/documents* canonical general docflow surface
// Keep the split explicit; do not route-flip legacy detail without an intentional product decision.
type ClientDocumentDetailsPageProps = {
  mode?: "legacy" | "canonical";
};

export function ClientDocumentDetailsPage({ mode = "canonical" }: ClientDocumentDetailsPageProps) {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const isLegacyMode = mode === "legacy";
  const backLink = isLegacyMode ? "/documents" : "/client/documents";
  const [document, setDocument] = useState<CanonicalClientDocumentDetails | null>(null);
  const [legacyDocument, setLegacyDocument] = useState<LegacyClientDocumentDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorCode, setErrorCode] = useState<number | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
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
    setErrorCode(null);
    setDocument(null);
    setLegacyDocument(null);
    setTimeline([]);
    setEdoState(null);
    setSignatures([]);
    setActiveTab("files");

    if (isLegacyMode) {
      fetchDocumentDetails(id, user)
        .then((details) => {
          setLegacyDocument(details);
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
      return;
    }

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
  }, [id, user, navigate, isLegacyMode, reloadKey]);

  useEffect(() => {
    if (isLegacyMode || !id || !edoState) return;
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
  }, [id, user, edoState?.edo_status, isLegacyMode]);

  const onUpload = async (file: File | null) => {
    if (!file || !id || isLegacyMode) return;
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
    if (!id || isLegacyMode) return;
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
    if (!id || isLegacyMode) return;
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

  const onSendToEdo = async () => {
    if (!id || isLegacyMode) return;
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

  const describeEvent = (event: ClientDocumentTimelineEvent): string => {
    if (event.event_type === "DOCUMENT_CREATED") return "Документ создан";
    if (event.event_type === "FILE_UPLOADED") return `Файл загружен: ${String(event.meta.filename ?? "—")}`;
    if (event.event_type === "STATUS_CHANGED") {
      return `Статус изменён: ${String(event.meta.from ?? "—")} → ${String(event.meta.to ?? "—")}`;
    }
    if (event.event_type === "SIGNED_CLIENT") return "Документ подписан клиентом";
    return event.event_type;
  };

  const backAction = (
    <div className="actions">
      <Link className="ghost" to={backLink}>
        Назад к списку
      </Link>
    </div>
  );

  if (!id) return <AppEmptyState title="Документ не найден" description="Проверьте идентификатор в ссылке." action={backAction} />;
  if (loading) return <AppLoadingState label="Загружаем документ..." />;
  if (errorCode === 404) {
    return <AppEmptyState title="Документ не найден" description="Документ больше не доступен в этом контуре." action={backAction} />;
  }
  if (errorCode) {
    return (
      <AppErrorState
        message="Не удалось загрузить документ."
        status={errorCode}
        onRetry={() => setReloadKey((value) => value + 1)}
      />
    );
  }

  if (isLegacyMode) {
    if (!legacyDocument) {
      return <AppEmptyState title="Документ не найден" description="Legacy detail больше не вернул документ по этому идентификатору." action={backAction} />;
    }

    return (
      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <div>
            <h2>{getDocumentTypeLabel(legacyDocument.document_type)}</h2>
            <div className="muted small">{legacyDocument.number ?? legacyDocument.id}</div>
          </div>
          <Link to={backLink}>Назад</Link>
        </div>
        <p>
          Статус:{" "}
          <span className={`pill pill--${getDocumentStatusTone(legacyDocument.status)}`}>
            {getDocumentStatusLabel(legacyDocument.status)}
          </span>
        </p>
        <p>Период: {formatDate(legacyDocument.period_from)} — {formatDate(legacyDocument.period_to)}</p>
        <p>Версия: {legacyDocument.version}</p>
        <p>Номер: {legacyDocument.number ?? "—"}</p>
        <p>Создан: {formatDateTime(legacyDocument.created_at)}</p>
        <p>Сформирован: {formatDateTime(legacyDocument.generated_at)}</p>
        <p>Отправлен: {formatDateTime(legacyDocument.sent_at)}</p>
        <p>Подтверждён: {formatDateTime(legacyDocument.ack_at)}</p>
        <p>Хэш документа: {legacyDocument.document_hash ?? "—"}</p>
        {legacyDocument.risk ? <p>Risk state: {legacyDocument.risk.state}</p> : null}

        <LegacyAckDetailsSection details={legacyDocument.ack_details} />

        <div style={{ margin: "12px 0", display: "flex", gap: 8 }}>
          <button type="button" className={activeTab === "files" ? "secondary" : "ghost"} onClick={() => setActiveTab("files")}>
            Файлы
          </button>
          <button type="button" className={activeTab === "history" ? "secondary" : "ghost"} onClick={() => setActiveTab("history")}>
            История
          </button>
        </div>

        {activeTab === "files" ? (
          legacyDocument.files.length ? (
            <table>
              <thead>
                <tr>
                  <th>Тип</th>
                  <th>Размер</th>
                  <th>Создан</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {legacyDocument.files.map((file: LegacyClientDocumentFile) => {
                  const downloadType = file.file_type;
                  return (
                    <tr key={`${file.file_type}-${file.created_at}-${file.sha256}`}>
                      <td>{file.file_type}</td>
                      <td>{formatSize(file.size_bytes)}</td>
                      <td>{formatDateTime(file.created_at)}</td>
                      <td>
                        {canDownloadLegacyFile(downloadType) ? (
                          <button type="button" onClick={() => void downloadLegacyDocumentFile(legacyDocument.id, downloadType, user)}>
                            Download
                          </button>
                        ) : (
                          <span className="muted small">Недоступно</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          ) : (
            <AppEmptyState
              title="Файлы пока не появились"
              description="Legacy closing-doc tail ещё не вернул ни одного файла для этого документа."
            />
          )
        ) : null}

        {activeTab === "history" ? (
          legacyDocument.events.length ? (
            <ul>
              {legacyDocument.events.map((event: LegacyClientDocumentEvent) => (
                <li key={event.id}>
                  <strong>{describeLegacyEvent(event)}</strong>
                  <div className="muted small">{formatDateTime(event.ts)}</div>
                </li>
              ))}
            </ul>
          ) : (
            <AppEmptyState
              title="История пока пуста"
              description="События появятся здесь после обработки, подтверждения или загрузки файлов."
            />
          )
        ) : null}
      </div>
    );
  }

  if (!document) {
    return <AppEmptyState title="Документ не найден" description="Canonical detail surface не вернул документ по этому идентификатору." action={backAction} />;
  }

  const currentStatus = document.status;
  const statusLabel =
    currentStatus === "READY_TO_SEND"
      ? "Готов к отправке"
      : currentStatus === "READY_TO_SIGN"
        ? "Готов к подписи"
        : currentStatus === "SIGNED_CLIENT" || currentStatus === "CLOSED"
          ? "Подписан"
          : "Черновик";
  const canSubmit = document.direction === "OUTBOUND" && document.status === "DRAFT";
  const canSign = document.direction === "INBOUND" && document.status === "READY_TO_SIGN";
  const isSigned = document.status === "SIGNED_CLIENT" || document.status === "CLOSED";

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <h2>{document.title}</h2>
        <Link to={backLink}>Назад</Link>
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
      <p>Action needed: {document.requires_action ? describeCanonicalAction(document.action_code) : "No"}</p>
      <p>Acknowledged: {formatDateTime(document.ack_at)}</p>
      <p>Document hash: {document.document_hash_sha256 ?? "-"}</p>
      {document.risk ? <p>Risk state: {document.risk.state}</p> : null}
      <LegacyAckDetailsSection details={document.ack_details} />
      <RiskExplainSection explain={document.risk_explain} />

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

      {activeTab === "files" ? (
        document.files.length ? (
          <table>
            <thead>
              <tr>
                <th>Файл</th>
                <th>Type</th>
                <th>Размер</th>
                <th>Создан</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {document.files.map((file) => (
                <tr key={file.id}>
                  <td>{file.filename}</td>
                  <td>{describeCanonicalFileKind(file.kind, file.mime)}</td>
                  <td>{formatSize(file.size)}</td>
                  <td>{new Date(file.created_at).toLocaleString()}</td>
                  <td>
                    <button type="button" onClick={() => void downloadClientDocumentFile(file.id, user)}>Download</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <AppEmptyState
            title="Файлов пока нет"
            description="Загрузите файл или дождитесь, пока owner contour добавит вложения. Именно здесь появится рабочий список файлов."
          />
        )
      ) : null}

      {activeTab === "history" ? (
        timeline.length ? (
          <ul>
            {timeline.map((event) => (
              <li key={event.id}>
                <strong>{describeEvent(event)}</strong>
                <div className="muted small">{new Date(event.created_at).toLocaleString()}</div>
              </li>
            ))}
          </ul>
        ) : (
          <AppEmptyState
            title="История пока пуста"
            description="Timeline появится после загрузки файлов, подготовки, подписи или отправки в ЭДО."
          />
        )
      ) : null}
      <Toast toast={toast} onClose={() => showToast(null)} />
    </div>
  );
}
