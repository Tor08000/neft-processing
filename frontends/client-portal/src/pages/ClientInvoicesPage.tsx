import { type ChangeEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchInvoices } from "../api/invoices";
import { useAuth } from "../auth/AuthContext";
import type { ClientInvoiceSummary } from "../types/invoices";
import { formatDate, formatMoney } from "../utils/format";

const STATUS_OPTIONS = [
  { value: "", label: "Все" },
  { value: "ISSUED", label: "Выставлен" },
  { value: "PAID", label: "Оплачен" },
  { value: "CANCELLED", label: "Отменен" },
];

export function ClientInvoicesPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<ClientInvoiceSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState({ from: "", to: "", status: "" });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setIsLoading(true);
    fetchInvoices(user, {
      from: filters.from || undefined,
      to: filters.to || undefined,
      status: filters.status || undefined,
    })
      .then((resp) => {
        setItems(resp.items);
        setTotal(resp.total);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [filters, user]);

  const handleFilterChange = (evt: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = evt.target;
    setFilters((prev) => ({ ...prev, [name]: value }));
  };

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
          <h2>Счета</h2>
          <p className="muted">История выставленных счетов и статусы оплат.</p>
        </div>
      </div>

      <div className="filters">
        <div className="filter">
          <label htmlFor="from">Период с</label>
          <input id="from" name="from" type="date" value={filters.from} onChange={handleFilterChange} />
        </div>
        <div className="filter">
          <label htmlFor="to">Период по</label>
          <input id="to" name="to" type="date" value={filters.to} onChange={handleFilterChange} />
        </div>
        <div className="filter">
          <label htmlFor="status">Статус</label>
          <select id="status" name="status" value={filters.status} onChange={handleFilterChange}>
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {isLoading ? (
        <div className="muted">Загружаем счета...</div>
      ) : items.length === 0 ? (
        <p className="muted">Счета не найдены.</p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Период</th>
              <th>Сумма</th>
              <th>НДС</th>
              <th>Итого</th>
              <th>Статус</th>
              <th>Дата выставления</th>
              <th>Дата оплаты</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {items.map((invoice) => (
              <tr key={invoice.id}>
                <td>
                  {formatDate(invoice.period_from)} – {formatDate(invoice.period_to)}
                </td>
                <td>{formatMoney(invoice.total_amount, invoice.currency)}</td>
                <td>{formatMoney(invoice.tax_amount, invoice.currency)}</td>
                <td>{formatMoney(invoice.total_with_tax, invoice.currency)}</td>
                <td>{invoice.status}</td>
                <td>{invoice.issued_at ? formatDate(invoice.issued_at) : "—"}</td>
                <td>{invoice.paid_at ? formatDate(invoice.paid_at) : "—"}</td>
                <td>
                  <Link to={`/invoices/${invoice.id}`} className="ghost">
                    Открыть
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="muted small">Всего счетов: {total}</div>
    </div>
  );
}
