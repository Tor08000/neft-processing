import { type ChangeEvent, useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { cancelMarketplaceOrder, fetchMarketplaceOrders } from "../api/marketplace";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { AppErrorState, AppForbiddenState } from "../components/states";
import { Table } from "../components/common/Table";
import { MoneyValue } from "../components/common/MoneyValue";
import { Toast } from "../components/Toast/Toast";
import { useToast } from "../components/Toast/useToast";
import type { MarketplaceOrderSummary } from "../types/marketplace";
import { formatDate, formatDateTime } from "../utils/format";
import { getMarketplaceDocumentStatusLabel, getOrderStatusLabel } from "../utils/status";
import { canCancelMarketplaceOrder } from "../utils/marketplacePermissions";
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
  if (!status) return "neft-chip neft-chip-warn";
  const normalized = status.toLowerCase();
  if (["completed", "confirmed"].includes(normalized)) return "neft-chip neft-chip-ok";
  if (["cancelled", "canceled", "failed"].includes(normalized)) return "neft-chip neft-chip-err";
  return "neft-chip neft-chip-warn";
};

const LAST_UPDATED_KEY = "pwa:lastUpdated:orders";
const DEFAULT_FILTERS = {
  preset: "30d",
  from: "",
  to: "",
  status: "",
  partner: "",
  service: "",
  category: "",
  q: "",
};

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
    if (filters.preset !== "custom") {
      const range = buildDateRange(filters.preset);
      setFilters((prev) => ({ ...prev, ...range }));
    }
  }, [filters.preset]);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const from = params.get("from") ?? "";
    const to = params.get("to") ?? "";
    const status = params.get("status") ?? "";
    const partner = params.get("partner") ?? "";
    const service = params.get("service") ?? "";
    const category = params.get("category") ?? "";
    const q = params.get("q") ?? "";
    if (from || to || status || partner || service || category || q) {
      setFilters((prev) => ({
        ...prev,
        from,
        to,
        status,
        partner,
        service,
        category,
        q,
        preset: "custom",
      }));
      setPagination((prev) => ({ ...prev, offset: 0 }));
    }
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
      from: filters.from || undefined,
      to: filters.to || undefined,
      status: filters.status || undefined,
      partner: filters.partner || undefined,
      service: filters.service || undefined,
      category: filters.category || undefined,
      q: filters.q || undefined,
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

  const filtersActive =
    filters.status !== "" ||
    filters.partner !== "" ||
    filters.service !== "" ||
    filters.category !== "" ||
    filters.q !== "" ||
    filters.from !== "" ||
    filters.to !== "";

  const handleResetFilters = () => {
    setFilters(DEFAULT_FILTERS);
    setPagination((prev) => ({ ...prev, offset: 0 }));
  };

  const statusOptions = [
    { value: "", label: t("common.all") },
    { value: "CREATED", label: t("statuses.orders.CREATED") },
    { value: "ACCEPTED", label: t("statuses.orders.ACCEPTED") },
    { value: "IN_PROGRESS", label: t("statuses.orders.IN_PROGRESS") },
    { value: "COMPLETED", label: t("statuses.orders.COMPLETED") },
    { value: "FAILED", label: t("statuses.orders.FAILED") },
    { value: "CANCELLED", label: t("statuses.orders.CANCELLED") },
  ];

  const resolveAmount = (order: MarketplaceOrderSummary) =>
    order.price_snapshot?.total_amount ?? order.total_amount ?? null;

  const resolveCurrency = (order: MarketplaceOrderSummary) =>
    order.price_snapshot?.currency ?? order.currency ?? "RUB";

  const renderSlaStatus = (order: MarketplaceOrderSummary) => {
    if (!order.sla_status) {
      return <span className="neft-chip neft-chip-warn">—</span>;
    }
    const normalized = order.sla_status.toUpperCase();
    const tone = normalized === "VIOLATION" ? "err" : normalized === "OK" ? "ok" : "warn";
    return <span className={`neft-chip neft-chip-${tone}`}>{t(`marketplaceOrders.slaStatus.${normalized}`)}</span>;
  };

  const handleCancel = async (orderId: string) => {
    if (!user) return;
    const confirmed = window.confirm(t("marketplaceOrders.actions.confirmCancel"));
    if (!confirmed) return;
    try {
      await cancelMarketplaceOrder(user, orderId);
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
            <select id="status" name="status" value={filters.status} onChange={handleFilterChange}>
              {statusOptions.map((status) => (
                <option key={status.value || "all"} value={status.value}>
                  {status.label}
                </option>
              ))}
            </select>
          </div>
          <div className="filter">
            <label htmlFor="partner">{t("marketplaceOrders.filters.partner")}</label>
            <input id="partner" name="partner" value={filters.partner} onChange={handleFilterChange} />
          </div>
          <div className="filter">
            <label htmlFor="category">{t("marketplaceOrders.filters.category")}</label>
            <input id="category" name="category" value={filters.category} onChange={handleFilterChange} />
          </div>
          <div className="filter">
            <label htmlFor="service">{t("marketplaceOrders.filters.service")}</label>
            <input id="service" name="service" value={filters.service} onChange={handleFilterChange} />
          </div>
          <div className="filter">
            <label htmlFor="q">{t("marketplaceOrders.filters.search")}</label>
            <input id="q" name="q" value={filters.q} onChange={handleFilterChange} />
          </div>
          <div className="filter">
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
      </div>

      {error ? (
        <AppErrorState message={error.message} status={error.status} correlationId={error.correlationId} onRetry={loadOrders} />
      ) : null}

      {!error ? (
        <div className="card">
          <Table
            data={orders}
            loading={isLoading}
            columns={[
              {
                key: "id",
                title: t("marketplaceOrders.table.orderId"),
                className: "mono",
                render: (order) => order.id.slice(0, 8),
              },
              {
                key: "service",
                title: t("marketplaceOrders.table.service"),
                render: (order) => order.service_title ?? t("common.notAvailable"),
              },
              {
                key: "partner",
                title: t("marketplaceOrders.table.partner"),
                render: (order) => order.partner_name ?? t("common.notAvailable"),
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
                key: "sla",
                title: t("marketplaceOrders.table.sla"),
                render: (order) => renderSlaStatus(order),
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
                render: (order) => <span className={statusClass(order.status)}>{getOrderStatusLabel(order.status)}</span>,
              },
              {
                key: "documents",
                title: t("marketplaceOrders.table.documents"),
                render: (order) => (
                  <span
                    className="neft-chip neft-chip-warn"
                    title={getMarketplaceDocumentStatusLabel(order.documents_status)}
                  >
                    {getMarketplaceDocumentStatusLabel(order.documents_status)}
                  </span>
                ),
              },
              {
                key: "actions",
                title: "",
                render: (order) => (
                  <div className="stack-inline">
                    <Link to={`/marketplace/orders/${order.id}`} className="link-button">
                      {t("common.open")}
                    </Link>
                    {canCancel && order.status === "CREATED" ? (
                      <button type="button" className="link-button" onClick={() => handleCancel(order.id)}>
                        {t("actions.cancel")}
                      </button>
                    ) : null}
                  </div>
                ),
              },
            ]}
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
          />

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
      <Toast toast={toast} />
    </div>
  );
}
