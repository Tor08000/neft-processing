import { type ChangeEvent, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchClientInvoices } from "../api/portal";
import { useAuth } from "../auth/AuthContext";
import type { ClientInvoiceSummary } from "../types/portal";
import { Table } from "../components/common/Table";
import { formatDate } from "../utils/format";
import { MoneyValue } from "../components/common/MoneyValue";
import { getInvoiceStatusLabel, getInvoiceStatusTone } from "../utils/invoices";

const STATUS_OPTIONS = [
  { value: "ISSUED", label: "Выставлен" },
  { value: "PAID", label: "Оплачен" },
  { value: "OVERDUE", label: "Просрочен" },
  { value: "VOID", label: "Аннулирован" },
];

const DEFAULT_LIMIT = 25;
const DEFAULT_FILTERS = {
  dateFrom: "",
  dateTo: "",
  status: [] as string[],
  limit: DEFAULT_LIMIT,
};

export function ClientInvoicesPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<ClientInvoiceSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
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
    fetchClientInvoices(user, {
      dateFrom: debouncedFilters.dateFrom || undefined,
      dateTo: debouncedFilters.dateTo || undefined,
      status: debouncedFilters.status.length > 0 ? debouncedFilters.status : undefined,
      limit: debouncedFilters.limit,
      offset,
    })
      .then((resp) => {
        setItems(resp.items ?? []);
        setTotal(resp.total ?? 0);
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
    setFilters((prev) => ({ ...prev, status: ["ISSUED", "OVERDUE"] }));
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

  const handleDownload = (invoice: ClientInvoiceSummary) => {
    if (!invoice.download_url) return;
    window.open(invoice.download_url, "_blank", "noopener");
  };

  const filtersActive = filters.dateFrom !== "" || filters.dateTo !== "" || filters.status.length > 0;

  const handleResetFilters = () => {
    setFilters(DEFAULT_FILTERS);
    setOffset(0);
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
        <div className="filter">
          <button type="button" className="secondary neft-btn-secondary" onClick={handleResetFilters} disabled={!filtersActive}>
            Сбросить
          </button>
        </div>
      </div>

      <Table
        data={items}
        loading={isLoading}
        columns={[
          {
            key: "number",
            title: "Номер",
            render: (invoice) => <span>{invoice.id}</span>,
          },
          {
            key: "period",
            title: "Период",
            render: (invoice) => `${formatDate(invoice.period_start)} — ${formatDate(invoice.period_end)}`,
          },
          {
            key: "amount_total",
            title: "Сумма",
            className: "neft-num",
            render: (invoice) => (
              <MoneyValue amount={invoice.amount_total ?? 0} currency={invoice.currency ?? undefined} />
            ),
          },
          {
            key: "status",
            title: "Статус",
            render: (invoice) => (
              <span className={`neft-chip neft-chip-${getInvoiceStatusTone(invoice.status)}`}>
                {getInvoiceStatusLabel(invoice.status)}
              </span>
            ),
          },
          {
            key: "due_at",
            title: "Срок",
            render: (invoice) => (invoice.due_at ? formatDate(invoice.due_at) : "—"),
          },
          {
            key: "actions",
            title: "",
            render: (invoice) => (
              <div className="actions">
                {invoice.id ? (
                  <Link to={`/invoices/${invoice.id}`} className="ghost">
                    Открыть
                  </Link>
                ) : (
                  <span className="muted">Недоступно</span>
                )}
                <button
                  type="button"
                  className="ghost"
                  onClick={() => handleDownload(invoice)}
                  disabled={!invoice.download_url}
                >
                  Скачать PDF
                </button>
              </div>
            ),
          },
        ]}
        emptyState={{
          title: "Счета не найдены",
          description: filtersActive ? "Попробуйте изменить фильтры или период." : "Попробуйте обновить список позже.",
          actionLabel: filtersActive ? "Сбросить фильтры" : "Обновить",
          actionOnClick: filtersActive ? handleResetFilters : () => setFilters((prev) => ({ ...prev })),
        }}
      />

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
