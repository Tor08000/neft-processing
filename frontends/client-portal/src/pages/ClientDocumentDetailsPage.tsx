import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { acknowledgeClosingDocument, downloadDocumentFile, fetchDocumentDetails } from "../api/documents";
import { useAuth } from "../auth/AuthContext";
import { CopyButton } from "../components/CopyButton";
import type { ClientDocumentDetails } from "../types/documents";
import { formatDate, formatDateTime } from "../utils/format";
import { getDocumentStatusLabel, getDocumentStatusTone, getDocumentTypeLabel } from "../utils/documents";

const LEGAL_TEXT =
  "Документ сформирован из данных системы и не изменяется после подтверждения. " +
  "Юридическая значимость фиксируется событиями, хешами и журналом аудита.";

export function ClientDocumentDetailsPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [document, setDocument] = useState<ClientDocumentDetails | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setIsLoading(true);
    setError(null);
    fetchDocumentDetails(id, user)
      .then((data) => setDocument(data))
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [id, user]);

  const canAcknowledge = useMemo(() => {
    const roles = user?.roles ?? [];
    return roles.some((role) => ["CLIENT_OWNER", "CLIENT_ADMIN"].includes(role));
  }, [user?.roles]);

  const handleDownload = async (fileType: "PDF" | "XLSX") => {
    if (!document) return;
    try {
      await downloadDocumentFile(document.id, fileType, user);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const handleAck = async () => {
    if (!document) return;
    try {
      const ack = await acknowledgeClosingDocument(document.id, user);
      setDocument((prev) =>
        prev
          ? {
              ...prev,
              status: "ACKNOWLEDGED",
              ack_at: ack.ack_at ?? prev.ack_at,
            }
          : prev,
      );
    } catch (err) {
      setError((err as Error).message);
    }
  };

  if (!id) {
    return (
      <div className="card error" role="alert">
        Документ не найден.
      </div>
    );
  }

  if (error) {
    return (
      <div className="card error" role="alert">
        {error}
      </div>
    );
  }

  if (isLoading || !document) {
    return (
      <div className="card">
        <div className="skeleton-stack">
          <div className="skeleton-line" />
          <div className="skeleton-line" />
          <div className="skeleton-line" />
        </div>
      </div>
    );
  }

  const risk = document.risk ?? null;
  const riskState = risk?.state ?? null;
  const riskDecisionId = risk?.decision_id ?? null;
  const riskDecidedAt = risk?.decided_at ?? null;
  const riskExplain = document.risk_explain ?? null;
  const riskThresholds = riskExplain?.thresholds ?? null;
  const riskFactors = riskExplain?.factors ?? null;
  const riskDecisionHash = riskExplain?.decision_hash ?? null;
  const riskPolicy = riskExplain?.policy ?? riskExplain?.policy_id ?? null;

  return (
    <div className="card">
      <div className="card__header">
        <div>
          <h2>{getDocumentTypeLabel(document.document_type)}</h2>
          <p className="muted">
            {formatDate(document.period_from)} — {formatDate(document.period_to)} · v{document.version}
          </p>
        </div>
        <Link className="ghost" to="/client/documents">
          Назад к списку
        </Link>
      </div>

      <div className="meta-grid">
        <div>
          <div className="label">Статус</div>
          <span className={`pill pill--${getDocumentStatusTone(document.status)}`}>
            {getDocumentStatusLabel(document.status)}
          </span>
        </div>
        <div>
          <div className="label">Номер</div>
          <div>{document.number ?? "—"}</div>
        </div>
        <div>
          <div className="label">Дата создания</div>
          <div>{formatDateTime(document.created_at)}</div>
        </div>
        <div>
          <div className="label">Дата подтверждения</div>
          <div>{document.ack_at ? formatDateTime(document.ack_at) : "—"}</div>
        </div>
        <div>
          <div className="label">Risk v4</div>
          <div>{document.risk?.state ?? "—"}</div>
        </div>
        <div>
          <div className="label">Hash документа</div>
          <div className="stack-inline">
            <span className="muted small">
              {document.document_hash ? `${document.document_hash.slice(0, 12)}…` : "—"}
            </span>
            <CopyButton value={document.document_hash ?? undefined} label="Скопировать" />
          </div>
        </div>
      </div>

      {risk ? (
        <div className="card__section">
          <h3>Risk v4</h3>
          <div className="meta-grid">
            <div>
              <div className="label">Статус</div>
              <div>{riskState ?? "—"}</div>
            </div>
            <div>
              <div className="label">Decision ID</div>
              <div>{riskDecisionId ?? "—"}</div>
            </div>
            <div>
              <div className="label">Дата решения</div>
              <div>{riskDecidedAt ? formatDateTime(riskDecidedAt) : "—"}</div>
            </div>
            <div>
              <div className="label">Decision hash</div>
              <div className="stack-inline">
                <span className="muted small">{riskDecisionHash ? `${riskDecisionHash.slice(0, 12)}…` : "—"}</span>
                <CopyButton
                  value={typeof riskDecisionHash === "string" ? riskDecisionHash : undefined}
                  label="Скопировать"
                />
              </div>
            </div>
          </div>
          {riskState === "BLOCK" ? (
            <span className="pill pill--danger">❌ Действие заблокировано</span>
          ) : riskState === "REQUIRE_OVERRIDE" ? (
            <span className="pill pill--warning">⚠️ Требуется override</span>
          ) : null}
          {riskExplain ? (
            <details>
              <summary>Explain</summary>
              <div className="meta-grid">
                <div>
                  <div className="label">Policy</div>
                  <div>{typeof riskPolicy === "string" ? riskPolicy : "—"}</div>
                </div>
                <div>
                  <div className="label">Thresholds</div>
                  {riskThresholds ? (
                    <ul className="bullets">
                      {Object.entries(riskThresholds).map(([key, value]) => (
                        <li key={key}>
                          {key}: {value}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div>—</div>
                  )}
                </div>
                <div>
                  <div className="label">Factors</div>
                  {Array.isArray(riskFactors) ? (
                    <ul className="bullets">
                      {riskFactors.map((factor) => (
                        <li key={factor}>{factor}</li>
                      ))}
                    </ul>
                  ) : (
                    <div>—</div>
                  )}
                </div>
              </div>
            </details>
          ) : null}
        </div>
      ) : null}

      {document.ack_details ? (
        <div className="card__section">
          <h3>Подтверждение</h3>
          <div className="meta-grid">
            <div>
              <div className="label">User ID</div>
              <div>{document.ack_details.ack_by_user_id ?? "—"}</div>
            </div>
            <div>
              <div className="label">Email</div>
              <div>{document.ack_details.ack_by_email ?? "—"}</div>
            </div>
            <div>
              <div className="label">IP</div>
              <div>{document.ack_details.ack_ip ?? "—"}</div>
            </div>
            <div>
              <div className="label">User Agent</div>
              <div>{document.ack_details.ack_user_agent ?? "—"}</div>
            </div>
            <div>
              <div className="label">Method</div>
              <div>{document.ack_details.ack_method ?? "—"}</div>
            </div>
            <div>
              <div className="label">Ack at</div>
              <div>{document.ack_details.ack_at ? formatDateTime(document.ack_details.ack_at) : "—"}</div>
            </div>
          </div>
        </div>
      ) : null}

      <div className="card__section">
        <h3>Файлы</h3>
        {document.files.length === 0 ? (
          <div className="muted">Файлы пока не опубликованы.</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Тип</th>
                <th>Размер</th>
                <th>SHA256</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              {document.files.map((file) => (
                <tr key={`${file.file_type}-${file.sha256}`}>
                  <td>{file.file_type}</td>
                  <td>{Math.round(file.size_bytes / 1024)} КБ</td>
                  <td>
                    <div className="stack-inline">
                      <span className="muted small">{file.sha256.slice(0, 12)}…</span>
                      <CopyButton value={file.sha256} label="Скопировать" />
                    </div>
                  </td>
                  <td>
                    <div className="actions">
                      {file.file_type === "PDF" ? (
                        <button type="button" className="ghost" onClick={() => handleDownload("PDF")}>
                          Скачать PDF
                        </button>
                      ) : null}
                      {file.file_type === "XLSX" ? (
                        <button type="button" className="ghost" onClick={() => handleDownload("XLSX")}>
                          Скачать XLSX
                        </button>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card__section">
        <h3>Подпись</h3>
        {document.signatures && document.signatures.length > 0 ? (
          <table className="table">
            <thead>
              <tr>
                <th>Статус</th>
                <th>Провайдер</th>
                <th>Дата</th>
                <th>Hash</th>
              </tr>
            </thead>
            <tbody>
              {document.signatures.map((signature) => (
                <tr key={signature.id}>
                  <td>{signature.status}</td>
                  <td>{signature.provider ?? "—"}</td>
                  <td>{signature.signed_at ? formatDateTime(signature.signed_at) : "—"}</td>
                  <td>
                    <div className="stack-inline">
                      <span className="muted small">
                        {signature.file_hash ? `${signature.file_hash.slice(0, 12)}…` : "—"}
                      </span>
                      <CopyButton value={signature.file_hash ?? undefined} label="Скопировать" />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="muted">Данных по подписи пока нет.</div>
        )}
      </div>

      <div className="card__section">
        <h3>ЭДО</h3>
        {document.edo_events && document.edo_events.length > 0 ? (
          <table className="table">
            <thead>
              <tr>
                <th>Статус</th>
                <th>Провайдер</th>
                <th>Дата</th>
                <th>Комментарий</th>
              </tr>
            </thead>
            <tbody>
              {document.edo_events.map((event) => (
                <tr key={event.id}>
                  <td>{event.status}</td>
                  <td>{event.provider ?? "—"}</td>
                  <td>{event.created_at ? formatDateTime(event.created_at) : "—"}</td>
                  <td>{event.message ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="muted">События ЭДО отсутствуют.</div>
        )}
      </div>

      <div className="card__section">
        <h3>Действия</h3>
        <div className="actions">
          {document.status === "ISSUED" && canAcknowledge ? (
            <button type="button" className="ghost" onClick={handleAck}>
              Подтвердить корректность
            </button>
          ) : null}
          <Link className="ghost" to="/actions">
            Перейти к действиям
          </Link>
        </div>
        <p className="muted small">{LEGAL_TEXT}</p>
      </div>

      <div className="card__section timeline">
        <h3>История событий</h3>
        {document.events.length === 0 ? (
          <div className="muted">Событий пока нет.</div>
        ) : (
          <div className="timeline-list">
            {document.events.map((event) => (
              <div className="timeline-item" key={event.id}>
                <div className="timeline-item__meta">
                  <span className="timeline-item__title">{event.event_type}</span>
                  <span className="muted small">{formatDateTime(event.ts)}</span>
                </div>
              <div className="timeline-item__body">
                <span className="muted small">Actor: {event.actor_type ?? "—"}</span>
                <span className="muted small">Actor ID: {event.actor_id ?? "—"}</span>
                <span className="muted small">Action: {event.action ?? "—"}</span>
                <span className="muted small">Hash: {event.hash ? `${event.hash.slice(0, 8)}…` : "—"}</span>
                <span className="muted small">Prev: {event.prev_hash ? `${event.prev_hash.slice(0, 8)}…` : "—"}</span>
              </div>
            </div>
          ))}
        </div>
      )}
      </div>
    </div>
  );
}
