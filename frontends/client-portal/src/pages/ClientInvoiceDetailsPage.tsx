import { type ChangeEvent, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { fetchInvoiceAudit, searchAuditByExternalRef } from "../api/audit";
import type { AuditFilters } from "../api/audit";
import { downloadInvoicePdf, fetchInvoiceDetails } from "../api/invoices";
import { useAuth } from "../auth/AuthContext";
import type { ClientAuditEvent, ClientInvoiceDetails } from "../types/invoices";
import { CopyButton } from "../components/CopyButton";
import { formatDate, formatDateTime, formatMoney } from "../utils/format";
import { getActorLabel, getAuditEventLabel } from "../utils/audit";
import { getInvoiceStatusLabel, getInvoiceStatusTone } from "../utils/invoices";

const EVENT_TYPE_OPTIONS = [
  { value: "INVOICE_CREATED", label: "Счет создан" },
  { value: "INVOICE_STATUS_CHANGED", label: "Статус счета изменен" },
  { value: "PAYMENT_POSTED", label: "Платеж принят" },
  { value: "PAYMENT_FAILED", label: "Платеж отклонен" },
  { value: "REFUND_POSTED", label: "Возврат выполнен" },
  { value: "INVOICE_PDF_DOWNLOADED", label: "PDF скачан" },
];

export function ClientInvoiceDetailsPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [invoice, setInvoice] = useState<ClientInvoiceDetails | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"details" | "payments" | "refunds" | "timeline">("details");
  const [auditItems, setAuditItems] = useState<ClientAuditEvent[]>([]);
  const [auditTotal, setAuditTotal] = useState(0);
  const [auditFilters, setAuditFilters] = useState<AuditFilters>({
    dateFrom: "",
    dateTo: "",
    eventType: [],
    limit: 50,
    offset: 0,
  });
  const [auditSearch, setAuditSearch] = useState("");
  const [auditLoading, setAuditLoading] = useState(false);

  useEffect(() => {
    if (!id) return;
    setIsLoading(true);
    setError(null);
    fetchInvoiceDetails(id, user)
      .then((data) => setInvoice(data))
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [id, user]);

  useEffect(() => {
    if (!invoice || activeTab !== "timeline") return;
    setAuditLoading(true);
    const timer = window.setTimeout(() => {
      const performFetch = async () => {
        const filters = {
          ...auditFilters,
          eventType: auditFilters.eventType && auditFilters.eventType.length > 0 ? auditFilters.eventType : undefined,
        };
        const auditResponse = auditSearch
          ? await searchAuditByExternalRef(user, { ...filters, externalRef: auditSearch })
          : await fetchInvoiceAudit(invoice.id, user, filters);
        if (!auditSearch) {
          setAuditItems(auditResponse.items);
          setAuditTotal(auditResponse.total);
          return;
        }
        const paymentIds = new Set(invoice.payments.map((payment) => payment.id));
        const refundIds = new Set(invoice.refunds.map((refund) => refund.id));
        const scoped = auditResponse.items.filter((item) => {
          if (item.entity_id === invoice.id) return true;
          if (paymentIds.has(item.entity_id)) return true;
          if (refundIds.has(item.entity_id)) return true;
          return false;
        });
        setAuditItems(scoped);
        setAuditTotal(scoped.length);
      };

      performFetch()
        .catch((err: Error) => setError(err.message))
        .finally(() => setAuditLoading(false));
    }, 350);

    return () => window.clearTimeout(timer);
  }, [activeTab, auditFilters, auditSearch, invoice, user]);

  const errorMessage = useMemo(() => {
    if (!error) return null;
    if (error.includes("invoice_not_found")) return "Документ не найден";
    if (error.includes("invoice_forbidden")) return "Нет доступа";
    return error;
  }, [error]);

  const handleDownload = async () => {
    if (!invoice) return;
    try {
      await downloadInvoicePdf(invoice.id, user);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const handleAuditFilterChange = (evt: ChangeEvent<HTMLInputElement>) => {
    const { name, value } = evt.target;
    setAuditFilters((prev) => ({ ...prev, [name]: value }));
  };

  const toggleAuditEventType = (value: string) => {
    setAuditFilters((prev) => {
      const exists = prev.eventType?.includes(value);
      const next = exists ? prev.eventType?.filter((item) => item !== value) : [...(prev.eventType ?? []), value];
      return { ...prev, eventType: next };
    });
  };

  const auditEmptyState = useMemo(() => {
    if (auditItems.length > 0) return null;
    const hasFilters =
      Boolean(auditFilters.dateFrom) ||
      Boolean(auditFilters.dateTo) ||
      Boolean(auditFilters.eventType && auditFilters.eventType.length > 0) ||
      Boolean(auditSearch);
    return hasFilters ? "Ничего не найдено по фильтрам" : "История пока пуста";
  }, [auditFilters.dateFrom, auditFilters.dateTo, auditFilters.eventType, auditItems.length, auditSearch]);

  if (error) {
    return (
      <div className="card error" role="alert">
        {errorMessage}
      </div>
    );
  }

  if (isLoading || !invoice) {
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

  return (
    <div className="card">
      <div className="card__header">
        <div>
          <div className="invoice-header">
            <h2>{invoice.number}</h2>
            <CopyButton value={invoice.number} />
          </div>
          <p className="muted">
            Дата {formatDate(invoice.issued_at)} ·{" "}
            <span className={`pill ${getInvoiceStatusTone(invoice.status)}`}>
              {getInvoiceStatusLabel(invoice.status)}
            </span>
          </p>
        </div>
        <button type="button" className="secondary" onClick={handleDownload} disabled={!invoice.pdf_available}>
          Скачать PDF
        </button>
      </div>

      <div className="tabs">
        <button
          type="button"
          className={`tab ${activeTab === "details" ? "active" : ""}`}
          onClick={() => setActiveTab("details")}
        >
          Детали
        </button>
        <button
          type="button"
          className={`tab ${activeTab === "payments" ? "active" : ""}`}
          onClick={() => setActiveTab("payments")}
        >
          Платежи
        </button>
        <button
          type="button"
          className={`tab ${activeTab === "refunds" ? "active" : ""}`}
          onClick={() => setActiveTab("refunds")}
        >
          Возвраты
        </button>
        <button
          type="button"
          className={`tab ${activeTab === "timeline" ? "active" : ""}`}
          onClick={() => setActiveTab("timeline")}
        >
          История
        </button>
      </div>

      {activeTab === "details" ? (
        <div className="stats-grid">
          <div className="stat">
            <div className="stat__label">Сумма</div>
            <div className="stat__value">{formatMoney(invoice.amount_total, invoice.currency)}</div>
          </div>
          <div className="stat">
            <div className="stat__label">Оплачено</div>
            <div className="stat__value">{formatMoney(invoice.amount_paid, invoice.currency)}</div>
          </div>
          <div className="stat">
            <div className="stat__label">Возвращено</div>
            <div className="stat__value">{formatMoney(invoice.amount_refunded, invoice.currency)}</div>
          </div>
          <div className="stat">
            <div className="stat__label">Остаток</div>
            <div className={`stat__value ${Number(invoice.amount_due) > 0 ? "amount-due--positive" : ""}`}>
              {formatMoney(invoice.amount_due, invoice.currency)}
            </div>
          </div>
        </div>
      ) : activeTab === "payments" ? (
        invoice.payments.length === 0 ? (
          <p className="muted">Платежей пока нет.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Дата</th>
                <th>Сумма</th>
                <th>Провайдер</th>
                <th>Ссылка</th>
                <th>Статус</th>
              </tr>
            </thead>
            <tbody>
              {invoice.payments.map((payment) => (
                <tr key={payment.id}>
                  <td>{formatDateTime(payment.created_at)}</td>
                  <td>{formatMoney(payment.amount, invoice.currency)}</td>
                  <td>{payment.provider ?? "—"}</td>
                  <td>
                    <div className="stack-inline">
                      <span>{payment.external_ref ?? "—"}</span>
                      <CopyButton value={payment.external_ref} />
                    </div>
                  </td>
                  <td>{payment.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )
      ) : activeTab === "refunds" ? (
        invoice.refunds.length === 0 ? (
          <p className="muted">Возвратов пока нет.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Дата</th>
                <th>Сумма</th>
                <th>Провайдер</th>
                <th>Ссылка</th>
                <th>Причина</th>
                <th>Статус</th>
              </tr>
            </thead>
            <tbody>
              {invoice.refunds.map((refund) => (
                <tr key={refund.id}>
                  <td>{formatDateTime(refund.created_at)}</td>
                  <td>{formatMoney(refund.amount, invoice.currency)}</td>
                  <td>{refund.provider ?? "—"}</td>
                  <td>
                    <div className="stack-inline">
                      <span>{refund.external_ref ?? "—"}</span>
                      <CopyButton value={refund.external_ref} />
                    </div>
                  </td>
                  <td>{refund.reason ?? "—"}</td>
                  <td>{refund.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )
      ) : (
        <div className="timeline">
          <div className="filters">
            <div className="filter">
              <label htmlFor="auditDateFrom">Период с</label>
              <input
                id="auditDateFrom"
                name="dateFrom"
                type="date"
                value={auditFilters.dateFrom ?? ""}
                onChange={handleAuditFilterChange}
              />
            </div>
            <div className="filter">
              <label htmlFor="auditDateTo">Период по</label>
              <input
                id="auditDateTo"
                name="dateTo"
                type="date"
                value={auditFilters.dateTo ?? ""}
                onChange={handleAuditFilterChange}
              />
            </div>
            <div className="filter">
              <label>Тип события</label>
              <div className="status-grid">
                {EVENT_TYPE_OPTIONS.map((option) => (
                  <label key={option.value} className="checkbox">
                    <input
                      type="checkbox"
                      checked={auditFilters.eventType?.includes(option.value) ?? false}
                      onChange={() => toggleAuditEventType(option.value)}
                    />
                    {option.label}
                  </label>
                ))}
              </div>
            </div>
            <div className="filter">
              <label htmlFor="auditSearch">Поиск external_ref</label>
              <input
                id="auditSearch"
                name="auditSearch"
                type="text"
                value={auditSearch}
                placeholder="BANK-123"
                onChange={(evt) => setAuditSearch(evt.target.value)}
              />
            </div>
          </div>

          {auditLoading ? (
            <div className="skeleton-stack">
              <div className="skeleton-line" />
              <div className="skeleton-line" />
              <div className="skeleton-line" />
            </div>
          ) : auditItems.length === 0 ? (
            <p className="muted">{auditEmptyState}</p>
          ) : (
            <div className="timeline-list">
              {auditItems.map((event) => (
                <div key={event.id} className="timeline-item">
                  <div className="timeline-item__meta">
                    <div className="muted small">{formatDateTime(event.ts)}</div>
                    <div className="timeline-item__title">{getAuditEventLabel(event.event_type)}</div>
                    <div className="muted small">{getActorLabel(event.actor_type)}</div>
                  </div>
                  <div className="timeline-item__body">
                    {event.after?.amount ? (
                      <div className="timeline-item__amount">
                        {formatMoney(event.after.amount as number | string, invoice.currency)}
                      </div>
                    ) : null}
                    {event.external_refs?.provider || event.external_refs?.external_ref ? (
                      <div className="timeline-item__refs">
                        <span>{event.external_refs?.provider ?? "—"}</span>
                        <span>{event.external_refs?.external_ref ?? "—"}</span>
                        <CopyButton value={event.external_refs?.external_ref} />
                      </div>
                    ) : null}
                    {event.after?.status ? (
                      <span className="pill pill--neutral">{String(event.after.status)}</span>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          )}
          <div className="muted small">Всего событий: {auditTotal}</div>
        </div>
      )}
    </div>
  );
}
