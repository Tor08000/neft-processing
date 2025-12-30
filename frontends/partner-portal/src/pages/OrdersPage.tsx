import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Package } from "../components/icons";
import { ApiError } from "../api/http";
import { fetchOrders, type OrderFilters, confirmOrder } from "../api/orders";
import { useAuth } from "../auth/AuthContext";
import { EmptyState } from "../components/EmptyState";
import { ErrorState, ForbiddenState, LoadingState } from "../components/states";
import { StatusBadge } from "../components/StatusBadge";
import type { MarketplaceOrder } from "../types/marketplace";
import { formatCurrency, formatDateTime, formatNumber } from "../utils/format";
import { canManageOrderLifecycle, canReadOrders } from "../utils/roles";
import { useI18n } from "../i18n";

const STORAGE_KEY = "partner-orders-filters";
const PAGE_SIZE = 20;

type PeriodPreset = "today" | "7d" | "30d" | "custom";

const statusOptions = [
  "",
  "CREATED",
  "PAID",
  "CONFIRMED",
  "IN_PROGRESS",
  "COMPLETED",
  "CANCELLED",
  "REFUNDED",
  "DISPUTED",
];

const toDateInput = (date: Date) => date.toISOString().slice(0, 10);

const startOfDay = (date: Date) => new Date(date.getFullYear(), date.getMonth(), date.getDate());

const getPresetRange = (preset: PeriodPreset) => {
  const now = new Date();
  if (preset === "today") {
    const start = startOfDay(now);
    return { from: toDateInput(start), to: toDateInput(now) };
  }
  if (preset === "7d") {
    const start = new Date(now);
    start.setDate(start.getDate() - 6);
    return { from: toDateInput(start), to: toDateInput(now) };
  }
  if (preset === "30d") {
    const start = new Date(now);
    start.setDate(start.getDate() - 29);
    return { from: toDateInput(start), to: toDateInput(now) };
  }
  return { from: "", to: "" };
};

const shortId = (value: string) => (value.length > 10 ? `${value.slice(0, 6)}…${value.slice(-4)}` : value);

export function OrdersPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [orders, setOrders] = useState<MarketplaceOrder[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [correlationId, setCorrelationId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState<OrderFilters>({});
  const [periodPreset, setPeriodPreset] = useState<PeriodPreset>("7d");
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const canRead = canReadOrders(user?.roles);
  const canManageLifecycle = canManageOrderLifecycle(user?.roles);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return;
    try {
      const parsed = JSON.parse(stored) as { filters?: OrderFilters; periodPreset?: PeriodPreset };
      if (parsed.filters) {
        setFilters(parsed.filters);
      }
      if (parsed.periodPreset) {
        setPeriodPreset(parsed.periodPreset);
      }
    } catch (err) {
      console.error("Failed to parse stored filters", err);
    }
  }, []);

  useEffect(() => {
    if (!user) return;
    if (!canRead) {
      setIsLoading(false);
      return;
    }
    let active = true;
    const offset = String((page - 1) * PAGE_SIZE);
    const limit = String(PAGE_SIZE);
    setIsLoading(true);
    setError(null);
    setCorrelationId(null);
    fetchOrders(user.token, { ...filters, offset, limit })
      .then((data) => {
        if (!active) return;
        setOrders(data.items ?? []);
        setTotal(data.total ?? 0);
      })
      .catch((err) => {
        console.error(err);
        if (!active) return;
        if (err instanceof ApiError) {
          setError(t("ordersPage.errors.apiError", { status: err.status, message: err.message }));
          setCorrelationId(err.correlationId);
        } else {
          setError(t("ordersPage.errors.loadFailed"));
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
  }, [user, filters, page, canRead]);

  useEffect(() => {
    if (!user) return;
    if (!filters.from && !filters.to) {
      const range = getPresetRange(periodPreset);
      setFilters((prev) => ({ ...prev, ...range }));
    }
  }, [user, periodPreset, filters.from, filters.to]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const kpis = useMemo(() => {
    const today = toDateInput(new Date());
    const ordersToday = orders.filter((order) => order.createdAt?.slice(0, 10) === today).length;
    const pendingConfirmation = orders.filter((order) =>
      ["CREATED", "PAID", "AUTHORIZED"].includes(order.status),
    ).length;
    const docsPending = orders.filter((order) =>
      (order.documentsStatus ?? "").toLowerCase().includes("pending") ||
      (order.documents ?? []).some((doc) => (doc.edoStatus ?? "").toLowerCase().includes("pending")),
    ).length;
    return { ordersToday, pendingConfirmation, docsPending };
  }, [orders]);

  const handlePresetChange = (preset: PeriodPreset) => {
    setPeriodPreset(preset);
    if (preset !== "custom") {
      const range = getPresetRange(preset);
      setFilters((prev) => ({ ...prev, from: range.from, to: range.to }));
    }
    setPage(1);
  };

  const handleFilterChange = (key: keyof OrderFilters, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
  };

  const handleSaveFilters = () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ filters, periodPreset }),
    );
  };

  const handleQuickConfirm = async (orderId: string) => {
    if (!user) return;
    setActionError(null);
    setActionMessage(null);
    try {
      const result = await confirmOrder(user.token, orderId);
      setActionMessage(
        t("ordersPage.notifications.confirmed", { id: result.correlationId ?? t("common.notAvailable") }),
      );
      const updated = await fetchOrders(user.token, { ...filters, offset: String((page - 1) * PAGE_SIZE), limit: String(PAGE_SIZE) });
      setOrders(updated.items ?? []);
      setTotal(updated.total ?? 0);
    } catch (err) {
      console.error(err);
      const message =
        err instanceof ApiError
          ? t("ordersPage.errors.apiError", { status: err.status, message: err.message })
          : t("ordersPage.errors.confirmFailed");
      setActionError(message);
      if (err instanceof ApiError) {
        setCorrelationId(err.correlationId);
      }
    }
  };

  if (!canRead) {
    return <ForbiddenState />;
  }

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <h2>{t("ordersPage.title")}</h2>
          <button type="button" className="secondary" onClick={handleSaveFilters}>
            {t("ordersPage.actions.saveFilters")}
          </button>
        </div>
        <div className="filters">
          <label className="filter">
            {t("ordersPage.filters.period")}
            <select value={periodPreset} onChange={(event) => handlePresetChange(event.target.value as PeriodPreset)}>
              <option value="today">{t("ordersPage.filters.presets.today")}</option>
              <option value="7d">{t("ordersPage.filters.presets.7d")}</option>
              <option value="30d">{t("ordersPage.filters.presets.30d")}</option>
              <option value="custom">{t("ordersPage.filters.presets.custom")}</option>
            </select>
          </label>
          <label className="filter">
            {t("ordersPage.filters.from")}
            <input
              type="date"
              value={filters.from ?? ""}
              onChange={(event) => handleFilterChange("from", event.target.value)}
            />
          </label>
          <label className="filter">
            {t("ordersPage.filters.to")}
            <input
              type="date"
              value={filters.to ?? ""}
              onChange={(event) => handleFilterChange("to", event.target.value)}
            />
          </label>
          <label className="filter">
            {t("ordersPage.filters.status")}
            <select value={filters.status ?? ""} onChange={(event) => handleFilterChange("status", event.target.value)}>
              {statusOptions.map((status) => (
                <option key={status || "all"} value={status}>
                  {status || t("common.all")}
                </option>
              ))}
            </select>
          </label>
          <label className="filter">
            {t("ordersPage.filters.search")}
            <input
              type="search"
              placeholder={t("ordersPage.filters.searchPlaceholder")}
              value={filters.q ?? ""}
              onChange={(event) => handleFilterChange("q", event.target.value)}
            />
          </label>
          <label className="filter">
            {t("ordersPage.filters.station")}
            <input
              type="text"
              placeholder={t("ordersPage.filters.stationPlaceholder")}
              value={filters.station_id ?? ""}
              onChange={(event) => handleFilterChange("station_id", event.target.value)}
            />
          </label>
          <label className="filter">
            {t("ordersPage.filters.service")}
            <input
              type="text"
              placeholder={t("ordersPage.filters.servicePlaceholder")}
              value={filters.service_id ?? ""}
              onChange={(event) => handleFilterChange("service_id", event.target.value)}
            />
          </label>
        </div>

        <div className="stats-grid">
          <div className="stat">
            <div className="stat__label">{t("ordersPage.kpis.today")}</div>
            <div className="stat__value">{formatNumber(kpis.ordersToday)}</div>
          </div>
          <div className="stat">
            <div className="stat__label">{t("ordersPage.kpis.pending")}</div>
            <div className="stat__value">{formatNumber(kpis.pendingConfirmation)}</div>
          </div>
          <div className="stat">
            <div className="stat__label">{t("ordersPage.kpis.documents")}</div>
            <div className="stat__value">{formatNumber(kpis.docsPending)}</div>
          </div>
          <div className="stat">
            <div className="stat__label">{t("ordersPage.kpis.total")}</div>
            <div className="stat__value">{formatNumber(total)}</div>
          </div>
        </div>

        {actionMessage ? <div className="notice">{actionMessage}</div> : null}
        {actionError ? <div className="notice error">{actionError}</div> : null}

        {isLoading ? (
          <LoadingState />
        ) : error ? (
          <ErrorState
            description={error}
            correlationId={correlationId}
            action={
              <button type="button" className="secondary" onClick={() => setPage(1)}>
                {t("errors.retry")}
              </button>
            }
          />
        ) : orders.length === 0 ? (
          <EmptyState
            icon={<Package />}
            title={t("emptyStates.orders.title")}
            description={t("emptyStates.orders.description")}
          />
        ) : (
          <>
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t("ordersPage.table.createdAt")}</th>
                  <th>{t("ordersPage.table.orderId")}</th>
                  <th>{t("ordersPage.table.client")}</th>
                  <th>{t("ordersPage.table.items")}</th>
                  <th>{t("ordersPage.table.amount")}</th>
                  <th>{t("ordersPage.table.payment")}</th>
                  <th>{t("ordersPage.table.status")}</th>
                  <th>{t("ordersPage.table.documents")}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {orders.map((order) => (
                  <tr key={order.id}>
                    <td>{formatDateTime(order.createdAt)}</td>
                    <td>{shortId(order.id)}</td>
                    <td>{order.clientName ?? order.clientId ?? t("common.notAvailable")}</td>
                    <td>{formatNumber(order.itemsCount ?? order.items?.length ?? null)}</td>
                    <td>{formatCurrency(order.totalAmount ?? null)}</td>
                    <td>
                      <StatusBadge status={order.paymentStatus ?? t("common.notAvailable")} />
                    </td>
                    <td>
                      <StatusBadge status={order.status} />
                    </td>
                    <td>
                      <StatusBadge status={order.documentsStatus ?? order.documents?.[0]?.status ?? t("common.notAvailable")} />
                    </td>
                    <td>
                      <div className="stack-inline">
                        <Link className="link-button" to={`/orders/${order.id}`}>
                          {t("common.open")}
                        </Link>
                        {canManageLifecycle && ["CREATED", "PAID", "AUTHORIZED"].includes(order.status) ? (
                          <button type="button" className="ghost" onClick={() => handleQuickConfirm(order.id)}>
                            {t("ordersPage.actions.quickConfirm")}
                          </button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="pagination">
              <button type="button" className="secondary" onClick={() => setPage((prev) => Math.max(prev - 1, 1))} disabled={page <= 1}>
                {t("common.back")}
              </button>
              <div className="muted">{t("ordersPage.pagination", { current: page, total: totalPages })}</div>
              <button type="button" className="secondary" onClick={() => setPage((prev) => Math.min(prev + 1, totalPages))} disabled={page >= totalPages}>
                {t("common.next")}
              </button>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
