import { type ChangeEvent, useEffect, useMemo, useState } from "react";
import { acknowledgeClosingDocument, downloadDocumentFile, fetchDocuments } from "../api/documents";
import { useAuth } from "../auth/AuthContext";
import { CopyButton } from "../components/CopyButton";
import type { ClientDocumentSummary } from "../types/documents";
import { formatDate } from "../utils/format";
import { getDocumentStatusLabel, getDocumentStatusTone, getDocumentTypeLabel } from "../utils/documents";

const DOCUMENT_TYPES = [
  { value: "", label: "Все типы" },
  { value: "INVOICE", label: "Счет" },
  { value: "ACT", label: "Акт" },
  { value: "RECONCILIATION_ACT", label: "Акт сверки" },
];

const STATUS_TYPES = [
  { value: "", label: "Все статусы" },
  { value: "GENERATED", label: "Сформирован" },
  { value: "SENT", label: "Отправлен" },
  { value: "ACKNOWLEDGED", label: "Подтвержден" },
  { value: "CANCELLED", label: "Отменен" },
];

const DEFAULT_LIMIT = 25;

export function ClosingDocumentsPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<ClientDocumentSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState({
    dateFrom: "",
    dateTo: "",
    documentType: "",
    status: "",
    limit: DEFAULT_LIMIT,
  });
  const [offset, setOffset] = useState(0);
  const [debouncedFilters, setDebouncedFilters] = useState(filters);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedFilters(filters), 450);
    return () => window.clearTimeout(timer);
  }, [filters]);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    fetchDocuments(user, {
      dateFrom: debouncedFilters.dateFrom || undefined,
      dateTo: debouncedFilters.dateTo || undefined,
      documentType: debouncedFilters.documentType || undefined,
      status: debouncedFilters.status || undefined,
      limit: debouncedFilters.limit,
      offset,
    })
      .then((resp) => {
        setItems(resp.items);
        setTotal(resp.total);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [debouncedFilters, offset, user]);

  const handleFilterChange = (evt: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = evt.target;
    setFilters((prev) => ({ ...prev, [name]: value }));
    setOffset(0);
  };

  const handleLimitChange = (evt: ChangeEvent<HTMLSelectElement>) => {
    setFilters((prev) => ({ ...prev, limit: Number(evt.target.value) }));
    setOffset(0);
  };

  const handleDownload = async (documentId: string, fileType: "PDF" | "XLSX") => {
    try {
      await downloadDocumentFile(documentId, fileType, user);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const handleAck = async (documentId: string) => {
    try {
      await acknowledgeClosingDocument(documentId, user);
      setItems((prev) =>
        prev.map((doc) => (doc.id === documentId ? { ...doc, status: "ACKNOWLEDGED" } : doc)),
      );
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const canAcknowledge = useMemo(() => {
    const roles = user?.roles ?? [];
    return roles.some((role) => ["CLIENT_OWNER", "CLIENT_ADMIN", "CLIENT_ACCOUNTANT"].includes(role));
  }, [user?.roles]);

  const totalRange = useMemo(() => {
    if (total === 0) {
      return "0";
    }
    const from = Math.min(offset + 1, total);
    const to = Math.min(offset + filters.limit, total);
    return `${from}-${to}`;
  }, [filters.limit, offset, total]);

  if (error) {
    return (
      <div className="card error" role="alert">
        {error}
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card__header">
        <div>
          <h2>Закрывающие документы</h2>
          <p className="muted">Пакет документов за период с хешем и версиями.</p>
        </div>
      </div>

      <div className="filters">
        <div className="filter">
          <label htmlFor="dateFrom">Период с</label>
          <input
            id="dateFrom"
            name="dateFrom"
            type="date"
            value={filters.dateFrom}
            onChange={handleFilterChange}
          />
        </div>
        <div className="filter">
          <label htmlFor="dateTo">Период по</label>
          <input id="dateTo" name="dateTo" type="date" value={filters.dateTo} onChange={handleFilterChange} />
        </div>
        <div className="filter">
          <label htmlFor="documentType">Тип</label>
          <select id="documentType" name="documentType" value={filters.documentType} onChange={handleFilterChange}>
            {DOCUMENT_TYPES.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
        <div className="filter">
          <label htmlFor="status">Статус</label>
          <select id="status" name="status" value={filters.status} onChange={handleFilterChange}>
            {STATUS_TYPES.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
        <div className="filter">
          <label htmlFor="limit">Лимит</label>
          <select id="limit" value={filters.limit} onChange={handleLimitChange}>
            {[25, 50].map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </div>
      </div>

      {isLoading ? (
        <div className="skeleton-stack">
          <div className="skeleton-line" />
          <div className="skeleton-line" />
          <div className="skeleton-line" />
        </div>
      ) : items.length === 0 ? (
        <div className="empty-state">
          <p className="muted">Документы не найдены.</p>
          <p className="muted small">Проверьте период или тип документа.</p>
          <div className="actions">
            <button
              type="button"
              className="ghost"
              onClick={() => setFilters((prev) => ({ ...prev, documentType: "", status: "" }))}
            >
              Сбросить фильтры
            </button>
            <button type="button" className="ghost" onClick={() => setOffset(0)}>
              Обновить
            </button>
          </div>
        </div>
      ) : (
        <>
          <table className="table">
            <thead>
              <tr>
                <th>Документ</th>
                <th>Период</th>
                <th>Версия</th>
                <th>Статус</th>
                <th>SHA256</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              {items.map((doc) => (
                <tr key={doc.id}>
                  <td>{getDocumentTypeLabel(doc.document_type)}</td>
                  <td>
                    {formatDate(doc.period_from)} — {formatDate(doc.period_to)}
                  </td>
                  <td>v{doc.version}</td>
                  <td>
                    <span className={`pill pill--${getDocumentStatusTone(doc.status)}`}>
                      {getDocumentStatusLabel(doc.status)}
                    </span>
                  </td>
                  <td>
                    <div className="stack-inline">
                      <span className="muted small">{doc.pdf_hash ? `${doc.pdf_hash.slice(0, 10)}…` : "—"}</span>
                      <CopyButton value={doc.pdf_hash ?? undefined} label="Скопировать" />
                    </div>
                  </td>
                  <td>
                    <div className="actions">
                      <button type="button" className="ghost" onClick={() => handleDownload(doc.id, "PDF")}>
                        PDF
                      </button>
                      <button type="button" className="ghost" onClick={() => handleDownload(doc.id, "XLSX")}>
                        XLSX
                      </button>
                      {canAcknowledge && doc.status !== "ACKNOWLEDGED" ? (
                        <button type="button" className="ghost" onClick={() => handleAck(doc.id)}>
                          Подтвердить
                        </button>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="table-footer">
            <div className="muted">
              Показаны {totalRange} из {total}
            </div>
            <div className="actions">
              <button
                type="button"
                className="ghost"
                disabled={offset === 0}
                onClick={() => setOffset((prev) => Math.max(prev - filters.limit, 0))}
              >
                Назад
              </button>
              <button
                type="button"
                className="ghost"
                disabled={offset + filters.limit >= total}
                onClick={() => setOffset((prev) => prev + filters.limit)}
              >
                Далее
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
