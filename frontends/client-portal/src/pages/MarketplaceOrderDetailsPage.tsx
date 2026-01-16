import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  cancelMarketplaceOrder,
  fetchMarketplaceOrderConsequences,
  fetchMarketplaceOrderDetails,
  fetchMarketplaceOrderEvents,
  fetchMarketplaceOrderIncidents,
  fetchMarketplaceOrderInvoices,
  fetchMarketplaceOrderSla,
} from "../api/marketplace";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { SupportRequestModal } from "../components/SupportRequestModal";
import { AppEmptyState, AppErrorState, AppForbiddenState } from "../components/states";
import { MoneyValue } from "../components/common/MoneyValue";
import type {
  MarketplaceOrderConsequence,
  MarketplaceOrderDetails,
  MarketplaceOrderEvent,
  MarketplaceOrderInvoice,
  MarketplaceOrderSlaMetric,
} from "../types/marketplace";
import { formatDate, formatDateTime } from "../utils/format";
import { getOrderStatusLabel } from "../utils/status";
import { useI18n } from "../i18n";
import { canCancelMarketplaceOrder } from "../utils/marketplacePermissions";
import type { CaseItem } from "../types/cases";

interface OrderErrorState {
  message: string;
  status?: number;
  correlationId?: string | null;
}

type DetailsTab = "timeline" | "sla" | "incidents" | "invoices";

const statusClass = (status?: string | null) => {
  if (!status) return "neft-chip neft-chip-warn";
  const normalized = status.toLowerCase();
  if (["completed", "confirmed"].includes(normalized)) return "neft-chip neft-chip-ok";
  if (["cancelled", "canceled", "failed"].includes(normalized)) return "neft-chip neft-chip-err";
  return "neft-chip neft-chip-warn";
};

const resolveAmount = (order: MarketplaceOrderDetails) =>
  order.price_snapshot?.total_amount ?? order.total_amount ?? null;

const resolveCurrency = (order: MarketplaceOrderDetails) => order.price_snapshot?.currency ?? order.currency ?? "RUB";

const resolveActorLabel = (actor?: string | null) => {
  if (!actor) return "—";
  const normalized = actor.toLowerCase();
  if (normalized.includes("client")) return "Client";
  if (normalized.includes("partner")) return "Partner";
  if (normalized.includes("system")) return "System";
  return actor;
};

export function MarketplaceOrderDetailsPage() {
  const { orderId } = useParams<{ orderId: string }>();
  const { user } = useAuth();
  const { t } = useI18n();
  const [order, setOrder] = useState<MarketplaceOrderDetails | null>(null);
  const [events, setEvents] = useState<MarketplaceOrderEvent[]>([]);
  const [sla, setSla] = useState<MarketplaceOrderSlaMetric[]>([]);
  const [consequences, setConsequences] = useState<MarketplaceOrderConsequence[]>([]);
  const [invoices, setInvoices] = useState<MarketplaceOrderInvoice[]>([]);
  const [incidents, setIncidents] = useState<CaseItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isEventsLoading, setIsEventsLoading] = useState(true);
  const [isSlaLoading, setIsSlaLoading] = useState(true);
  const [isConsequencesLoading, setIsConsequencesLoading] = useState(true);
  const [isInvoicesLoading, setIsInvoicesLoading] = useState(true);
  const [isIncidentsLoading, setIsIncidentsLoading] = useState(true);
  const [orderError, setOrderError] = useState<OrderErrorState | null>(null);
  const [eventsError, setEventsError] = useState<OrderErrorState | null>(null);
  const [slaError, setSlaError] = useState<OrderErrorState | null>(null);
  const [consequencesError, setConsequencesError] = useState<OrderErrorState | null>(null);
  const [invoicesError, setInvoicesError] = useState<OrderErrorState | null>(null);
  const [incidentsError, setIncidentsError] = useState<OrderErrorState | null>(null);
  const resolvedAmount = order ? resolveAmount(order) : null;
  const resolvedCurrency = order ? resolveCurrency(order) : "RUB";
  const [isSupportOpen, setIsSupportOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<DetailsTab>("timeline");

  const canCancel = canCancelMarketplaceOrder(user);

  const loadOrder = () => {
    if (!user || !orderId) return;
    setIsLoading(true);
    setOrderError(null);
    fetchMarketplaceOrderDetails(user, orderId)
      .then((orderData) => setOrder(orderData))
      .catch((err: unknown) => {
        if (err instanceof ApiError) {
          setOrderError({ message: err.message, status: err.status, correlationId: err.correlationId });
          return;
        }
        setOrderError({ message: err instanceof Error ? err.message : t("marketplaceOrderDetails.errors.loadFailed") });
      })
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    loadOrder();
  }, [user, orderId]);

  useEffect(() => {
    if (!user || !orderId) return;
    setEventsError(null);
    setIsEventsLoading(true);
    fetchMarketplaceOrderEvents(user, orderId)
      .then((data) => setEvents(data ?? []))
      .catch((err: unknown) => {
        if (err instanceof ApiError) {
          setEventsError({ message: err.message, status: err.status, correlationId: err.correlationId });
          return;
        }
        setEventsError({ message: err instanceof Error ? err.message : t("marketplaceOrderDetails.errors.eventsFailed") });
      })
      .finally(() => setIsEventsLoading(false));
  }, [user, orderId, t]);

  useEffect(() => {
    if (!user || !orderId) return;
    setSlaError(null);
    setIsSlaLoading(true);
    fetchMarketplaceOrderSla(user, orderId)
      .then((data) => setSla(data.obligations ?? []))
      .catch((err: unknown) => {
        if (err instanceof ApiError) {
          setSlaError({ message: err.message, status: err.status, correlationId: err.correlationId });
          return;
        }
        setSlaError({ message: err instanceof Error ? err.message : t("marketplaceOrderDetails.errors.slaFailed") });
      })
      .finally(() => setIsSlaLoading(false));
  }, [user, orderId, t]);

  useEffect(() => {
    if (!user || !orderId) return;
    setConsequencesError(null);
    setIsConsequencesLoading(true);
    fetchMarketplaceOrderConsequences(user, orderId)
      .then((data) => setConsequences(data.items ?? []))
      .catch((err: unknown) => {
        if (err instanceof ApiError) {
          setConsequencesError({ message: err.message, status: err.status, correlationId: err.correlationId });
          return;
        }
        setConsequencesError({ message: err instanceof Error ? err.message : t("marketplaceOrderDetails.errors.consequencesFailed") });
      })
      .finally(() => setIsConsequencesLoading(false));
  }, [user, orderId, t]);

  useEffect(() => {
    if (!user || !orderId) return;
    setInvoicesError(null);
    setIsInvoicesLoading(true);
    fetchMarketplaceOrderInvoices(user, orderId)
      .then((data) => setInvoices(data ?? []))
      .catch((err: unknown) => {
        if (err instanceof ApiError) {
          setInvoicesError({ message: err.message, status: err.status, correlationId: err.correlationId });
          return;
        }
        setInvoicesError({ message: err instanceof Error ? err.message : t("marketplaceOrderDetails.errors.invoicesFailed") });
      })
      .finally(() => setIsInvoicesLoading(false));
  }, [user, orderId, t]);

  useEffect(() => {
    if (!user || !orderId) return;
    setIncidentsError(null);
    setIsIncidentsLoading(true);
    fetchMarketplaceOrderIncidents(user, orderId)
      .then((data) => setIncidents(data.items ?? []))
      .catch((err: unknown) => {
        if (err instanceof ApiError) {
          setIncidentsError({ message: err.message, status: err.status, correlationId: err.correlationId });
          return;
        }
        setIncidentsError({ message: err instanceof Error ? err.message : t("marketplaceOrderDetails.errors.incidentsFailed") });
      })
      .finally(() => setIsIncidentsLoading(false));
  }, [user, orderId, t]);

  const timeline = useMemo(() => events.slice().sort((a, b) => a.created_at.localeCompare(b.created_at)), [events]);

  const tabs = useMemo(
    () => [
      { key: "timeline" as const, label: t("marketplaceOrderDetails.tabs.timeline") },
      { key: "sla" as const, label: t("marketplaceOrderDetails.tabs.sla") },
      { key: "incidents" as const, label: t("marketplaceOrderDetails.tabs.incidents") },
      { key: "invoices" as const, label: t("marketplaceOrderDetails.tabs.invoices") },
    ],
    [t],
  );

  const invoiceExport = invoices.find((invoice) => invoice.url);

  const handleCancel = async () => {
    if (!user || !orderId) return;
    const confirmed = window.confirm(t("marketplaceOrderDetails.actions.confirmCancel"));
    if (!confirmed) return;
    try {
      await cancelMarketplaceOrder(user, orderId);
      loadOrder();
      setActiveTab("timeline");
    } catch (err) {
      const message = err instanceof ApiError ? err.message : t("marketplaceOrderDetails.errors.cancelFailed");
      setOrderError({ message });
    }
  };

  if (!user) {
    return <AppForbiddenState message={t("marketplaceOrderDetails.forbidden.noAccess")} />;
  }

  if (orderError?.status === 403) {
    return <AppForbiddenState message={t("marketplaceOrderDetails.forbidden.denied")} />;
  }

  return (
    <div className="stack">
      <div className="card">
        <div className="card__header">
          <div>
            <h2>{order?.service_title ?? t("marketplaceOrderDetails.title")}</h2>
            <p className="muted">
              {order?.partner_name ? t("marketplaceOrderDetails.partner", { name: order.partner_name }) : t("marketplaceOrderDetails.subtitle")}
            </p>
          </div>
          <div className="actions">
            <button type="button" className="secondary" onClick={() => setIsSupportOpen(true)}>
              {t("marketplaceOrderDetails.actions.contactSupport")}
            </button>
            {invoiceExport ? (
              <a href={invoiceExport.url ?? "#"} className="link-button" target="_blank" rel="noreferrer">
                {t("marketplaceOrderDetails.actions.downloadInvoice")}
              </a>
            ) : null}
            {canCancel && order?.status === "CREATED" ? (
              <button type="button" className="secondary" onClick={handleCancel}>
                {t("actions.cancel")}
              </button>
            ) : null}
            <Link to="/marketplace/orders" className="link-button">
              {t("marketplaceOrderDetails.actions.backToOrders")}
            </Link>
          </div>
        </div>

        {isLoading ? (
          <div className="skeleton-stack">
            <div className="skeleton-line" />
            <div className="skeleton-line" />
            <div className="skeleton-line" />
          </div>
        ) : null}

        {orderError ? (
          <AppErrorState
            message={orderError.message}
            status={orderError.status}
            correlationId={orderError.correlationId}
            onRetry={loadOrder}
          />
        ) : null}

        {!isLoading && !orderError && order ? (
          <div className="grid two">
            <div className="card muted-card">
              <div className="muted small">{t("marketplaceOrderDetails.fields.status")}</div>
              <div className={statusClass(order.status)}>{getOrderStatusLabel(order.status)}</div>
              <div className="muted small">{t("marketplaceOrderDetails.fields.created")}</div>
              <div>{order.created_at ? formatDate(order.created_at) : "—"}</div>
            </div>
            <div className="card muted-card">
              <div className="muted small">{t("marketplaceOrderDetails.fields.amount")}</div>
              <div>
                {resolvedAmount !== null && resolvedAmount !== undefined
                  ? <MoneyValue amount={resolvedAmount} currency={resolvedCurrency} />
                  : "—"}
              </div>
              <div className="muted small">{t("marketplaceOrderDetails.fields.updated")}</div>
              <div>{order.updated_at ? formatDateTime(order.updated_at) : "—"}</div>
            </div>
          </div>
        ) : null}
      </div>

      <div className="card">
        <div className="tabs">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              type="button"
              className={activeTab === tab.key ? "secondary" : "ghost"}
              onClick={() => setActiveTab(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === "timeline" ? (
          <div>
            {eventsError ? (
              <AppErrorState message={eventsError.message} status={eventsError.status} correlationId={eventsError.correlationId} />
            ) : null}
            {isEventsLoading ? (
              <div className="skeleton-stack">
                <div className="skeleton-line" />
                <div className="skeleton-line" />
              </div>
            ) : null}
            {!eventsError && !isEventsLoading && timeline.length === 0 ? (
              <AppEmptyState title={t("marketplaceOrderDetails.timeline.emptyTitle")} description={t("marketplaceOrderDetails.timeline.emptyDescription")} />
            ) : null}
            {!eventsError && !isEventsLoading && timeline.length > 0 ? (
              <ul className="timeline">
                {timeline.map((event) => (
                  <li key={event.id}>
                    <div className="timeline__marker" />
                    <div>
                      <strong>{event.type}</strong>
                      <div className="muted small">{event.created_at ? formatDateTime(event.created_at) : "—"}</div>
                      <div className="muted small">{t("marketplaceOrderDetails.timeline.actor", { actor: resolveActorLabel(event.actor_type) })}</div>
                      {event.note ? <div className="muted">{event.note}</div> : null}
                    </div>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}

        {activeTab === "sla" ? (
          <div className="stack">
            {slaError ? (
              <AppErrorState message={slaError.message} status={slaError.status} correlationId={slaError.correlationId} />
            ) : null}
            {isSlaLoading ? (
              <div className="skeleton-stack">
                <div className="skeleton-line" />
                <div className="skeleton-line" />
              </div>
            ) : null}
            {!slaError && !isSlaLoading && sla.length === 0 ? (
              <AppEmptyState title={t("marketplaceOrderDetails.sla.emptyTitle")} description={t("marketplaceOrderDetails.sla.emptyDescription")} />
            ) : null}
            {!slaError && !isSlaLoading && sla.length > 0 ? (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>{t("marketplaceOrderDetails.sla.table.metric")}</th>
                    <th>{t("marketplaceOrderDetails.sla.table.threshold")}</th>
                    <th>{t("marketplaceOrderDetails.sla.table.measured")}</th>
                    <th>{t("marketplaceOrderDetails.sla.table.status")}</th>
                    <th>{t("marketplaceOrderDetails.sla.table.penalty")}</th>
                  </tr>
                </thead>
                <tbody>
                  {sla.map((metric) => (
                    <tr key={`${metric.metric}-${metric.deadline_at ?? ""}`}>
                      <td>{metric.metric}</td>
                      <td>{metric.threshold ?? "—"}</td>
                      <td>{metric.measured_value ?? "—"}</td>
                      <td>{metric.status ?? "—"}</td>
                      <td>{metric.penalty ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : null}
          </div>
        ) : null}

        {activeTab === "incidents" ? (
          <div>
            {incidentsError ? (
              <AppErrorState message={incidentsError.message} status={incidentsError.status} correlationId={incidentsError.correlationId} />
            ) : null}
            {isIncidentsLoading ? (
              <div className="skeleton-stack">
                <div className="skeleton-line" />
                <div className="skeleton-line" />
              </div>
            ) : null}
            {!incidentsError && !isIncidentsLoading && incidents.length === 0 ? (
              <AppEmptyState title={t("marketplaceOrderDetails.incidents.emptyTitle")} description={t("marketplaceOrderDetails.incidents.emptyDescription")} />
            ) : null}
            {!incidentsError && !isIncidentsLoading && incidents.length > 0 ? (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>{t("marketplaceOrderDetails.incidents.table.id")}</th>
                    <th>{t("marketplaceOrderDetails.incidents.table.title")}</th>
                    <th>{t("marketplaceOrderDetails.incidents.table.status")}</th>
                    <th>{t("marketplaceOrderDetails.incidents.table.updated")}</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {incidents.map((incident) => (
                    <tr key={incident.id}>
                      <td className="mono">{incident.id}</td>
                      <td>{incident.title}</td>
                      <td>{incident.status}</td>
                      <td>{formatDateTime(incident.updated_at)}</td>
                      <td>
                        <Link to={`/cases/${incident.id}`} className="link-button">
                          {t("common.open")}
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : null}
          </div>
        ) : null}

        {activeTab === "invoices" ? (
          <div className="stack">
            {invoicesError ? (
              <AppErrorState message={invoicesError.message} status={invoicesError.status} correlationId={invoicesError.correlationId} />
            ) : null}
            {isInvoicesLoading || isConsequencesLoading ? (
              <div className="skeleton-stack">
                <div className="skeleton-line" />
                <div className="skeleton-line" />
              </div>
            ) : null}
            {!invoicesError && !isInvoicesLoading && invoices.length === 0 ? (
              <AppEmptyState title={t("marketplaceOrderDetails.invoices.emptyTitle")} description={t("marketplaceOrderDetails.invoices.emptyDescription")} />
            ) : null}
            {!invoicesError && !isInvoicesLoading && invoices.length > 0 ? (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>{t("marketplaceOrderDetails.invoices.table.number")}</th>
                    <th>{t("marketplaceOrderDetails.invoices.table.status")}</th>
                    <th>{t("marketplaceOrderDetails.invoices.table.amount")}</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {invoices.map((invoice) => (
                    <tr key={invoice.id}>
                      <td>{invoice.invoice_number ?? invoice.id}</td>
                      <td>{invoice.status ?? "—"}</td>
                      <td>
                        {invoice.amount !== undefined && invoice.amount !== null
                          ? <MoneyValue amount={invoice.amount} currency={invoice.currency ?? "RUB"} />
                          : "—"}
                      </td>
                      <td>
                        {invoice.url ? (
                          <a href={invoice.url} target="_blank" rel="noreferrer" className="link-button">
                            {t("actions.download")}
                          </a>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : null}
            {!consequencesError && !isConsequencesLoading && consequences.length > 0 ? (
              <div>
                <div className="section-title">
                  <h4>{t("marketplaceOrderDetails.invoices.creditsTitle")}</h4>
                </div>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>{t("marketplaceOrderDetails.invoices.credits.table.type")}</th>
                      <th>{t("marketplaceOrderDetails.invoices.credits.table.amount")}</th>
                      <th>{t("marketplaceOrderDetails.invoices.credits.table.reason")}</th>
                      <th>{t("marketplaceOrderDetails.invoices.credits.table.date")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {consequences.map((item) => (
                      <tr key={item.id}>
                        <td>{item.type ?? "—"}</td>
                        <td>
                          {item.amount !== undefined && item.amount !== null
                            ? <MoneyValue amount={item.amount} currency={item.currency ?? "RUB"} />
                            : "—"}
                        </td>
                        <td>{item.reason ?? "—"}</td>
                        <td>{item.created_at ? formatDateTime(item.created_at) : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
            {consequencesError ? (
              <AppErrorState
                message={consequencesError.message}
                status={consequencesError.status}
                correlationId={consequencesError.correlationId}
              />
            ) : null}
          </div>
        ) : null}
      </div>

      {order ? (
        <SupportRequestModal
          isOpen={isSupportOpen}
          onClose={() => setIsSupportOpen(false)}
          defaultSubject={t("marketplaceOrderDetails.supportTitle", { id: order.id })}
        />
      ) : null}
    </div>
  );
}
