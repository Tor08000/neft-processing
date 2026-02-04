import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { StatusBadge } from "../../components/StatusBadge";
import { demoOrders, demoOrdersKpis } from "../../demo/partnerDemoData";
import type { MarketplaceOrder } from "../../types/marketplace";
import { formatCurrency, formatDateTime, formatNumber } from "../../utils/format";

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

type PeriodPreset = "today" | "7d" | "30d" | "custom";

const shortId = (value: string) => (value.length > 10 ? `${value.slice(0, 6)}…${value.slice(-4)}` : value);

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

export function OrdersPageDemo() {
  const { t } = useTranslation();
  const [periodPreset, setPeriodPreset] = useState<PeriodPreset>("7d");
  const [filters, setFilters] = useState({
    from: "",
    to: "",
    status: "",
    q: "",
    station_id: "",
    service_id: "",
    sla_risk: "",
  });

  const safeT = (key: string, fallback: string, options?: Record<string, unknown>) => {
    const value = t(key, options ?? {});
    return value === key ? fallback : value;
  };

  return (
    <div className="stack">
      <section className="card">
        <div className="page-section">
          <div className="page-section__header">
            <h2>{safeT("ordersPage.title", "Заказы")}</h2>
            <div className="neft-actions">
              <button type="button" className="secondary">
                {safeT("ordersPage.actions.saveFilters", "Сохранить фильтры")}
              </button>
            </div>
          </div>
          <div className="page-section__content">
            <div className="filters neft-filters">
              <label className="filter neft-filter">
                {safeT("ordersPage.filters.period", "Период")}
                <select value={periodPreset} onChange={(event) => setPeriodPreset(event.target.value as PeriodPreset)}>
                  <option value="today">{safeT("ordersPage.filters.presets.today", "Сегодня")}</option>
                  <option value="7d">{safeT("ordersPage.filters.presets.7d", "7 дней")}</option>
                  <option value="30d">{safeT("ordersPage.filters.presets.30d", "30 дней")}</option>
                  <option value="custom">{safeT("ordersPage.filters.presets.custom", "Произвольно")}</option>
                </select>
              </label>
              <label className="filter neft-filter">
                {safeT("ordersPage.filters.from", "С")}
                <input
                  type="date"
                  value={filters.from}
                  onChange={(event) => setFilters((prev) => ({ ...prev, from: event.target.value }))}
                />
              </label>
              <label className="filter neft-filter">
                {safeT("ordersPage.filters.to", "По")}
                <input
                  type="date"
                  value={filters.to}
                  onChange={(event) => setFilters((prev) => ({ ...prev, to: event.target.value }))}
                />
              </label>
              <label className="filter neft-filter">
                {safeT("ordersPage.filters.status", "Статус")}
                <select value={filters.status} onChange={(event) => setFilters((prev) => ({ ...prev, status: event.target.value }))}>
                  {statusOptions.map((status) => (
                    <option key={status || "all"} value={status}>
                      {status || safeT("common.all", "Все")}
                    </option>
                  ))}
                </select>
              </label>
              <label className="filter neft-filter">
                {safeT("ordersPage.filters.search", "Поиск")}
                <input
                  type="search"
                  placeholder={safeT("ordersPage.filters.searchPlaceholder", "Номер заказа или клиент")}
                  value={filters.q}
                  onChange={(event) => setFilters((prev) => ({ ...prev, q: event.target.value }))}
                />
              </label>
              <label className="filter neft-filter">
                {safeT("ordersPage.filters.station", "Станция")}
                <input
                  type="text"
                  placeholder={safeT("ordersPage.filters.stationPlaceholder", "ID станции")}
                  value={filters.station_id}
                  onChange={(event) => setFilters((prev) => ({ ...prev, station_id: event.target.value }))}
                />
              </label>
              <label className="filter neft-filter">
                {safeT("ordersPage.filters.service", "Услуга")}
                <input
                  type="text"
                  placeholder={safeT("ordersPage.filters.servicePlaceholder", "ID услуги")}
                  value={filters.service_id}
                  onChange={(event) => setFilters((prev) => ({ ...prev, service_id: event.target.value }))}
                />
              </label>
              <label className="filter neft-filter">
                {safeT("ordersPage.filters.slaRisk", "Риск SLA")}
                <select
                  value={filters.sla_risk}
                  onChange={(event) => setFilters((prev) => ({ ...prev, sla_risk: event.target.value }))}
                >
                  <option value="">{safeT("common.all", "Все")}</option>
                  <option value="near">{safeT("ordersPage.filters.slaRiskNear", "Высокий")}</option>
                </select>
              </label>
            </div>

            <div className="stats-grid">
              <div className="stat">
                <div className="stat__label">{safeT("ordersPage.kpis.today", "Сегодня")}</div>
                <div className="stat__value">{formatNumber(demoOrdersKpis.ordersToday)}</div>
              </div>
              <div className="stat">
                <div className="stat__label">{safeT("ordersPage.kpis.pending", "Ожидают подтверждения")}</div>
                <div className="stat__value">{formatNumber(demoOrdersKpis.pendingConfirmation)}</div>
              </div>
              <div className="stat">
                <div className="stat__label">{safeT("ordersPage.kpis.documents", "Документы")}</div>
                <div className="stat__value">{formatNumber(demoOrdersKpis.docsPending)}</div>
              </div>
              <div className="stat">
                <div className="stat__label">{safeT("ordersPage.kpis.total", "Всего")}</div>
                <div className="stat__value">{formatNumber(demoOrdersKpis.total)}</div>
              </div>
            </div>
          </div>
        </div>

        <div className="page-section">
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>{safeT("ordersPage.table.orderId", "№ заказа")}</th>
                  <th>{safeT("ordersPage.table.client", "Клиент")}</th>
                  <th>{safeT("ordersPage.table.service", "Услуга")}</th>
                  <th>{safeT("ordersPage.table.createdAt", "Создан")}</th>
                  <th>{safeT("ordersPage.table.sla", "SLA")}</th>
                  <th>{safeT("ordersPage.table.amount", "Сумма")}</th>
                  <th>{safeT("ordersPage.table.status", "Статус")}</th>
                  <th>{safeT("ordersPage.table.actions", "Действия")}</th>
                </tr>
              </thead>
              <tbody>
                {demoOrders.map((order) => (
                  <tr key={order.id}>
                    <td>{shortId(order.id)}</td>
                    <td>{order.clientName ?? order.clientId ?? safeT("common.notAvailable", "—")}</td>
                    <td>{order.serviceTitle ?? safeT("common.notAvailable", "—")}</td>
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
                        {safeT("common.open", "Открыть")}
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="pagination pagination-wrapper">
            <button type="button" className="secondary" disabled>
              {safeT("ordersPage.pagination.prev", "Назад")}
            </button>
            <div className="muted">{safeT("ordersPage.pagination.page", "Страница 1 из 1", { current: 1, total: 1 })}</div>
            <button type="button" className="secondary" disabled>
              {safeT("ordersPage.pagination.next", "Вперед")}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
