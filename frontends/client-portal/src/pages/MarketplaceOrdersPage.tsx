import { type ChangeEvent, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Package } from "../components/icons";
import { fetchMarketplaceOrders } from "../api/marketplace";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { EmptyState } from "../components/EmptyState";
import { AppErrorState, AppForbiddenState } from "../components/states";
import type { MarketplaceOrderSummary } from "../types/marketplace";
import { formatDate, formatDateTime, formatMoney } from "../utils/format";
import { getMarketplaceDocumentStatusLabel, getOrderStatusLabel } from "../utils/status";
import { useI18n } from "../i18n";
import { isPwaMode } from "../pwa/mode";

interface OrdersErrorState {
  message: string;
  status?: number;
  correlationId?: string | null;
}

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

const LAST_UPDATED_KEY = "pwa:lastUpdated:orders";

export function MarketplaceOrdersPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [lastUpdated, setLastUpdated] = useState<string | null>(() => localStorage.getItem(LAST_UPDATED_KEY));
  const [isOffline, setIsOffline] = useState(() => !navigator.onLine);
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
  const [pagination, setPagination] = useState({ limit: isPwaMode ? 20 : 10, offset: 0 });
  const [total, setTotal] = useState(0);

  useEffect(() => {
    if (filters.preset !== "custom") {
      const range = buildDateRange(filters.preset);
      setFilters((prev) => ({ ...prev, ...range }));
    }
  }, [filters.preset]);

  useEffect(() => {
    const handleStatus = () => setIsOffline(!navigator.onLine);
    window.addEventListener("online", handleStatus);
    window.addEventListener("offline", handleStatus);
    return () => {
      window.removeEventListener("online", handleStatus);
      window.removeEventListener("offline", handleStatus);
    };
  }, []);

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
        const timestamp = new Date().toISOString();
        localStorage.setItem(LAST_UPDATED_KEY, timestamp);
        setLastUpdated(timestamp);
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError) {
          setError({ message: err.message, status: err.status, correlationId: err.correlationId });
          return;
        }
        setError({ message: err instanceof Error ? err.message : t("marketplaceOrders.errors.loadFailed") });
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

  const periodPresets = useMemo(
    () => [
      { value: "7d", label: t("filters.periodPresets.7d") },
      { value: "30d", label: t("filters.periodPresets.30d") },
      { value: "90d", label: t("filters.periodPresets.90d") },
      { value: "custom", label: t("filters.periodPresets.custom") },
    ],
    [t],
  );

  if (!user) {
    return <AppForbiddenState message={t("marketplaceOrders.forbidden.noAccess")} />;
  }

  if (error?.status === 403) {
    return <AppForbiddenState message={t("marketplaceOrders.forbidden.denied")} />;
  }

  return (
    <div className="stack">
      <div className="card">
        <div className="card__header">
          <div>
            <h2>{t("marketplaceOrders.title")}</h2>
            <p className="muted">{t("marketplaceOrders.subtitle")}</p>
            {isOffline && lastUpdated ? (
              <p className="muted small">{t("pwa.offlineStatus", { timestamp: formatDateTime(lastUpdated) })}</p>
            ) : null}
          </div>
        </div>

        <div className="filters">
          <div className="filter">
            <label htmlFor="preset">{t("marketplaceOrders.filters.periodPreset")}</label>
            <select id="preset" name="preset" value={filters.preset} onChange={handleFilterChange}>
              {periodPresets.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
          <div className="filter">
            <label htmlFor="from">{t("marketplaceOrders.filters.periodFrom")}</label>
            <input id="from" name="from" type="date" value={filters.from} onChange={handleFilterChange} />
          </div>
          <div className="filter">
            <label htmlFor="to">{t("marketplaceOrders.filters.periodTo")}</label>
            <input id="to" name="to" type="date" value={filters.to} onChange={handleFilterChange} />
          </div>
          <div className="filter">
            <label htmlFor="status">{t("marketplaceOrders.filters.status")}</label>
            <input id="status" name="status" value={filters.status} onChange={handleFilterChange} />
          </div>
          <div className="filter">
            <label htmlFor="partner">{t("marketplaceOrders.filters.partner")}</label>
            <input id="partner" name="partner" value={filters.partner} onChange={handleFilterChange} />
          </div>
          <div className="filter">
            <label htmlFor="service">{t("marketplaceOrders.filters.service")}</label>
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
        <EmptyState
          icon={<Package />}
          title={t("emptyStates.marketplaceOrders.title")}
          description={t("emptyStates.marketplaceOrders.description")}
          primaryAction={isPwaMode ? undefined : { label: t("actions.goToCatalog"), to: "/marketplace" }}
        />
      ) : null}

      {!isLoading && !error && orders.length > 0 ? (
        <div className="card">
          <table className="data-table">
            <thead>
              <tr>
                <th>{t("marketplaceOrders.table.orderId")}</th>
                <th>{t("marketplaceOrders.table.service")}</th>
                <th>{t("marketplaceOrders.table.partner")}</th>
                <th>{t("marketplaceOrders.table.date")}</th>
                <th>{t("marketplaceOrders.table.amount")}</th>
                <th>{t("marketplaceOrders.table.status")}</th>
                <th>{t("marketplaceOrders.table.documents")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {orders.map((order) => (
                <tr key={order.id}>
                  <td className="mono">{order.id.slice(0, 8)}</td>
                  <td>{order.service_title ?? t("common.notAvailable")}</td>
                  <td>{order.partner_name ?? t("common.notAvailable")}</td>
                  <td>{order.created_at ? formatDate(order.created_at) : t("common.notAvailable")}</td>
                  <td>
                    {order.total_amount !== undefined && order.total_amount !== null
                      ? formatMoney(order.total_amount, order.currency ?? "RUB")
                      : t("common.notAvailable")}
                  </td>
                  <td>
                    <span className={statusClass(order.status)}>{getOrderStatusLabel(order.status)}</span>
                  </td>
                  <td>
                    <span className="badge pending">{getMarketplaceDocumentStatusLabel(order.documents_status)}</span>
                  </td>
                  <td>
                    <Link to={`/marketplace/orders/${order.id}`} className="link-button">
                      {t("common.open")}
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
              {t("common.back")}
            </button>
            <div className="muted">
              {t("marketplaceOrders.pagination.page", { current: pageNumber, total: totalPages })}
            </div>
            <button
              type="button"
              className="secondary"
              onClick={() =>
                setPagination((prev) => ({ ...prev, offset: prev.offset + prev.limit }))
              }
              disabled={pageNumber >= totalPages}
            >
              {t("common.next")}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
