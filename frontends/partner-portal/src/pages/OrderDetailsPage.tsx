import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../api/http";
import {
  acceptOrder,
  failOrder,
  fetchOrder,
  fetchOrderEvents,
  fetchOrderSettlement,
  fetchOrderSettlementBreakdown,
  fetchOrderSla,
  progressOrder,
  rejectOrder,
  startOrder,
  completeOrder,
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
import { useI18n } from "../i18n";

const canAcceptStatus = (status: string) => ["CREATED"].includes(status);
const canStartStatus = (status: string) => ["ACCEPTED"].includes(status);
const canProgressStatus = (status: string) => ["IN_PROGRESS"].includes(status);
const canCompleteStatus = (status: string) => ["IN_PROGRESS"].includes(status);
const canFailStatus = (status: string) => ["IN_PROGRESS"].includes(status);
const canRejectStatus = (status: string) => ["CREATED"].includes(status);

const describeError = (err: unknown, fallback: string) => {
  if (err instanceof ApiError) {
    return { message: fallback, correlationId: null };
  }
  if (err instanceof Error) {
    return { message: fallback, correlationId: null };
  }
  return { message: fallback, correlationId: null };
};

type ActionModal = "accept" | "reject" | "start" | "progress" | "complete" | "fail" | null;

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
  const { t } = useI18n();
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
  const [rejectReason, setRejectReason] = useState("");
  const [failReason, setFailReason] = useState("");
  const [progressPercent, setProgressPercent] = useState("");
  const [progressMessage, setProgressMessage] = useState("");
  const [completeSummary, setCompleteSummary] = useState("");
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
      if (actionModal === "accept") {
        const result = await acceptOrder(user.token, order.id);
        setActionMessage(t("orderDetails.notifications.accepted"));
        setActionCorrelationId(null);
      }
      if (actionModal === "reject") {
        const result = await rejectOrder(user.token, order.id, rejectReason.trim());
        setActionMessage(t("orderDetails.notifications.rejected"));
        setActionCorrelationId(null);
      }
      if (actionModal === "start") {
        const result = await startOrder(user.token, order.id);
        setActionMessage(t("orderDetails.notifications.started"));
        setActionCorrelationId(null);
      }
      if (actionModal === "progress") {
        const result = await progressOrder(user.token, order.id, {
          percent: Number(progressPercent),
          message: progressMessage.trim() || undefined,
        });
        setActionMessage(t("orderDetails.notifications.progressed"));
        setActionCorrelationId(null);
      }
      if (actionModal === "complete") {
        const result = await completeOrder(user.token, order.id, { summary: completeSummary.trim() || undefined });
        setActionMessage(t("orderDetails.notifications.completed"));
        setActionCorrelationId(null);
      }
      if (actionModal === "fail") {
        const result = await failOrder(user.token, order.id, failReason.trim());
        setActionMessage(t("orderDetails.notifications.failed"));
        setActionCorrelationId(null);
      }
      setActionModal(null);
      setRejectReason("");
      setFailReason("");
      setProgressPercent("");
      setProgressMessage("");
      setCompleteSummary("");
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

  const disableReject = rejectReason.trim().length === 0;
  const disableFail = failReason.trim().length === 0;
  const disableProgress = !progressPercent || Number(progressPercent) < 0 || Number(progressPercent) > 100;
  const disableComplete = completeSummary.trim().length === 0;

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
                onClick={() => setActionModal("accept")}
                disabled={!canAcceptStatus(order.status)}
              >
                {t("orderDetails.actions.accept")}
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => setActionModal("reject")}
                disabled={!canRejectStatus(order.status)}
              >
                {t("orderDetails.actions.reject")}
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => setActionModal("start")}
                disabled={!canStartStatus(order.status)}
              >
                {t("orderDetails.actions.start")}
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => setActionModal("progress")}
                disabled={!canProgressStatus(order.status)}
              >
                {t("orderDetails.actions.progress")}
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => setActionModal("complete")}
                disabled={!canCompleteStatus(order.status)}
              >
                {t("orderDetails.actions.complete")}
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => setActionModal("fail")}
                disabled={!canFailStatus(order.status)}
              >
                {t("orderDetails.actions.fail")}
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
            {actionModal === "reject" ? (
              <label className="form-field">
                {t("orderDetails.modals.reject.reason")}
                <textarea
                  className="textarea"
                  value={rejectReason}
                  onChange={(event) => setRejectReason(event.target.value)}
                  placeholder={t("orderDetails.modals.reject.placeholder")}
                />
              </label>
            ) : null}
            {actionModal === "progress" ? (
              <div className="stack">
                <label className="form-field">
                  {t("orderDetails.modals.progress.percent")}
                  <input
                    type="number"
                    min={0}
                    max={100}
                    value={progressPercent}
                    onChange={(event) => setProgressPercent(event.target.value)}
                  />
                </label>
                <label className="form-field">
                  {t("orderDetails.modals.progress.message")}
                  <textarea
                    className="textarea"
                    value={progressMessage}
                    onChange={(event) => setProgressMessage(event.target.value)}
                    placeholder={t("orderDetails.modals.progress.placeholder")}
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
            {actionModal === "fail" ? (
              <label className="form-field">
                {t("orderDetails.modals.fail.reason")}
                <textarea
                  className="textarea"
                  value={failReason}
                  onChange={(event) => setFailReason(event.target.value)}
                  placeholder={t("orderDetails.modals.fail.placeholder")}
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
                  (actionModal === "reject" && disableReject) ||
                  (actionModal === "fail" && disableFail) ||
                  (actionModal === "progress" && disableProgress) ||
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
