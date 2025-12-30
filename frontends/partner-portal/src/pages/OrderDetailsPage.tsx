import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../api/http";
import {
  cancelOrder,
  completeOrder,
  confirmOrder,
  fetchOrder,
  fetchOrderDocuments,
  fetchOrderEvents,
  fetchOrderSettlement,
  startOrder,
} from "../api/orders";
import { fetchRefunds } from "../api/refunds";
import { useAuth } from "../auth/AuthContext";
import { StatusBadge } from "../components/StatusBadge";
import { EmptyState, ErrorState, ForbiddenState, LoadingState } from "../components/states";
import type { MarketplaceDocumentDetails, MarketplaceOrder, MarketplaceOrderEvent, MarketplaceSettlementLink, RefundRequest } from "../types/marketplace";
import { formatCurrency, formatDateTime } from "../utils/format";
import { canCancelOrders, canManageOrderLifecycle, canReadOrders, canReadRefunds } from "../utils/roles";
import { OrderDocumentsPanel } from "./OrderDocumentsPanel";
import { OrderTimelinePanel } from "./OrderTimelinePanel";

const lifecycleActionLabels: Record<string, string> = {
  confirm: "Подтвердить заказ",
  start: "Начать выполнение",
  complete: "Завершить заказ",
  cancel: "Отменить заказ",
};

const canConfirmStatus = (status: string) => ["CREATED", "PAID", "AUTHORIZED"].includes(status);
const canStartStatus = (status: string) => ["CONFIRMED", "CONFIRMED_BY_PARTNER"].includes(status);
const canCompleteStatus = (status: string) => ["IN_PROGRESS"].includes(status);
const canCancelStatus = (status: string) =>
  ["CREATED", "PAID", "AUTHORIZED", "CONFIRMED", "CONFIRMED_BY_PARTNER", "IN_PROGRESS"].includes(status);

const describeError = (err: unknown, fallback: string) => {
  if (err instanceof ApiError) {
    return { message: `HTTP ${err.status}: ${err.message}`, correlationId: err.correlationId };
  }
  if (err instanceof Error) {
    return { message: err.message, correlationId: null };
  }
  return { message: fallback, correlationId: null };
};

export function OrderDetailsPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [order, setOrder] = useState<MarketplaceOrder | null>(null);
  const [orderLoading, setOrderLoading] = useState(true);
  const [orderError, setOrderError] = useState<string | null>(null);
  const [orderCorrelationId, setOrderCorrelationId] = useState<string | null>(null);

  const [events, setEvents] = useState<MarketplaceOrderEvent[]>([]);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [eventsError, setEventsError] = useState<string | null>(null);
  const [eventsCorrelationId, setEventsCorrelationId] = useState<string | null>(null);

  const [documents, setDocuments] = useState<MarketplaceDocumentDetails[]>([]);
  const [documentsLoading, setDocumentsLoading] = useState(true);
  const [documentsError, setDocumentsError] = useState<string | null>(null);
  const [documentsCorrelationId, setDocumentsCorrelationId] = useState<string | null>(null);

  const [refunds, setRefunds] = useState<RefundRequest[]>([]);
  const [refundsLoading, setRefundsLoading] = useState(true);
  const [refundsError, setRefundsError] = useState<string | null>(null);
  const [refundsCorrelationId, setRefundsCorrelationId] = useState<string | null>(null);

  const [settlement, setSettlement] = useState<MarketplaceSettlementLink | null>(null);
  const [settlementLoading, setSettlementLoading] = useState(true);
  const [settlementError, setSettlementError] = useState<string | null>(null);
  const [settlementCorrelationId, setSettlementCorrelationId] = useState<string | null>(null);

  const [actionModal, setActionModal] = useState<"confirm" | "start" | "complete" | "cancel" | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionCorrelationId, setActionCorrelationId] = useState<string | null>(null);
  const [cancelReason, setCancelReason] = useState("");

  const canRead = canReadOrders(user?.roles);
  const canManage = canManageOrderLifecycle(user?.roles);
  const canCancel = canCancelOrders(user?.roles);
  const canSeeRefunds = canReadRefunds(user?.roles);

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
        const { message, correlationId } = describeError(err, "Не удалось загрузить заказ");
        setOrderError(message);
        setOrderCorrelationId(correlationId);
      })
      .finally(() => {
        setOrderLoading(false);
      });
  }, [user, orderId]);

  const loadEvents = useCallback(() => {
    if (!user || !orderId) return;
    setEventsLoading(true);
    setEventsError(null);
    setEventsCorrelationId(null);
    fetchOrderEvents(user.token, orderId)
      .then((data) => setEvents(data))
      .catch((err) => {
        console.error(err);
        const { message, correlationId } = describeError(err, "Не удалось загрузить таймлайн");
        setEventsError(message);
        setEventsCorrelationId(correlationId);
      })
      .finally(() => setEventsLoading(false));
  }, [user, orderId]);

  const loadDocuments = useCallback(() => {
    if (!user || !orderId) return;
    setDocumentsLoading(true);
    setDocumentsError(null);
    setDocumentsCorrelationId(null);
    fetchOrderDocuments(user.token, orderId)
      .then((data) => setDocuments(data))
      .catch((err) => {
        console.error(err);
        const { message, correlationId } = describeError(err, "Не удалось загрузить документы");
        setDocumentsError(message);
        setDocumentsCorrelationId(correlationId);
      })
      .finally(() => setDocumentsLoading(false));
  }, [user, orderId]);

  const loadRefunds = useCallback(() => {
    if (!user || !orderId || !canSeeRefunds) return;
    setRefundsLoading(true);
    setRefundsError(null);
    setRefundsCorrelationId(null);
    fetchRefunds(user.token, { order_id: orderId })
      .then((data) => setRefunds(data.items ?? []))
      .catch((err) => {
        console.error(err);
        const { message, correlationId } = describeError(err, "Не удалось загрузить возвраты");
        setRefundsError(message);
        setRefundsCorrelationId(correlationId);
      })
      .finally(() => setRefundsLoading(false));
  }, [user, orderId, canSeeRefunds]);

  const loadSettlement = useCallback(() => {
    if (!user || !orderId) return;
    setSettlementLoading(true);
    setSettlementError(null);
    setSettlementCorrelationId(null);
    fetchOrderSettlement(user.token, orderId)
      .then((data) => setSettlement(data.items?.[0] ?? null))
      .catch((err) => {
        console.error(err);
        const { message, correlationId } = describeError(err, "Не удалось загрузить связь с выплатой");
        setSettlementError(message);
        setSettlementCorrelationId(correlationId);
      })
      .finally(() => setSettlementLoading(false));
  }, [user, orderId]);

  useEffect(() => {
    if (!canRead) return;
    loadOrder();
    loadEvents();
    loadDocuments();
    loadRefunds();
    loadSettlement();
  }, [canRead, loadOrder, loadEvents, loadDocuments, loadRefunds, loadSettlement]);

  const handleAction = async () => {
    if (!user || !order) return;
    setActionError(null);
    setActionMessage(null);
    setActionCorrelationId(null);
    try {
      if (actionModal === "confirm") {
        const result = await confirmOrder(user.token, order.id);
        setActionMessage(`Заказ подтверждён. Correlation ID: ${result.correlationId ?? "—"}`);
        setActionCorrelationId(result.correlationId ?? null);
      }
      if (actionModal === "start") {
        const result = await startOrder(user.token, order.id);
        setActionMessage(`Заказ принят в работу. Correlation ID: ${result.correlationId ?? "—"}`);
        setActionCorrelationId(result.correlationId ?? null);
      }
      if (actionModal === "complete") {
        const result = await completeOrder(user.token, order.id);
        setActionMessage(`Заказ завершён. Correlation ID: ${result.correlationId ?? "—"}`);
        setActionCorrelationId(result.correlationId ?? null);
      }
      if (actionModal === "cancel") {
        const result = await cancelOrder(user.token, order.id, cancelReason);
        setActionMessage(`Заказ отменён. Correlation ID: ${result.correlationId ?? "—"}`);
        setActionCorrelationId(result.correlationId ?? null);
      }
      setActionModal(null);
      setCancelReason("");
      loadOrder();
      loadEvents();
    } catch (err) {
      console.error(err);
      const { message, correlationId } = describeError(err, "Действие не выполнено");
      setActionError(message);
      setActionCorrelationId(correlationId);
    }
  };

  const shouldShowCancelReason = actionModal === "cancel";
  const cancelDisabled = shouldShowCancelReason && cancelReason.trim().length === 0;

  const summary = useMemo(() => {
    if (!order) return [];
    return [
      { label: "Клиент", value: order.clientName ?? order.clientId },
      { label: "Телефон", value: order.clientPhone },
      { label: "Email", value: order.clientEmail },
      { label: "Станция", value: order.stationName },
      { label: "Локация", value: order.locationName },
      { label: "Сервис", value: order.serviceTitle },
    ].filter((item) => item.value);
  }, [order]);

  if (!canRead) {
    return <ForbiddenState />;
  }

  if (orderLoading) {
    return <LoadingState label="Загружаем заказ..." />;
  }

  if (orderError || !order) {
    return (
      <ErrorState
        title="Не удалось загрузить заказ"
        description={orderError ?? "Заказ не найден"}
        correlationId={orderCorrelationId}
        action={
          <button type="button" className="secondary" onClick={loadOrder}>
            Повторить
          </button>
        }
      />
    );
  }

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <h2>Заказ {order.id}</h2>
          <Link to="/orders" className="ghost">
            Назад к списку
          </Link>
        </div>
        <div className="meta-grid">
          <div>
            <div className="label">Статус заказа</div>
            <StatusBadge status={order.status} />
          </div>
          <div>
            <div className="label">Статус оплаты</div>
            <StatusBadge status={order.paymentStatus ?? "—"} />
          </div>
          <div>
            <div className="label">Создан</div>
            <div>{formatDateTime(order.createdAt)}</div>
          </div>
          <div>
            <div className="label">Correlation ID</div>
            <div className="mono">{order.correlationId ?? "—"}</div>
          </div>
        </div>
        {summary.length > 0 ? (
          <div className="card__section">
            <div className="meta-grid">
              {summary.map((item) => (
                <div key={item.label}>
                  <div className="label">{item.label}</div>
                  <div>{item.value}</div>
                </div>
              ))}
            </div>
          </div>
        ) : null}
        <div className="card__section">
          <div className="meta-grid">
            <div>
              <div className="label">Сумма</div>
              <div>{formatCurrency(order.totalAmount ?? null)}</div>
            </div>
            <div>
              <div className="label">НДС</div>
              <div>{formatCurrency(order.vatAmount ?? null)}</div>
            </div>
            <div>
              <div className="label">Оплата (ref)</div>
              <div className="mono">{order.paymentRef ?? "—"}</div>
            </div>
          </div>
        </div>
      </section>

      <section className="card">
        <div className="section-title">
          <h3>Позиции</h3>
        </div>
        {order.items.length === 0 ? (
          <EmptyState title="Нет позиций" description="В этом заказе нет позиций." />
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Название</th>
                <th>Кол-во</th>
                <th>Цена</th>
                <th>Сумма</th>
              </tr>
            </thead>
            <tbody>
              {order.items.map((item, index) => (
                <tr key={`${item.offerId}-${index}`}>
                  <td>{item.title ?? item.offerId}</td>
                  <td>{item.qty}</td>
                  <td>{formatCurrency(item.unitPrice)}</td>
                  <td>{formatCurrency(item.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="card">
        <div className="section-title">
          <h3>Управление жизненным циклом</h3>
          <span className="muted">Все действия логируются в audit.</span>
        </div>
        {!canManage && !canCancel ? (
          <EmptyState title="Действия недоступны" description="У вашей роли нет доступа к изменениям заказа." />
        ) : (
          <div className="actions">
            {canManage ? (
              <>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setActionModal("confirm")}
                  disabled={!canConfirmStatus(order.status)}
                >
                  Подтвердить
                </button>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setActionModal("start")}
                  disabled={!canStartStatus(order.status)}
                >
                  Начать
                </button>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setActionModal("complete")}
                  disabled={!canCompleteStatus(order.status)}
                >
                  Завершить
                </button>
              </>
            ) : null}
            {canCancel ? (
              <button
                type="button"
                className="secondary"
                onClick={() => setActionModal("cancel")}
                disabled={!canCancelStatus(order.status)}
              >
                Отменить
              </button>
            ) : null}
          </div>
        )}
        {actionMessage ? <div className="notice">{actionMessage}</div> : null}
        {actionError ? (
          <div className="notice error">
            {actionError}
            {actionCorrelationId ? <div className="muted small">Correlation ID: {actionCorrelationId}</div> : null}
          </div>
        ) : null}
      </section>

      <section className="card">
        <div className="section-title">
          <h3>Таймлайн заказа</h3>
        </div>
        <OrderTimelinePanel
          events={events}
          isLoading={eventsLoading}
          error={eventsError}
          correlationId={eventsCorrelationId}
          onRetry={loadEvents}
        />
      </section>

      <section className="card">
        <div className="section-title">
          <h3>Документы</h3>
        </div>
        <OrderDocumentsPanel
          documents={documents}
          isLoading={documentsLoading}
          error={documentsError}
          correlationId={documentsCorrelationId}
          canManage={canManage}
          onRefresh={loadDocuments}
        />
      </section>

      <section className="card">
        <div className="section-title">
          <h3>Возвраты</h3>
          <Link className="ghost" to="/refunds">
            Все возвраты
          </Link>
        </div>
        {!canSeeRefunds ? (
          <EmptyState title="Возвраты недоступны" description="У вашей роли нет доступа к возвратам." />
        ) : refundsLoading ? (
          <LoadingState label="Загружаем возвраты..." />
        ) : refundsError ? (
          <ErrorState
            title="Не удалось загрузить возвраты"
            description={refundsError}
            correlationId={refundsCorrelationId}
            action={
              <button type="button" className="secondary" onClick={loadRefunds}>
                Повторить
              </button>
            }
          />
        ) : refunds.length === 0 ? (
          <EmptyState title="Нет возвратов" description="Возвраты по этому заказу отсутствуют." />
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Refund ID</th>
                <th>Статус</th>
                <th>Сумма</th>
                <th>Причина</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {refunds.map((refund) => (
                <tr key={refund.id}>
                  <td>{refund.id}</td>
                  <td>
                    <StatusBadge status={refund.status} />
                  </td>
                  <td>{formatCurrency(refund.amount)}</td>
                  <td>{refund.reason ?? "—"}</td>
                  <td>
                    <Link className="link-button" to={`/refunds/${refund.id}`}>
                      Открыть
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="card">
        <div className="section-title">
          <h3>Связь с выплатой</h3>
        </div>
        {settlementLoading ? (
          <LoadingState label="Загружаем данные по выплате..." />
        ) : settlementError ? (
          <ErrorState
            title="Не удалось загрузить данные по выплате"
            description={settlementError}
            correlationId={settlementCorrelationId}
            action={
              <button type="button" className="secondary" onClick={loadSettlement}>
                Повторить
              </button>
            }
          />
        ) : settlement ? (
          <div className="meta-grid">
            <div>
              <div className="label">Settlement ID</div>
              <div className="mono">{settlement.id}</div>
            </div>
            <div>
              <div className="label">Статус</div>
              <StatusBadge status={settlement.status} />
            </div>
            <div>
              <div className="label">Период</div>
              <div>
                {settlement.periodStart ? formatDateTime(settlement.periodStart) : "—"} — {settlement.periodEnd ? formatDateTime(settlement.periodEnd) : "—"}
              </div>
            </div>
            <div>
              <div className="label">Payout batch</div>
              <div className="mono">{settlement.payoutBatchId ?? "—"}</div>
            </div>
            <div>
              <Link className="link-button" to={`/payouts/${settlement.id}`}>
                Перейти к выплате
              </Link>
            </div>
          </div>
        ) : (
          <EmptyState title="Выплата не найдена" description="Связь с выплатой пока не сформирована." />
        )}
      </section>

      {actionModal ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal">
            <div className="section-title">
              <h3>{lifecycleActionLabels[actionModal]}</h3>
              <button type="button" className="ghost" onClick={() => setActionModal(null)}>
                Закрыть
              </button>
            </div>
            <div>Вы уверены, что хотите выполнить действие? Результат будет зафиксирован в аудите.</div>
            {shouldShowCancelReason ? (
              <label className="form-field">
                Причина отмены
                <textarea
                  className="textarea"
                  value={cancelReason}
                  onChange={(event) => setCancelReason(event.target.value)}
                  placeholder="Опишите причину отмены"
                />
              </label>
            ) : null}
            <div className="actions">
              <button type="button" className="secondary" onClick={() => setActionModal(null)}>
                Отмена
              </button>
              <button type="button" className="primary" onClick={handleAction} disabled={cancelDisabled}>
                Подтвердить
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
