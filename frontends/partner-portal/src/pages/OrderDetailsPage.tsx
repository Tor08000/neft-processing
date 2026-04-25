import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../api/http";
import {
  completeOrder,
  confirmOrder,
  declineOrder,
  fetchOrder,
  fetchOrderEvents,
  fetchOrderIncidents,
  fetchOrderSettlementBreakdown,
  fetchOrderSla,
  uploadOrderProof,
} from "../api/orders";
import { useAuth } from "../auth/AuthContext";
import { usePortal } from "../auth/PortalContext";
import { StatusBadge } from "../components/StatusBadge";
import { SupportRequestModal } from "../components/SupportRequestModal";
import { EmptyState, ErrorState, ForbiddenState, LoadingState } from "../components/states";
import type {
  MarketplaceOrder,
  MarketplaceOrderEvent,
  MarketplaceOrderIncident,
  MarketplaceOrderSettlementBreakdown,
  MarketplaceOrderSlaMetric,
} from "../types/marketplace";
import { formatCurrency, formatDateTime } from "../utils/format";
import { canManageOrderLifecycle, canReadOrders } from "../utils/roles";
import { resolveEffectivePartnerRoles } from "../access/partnerWorkspace";
import { OrderTimelinePanel } from "./OrderTimelinePanel";
import { useTranslation } from "react-i18next";

const canConfirmStatus = (status: string) => ["PAID"].includes(status);
const canDeclineStatus = (status: string) => ["PAID"].includes(status);
const canCompleteStatus = (status: string) => ["CONFIRMED_BY_PARTNER"].includes(status);

const describeError = (err: unknown, fallback: string) => {
  if (err instanceof ApiError) {
    return { message: fallback, correlationId: null };
  }
  if (err instanceof Error) {
    return { message: fallback, correlationId: null };
  }
  return { message: fallback, correlationId: null };
};

const isSettlementNotFinalizedError = (err: unknown) =>
  err instanceof ApiError &&
  err.status === 409 &&
  (err.errorCode === "SETTLEMENT_NOT_FINALIZED" || err.message === "SETTLEMENT_NOT_FINALIZED");

const reportUnexpectedError = (err: unknown) => {
  if (err instanceof ApiError) {
    return;
  }
  console.error(err);
};

type ActionModal = "confirm" | "decline" | "complete" | "proof" | null;

const createAttachmentId = () => {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `attachment-${Math.random().toString(16).slice(2)}`;
};

const formatCountdown = (seconds: number | null) => {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return "—";
  const clamped = Math.max(0, seconds);
  const hours = Math.floor(clamped / 3600);
  const minutes = Math.floor((clamped % 3600) / 60);
  const secs = clamped % 60;
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
};

const resolveSlaTone = (metric: MarketplaceOrderSlaMetric) => {
  const total = metric.totalSeconds ?? null;
  const remaining = metric.remainingSeconds ?? null;
  if (!total || remaining === null) return "neutral";
  const ratio = remaining / total;
  if (ratio <= 0.1) return "error";
  if (ratio <= 0.25) return "pending";
  return "success";
};

export function OrderDetailsPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const { portal } = usePortal();
  const { t } = useTranslation();
  const [order, setOrder] = useState<MarketplaceOrder | null>(null);
  const [orderLoading, setOrderLoading] = useState(true);
  const [orderError, setOrderError] = useState<string | null>(null);
  const [orderCorrelationId, setOrderCorrelationId] = useState<string | null>(null);

  const [events, setEvents] = useState<MarketplaceOrderEvent[]>([]);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [eventsError, setEventsError] = useState<string | null>(null);
  const [eventsCorrelationId, setEventsCorrelationId] = useState<string | null>(null);

  const [incidents, setIncidents] = useState<MarketplaceOrderIncident[]>([]);
  const [incidentsLoading, setIncidentsLoading] = useState(true);
  const [incidentsError, setIncidentsError] = useState<string | null>(null);
  const [incidentsCorrelationId, setIncidentsCorrelationId] = useState<string | null>(null);

  const [sla, setSla] = useState<MarketplaceOrderSlaMetric[]>([]);
  const [slaLoading, setSlaLoading] = useState(true);
  const [slaError, setSlaError] = useState<string | null>(null);
  const [slaCorrelationId, setSlaCorrelationId] = useState<string | null>(null);

  const [settlementBreakdown, setSettlementBreakdown] = useState<MarketplaceOrderSettlementBreakdown | null>(null);
  const [breakdownLoading, setBreakdownLoading] = useState(true);
  const [breakdownError, setBreakdownError] = useState<string | null>(null);
  const [breakdownCorrelationId, setBreakdownCorrelationId] = useState<string | null>(null);
  const [breakdownPending, setBreakdownPending] = useState(false);

  const [actionModal, setActionModal] = useState<ActionModal>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionCorrelationId, setActionCorrelationId] = useState<string | null>(null);
  const [declineReason, setDeclineReason] = useState("");
  const [declineComment, setDeclineComment] = useState("");
  const [completeSummary, setCompleteSummary] = useState("");
  const [proofKind, setProofKind] = useState("PHOTO");
  const [proofNote, setProofNote] = useState("");
  const [proofAttachmentId, setProofAttachmentId] = useState("");
  const [isSupportOpen, setIsSupportOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<"timeline" | "incidents" | "sla" | "payouts">("timeline");

  const effectiveRoles = resolveEffectivePartnerRoles(portal, user?.roles);
  const canRead = canReadOrders(effectiveRoles);
  const canManage = canManageOrderLifecycle(effectiveRoles);

  const orderId = id ?? "";

  const loadOrder = useCallback(() => {
    if (!user || !orderId) return;
    setOrderLoading(true);
    setOrderError(null);
    setOrderCorrelationId(null);
    fetchOrder(user.token, orderId)
      .then((data) => {
        setOrder(data);
      })
      .catch((err) => {
        reportUnexpectedError(err);
        const { message, correlationId } = describeError(err, t("marketplace.orderDetails.errors.loadFailed"));
        setOrderError(message);
        setOrderCorrelationId(correlationId);
      })
      .finally(() => {
        setOrderLoading(false);
      });
  }, [user, orderId, t]);

  const loadEvents = useCallback(() => {
    if (!user || !orderId) return;
    setEventsLoading(true);
    setEventsError(null);
    setEventsCorrelationId(null);
    fetchOrderEvents(user.token, orderId)
      .then((data) => setEvents(data))
      .catch((err) => {
        reportUnexpectedError(err);
        const { message, correlationId } = describeError(err, t("marketplace.orderDetails.errors.timelineFailed"));
        setEventsError(message);
        setEventsCorrelationId(correlationId);
      })
      .finally(() => setEventsLoading(false));
  }, [user, orderId, t]);

  const loadIncidents = useCallback(() => {
    if (!user || !orderId) return;
    setIncidentsLoading(true);
    setIncidentsError(null);
    setIncidentsCorrelationId(null);
    fetchOrderIncidents(user.token, orderId)
      .then((data) => setIncidents(data))
      .catch((err) => {
        reportUnexpectedError(err);
        const { message, correlationId } = describeError(err, t("marketplace.orderDetails.errors.incidentsFailed"));
        setIncidentsError(message);
        setIncidentsCorrelationId(correlationId);
      })
      .finally(() => setIncidentsLoading(false));
  }, [user, orderId, t]);

  const loadSla = useCallback(() => {
    if (!user || !orderId) return;
    setSlaLoading(true);
    setSlaError(null);
    setSlaCorrelationId(null);
    fetchOrderSla(user.token, orderId)
      .then((data) => setSla(data.obligations ?? []))
      .catch((err) => {
        reportUnexpectedError(err);
        const { message, correlationId } = describeError(err, t("marketplace.orderDetails.errors.slaFailed"));
        setSlaError(message);
        setSlaCorrelationId(correlationId);
      })
      .finally(() => setSlaLoading(false));
  }, [user, orderId, t]);

  const loadSettlementBreakdown = useCallback(() => {
    if (!user || !orderId) return;
    setBreakdownLoading(true);
    setBreakdownError(null);
    setBreakdownCorrelationId(null);
    setBreakdownPending(false);
    fetchOrderSettlementBreakdown(user.token, orderId)
      .then((data) => {
        setSettlementBreakdown(data);
        setBreakdownPending(false);
      })
      .catch((err) => {
        if (isSettlementNotFinalizedError(err)) {
          setSettlementBreakdown(null);
          setBreakdownPending(true);
          return;
        }
        reportUnexpectedError(err);
        const { message, correlationId } = describeError(err, t("marketplace.orderDetails.errors.payoutFailed"));
        setBreakdownError(message);
        setBreakdownCorrelationId(correlationId);
      })
      .finally(() => setBreakdownLoading(false));
  }, [user, orderId, t]);

  useEffect(() => {
    if (!canRead) return;
    loadOrder();
    loadEvents();
    loadIncidents();
    loadSla();
    loadSettlementBreakdown();
  }, [canRead, loadOrder, loadEvents, loadIncidents, loadSla, loadSettlementBreakdown]);

  const handleAction = async () => {
    if (!user || !order || !actionModal) return;
    setActionError(null);
    setActionMessage(null);
    setActionCorrelationId(null);
    try {
      if (actionModal === "confirm") {
        await confirmOrder(user.token, order.id);
        setActionMessage(t("marketplace.orderDetails.notifications.confirmed"));
        setActionCorrelationId(null);
      }
      if (actionModal === "decline") {
        await declineOrder(user.token, order.id, declineReason.trim(), declineComment.trim());
        setActionMessage(t("marketplace.orderDetails.notifications.declined"));
        setActionCorrelationId(null);
      }
      if (actionModal === "proof") {
        const attachmentId = proofAttachmentId.trim() || createAttachmentId();
        await uploadOrderProof(user.token, order.id, {
          attachment_id: attachmentId,
          kind: proofKind,
          note: proofNote.trim() || undefined,
        });
        setActionMessage(t("marketplace.orderDetails.notifications.proofUploaded"));
        setActionCorrelationId(null);
      }
      if (actionModal === "complete") {
        await completeOrder(user.token, order.id, { comment: completeSummary.trim() || undefined });
        setActionMessage(t("marketplace.orderDetails.notifications.completed"));
        setActionCorrelationId(null);
      }
      setActionModal(null);
      setDeclineReason("");
      setDeclineComment("");
      setCompleteSummary("");
      setProofNote("");
      setProofKind("PHOTO");
      setProofAttachmentId("");
      loadOrder();
      loadEvents();
      loadIncidents();
      loadSla();
      loadSettlementBreakdown();
    } catch (err) {
      reportUnexpectedError(err);
      const { message, correlationId } = describeError(err, t("marketplace.orderDetails.errors.actionFailed"));
      setActionError(message);
      setActionCorrelationId(correlationId);
    }
  };

  const responseSla = useMemo(() => sla.find((item) => item.metric?.toLowerCase().includes("response")) ?? null, [sla]);
  const completionSla = useMemo(() => sla.find((item) => item.metric?.toLowerCase().includes("completion")) ?? null, [sla]);

  const disableDecline = declineReason.trim().length === 0 || declineComment.trim().length === 0;
  const disableComplete = completeSummary.trim().length === 0;
  const disableProof = proofKind.trim().length === 0;
  const proofsCount = order?.proofs?.length ?? 0;

  if (!canRead) {
    return <ForbiddenState />;
  }

  if (orderLoading) {
    return <LoadingState label={t("marketplace.orderDetails.loading")} />;
  }

  if (orderError || !order) {
    return (
      <ErrorState
        title={t("marketplace.orderDetails.errors.loadTitle")}
        description={orderError ?? t("marketplace.orderDetails.errors.notFound")}
        correlationId={orderCorrelationId}
        action={
          <button type="button" className="secondary" onClick={loadOrder}>
            {t("errors.retry")}
          </button>
        }
      />
    );
  }

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <div>
            <h2>{t("marketplace.orderDetails.title", { id: order.id })}</h2>
            <p className="muted">{order.serviceTitle ?? t("marketplace.orderDetails.subtitle")}</p>
          </div>
          <div className="actions">
            <button type="button" className="secondary" onClick={() => setIsSupportOpen(true)}>
              {t("marketplace.orderDetails.actions.support")}
            </button>
            <Link to="/orders" className="ghost">
              {t("marketplace.orderDetails.actions.back")}
            </Link>
          </div>
        </div>
        <div className="meta-grid">
          <div>
            <div className="label">{t("marketplace.orderDetails.fields.status")}</div>
            <StatusBadge status={order.status} />
          </div>
          <div>
            <div className="label">{t("marketplace.orderDetails.fields.client")}</div>
            <div>{order.clientName ?? order.clientId ?? t("common.notAvailable")}</div>
          </div>
          <div>
            <div className="label">{t("marketplace.orderDetails.fields.created")}</div>
            <div>{formatDateTime(order.createdAt)}</div>
          </div>
          <div>
            <div className="label">{t("marketplace.orderDetails.fields.amount")}</div>
            <div>{formatCurrency(order.totalAmount ?? null, order.currency ?? "RUB")}</div>
          </div>
        </div>
        <div className="card__section">
          <div className="meta-grid">
            <div>
              <div className="label">{t("marketplace.orderDetails.fields.responseDue")}</div>
              <div className={`badge ${responseSla ? resolveSlaTone(responseSla) : "neutral"}`}>
                {responseSla ? formatCountdown(responseSla.remainingSeconds ?? null) : "—"}
              </div>
            </div>
            <div>
              <div className="label">{t("marketplace.orderDetails.fields.completionDue")}</div>
              <div className={`badge ${completionSla ? resolveSlaTone(completionSla) : "neutral"}`}>
                {completionSla ? formatCountdown(completionSla.remainingSeconds ?? null) : "—"}
              </div>
            </div>
          </div>
        </div>
        <div className="card__section">
          <div className="section-title">
            <h3>{t("marketplace.orderDetails.lifecycle.title")}</h3>
          </div>
          {!canManage ? (
            <EmptyState title={t("marketplace.orderDetails.lifecycle.deniedTitle")} description={t("marketplace.orderDetails.lifecycle.deniedDescription")} />
          ) : (
            <div className="actions">
              <button
                type="button"
                className="secondary"
                onClick={() => setActionModal("confirm")}
                disabled={!canConfirmStatus(order.status)}
              >
                {t("marketplace.orderDetails.actions.confirm")}
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => setActionModal("decline")}
                disabled={!canDeclineStatus(order.status)}
              >
                {t("marketplace.orderDetails.actions.decline")}
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => setActionModal("proof")}
                disabled={!canCompleteStatus(order.status)}
              >
                {t("marketplace.orderDetails.actions.uploadProof")}
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => setActionModal("complete")}
                disabled={!canCompleteStatus(order.status) || proofsCount === 0}
              >
                {t("marketplace.orderDetails.actions.complete")}
              </button>
            </div>
          )}
          {actionMessage ? <div className="notice">{actionMessage}</div> : null}
          {actionError ? (
            <div className="notice error">
              {actionError}
            </div>
          ) : null}
        </div>
        <div className="card__section">
          <div className="section-title">
            <h3>{t("marketplace.orderDetails.proofs.title")}</h3>
          </div>
          {order.proofs && order.proofs.length ? (
            <ul className="stack">
              {order.proofs.map((proof) => (
                <li key={proof.id}>
                  <div className="muted small">{proof.kind}</div>
                  <div className="mono">{proof.attachmentId}</div>
                  {proof.note ? <div className="muted">{proof.note}</div> : null}
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState
              title={t("marketplace.orderDetails.proofs.title")}
              description={t("marketplace.orderDetails.proofs.empty")}
              action={
                canManage && canCompleteStatus(order.status) ? (
                  <button type="button" className="secondary" onClick={() => setActionModal("proof")}>
                    {t("marketplace.orderDetails.actions.uploadProof")}
                  </button>
                ) : undefined
              }
            />
          )}
        </div>
      </section>

      <section className="card">
        <div className="section-title">
          <h3>{t("marketplace.orderDetails.settlement.title")}</h3>
        </div>
        {breakdownLoading ? (
          <LoadingState label={t("marketplace.orderDetails.settlement.loading")} />
        ) : breakdownPending ? (
          <EmptyState
            title={t("marketplace.orderDetails.settlement.pendingTitle")}
            description={t("marketplace.orderDetails.settlement.pendingDescription")}
            action={
              <>
                <Link className="secondary" to="/finance">
                  {t("marketplace.orderDetails.settlement.pendingActions.openFinance")}
                </Link>
                <Link className="ghost" to="/support/requests">
                  {t("marketplace.orderDetails.settlement.pendingActions.openSupport")}
                </Link>
              </>
            }
          />
        ) : breakdownError ? (
          <ErrorState
            title={t("marketplace.orderDetails.settlement.errorTitle")}
            description={breakdownError}
            correlationId={breakdownCorrelationId}
            action={
              <button type="button" className="secondary" onClick={loadSettlementBreakdown}>
                {t("errors.retry")}
              </button>
            }
          />
        ) : settlementBreakdown ? (
          <div className="stack">
            <div className="meta-grid">
              <div>
                <div className="label">{t("marketplace.orderDetails.settlement.metrics.gross")}</div>
                <div>{formatCurrency(settlementBreakdown.gross_amount, settlementBreakdown.currency)}</div>
              </div>
              <div>
                <div className="label">{t("marketplace.orderDetails.settlement.metrics.fee")}</div>
                <div>
                  {formatCurrency(settlementBreakdown.platform_fee.amount, settlementBreakdown.currency)}
                  <div className="muted small">{settlementBreakdown.platform_fee.explain}</div>
                </div>
              </div>
              <div>
                <div className="label">{t("marketplace.orderDetails.settlement.metrics.penalties")}</div>
                <div>
                  {formatCurrency(
                    settlementBreakdown.penalties.reduce((sum, item) => sum + item.amount, 0),
                    settlementBreakdown.currency,
                  )}
                </div>
              </div>
              <div>
                <div className="label">{t("marketplace.orderDetails.settlement.metrics.net")}</div>
                <div>{formatCurrency(settlementBreakdown.partner_net, settlementBreakdown.currency)}</div>
              </div>
            </div>
            {settlementBreakdown.penalties.length ? (
              <table className="table">
                <thead>
                  <tr>
                    <th>{t("marketplace.orderDetails.settlement.penalties.table.type")}</th>
                    <th>{t("marketplace.orderDetails.settlement.penalties.table.reason")}</th>
                    <th>{t("marketplace.orderDetails.settlement.penalties.table.amount")}</th>
                    <th>{t("marketplace.orderDetails.settlement.penalties.table.source")}</th>
                  </tr>
                </thead>
                <tbody>
                  {settlementBreakdown.penalties.map((penalty, index) => (
                    <tr key={`${penalty.type}-${index}`}>
                      <td>{penalty.type}</td>
                      <td>{penalty.reason ?? "—"}</td>
                      <td>{formatCurrency(penalty.amount, settlementBreakdown.currency)}</td>
                      <td>
                        {penalty.source_ref?.audit_event_id ? (
                          <Link className="link-button" to="/support/requests">
                            {t("marketplace.orderDetails.settlement.penalties.actions.support")}
                          </Link>
                        ) : penalty.source_ref?.sla_event_id ? (
                          <span className="muted">
                            {t("marketplace.orderDetails.settlement.penalties.actions.sla", {
                              id: penalty.source_ref.sla_event_id,
                            })}
                          </span>
                        ) : (
                          <span className="muted">{t("common.notAvailable")}</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <EmptyState
                title={t("marketplace.orderDetails.settlement.noPenaltiesTitle")}
                description={t("marketplace.orderDetails.settlement.noPenaltiesDescription")}
              />
            )}
            {settlementBreakdown.snapshot ? (
              <div className="meta-grid">
                <div>
                  <div className="label">{t("marketplace.orderDetails.settlement.snapshot.finalizedAt")}</div>
                  <div>
                    {settlementBreakdown.snapshot.finalized_at
                      ? formatDateTime(settlementBreakdown.snapshot.finalized_at)
                      : t("common.notAvailable")}
                  </div>
                </div>
                <div>
                  <div className="label">{t("marketplace.orderDetails.settlement.snapshot.hash")}</div>
                  <div className="mono">{settlementBreakdown.snapshot.hash ?? t("common.notAvailable")}</div>
                </div>
              </div>
            ) : (
              <EmptyState
                title={t("marketplace.orderDetails.settlement.snapshot.pendingTitle")}
                description={t("marketplace.orderDetails.settlement.snapshot.pendingDescription")}
              />
            )}
          </div>
        ) : (
          <EmptyState
            title={t("marketplace.orderDetails.settlement.emptyTitle")}
            description={t("marketplace.orderDetails.settlement.emptyDescription")}
          />
        )}
      </section>

      <section className="card">
        <div className="tabs">
          <button type="button" className={activeTab === "timeline" ? "secondary" : "ghost"} onClick={() => setActiveTab("timeline")}>
            {t("marketplace.orderDetails.tabs.timeline")}
          </button>
          <button type="button" className={activeTab === "incidents" ? "secondary" : "ghost"} onClick={() => setActiveTab("incidents")}>
            {t("marketplace.orderDetails.tabs.incidents")}
          </button>
          <button type="button" className={activeTab === "sla" ? "secondary" : "ghost"} onClick={() => setActiveTab("sla")}>
            {t("marketplace.orderDetails.tabs.sla")}
          </button>
          <button type="button" className={activeTab === "payouts" ? "secondary" : "ghost"} onClick={() => setActiveTab("payouts")}>
            {t("marketplace.orderDetails.tabs.payouts")}
          </button>
        </div>

        {activeTab === "timeline" ? (
          <OrderTimelinePanel
            events={events}
            isLoading={eventsLoading}
            error={eventsError}
            correlationId={eventsCorrelationId}
            onRetry={loadEvents}
          />
        ) : null}

        {activeTab === "incidents" ? (
          <div>
            {incidentsLoading ? (
              <LoadingState label={t("marketplace.orderDetails.incidents.loading")} />
            ) : incidentsError ? (
              <ErrorState
                title={t("marketplace.orderDetails.incidents.errorTitle")}
                description={incidentsError}
                correlationId={incidentsCorrelationId}
                action={
                  <button type="button" className="secondary" onClick={loadIncidents}>
                    {t("errors.retry")}
                  </button>
                }
              />
            ) : incidents.length === 0 ? (
              <EmptyState
                title={t("marketplace.orderDetails.incidents.emptyTitle")}
                description={t("marketplace.orderDetails.incidents.emptyDescription")}
                action={
                  <button type="button" className="secondary" onClick={() => setIsSupportOpen(true)}>
                    {t("marketplace.orderDetails.actions.support")}
                  </button>
                }
              />
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>{t("marketplace.orderDetails.incidents.table.id")}</th>
                    <th>{t("marketplace.orderDetails.incidents.table.title")}</th>
                    <th>{t("marketplace.orderDetails.incidents.table.status")}</th>
                    <th>{t("marketplace.orderDetails.incidents.table.queue")}</th>
                    <th>{t("marketplace.orderDetails.incidents.table.source")}</th>
                    <th>{t("marketplace.orderDetails.incidents.table.updated")}</th>
                    <th>{t("common.actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {incidents.map((incident) => (
                    <tr key={incident.id}>
                      <td className="mono">{incident.id}</td>
                      <td>{incident.title}</td>
                      <td>{incident.status}</td>
                      <td>{incident.queue ?? "—"}</td>
                      <td>
                        {incident.sourceRefType
                          ? `${incident.sourceRefType}${incident.sourceRefId ? ` / ${incident.sourceRefId}` : ""}`
                          : "—"}
                      </td>
                      <td>{formatDateTime(incident.updatedAt)}</td>
                      <td>
                        <Link to={`/cases/${incident.id}`}>{t("common.open")}</Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        ) : null}

        {activeTab === "sla" ? (
          <div>
            {slaLoading ? (
              <LoadingState label={t("marketplace.orderDetails.sla.loading")} />
            ) : slaError ? (
              <ErrorState
                title={t("marketplace.orderDetails.sla.errorTitle")}
                description={slaError}
                correlationId={slaCorrelationId}
                action={
                  <button type="button" className="secondary" onClick={loadSla}>
                    {t("errors.retry")}
                  </button>
                }
              />
            ) : sla.length === 0 ? (
              <EmptyState title={t("marketplace.orderDetails.sla.emptyTitle")} description={t("marketplace.orderDetails.sla.emptyDescription")} />
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>{t("marketplace.orderDetails.sla.table.metric")}</th>
                    <th>{t("marketplace.orderDetails.sla.table.deadline")}</th>
                    <th>{t("marketplace.orderDetails.sla.table.remaining")}</th>
                    <th>{t("marketplace.orderDetails.sla.table.status")}</th>
                    <th>{t("marketplace.orderDetails.sla.table.penalty")}</th>
                  </tr>
                </thead>
                <tbody>
                  {sla.map((metric) => (
                    <tr key={`${metric.metric}-${metric.deadlineAt ?? ""}`}>
                      <td>{metric.metric}</td>
                      <td>{metric.deadlineAt ? formatDateTime(metric.deadlineAt) : "—"}</td>
                      <td>
                        <span className={`badge ${resolveSlaTone(metric)}`}>{formatCountdown(metric.remainingSeconds ?? null)}</span>
                      </td>
                      <td>{metric.status ?? "—"}</td>
                      <td>{metric.penalty ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        ) : null}

        {activeTab === "payouts" ? (
          <EmptyState
            title={t("marketplace.orderDetails.payouts.frozenTitle")}
            description={t("marketplace.orderDetails.payouts.frozenDescription")}
            action={
              <>
                <div className="muted small">{t("marketplace.orderDetails.payouts.frozenNote")}</div>
                <Link className="secondary" to="/finance">
                  {t("marketplace.orderDetails.payouts.openFinance")}
                </Link>
                <Link className="ghost" to="/support/requests">
                  {t("marketplace.orderDetails.payouts.openSupport")}
                </Link>
              </>
            }
          />
        ) : null}
      </section>

      <SupportRequestModal
        isOpen={isSupportOpen}
        onClose={() => setIsSupportOpen(false)}
        subjectType="ORDER"
        subjectId={order.id}
        correlationId={order.correlationId ?? undefined}
        defaultTitle={t("marketplace.orderDetails.supportTitle", { id: order.id })}
      />

      {actionModal ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal">
            <div className="section-title">
              <h3>{t(`marketplace.orderDetails.modals.${actionModal}.title`)}</h3>
              <button type="button" className="ghost" onClick={() => setActionModal(null)}>
                {t("marketplace.orderDetails.modals.close")}
              </button>
            </div>
            <div>{t(`marketplace.orderDetails.modals.${actionModal}.description`)}</div>
            {actionModal === "decline" ? (
              <div className="stack">
                <label className="form-field">
                  {t("marketplace.orderDetails.modals.decline.reason")}
                  <input
                    type="text"
                    value={declineReason}
                    onChange={(event) => setDeclineReason(event.target.value)}
                    placeholder={t("marketplace.orderDetails.modals.decline.reasonPlaceholder")}
                  />
                </label>
                <label className="form-field">
                  {t("marketplace.orderDetails.modals.decline.comment")}
                  <textarea
                    className="textarea"
                    value={declineComment}
                    onChange={(event) => setDeclineComment(event.target.value)}
                    placeholder={t("marketplace.orderDetails.modals.decline.commentPlaceholder")}
                  />
                </label>
              </div>
            ) : null}
            {actionModal === "proof" ? (
              <div className="stack">
                <label className="form-field">
                  {t("marketplace.orderDetails.modals.proof.kind")}
                  <select value={proofKind} onChange={(event) => setProofKind(event.target.value)}>
                    <option value="PHOTO">{t("marketplace.orderDetails.modals.proof.kinds.photo")}</option>
                    <option value="PDF">{t("marketplace.orderDetails.modals.proof.kinds.pdf")}</option>
                    <option value="ACT">{t("marketplace.orderDetails.modals.proof.kinds.act")}</option>
                    <option value="CHECK">{t("marketplace.orderDetails.modals.proof.kinds.check")}</option>
                    <option value="OTHER">{t("marketplace.orderDetails.modals.proof.kinds.other")}</option>
                  </select>
                </label>
                <label className="form-field">
                  {t("marketplace.orderDetails.modals.proof.attachment")}
                  <input
                    type="text"
                    value={proofAttachmentId}
                    onChange={(event) => setProofAttachmentId(event.target.value)}
                    placeholder={t("marketplace.orderDetails.modals.proof.attachmentPlaceholder")}
                  />
                </label>
                <label className="form-field">
                  {t("marketplace.orderDetails.modals.proof.note")}
                  <textarea
                    className="textarea"
                    value={proofNote}
                    onChange={(event) => setProofNote(event.target.value)}
                    placeholder={t("marketplace.orderDetails.modals.proof.notePlaceholder")}
                  />
                </label>
              </div>
            ) : null}
            {actionModal === "complete" ? (
              <label className="form-field">
                {t("marketplace.orderDetails.modals.complete.summary")}
                <textarea
                  className="textarea"
                  value={completeSummary}
                  onChange={(event) => setCompleteSummary(event.target.value)}
                  placeholder={t("marketplace.orderDetails.modals.complete.placeholder")}
                />
              </label>
            ) : null}
            <div className="actions">
              <button type="button" className="secondary" onClick={() => setActionModal(null)}>
                {t("marketplace.orderDetails.modals.cancel")}
              </button>
              <button
                type="button"
                className="primary"
                onClick={handleAction}
                disabled={
                  (actionModal === "decline" && disableDecline) ||
                  (actionModal === "proof" && disableProof) ||
                  (actionModal === "complete" && disableComplete)
                }
              >
                {t("marketplace.orderDetails.actions.confirm")}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
