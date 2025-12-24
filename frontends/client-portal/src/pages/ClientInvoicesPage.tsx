import { type ChangeEvent, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { downloadInvoicePdf, fetchInvoices } from "../api/invoices";
import { useAuth } from "../auth/AuthContext";
import type { ClientInvoiceSummary } from "../types/invoices";
import { CopyButton } from "../components/CopyButton";
import { formatDate, formatMoney } from "../utils/format";
import { getInvoiceStatusLabel, getInvoiceStatusTone } from "../utils/invoices";

const STATUS_OPTIONS = [
  { value: "SENT", label: "Выставлен" },
  { value: "PARTIALLY_PAID", label: "Частично оплачен" },
  { value: "PAID", label: "Оплачен" },
];

const DEFAULT_LIMIT = 25;

export function ClientInvoicesPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<ClientInvoiceSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState({
    dateFrom: "",
    dateTo: "",
    status: [] as string[],
    limit: DEFAULT_LIMIT,
    sort: "issued_at:desc",
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
    fetchInvoices(user, {
      dateFrom: debouncedFilters.dateFrom || undefined,
      dateTo: debouncedFilters.dateTo || undefined,
      status: debouncedFilters.status.length > 0 ? debouncedFilters.status : undefined,
      limit: debouncedFilters.limit,
      offset,
      sort: debouncedFilters.sort,
    })
      .then((resp) => {
        setItems(resp.items);
        setTotal(resp.total);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [debouncedFilters, offset, user]);

  const handleFilterChange = (evt: ChangeEvent<HTMLInputElement>) => {
    const { name, value } = evt.target;
    setFilters((prev) => ({ ...prev, [name]: value }));
    setOffset(0);
  };

  const toggleStatus = (value: string) => {
    setFilters((prev) => {
      const exists = prev.status.includes(value);
      const status = exists ? prev.status.filter((item) => item !== value) : [...prev.status, value];
      return { ...prev, status };
    });
    setOffset(0);
  };

  const handleLimitChange = (evt: ChangeEvent<HTMLSelectElement>) => {
    setFilters((prev) => ({ ...prev, limit: Number(evt.target.value) }));
    setOffset(0);
  };

  const handleQuickUnpaid = () => {
    setFilters((prev) => ({ ...prev, status: ["SENT", "PARTIALLY_PAID"] }));
    setOffset(0);
  };

  const handleQuickMonth = () => {
    const now = new Date();
    const firstDay = new Date(now.getFullYear(), now.getMonth(), 1);
    const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0);
    const toDateValue = (date: Date) => date.toISOString().slice(0, 10);
    setFilters((prev) => ({
      ...prev,
      dateFrom: toDateValue(firstDay),
      dateTo: toDateValue(lastDay),
    }));
    setOffset(0);
  };

  const handleDownload = async (invoiceId: string) => {
    try {
      await downloadInvoicePdf(invoiceId, user);
    } catch (err) {
      setError((err as Error).message);
    }
  };

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
          <h2>Инвойсы</h2>
          <p className="muted">Просматривайте выставленные счета и состояние оплат.</p>
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
          <label>Статус</label>
          <div className="status-grid">
            {STATUS_OPTIONS.map((opt) => (
              <label key={opt.value} className="checkbox">
                <input
                  type="checkbox"
                  checked={filters.status.includes(opt.value)}
                  onChange={() => toggleStatus(opt.value)}
                />
                {opt.label}
              </label>
            ))}
          </div>
        </div>
        <div className="filter quick-filters">
          <button type="button" className="ghost" onClick={handleQuickUnpaid}>
            Только неоплаченные
          </button>
          <button type="button" className="ghost" onClick={handleQuickMonth}>
            За этот месяц
          </button>
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
          <p className="muted">Счета не найдены.</p>
          <p className="muted small">Попробуйте изменить фильтры или выбрать другой период.</p>
        </div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Номер</th>
              <th>Дата</th>
              <th>Статус</th>
              <th>Сумма</th>
              <th>Оплачено</th>
              <th>Возвращено</th>
              <th>Остаток</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {items.map((invoice) => (
              <tr key={invoice.id}>
                <td>
                  <div className="stack-inline">
                    <span>{invoice.number}</span>
                    <CopyButton value={invoice.number} />
                  </div>
                </td>
                <td>{formatDate(invoice.issued_at)}</td>
                <td>
                  <span className={`pill ${getInvoiceStatusTone(invoice.status)}`}>
                    {getInvoiceStatusLabel(invoice.status)}
                  </span>
                </td>
                <td>{formatMoney(invoice.amount_total, invoice.currency)}</td>
                <td>{formatMoney(invoice.amount_paid, invoice.currency)}</td>
                <td>{formatMoney(invoice.amount_refunded, invoice.currency)}</td>
                <td className={Number(invoice.amount_due) > 0 ? "amount-due amount-due--positive" : "amount-due"}>
                  {formatMoney(invoice.amount_due, invoice.currency)}
                </td>
                <td>
                  <div className="actions">
                    <Link to={`/finance/invoices/${invoice.id}`} className="ghost">
                      Открыть
                    </Link>
                    <button type="button" className="ghost" onClick={() => handleDownload(invoice.id)}>
                      Скачать PDF
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="pagination">
        <div className="muted small">
          Показаны {totalRange} из {total}
        </div>
        <div className="actions">
          <button type="button" className="ghost" onClick={() => setOffset(Math.max(0, offset - filters.limit))} disabled={offset === 0}>
            Назад
          </button>
          <button
            type="button"
            className="ghost"
            onClick={() => setOffset(offset + filters.limit)}
            disabled={offset + filters.limit >= total}
          >
            Далее
          </button>
        </div>
      </div>
    </div>
  );
}
