import { type ChangeEvent, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchMarketplaceOrders } from "../api/marketplace";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { AppEmptyState, AppErrorState, AppForbiddenState } from "../components/states";
import type { MarketplaceOrderSummary } from "../types/marketplace";
import { formatDate, formatMoney } from "../utils/format";

interface OrdersErrorState {
  message: string;
  status?: number;
  correlationId?: string | null;
}

const PERIOD_PRESETS = [
  { value: "7d", label: "7 дней" },
  { value: "30d", label: "30 дней" },
  { value: "90d", label: "90 дней" },
  { value: "custom", label: "Выбрать" },
];

const buildDateRange = (preset: string) => {
  const to = new Date();
  const from = new Date();
  if (preset === "7d") {
    from.setDate(to.getDate() - 7);
  } else if (preset === "30d") {
    from.setDate(to.getDate() - 30);
  } else if (preset === "90d") {
    from.setDate(to.getDate() - 90);
  }
  return { from: from.toISOString().slice(0, 10), to: to.toISOString().slice(0, 10) };
};

const statusClass = (status?: string | null) => {
  if (!status) return "badge pending";
  const normalized = status.toLowerCase();
  if (["completed", "confirmed"].includes(normalized)) return "badge success";
  if (["cancelled", "canceled", "failed"].includes(normalized)) return "badge error";
  return "badge pending";
};

export function MarketplaceOrdersPage() {
  const { user } = useAuth();
  const [orders, setOrders] = useState<MarketplaceOrderSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<OrdersErrorState | null>(null);
  const [filters, setFilters] = useState({
    preset: "30d",
    from: "",
    to: "",
    status: "",
    partner: "",
    service: "",
  });
  const [pagination, setPagination] = useState({ limit: 10, offset: 0 });
  const [total, setTotal] = useState(0);

  useEffect(() => {
    if (filters.preset !== "custom") {
      const range = buildDateRange(filters.preset);
      setFilters((prev) => ({ ...prev, ...range }));
    }
  }, [filters.preset]);

  const loadOrders = () => {
    if (!user) return;
    setIsLoading(true);
    setError(null);
    fetchMarketplaceOrders(user, {
      from: filters.from || undefined,
      to: filters.to || undefined,
      status: filters.status || undefined,
      partner: filters.partner || undefined,
      service: filters.service || undefined,
      limit: pagination.limit,
      offset: pagination.offset,
    })
      .then((resp) => {
        setOrders(resp.items ?? []);
        setTotal(resp.total ?? 0);
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError) {
          setError({ message: err.message, status: err.status, correlationId: err.correlationId });
          return;
        }
        setError({ message: err instanceof Error ? err.message : "Не удалось загрузить заказы" });
      })
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    loadOrders();
  }, [user, filters, pagination]);

  const handleFilterChange = (evt: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = evt.target;
    setPagination((prev) => ({ ...prev, offset: 0 }));
    setFilters((prev) => ({ ...prev, [name]: value, preset: name === "from" || name === "to" ? "custom" : prev.preset }));
  };

  const pageNumber = useMemo(
    () => Math.floor(pagination.offset / pagination.limit) + 1,
    [pagination.offset, pagination.limit],
  );
  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(total / pagination.limit)),
    [pagination.limit, total],
  );

  if (!user) {
    return <AppForbiddenState message="Нет доступа к заказам." />;
  }

  if (error?.status === 403) {
    return <AppForbiddenState message="Просмотр заказов запрещён." />;
  }

  return (
    <div className="stack">
      <div className="card">
        <div className="card__header">
          <div>
            <h2>Мои заказы</h2>
            <p className="muted">История заказов и статусов по маркетплейсу.</p>
          </div>
        </div>

        <div className="filters">
          <div className="filter">
            <label htmlFor="preset">Период</label>
            <select id="preset" name="preset" value={filters.preset} onChange={handleFilterChange}>
              {PERIOD_PRESETS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
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
            <input id="status" name="status" value={filters.status} onChange={handleFilterChange} />
          </div>
          <div className="filter">
            <label htmlFor="partner">Партнёр</label>
            <input id="partner" name="partner" value={filters.partner} onChange={handleFilterChange} />
          </div>
          <div className="filter">
            <label htmlFor="service">Услуга</label>
            <input id="service" name="service" value={filters.service} onChange={handleFilterChange} />
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="card">
          <div className="skeleton-stack">
            <div className="skeleton-line" />
            <div className="skeleton-line" />
            <div className="skeleton-line" />
          </div>
        </div>
      ) : null}

      {error ? (
        <AppErrorState message={error.message} status={error.status} correlationId={error.correlationId} onRetry={loadOrders} />
      ) : null}

      {!isLoading && !error && orders.length === 0 ? (
        <AppEmptyState title="Заказы не найдены" description="Попробуйте изменить фильтры." />
      ) : null}

      {!isLoading && !error && orders.length > 0 ? (
        <div className="card">
          <table className="data-table">
            <thead>
              <tr>
                <th>Order ID</th>
                <th>Услуга</th>
                <th>Партнёр</th>
                <th>Дата</th>
                <th>Сумма</th>
                <th>Статус</th>
                <th>Документы</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {orders.map((order) => (
                <tr key={order.id}>
                  <td className="mono">{order.id.slice(0, 8)}</td>
                  <td>{order.service_title ?? "—"}</td>
                  <td>{order.partner_name ?? "—"}</td>
                  <td>{order.created_at ? formatDate(order.created_at) : "—"}</td>
                  <td>
                    {order.total_amount !== undefined && order.total_amount !== null
                      ? formatMoney(order.total_amount, order.currency ?? "RUB")
                      : "—"}
                  </td>
                  <td>
                    <span className={statusClass(order.status)}>{order.status ?? "—"}</span>
                  </td>
                  <td>
                    <span className="badge pending">{order.documents_status ?? "—"}</span>
                  </td>
                  <td>
                    <Link to={`/marketplace/orders/${order.id}`} className="link-button">
                      Открыть
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="pagination">
            <button
              type="button"
              className="secondary"
              onClick={() =>
                setPagination((prev) => ({ ...prev, offset: Math.max(0, prev.offset - prev.limit) }))
              }
              disabled={pagination.offset === 0}
            >
              Назад
            </button>
            <div className="muted">
              Страница {pageNumber} из {totalPages}
            </div>
            <button
              type="button"
              className="secondary"
              onClick={() =>
                setPagination((prev) => ({ ...prev, offset: prev.offset + prev.limit }))
              }
              disabled={pageNumber >= totalPages}
            >
              Вперёд
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
