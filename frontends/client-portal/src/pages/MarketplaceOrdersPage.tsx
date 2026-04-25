import { type ChangeEvent, useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { cancelMarketplaceOrder, fetchMarketplaceOrders } from "../api/marketplace";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { AppForbiddenState } from "../components/states";
import { Table } from "../components/common/Table";
import { MoneyValue } from "../components/common/MoneyValue";
import { Toast } from "../components/Toast/Toast";
import { useToast } from "../components/Toast/useToast";
import type { MarketplaceOrderStatus, MarketplaceOrderSummary } from "../types/marketplace";
import { formatDate, formatDateTime } from "../utils/format";
import { canCancelMarketplaceOrder } from "../utils/marketplacePermissions";
import {
  getMarketplaceOrderStatusClass,
  isCancelableMarketplaceOrderStatus,
} from "../utils/marketplaceOrders";
import { getOrderStatusLabel } from "../utils/status";
import { useI18n } from "../i18n";
import { isPwaMode } from "../pwa/mode";

interface OrdersErrorState {
  message: string;
  status?: number;
  correlationId?: string | null;
}

const LAST_UPDATED_KEY = "pwa:lastUpdated:orders";
const DEFAULT_FILTERS = {
  status: "",
};

const STATUS_OPTIONS: { value: "" | MarketplaceOrderStatus; labelKey: string }[] = [
  { value: "", labelKey: "marketplaceCatalog.filters.all" },
  { value: "CREATED", labelKey: "statuses.orders.CREATED" },
  { value: "PENDING_PAYMENT", labelKey: "statuses.orders.PENDING_PAYMENT" },
  { value: "PAID", labelKey: "statuses.orders.PAID" },
  { value: "CONFIRMED_BY_PARTNER", labelKey: "statuses.orders.CONFIRMED_BY_PARTNER" },
  { value: "IN_PROGRESS", labelKey: "statuses.orders.IN_PROGRESS" },
  { value: "COMPLETED", labelKey: "statuses.orders.COMPLETED" },
  { value: "DECLINED_BY_PARTNER", labelKey: "statuses.orders.DECLINED_BY_PARTNER" },
  { value: "CANCELED_BY_CLIENT", labelKey: "statuses.orders.CANCELED_BY_CLIENT" },
  { value: "PAYMENT_FAILED", labelKey: "statuses.orders.PAYMENT_FAILED" },
  { value: "CLOSED", labelKey: "statuses.orders.CLOSED" },
];

export function MarketplaceOrdersPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const location = useLocation();
  const navigate = useNavigate();
  const { toast, showToast } = useToast();
  const [lastUpdated, setLastUpdated] = useState<string | null>(() => localStorage.getItem(LAST_UPDATED_KEY));
  const [isOffline, setIsOffline] = useState(() => !navigator.onLine);
  const [orders, setOrders] = useState<MarketplaceOrderSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<OrdersErrorState | null>(null);
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [pagination, setPagination] = useState({ limit: isPwaMode ? 20 : 10, offset: 0 });
  const [total, setTotal] = useState(0);
  const canCancel = canCancelMarketplaceOrder(user);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const status = params.get("status") ?? "";
    setFilters({ status });
    setPagination((prev) => ({ ...prev, offset: 0 }));
  }, [location.search]);

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
      status: filters.status || undefined,
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

  useEffect(() => {
    if (!error?.status) return;
    if (error.status === 403 || error.status >= 500) {
      showToast("error", error.message);
    }
  }, [error, showToast]);

  const handleFilterChange = (evt: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = evt.target;
    setPagination((prev) => ({ ...prev, offset: 0 }));
    setFilters((prev) => ({ ...prev, [name]: value }));
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
    return <AppForbiddenState message={t("marketplaceOrders.forbidden.noAccess")} />;
  }

  if (error?.status === 403) {
    return <AppForbiddenState message={t("marketplaceOrders.forbidden.denied")} />;
  }

  const filtersActive = filters.status !== "";

  const handleResetFilters = () => {
    setFilters(DEFAULT_FILTERS);
    setPagination((prev) => ({ ...prev, offset: 0 }));
  };

  const resolveAmount = (order: MarketplaceOrderSummary) => order.total_amount ?? null;

  const resolveCurrency = (order: MarketplaceOrderSummary) => order.currency ?? "RUB";

  const handleCancel = async (orderId: string) => {
    if (!user) return;
    const confirmed = window.confirm(t("marketplaceOrders.actions.confirmCancel"));
    if (!confirmed) return;
    try {
      await cancelMarketplaceOrder(user, orderId, null);
      showToast("success", t("marketplaceOrders.actions.cancelSuccess"));
      loadOrders();
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : t("marketplaceOrders.errors.cancelFailed");
      showToast("error", message);
    }
  };

  return (
    <div className="stack">
      <div className="page-header">
        <div>
          <h2>{t("marketplaceOrders.title")}</h2>
          <p className="muted">{t("marketplaceOrders.subtitle")}</p>
          {isOffline && lastUpdated ? (
            <p className="muted small">{t("pwa.offlineStatus", { timestamp: formatDateTime(lastUpdated) })}</p>
          ) : null}
        </div>
      </div>

      <Table
        data={orders}
        loading={isLoading}
        toolbar={
          <div className="table-toolbar">
            <div className="filters">
              <div className="filter">
                <label htmlFor="marketplace-orders-status">{t("marketplaceOrders.filters.status")}</label>
                <select
                  id="marketplace-orders-status"
                  name="status"
                  value={filters.status}
                  onChange={handleFilterChange}
                >
                  {STATUS_OPTIONS.map((status) => (
                    <option key={status.value || "all"} value={status.value}>
                      {t(status.labelKey)}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="toolbar-actions">
              <button
                type="button"
                className="secondary neft-btn-secondary"
                onClick={handleResetFilters}
                disabled={!filtersActive}
              >
                {t("actions.resetFilters")}
              </button>
            </div>
          </div>
        }
        columns={[
          {
            key: "id",
            title: t("marketplaceOrders.table.orderId"),
            className: "mono",
            render: (order) => order.id.slice(0, 8),
          },
          {
            key: "date",
            title: t("marketplaceOrders.table.date"),
            render: (order) => (order.created_at ? formatDate(order.created_at) : t("common.notAvailable")),
          },
          {
            key: "updated",
            title: t("marketplaceOrders.table.updated"),
            render: (order) => (order.updated_at ? formatDateTime(order.updated_at) : t("common.notAvailable")),
          },
          {
            key: "amount",
            title: t("marketplaceOrders.table.amount"),
            className: "neft-num",
            render: (order) => {
              const amount = resolveAmount(order);
              if (amount === undefined || amount === null) {
                return t("common.notAvailable");
              }
              return <MoneyValue amount={amount} currency={resolveCurrency(order)} />;
            },
          },
          {
            key: "status",
            title: t("marketplaceOrders.table.status"),
            render: (order) => (
              <span className={getMarketplaceOrderStatusClass(order.status)}>{getOrderStatusLabel(order.status)}</span>
            ),
          },
          {
            key: "actions",
            title: "",
            render: (order) => (
              <div className="table-row-actions">
                <Link to={`/marketplace/orders/${order.id}`} className="link-button">
                  {t("common.open")}
                </Link>
                {canCancel && isCancelableMarketplaceOrderStatus(order.status) ? (
                  <button type="button" className="link-button" onClick={() => handleCancel(order.id)}>
                    {t("actions.cancel")}
                  </button>
                ) : null}
              </div>
            ),
          },
        ]}
        errorState={
          error
            ? {
                title: t("errors.actionFailedTitle"),
                description: error.message,
                details: [error.status ? `HTTP ${error.status}` : null, error.correlationId ? `correlation_id: ${error.correlationId}` : null]
                  .filter(Boolean)
                  .join(" · "),
                actionLabel: t("errors.retry"),
                actionOnClick: loadOrders,
              }
            : undefined
        }
        emptyState={{
          title: t("emptyStates.marketplaceOrders.title"),
          description: t("emptyStates.marketplaceOrders.description"),
          actionLabel: filtersActive
            ? t("actions.resetFilters")
            : isPwaMode
              ? undefined
              : t("actions.goToCatalog"),
          actionOnClick: filtersActive
            ? handleResetFilters
            : isPwaMode
              ? undefined
              : () => navigate("/marketplace"),
        }}
        footer={
          <div className="table-footer__content">
            <div className="stack-inline">
              <span className="muted">Rows: {orders.length}</span>
              <span className="muted">
                {t("marketplaceOrders.pagination.page", { current: pageNumber, total: totalPages })}
              </span>
            </div>
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
        }
      />
      <Toast toast={toast} />
    </div>
  );
}
