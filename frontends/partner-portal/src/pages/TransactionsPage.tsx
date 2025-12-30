import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchTransactions, type TransactionListItem, type TransactionFilters } from "../api/partner";
import { useAuth } from "../auth/AuthContext";
import { StatusBadge } from "../components/StatusBadge";
import { formatCurrency, formatDateTime, formatNumber } from "../utils/format";

const initialFilters: TransactionFilters = {
  periodStart: "",
  periodEnd: "",
  stationId: "",
  productType: "",
  status: "",
  amountMin: "",
  amountMax: "",
};

export function TransactionsPage() {
  const { user } = useAuth();
  const [filters, setFilters] = useState<TransactionFilters>(initialFilters);
  const [activeFilters, setActiveFilters] = useState<TransactionFilters>(initialFilters);
  const [items, setItems] = useState<TransactionListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    if (!user) return;
    setIsLoading(true);
    fetchTransactions(user.token, activeFilters)
      .then((data) => {
        if (active) {
          setItems(data.items ?? []);
        }
      })
      .catch((err) => {
        console.error(err);
        if (active) {
          setError("Не удалось загрузить операции");
        }
      })
      .finally(() => {
        if (active) {
          setIsLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [user, activeFilters]);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    setActiveFilters(filters);
  };

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <h2>Операции партнёра</h2>
          <span className="muted">Всего: {items.length}</span>
        </div>
        <form className="filters" onSubmit={handleSubmit}>
          <label className="filter">
            Период c
            <input
              type="date"
              value={filters.periodStart}
              onChange={(event) => setFilters((prev) => ({ ...prev, periodStart: event.target.value }))}
            />
          </label>
          <label className="filter">
            По
            <input
              type="date"
              value={filters.periodEnd}
              onChange={(event) => setFilters((prev) => ({ ...prev, periodEnd: event.target.value }))}
            />
          </label>
          <label className="filter">
            Station
            <input
              type="text"
              value={filters.stationId}
              onChange={(event) => setFilters((prev) => ({ ...prev, stationId: event.target.value }))}
              placeholder="ID станции"
            />
          </label>
          <label className="filter">
            Product type
            <input
              type="text"
              value={filters.productType}
              onChange={(event) => setFilters((prev) => ({ ...prev, productType: event.target.value }))}
              placeholder="Fuel / Services"
            />
          </label>
          <label className="filter">
            Status
            <select
              value={filters.status}
              onChange={(event) => setFilters((prev) => ({ ...prev, status: event.target.value }))}
            >
              <option value="">Все</option>
              <option value="authorized">authorized</option>
              <option value="declined">declined</option>
              <option value="settled">settled</option>
            </select>
          </label>
          <label className="filter">
            Сумма от
            <input
              type="number"
              value={filters.amountMin}
              onChange={(event) => setFilters((prev) => ({ ...prev, amountMin: event.target.value }))}
              placeholder="0"
            />
          </label>
          <label className="filter">
            До
            <input
              type="number"
              value={filters.amountMax}
              onChange={(event) => setFilters((prev) => ({ ...prev, amountMax: event.target.value }))}
              placeholder="10000"
            />
          </label>
          <button className="primary" type="submit">
            Применить
          </button>
        </form>
      </section>

      <section className="card">
        {isLoading ? (
          <div className="skeleton-stack" aria-busy="true">
            <div className="skeleton-line" />
            <div className="skeleton-line" />
          </div>
        ) : error ? (
          <div className="error" role="alert">
            {error}
          </div>
        ) : items.length === 0 ? (
          <div className="empty-state">
            <strong>Операции не найдены</strong>
            <span className="muted">Попробуйте изменить фильтры.</span>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Время</th>
                <th>Станция</th>
                <th>Продукт</th>
                <th>Литры / кол-во</th>
                <th>Сумма</th>
                <th>Статус</th>
                <th>Причина</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td>{formatDateTime(item.ts)}</td>
                  <td>{item.station}</td>
                  <td>{item.product}</td>
                  <td>{formatNumber(item.quantity ?? null)}</td>
                  <td>{formatCurrency(item.amount)}</td>
                  <td>
                    <StatusBadge status={item.status} />
                  </td>
                  <td>{item.primaryReason ?? "—"}</td>
                  <td className="stack-inline">
                    <Link className="link-button" to={`/transactions/${item.id}`}>
                      Details
                    </Link>
                    {item.explainUrl ? (
                      <a className="link-button" href={item.explainUrl} target="_blank" rel="noreferrer">
                        Explain
                      </a>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
