import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Package } from "../components/icons";
import { ApiError } from "../api/http";
import { fetchOrders, type OrderFilters } from "../api/orders";
import { useAuth } from "../auth/AuthContext";
import { EmptyState } from "../components/EmptyState";
import { ForbiddenState, LoadingState } from "../components/states";
import { StatusBadge } from "../components/StatusBadge";
import type { MarketplaceOrder } from "../types/marketplace";
import { formatCurrency, formatDateTime, formatNumber } from "../utils/format";
import { canReadOrders } from "../utils/roles";
import { useTranslation } from "react-i18next";
import { PartnerErrorState } from "../components/PartnerErrorState";
import { demoOrders } from "../demo/partnerDemoData";
import { isDemoPartner } from "@shared/demo/demo";

const STORAGE_KEY = "partner-orders-filters";
const PAGE_SIZE = 20;

type PeriodPreset = "today" | "7d" | "30d" | "custom";

const statusOptions = [
  "",
  "CREATED",
  "PAID",
  "ACCEPTED",
  "IN_PROGRESS",
  "COMPLETED",
  "FAILED",
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
  const { t } = useTranslation();
  const [orders, setOrders] = useState<MarketplaceOrder[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [isDemoFallback, setIsDemoFallback] = useState(false);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState<OrderFilters>({});
  const [periodPreset, setPeriodPreset] = useState<PeriodPreset>("7d");
  const canRead = canReadOrders(user?.roles);
  const isDemoPartnerAccount = isDemoPartner(user?.email ?? null);
  const getSlaDeadline = (order: MarketplaceOrder) => {
    if (order.status === "CREATED") {
      return order.slaResponseDueAt ?? null;
    }
    if (order.status === "IN_PROGRESS") {
      return order.slaCompletionDueAt ?? null;
    }
    return null;
  };

  const getSlaRemainingSeconds = (order: MarketplaceOrder) => {
    if (order.status === "CREATED") {
      return order.slaResponseRemainingSeconds ?? null;
    }
    if (order.status === "IN_PROGRESS") {
      return order.slaCompletionRemainingSeconds ?? null;
    }
    return null;
  };

  const formatCountdown = (seconds: number | null) => {
    if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return "—";
    const clamped = Math.max(0, seconds);
    const hours = Math.floor(clamped / 3600);
    const minutes = Math.floor((clamped % 3600) / 60);
    const secs = clamped % 60;
    return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  };

  const resolveSlaTone = (order: MarketplaceOrder) => {
    const remaining = getSlaRemainingSeconds(order);
    const deadline = getSlaDeadline(order);
    if (!deadline && remaining === null) return "neutral";
    const totalSeconds = (() => {
      if (!deadline) return null;
      const created = new Date(order.createdAt).getTime();
      const due = new Date(deadline).getTime();
      if (Number.isNaN(created) || Number.isNaN(due)) return null;
      return Math.max(1, Math.floor((due - created) / 1000));
    })();
    if (!totalSeconds || remaining === null) return "pending";
    const ratio = remaining / totalSeconds;
    if (ratio <= 0.1) return "error";
    if (ratio <= 0.25) return "pending";
    return "success";
  };

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
    if (isDemoPartnerAccount) {
      setOrders(demoOrders);
      setTotal(demoOrders.length);
      setIsDemoFallback(true);
      setError(null);
      setIsLoading(false);
      return;
    }
    let active = true;
    const offset = String((page - 1) * PAGE_SIZE);
    const limit = String(PAGE_SIZE);
    setIsLoading(true);
    setError(null);
    fetchOrders(user.token, { ...filters, offset, limit })
      .then((data) => {
        if (!active) return;
        setOrders(data.items ?? []);
        setTotal(data.total ?? 0);
        setIsDemoFallback(false);
      })
      .catch((err) => {
        if (!active) return;
        if (err instanceof ApiError && isDemoPartnerAccount && (err.status === 403 || err.status === 404)) {
          setOrders(demoOrders);
          setTotal(demoOrders.length);
          setIsDemoFallback(true);
          setError(null);
          return;
        }
        console.error(err);
        setError(err);
      })
      .finally(() => {
        if (active) {
          setIsLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [user, filters, page, canRead, isDemoPartnerAccount]);

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

  const refreshOrders = () => {
    setPage(1);
    setFilters((prev) => ({ ...prev }));
  };

  if (!canRead) {
    return <ForbiddenState />;
  }

  return (
    <div className="stack">
      <section className="card">
        <div className="page-section">
          <div className="page-section__header">
            <h2>{t("ordersPage.title")}</h2>
            <div className="neft-actions">
              <button type="button" className="secondary" onClick={handleSaveFilters}>
                {t("ordersPage.actions.saveFilters")}
              </button>
            </div>
          </div>
          <div className="page-section__content">
            <div className="filters neft-filters">
              <label className="filter neft-filter">
                {t("ordersPage.filters.period")}
                <select value={periodPreset} onChange={(event) => handlePresetChange(event.target.value as PeriodPreset)}>
                  <option value="today">{t("ordersPage.filters.presets.today")}</option>
                  <option value="7d">{t("ordersPage.filters.presets.7d")}</option>
                  <option value="30d">{t("ordersPage.filters.presets.30d")}</option>
                  <option value="custom">{t("ordersPage.filters.presets.custom")}</option>
                </select>
              </label>
              <label className="filter neft-filter">
                {t("ordersPage.filters.from")}
                <input
                  type="date"
                  value={filters.from ?? ""}
                  onChange={(event) => handleFilterChange("from", event.target.value)}
                />
              </label>
              <label className="filter neft-filter">
                {t("ordersPage.filters.to")}
                <input
                  type="date"
                  value={filters.to ?? ""}
                  onChange={(event) => handleFilterChange("to", event.target.value)}
                />
              </label>
              <label className="filter neft-filter">
                {t("ordersPage.filters.status")}
                <select value={filters.status ?? ""} onChange={(event) => handleFilterChange("status", event.target.value)}>
                  {statusOptions.map((status) => (
                    <option key={status || "all"} value={status}>
                      {status || t("common.all")}
                    </option>
                  ))}
                </select>
              </label>
              <label className="filter neft-filter">
                {t("ordersPage.filters.search")}
                <input
                  type="search"
                  placeholder={t("ordersPage.filters.searchPlaceholder")}
                  value={filters.q ?? ""}
                  onChange={(event) => handleFilterChange("q", event.target.value)}
                />
              </label>
              <label className="filter neft-filter">
                {t("ordersPage.filters.station")}
                <input
                  type="text"
                  placeholder={t("ordersPage.filters.stationPlaceholder")}
                  value={filters.station_id ?? ""}
                  onChange={(event) => handleFilterChange("station_id", event.target.value)}
                />
              </label>
              <label className="filter neft-filter">
                {t("ordersPage.filters.service")}
                <input
                  type="text"
                  placeholder={t("ordersPage.filters.servicePlaceholder")}
                  value={filters.service_id ?? ""}
                  onChange={(event) => handleFilterChange("service_id", event.target.value)}
                />
              </label>
              <label className="filter neft-filter">
                {t("ordersPage.filters.slaRisk")}
                <select
                  value={filters.sla_risk ?? ""}
                  onChange={(event) => handleFilterChange("sla_risk", event.target.value)}
                >
                  <option value="">{t("common.all")}</option>
                  <option value="near">{t("ordersPage.filters.slaRiskNear")}</option>
                </select>
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
            {isDemoFallback ? (
              <div className="notice">
                <div>В демо-режиме показываются примерные заказы и показатели.</div>
              </div>
            ) : null}
          </div>
        </div>

        {isLoading ? (
          <LoadingState />
        ) : error ? (
          <PartnerErrorState error={error} />
        ) : orders.length === 0 ? (
          <EmptyState
            icon={<Package />}
            title={t("emptyStates.orders.title")}
            description={t("emptyStates.orders.description")}
            primaryAction={{ label: t("actions.refresh"), onClick: refreshOrders }}
          />
        ) : (
          <div className="page-section">
            <div className="table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>{t("ordersPage.table.orderId")}</th>
                    <th>{t("ordersPage.table.client")}</th>
                    <th>{t("ordersPage.table.service")}</th>
                    <th>{t("ordersPage.table.createdAt")}</th>
                    <th>{t("ordersPage.table.sla")}</th>
                    <th>{t("ordersPage.table.amount")}</th>
                    <th>{t("ordersPage.table.status")}</th>
                    <th>{t("ordersPage.table.actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.map((order) => (
                    <tr key={order.id}>
                      <td>{shortId(order.id)}</td>
                      <td>{order.clientName ?? order.clientId ?? t("common.notAvailable")}</td>
                      <td>{order.serviceTitle ?? t("common.notAvailable")}</td>
                      <td>{formatDateTime(order.createdAt)}</td>
                      <td>
                        <span className={`badge ${resolveSlaTone(order)}`}>{formatCountdown(getSlaRemainingSeconds(order))}</span>
                      </td>
                      <td>{formatCurrency(order.totalAmount ?? null)}</td>
                      <td>
                        <StatusBadge status={order.status} />
                      </td>
                      <td>
                        <Link className="link-button" to={`/orders/${order.id}`}>
                          {t("common.open")}
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="pagination pagination-wrapper">
              <button type="button" className="secondary" onClick={() => setPage((prev) => Math.max(prev - 1, 1))} disabled={page <= 1}>
                {t("ordersPage.pagination.prev")}
              </button>
              <div className="muted">{t("ordersPage.pagination.page", { current: page, total: totalPages })}</div>
              <button type="button" className="secondary" onClick={() => setPage((prev) => Math.min(prev + 1, totalPages))} disabled={page >= totalPages}>
                {t("ordersPage.pagination.next")}
              </button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
