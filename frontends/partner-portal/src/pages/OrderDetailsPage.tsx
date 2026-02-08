import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../api/http";
import {
  completeOrder,
  confirmOrder,
  declineOrder,
  fetchOrder,
  fetchOrderEvents,
  fetchOrderSettlement,
  fetchOrderSettlementBreakdown,
  fetchOrderSla,
  uploadOrderProof,
} from "../api/orders";
import { useAuth } from "../auth/AuthContext";
import { StatusBadge } from "../components/StatusBadge";
import { SupportRequestModal } from "../components/SupportRequestModal";
import { EmptyState, ErrorState, ForbiddenState, LoadingState } from "../components/states";
import type {
  MarketplaceOrder,
  MarketplaceOrderEvent,
  MarketplaceOrderSettlementBreakdown,
  MarketplaceOrderSlaMetric,
  MarketplaceSettlementLink,
} from "../types/marketplace";
import { formatCurrency, formatDateTime } from "../utils/format";
import { canManageOrderLifecycle, canReadOrders } from "../utils/roles";
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
  const { t } = useTranslation();
  const [order, setOrder] = useState<MarketplaceOrder | null>(null);
  const [orderLoading, setOrderLoading] = useState(true);
  const [orderError, setOrderError] = useState<string | null>(null);
  const [orderCorrelationId, setOrderCorrelationId] = useState<string | null>(null);

  const [events, setEvents] = useState<MarketplaceOrderEvent[]>([]);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [eventsError, setEventsError] = useState<string | null>(null);
  const [eventsCorrelationId, setEventsCorrelationId] = useState<string | null>(null);

  const [sla, setSla] = useState<MarketplaceOrderSlaMetric[]>([]);
  const [slaLoading, setSlaLoading] = useState(true);
  const [slaError, setSlaError] = useState<string | null>(null);
  const [slaCorrelationId, setSlaCorrelationId] = useState<string | null>(null);

  const [settlement, setSettlement] = useState<MarketplaceSettlementLink | null>(null);
  const [settlementLoading, setSettlementLoading] = useState(true);
  const [settlementError, setSettlementError] = useState<string | null>(null);
  const [settlementCorrelationId, setSettlementCorrelationId] = useState<string | null>(null);

  const [settlementBreakdown, setSettlementBreakdown] = useState<MarketplaceOrderSettlementBreakdown | null>(null);
  const [breakdownLoading, setBreakdownLoading] = useState(true);
  const [breakdownError, setBreakdownError] = useState<string | null>(null);
  const [breakdownCorrelationId, setBreakdownCorrelationId] = useState<string | null>(null);

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
  const [activeTab, setActiveTab] = useState<"timeline" | "sla" | "payouts">("timeline");

  const canRead = canReadOrders(user?.roles);
  const canManage = canManageOrderLifecycle(user?.roles);

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
        console.error(err);
        const { message, correlationId } = describeError(err, t("orderDetails.errors.loadFailed"));
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
        console.error(err);
        const { message, correlationId } = describeError(err, t("orderDetails.errors.timelineFailed"));
        setEventsError(message);
        setEventsCorrelationId(correlationId);
      })
      .finally(() => setEventsLoading(false));
  }, [user, orderId, t]);

  const loadSla = useCallback(() => {
    if (!user || !orderId) return;
    setSlaLoading(true);
    setSlaError(null);
    setSlaCorrelationId(null);
    fetchOrderSla(user.token, orderId)
      .then((data) => setSla(data.obligations ?? []))
      .catch((err) => {
        console.error(err);
        const { message, correlationId } = describeError(err, t("orderDetails.errors.slaFailed"));
        setSlaError(message);
        setSlaCorrelationId(correlationId);
      })
      .finally(() => setSlaLoading(false));
  }, [user, orderId, t]);

  const loadSettlement = useCallback(() => {
    if (!user || !orderId) return;
    setSettlementLoading(true);
    setSettlementError(null);
    setSettlementCorrelationId(null);
    fetchOrderSettlement(user.token, orderId)
      .then((data) => setSettlement(data.items?.[0] ?? null))
      .catch((err) => {
        console.error(err);
        const { message, correlationId } = describeError(err, t("orderDetails.errors.payoutFailed"));
        setSettlementError(message);
        setSettlementCorrelationId(correlationId);
      })
      .finally(() => setSettlementLoading(false));
  }, [user, orderId, t]);

  const loadSettlementBreakdown = useCallback(() => {
    if (!user || !orderId) return;
    setBreakdownLoading(true);
    setBreakdownError(null);
    setBreakdownCorrelationId(null);
    fetchOrderSettlementBreakdown(user.token, orderId)
      .then((data) => setSettlementBreakdown(data))
      .catch((err) => {
        console.error(err);
        const { message, correlationId } = describeError(err, t("orderDetails.errors.payoutFailed"));
        setBreakdownError(message);
        setBreakdownCorrelationId(correlationId);
      })
      .finally(() => setBreakdownLoading(false));
  }, [user, orderId, t]);

  useEffect(() => {
    if (!canRead) return;
    loadOrder();
    loadEvents();
    loadSla();
    loadSettlement();
    loadSettlementBreakdown();
  }, [canRead, loadOrder, loadEvents, loadSla, loadSettlement, loadSettlementBreakdown]);

  const handleAction = async () => {
    if (!user || !order || !actionModal) return;
    setActionError(null);
    setActionMessage(null);
    setActionCorrelationId(null);
    try {
      if (actionModal === "confirm") {
        await confirmOrder(user.token, order.id);
        setActionMessage(t("orderDetails.notifications.confirmed"));
        setActionCorrelationId(null);
      }
      if (actionModal === "decline") {
        await declineOrder(user.token, order.id, declineReason.trim(), declineComment.trim());
        setActionMessage(t("orderDetails.notifications.declined"));
        setActionCorrelationId(null);
      }
      if (actionModal === "proof") {
        const attachmentId = proofAttachmentId.trim() || createAttachmentId();
        await uploadOrderProof(user.token, order.id, {
          attachment_id: attachmentId,
          kind: proofKind,
          note: proofNote.trim() || undefined,
        });
        setActionMessage(t("orderDetails.notifications.proofUploaded"));
        setActionCorrelationId(null);
      }
      if (actionModal === "complete") {
        await completeOrder(user.token, order.id, { comment: completeSummary.trim() || undefined });
        setActionMessage(t("orderDetails.notifications.completed"));
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
      loadSla();
      loadSettlementBreakdown();
    } catch (err) {
      console.error(err);
      const { message, correlationId } = describeError(err, t("orderDetails.errors.actionFailed"));
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
    return <LoadingState label={t("orderDetails.loading")} />;
  }

  if (orderError || !order) {
    return (
      <ErrorState
        title={t("orderDetails.errors.loadTitle")}
        description={orderError ?? t("orderDetails.errors.notFound")}
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
            <h2>{t("orderDetails.title", { id: order.id })}</h2>
            <p className="muted">{order.serviceTitle ?? t("orderDetails.subtitle")}</p>
          </div>
          <div className="actions">
            <button type="button" className="secondary" onClick={() => setIsSupportOpen(true)}>
              {t("orderDetails.actions.support")}
            </button>
            <Link to="/orders" className="ghost">
              {t("orderDetails.actions.back")}
            </Link>
          </div>
        </div>
        <div className="meta-grid">
          <div>
            <div className="label">{t("orderDetails.fields.status")}</div>
            <StatusBadge status={order.status} />
          </div>
          <div>
            <div className="label">{t("orderDetails.fields.client")}</div>
            <div>{order.clientName ?? order.clientId ?? t("common.notAvailable")}</div>
          </div>
          <div>
            <div className="label">{t("orderDetails.fields.created")}</div>
            <div>{formatDateTime(order.createdAt)}</div>
          </div>
          <div>
            <div className="label">{t("orderDetails.fields.amount")}</div>
            <div>{formatCurrency(order.totalAmount ?? null, order.currency ?? "RUB")}</div>
          </div>
        </div>
        <div className="card__section">
          <div className="meta-grid">
            <div>
              <div className="label">{t("orderDetails.fields.responseDue")}</div>
              <div className={`badge ${responseSla ? resolveSlaTone(responseSla) : "neutral"}`}>
                {responseSla ? formatCountdown(responseSla.remainingSeconds ?? null) : "—"}
              </div>
            </div>
            <div>
              <div className="label">{t("orderDetails.fields.completionDue")}</div>
              <div className={`badge ${completionSla ? resolveSlaTone(completionSla) : "neutral"}`}>
                {completionSla ? formatCountdown(completionSla.remainingSeconds ?? null) : "—"}
              </div>
            </div>
          </div>
        </div>
        <div className="card__section">
          <div className="section-title">
            <h3>{t("orderDetails.lifecycle.title")}</h3>
          </div>
          {!canManage ? (
            <EmptyState title={t("orderDetails.lifecycle.deniedTitle")} description={t("orderDetails.lifecycle.deniedDescription")} />
          ) : (
            <div className="actions">
              <button
                type="button"
                className="secondary"
                onClick={() => setActionModal("confirm")}
                disabled={!canConfirmStatus(order.status)}
              >
                {t("orderDetails.actions.confirm")}
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => setActionModal("decline")}
                disabled={!canDeclineStatus(order.status)}
              >
                {t("orderDetails.actions.decline")}
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => setActionModal("proof")}
                disabled={!canCompleteStatus(order.status)}
              >
                {t("orderDetails.actions.uploadProof")}
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => setActionModal("complete")}
                disabled={!canCompleteStatus(order.status) || proofsCount === 0}
              >
                {t("orderDetails.actions.complete")}
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
            <h3>{t("orderDetails.proofs.title")}</h3>
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
            <div className="muted">{t("orderDetails.proofs.empty")}</div>
          )}
        </div>
      </section>

      <section className="card">
        <div className="section-title">
          <h3>Settlement breakdown</h3>
        </div>
        {breakdownLoading ? (
          <LoadingState label="Загружаем расчёт..." />
        ) : breakdownError ? (
          <ErrorState
            title="Не удалось загрузить расчёт"
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
                <div className="label">Gross</div>
                <div>{formatCurrency(settlementBreakdown.gross_amount, settlementBreakdown.currency)}</div>
              </div>
              <div>
                <div className="label">Fee</div>
                <div>
                  {formatCurrency(settlementBreakdown.platform_fee.amount, settlementBreakdown.currency)}
                  <div className="muted small">{settlementBreakdown.platform_fee.explain}</div>
                </div>
              </div>
              <div>
                <div className="label">Penalties</div>
                <div>
                  {formatCurrency(
                    settlementBreakdown.penalties.reduce((sum, item) => sum + item.amount, 0),
                    settlementBreakdown.currency,
                  )}
                </div>
              </div>
              <div>
                <div className="label">Net</div>
                <div>{formatCurrency(settlementBreakdown.partner_net, settlementBreakdown.currency)}</div>
              </div>
            </div>
            {settlementBreakdown.penalties.length ? (
              <table className="table">
                <thead>
                  <tr>
                    <th>Тип</th>
                    <th>Причина</th>
                    <th>Сумма</th>
                    <th>Источник</th>
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
                          <Link
                            className="link-button"
                            to={`/support/requests?audit_event_id=${penalty.source_ref.audit_event_id}`}
                          >
                            Почему?
                          </Link>
                        ) : penalty.source_ref?.sla_event_id ? (
                          <span className="muted">SLA {penalty.source_ref.sla_event_id}</span>
                        ) : (
                          <span className="muted">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="muted">Штрафы отсутствуют.</div>
            )}
            {settlementBreakdown.snapshot ? (
              <div className="meta-grid">
                <div>
                  <div className="label">Finalized at</div>
                  <div>
                    {settlementBreakdown.snapshot.finalized_at
                      ? formatDateTime(settlementBreakdown.snapshot.finalized_at)
                      : "—"}
                  </div>
                </div>
                <div>
                  <div className="label">Snapshot hash</div>
                  <div className="mono">{settlementBreakdown.snapshot.hash ?? "—"}</div>
                </div>
              </div>
            ) : null}
          </div>
        ) : (
          <EmptyState title="Нет данных" description="Расчёт будет доступен после принятия или завершения заказа." />
        )}
      </section>

      <section className="card">
        <div className="tabs">
          <button type="button" className={activeTab === "timeline" ? "secondary" : "ghost"} onClick={() => setActiveTab("timeline")}>
            {t("orderDetails.tabs.timeline")}
          </button>
          <button type="button" className={activeTab === "sla" ? "secondary" : "ghost"} onClick={() => setActiveTab("sla")}>
            {t("orderDetails.tabs.sla")}
          </button>
          <button type="button" className={activeTab === "payouts" ? "secondary" : "ghost"} onClick={() => setActiveTab("payouts")}>
            {t("orderDetails.tabs.payouts")}
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

        {activeTab === "sla" ? (
          <div>
            {slaLoading ? (
              <LoadingState label={t("orderDetails.sla.loading")} />
            ) : slaError ? (
              <ErrorState
                title={t("orderDetails.sla.errorTitle")}
                description={slaError}
                correlationId={slaCorrelationId}
                action={
                  <button type="button" className="secondary" onClick={loadSla}>
                    {t("errors.retry")}
                  </button>
                }
              />
            ) : sla.length === 0 ? (
              <EmptyState title={t("orderDetails.sla.emptyTitle")} description={t("orderDetails.sla.emptyDescription")} />
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>{t("orderDetails.sla.table.metric")}</th>
                    <th>{t("orderDetails.sla.table.deadline")}</th>
                    <th>{t("orderDetails.sla.table.remaining")}</th>
                    <th>{t("orderDetails.sla.table.status")}</th>
                    <th>{t("orderDetails.sla.table.penalty")}</th>
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
          <div>
            {settlementLoading ? (
              <LoadingState label={t("orderDetails.payouts.loading")} />
            ) : settlementError ? (
              <ErrorState
                title={t("orderDetails.payouts.errorTitle")}
                description={settlementError}
                correlationId={settlementCorrelationId}
                action={
                  <button type="button" className="secondary" onClick={loadSettlement}>
                    {t("errors.retry")}
                  </button>
                }
              />
            ) : settlement ? (
              <div className="meta-grid">
                <div>
                  <div className="label">{t("orderDetails.payouts.fields.settlementId")}</div>
                  <div className="mono">{settlement.id ?? (settlement as { settlement_ref?: string }).settlement_ref ?? "—"}</div>
                </div>
                <div>
                  <div className="label">{t("orderDetails.payouts.fields.status")}</div>
                  <StatusBadge status={settlement.status} />
                </div>
                <div>
                  <div className="label">{t("orderDetails.payouts.fields.period")}</div>
                  <div>
                    {settlement.periodStart ? formatDateTime(settlement.periodStart) : "—"} — {settlement.periodEnd ? formatDateTime(settlement.periodEnd) : "—"}
                  </div>
                </div>
                <div>
                  <div className="label">{t("orderDetails.payouts.fields.netAmount")}</div>
                  <div>{formatCurrency((settlement as { net_amount?: number }).net_amount ?? null)}</div>
                </div>
                <div>
                  <Link
                    className="link-button"
                    to={`/payouts/${settlement.id ?? (settlement as { settlement_ref?: string }).settlement_ref ?? ""}`}
                  >
                    {t("orderDetails.payouts.actions.open")}
                  </Link>
                </div>
              </div>
            ) : (
              <EmptyState title={t("orderDetails.payouts.emptyTitle")} description={t("orderDetails.payouts.emptyDescription")} />
            )}
          </div>
        ) : null}
      </section>

      <SupportRequestModal
        isOpen={isSupportOpen}
        onClose={() => setIsSupportOpen(false)}
        subjectType="ORDER"
        subjectId={order.id}
        correlationId={order.correlationId ?? undefined}
        defaultTitle={t("orderDetails.supportTitle", { id: order.id })}
      />

      {actionModal ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal">
            <div className="section-title">
              <h3>{t(`orderDetails.modals.${actionModal}.title`)}</h3>
              <button type="button" className="ghost" onClick={() => setActionModal(null)}>
                {t("orderDetails.modals.close")}
              </button>
            </div>
            <div>{t(`orderDetails.modals.${actionModal}.description`)}</div>
            {actionModal === "decline" ? (
              <div className="stack">
                <label className="form-field">
                  {t("orderDetails.modals.decline.reason")}
                  <input
                    type="text"
                    value={declineReason}
                    onChange={(event) => setDeclineReason(event.target.value)}
                    placeholder={t("orderDetails.modals.decline.reasonPlaceholder")}
                  />
                </label>
                <label className="form-field">
                  {t("orderDetails.modals.decline.comment")}
                  <textarea
                    className="textarea"
                    value={declineComment}
                    onChange={(event) => setDeclineComment(event.target.value)}
                    placeholder={t("orderDetails.modals.decline.commentPlaceholder")}
                  />
                </label>
              </div>
            ) : null}
            {actionModal === "proof" ? (
              <div className="stack">
                <label className="form-field">
                  {t("orderDetails.modals.proof.kind")}
                  <select value={proofKind} onChange={(event) => setProofKind(event.target.value)}>
                    <option value="PHOTO">{t("orderDetails.modals.proof.kinds.photo")}</option>
                    <option value="PDF">{t("orderDetails.modals.proof.kinds.pdf")}</option>
                    <option value="ACT">{t("orderDetails.modals.proof.kinds.act")}</option>
                    <option value="CHECK">{t("orderDetails.modals.proof.kinds.check")}</option>
                    <option value="OTHER">{t("orderDetails.modals.proof.kinds.other")}</option>
                  </select>
                </label>
                <label className="form-field">
                  {t("orderDetails.modals.proof.attachment")}
                  <input
                    type="text"
                    value={proofAttachmentId}
                    onChange={(event) => setProofAttachmentId(event.target.value)}
                    placeholder={t("orderDetails.modals.proof.attachmentPlaceholder")}
                  />
                </label>
                <label className="form-field">
                  {t("orderDetails.modals.proof.note")}
                  <textarea
                    className="textarea"
                    value={proofNote}
                    onChange={(event) => setProofNote(event.target.value)}
                    placeholder={t("orderDetails.modals.proof.notePlaceholder")}
                  />
                </label>
              </div>
            ) : null}
            {actionModal === "complete" ? (
              <label className="form-field">
                {t("orderDetails.modals.complete.summary")}
                <textarea
                  className="textarea"
                  value={completeSummary}
                  onChange={(event) => setCompleteSummary(event.target.value)}
                  placeholder={t("orderDetails.modals.complete.placeholder")}
                />
              </label>
            ) : null}
            <div className="actions">
              <button type="button" className="secondary" onClick={() => setActionModal(null)}>
                {t("orderDetails.modals.cancel")}
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
                {t("orderDetails.modals.confirm")}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
