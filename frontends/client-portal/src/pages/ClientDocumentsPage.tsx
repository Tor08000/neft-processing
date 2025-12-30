import { type ChangeEvent, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { acknowledgeClosingDocument, downloadDocumentFile, fetchDocuments } from "../api/documents";
import { useAuth } from "../auth/AuthContext";
import { AppEmptyState, AppErrorState, AppLoadingState } from "../components/states";
import type { ClientDocumentSummary } from "../types/documents";
import { formatDate, formatMoney } from "../utils/format";
import {
  getDocumentStatusLabel,
  getDocumentStatusTone,
  getDocumentTypeLabel,
  getEdoTone,
  getSignatureTone,
} from "../utils/documents";
import { canAccessFinance } from "../utils/roles";

const DOCUMENT_TYPES = [
  { value: "", label: "Все типы" },
  { value: "INVOICE", label: "Счет" },
  { value: "ACT", label: "Акт" },
  { value: "RECONCILIATION_ACT", label: "Акт сверки" },
  { value: "CLOSING_PACKAGE", label: "Закрывающий пакет (closing_package)" },
  { value: "OFFER", label: "Оферта" },
];

const STATUS_TYPES = [
  { value: "", label: "Все статусы" },
  { value: "DRAFT", label: "DRAFT" },
  { value: "ISSUED", label: "ISSUED" },
  { value: "ACKNOWLEDGED", label: "ACKNOWLEDGED" },
  { value: "FINALIZED", label: "FINALIZED" },
  { value: "VOID", label: "VOID" },
];

const SIGNATURE_TYPES = [
  { value: "", label: "Все" },
  { value: "signed", label: "Подписан" },
  { value: "pending", label: "Ожидает" },
];

const EDO_TYPES = [
  { value: "", label: "Все" },
  { value: "sent", label: "Отправлен" },
  { value: "delivered", label: "Доставлен" },
  { value: "failed", label: "Ошибка" },
  { value: "rejected", label: "Отклонен" },
];

const DEFAULT_LIMIT = 25;

export function ClientDocumentsPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<ClientDocumentSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState({
    dateFrom: "",
    dateTo: "",
    documentType: "",
    status: "",
    signature: "",
    edoStatus: "",
    requiresAction: "",
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
      acknowledged:
        debouncedFilters.signature === "signed"
          ? true
          : debouncedFilters.signature === "pending"
            ? false
            : undefined,
      limit: debouncedFilters.limit,
      offset,
    })
      .then((resp) => {
        const filtered =
          debouncedFilters.edoStatus || debouncedFilters.requiresAction
            ? resp.items.filter((item) => {
                const matchesEdo = debouncedFilters.edoStatus
                  ? item.edo_status === debouncedFilters.edoStatus
                  : true;
                const requiresAction =
                  debouncedFilters.requiresAction === "yes"
                    ? item.signature_status !== "signed" ||
                      item.edo_status === "failed" ||
                      item.edo_status === "rejected"
                    : true;
                return matchesEdo && requiresAction;
              })
            : resp.items;
        setItems(filtered);
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

  const canAcknowledge = useMemo(() => canAccessFinance(user), [user]);

  const totalRange = useMemo(() => {
    if (total === 0) {
      return "0";
    }
    const from = Math.min(offset + 1, total);
    const to = Math.min(offset + filters.limit, total);
    return `${from}-${to}`;
  }, [filters.limit, offset, total]);

  return (
    <div className="card">
      <div className="card__header">
        <div>
          <h2>Документы</h2>
          <p className="muted">Сформированные документы с юридическими статусами и файлами.</p>
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
          <label htmlFor="signature">Подписание</label>
          <select id="signature" name="signature" value={filters.signature} onChange={handleFilterChange}>
            {SIGNATURE_TYPES.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
        <div className="filter">
          <label htmlFor="edoStatus">EDO status</label>
          <select id="edoStatus" name="edoStatus" value={filters.edoStatus} onChange={handleFilterChange}>
            {EDO_TYPES.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
        <div className="filter">
          <label htmlFor="requiresAction">Requires action</label>
          <select
            id="requiresAction"
            name="requiresAction"
            value={filters.requiresAction}
            onChange={handleFilterChange}
          >
            <option value="">Все</option>
            <option value="yes">Требует действий</option>
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

      {isLoading ? <AppLoadingState /> : null}
      {error ? <AppErrorState message={error} /> : null}
      {!isLoading && !error && items.length === 0 ? (
        <AppEmptyState title="Документы не найдены" description="Проверьте период или тип документа." />
      ) : null}
      {!isLoading && !error && items.length > 0 ? (
        <>
          {Object.entries(
            items.reduce<Record<string, ClientDocumentSummary[]>>((acc, doc) => {
              const key = doc.period_from ? doc.period_from.slice(0, 7) : "Без периода";
              if (!acc[key]) acc[key] = [];
              acc[key].push(doc);
              return acc;
            }, {}),
          ).map(([period, docs]) => (
            <section className="card__section" key={period}>
              <h3>{period}</h3>
              <table className="table">
                <thead>
                  <tr>
                    <th>Тип</th>
                    <th>Период</th>
                    <th>Номер</th>
                    <th>Сумма</th>
                    <th>Lifecycle</th>
                    <th>Sign</th>
                    <th>EDO</th>
                    <th>Updated</th>
                    <th>Действия</th>
                  </tr>
                </thead>
                <tbody>
                  {docs.map((doc) => (
                    <tr key={doc.id}>
                      <td>{getDocumentTypeLabel(doc.document_type)}</td>
                      <td>
                        {formatDate(doc.period_from)} — {formatDate(doc.period_to)}
                      </td>
                      <td>{doc.number ?? "—"}</td>
                      <td>{doc.amount ? formatMoney(doc.amount) : "—"}</td>
                      <td>
                        <span className={`pill pill--${getDocumentStatusTone(doc.status)}`}>
                          {getDocumentStatusLabel(doc.status)}
                        </span>
                      </td>
                      <td>
                        <span className={`pill pill--${getSignatureTone(doc.signature_status)}`}>
                          {doc.signature_status ?? "—"}
                        </span>
                      </td>
                      <td>
                        <span className={`pill pill--${getEdoTone(doc.edo_status)}`}>{doc.edo_status ?? "—"}</span>
                      </td>
                      <td>{formatDate(doc.updated_at ?? doc.created_at)}</td>
                      <td>
                        <div className="actions">
                          <Link className="ghost" to={`/client/documents/${doc.id}`}>
                            Открыть
                          </Link>
                          {doc.status !== "DRAFT" ? (
                            <>
                              <button type="button" className="ghost" onClick={() => handleDownload(doc.id, "PDF")}>
                                PDF
                              </button>
                              <button type="button" className="ghost" onClick={() => handleDownload(doc.id, "XLSX")}>
                                XLSX
                              </button>
                            </>
                          ) : (
                            <span className="muted small">Файлы недоступны</span>
                          )}
                          {canAcknowledge && doc.status === "ISSUED" ? (
                            <button type="button" className="ghost" onClick={() => handleAck(doc.id)}>
                              Request sign
                            </button>
                          ) : null}
                          {canAcknowledge ? (
                            <button type="button" className="ghost" disabled>
                              Resend EDO
                            </button>
                          ) : null}
                          <button type="button" className="ghost" disabled>
                            View status timeline
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          ))}

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
      ) : null}
    </div>
  );
}
