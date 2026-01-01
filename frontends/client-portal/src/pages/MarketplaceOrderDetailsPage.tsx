import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  fetchMarketplaceOrderDetails,
  fetchMarketplaceOrderDocuments,
  fetchMarketplaceOrderEvents,
} from "../api/marketplace";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { SupportRequestModal } from "../components/SupportRequestModal";
import { AppEmptyState, AppErrorState, AppForbiddenState } from "../components/states";
import { MoneyValue } from "../components/common/MoneyValue";
import type { MarketplaceOrderDetails, MarketplaceOrderDocument, MarketplaceOrderEvent } from "../types/marketplace";
import { formatDate, formatDateTime } from "../utils/format";

interface OrderErrorState {
  message: string;
  status?: number;
  correlationId?: string | null;
}

const statusClass = (status?: string | null) => {
  if (!status) return "badge warning";
  const normalized = status.toLowerCase();
  if (["completed", "confirmed"].includes(normalized)) return "badge success";
  if (["cancelled", "canceled", "failed"].includes(normalized)) return "badge error";
  return "badge warning";
};

export function MarketplaceOrderDetailsPage() {
  const { orderId } = useParams<{ orderId: string }>();
  const { user } = useAuth();
  const [order, setOrder] = useState<MarketplaceOrderDetails | null>(null);
  const [events, setEvents] = useState<MarketplaceOrderEvent[]>([]);
  const [documents, setDocuments] = useState<MarketplaceOrderDocument[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isEventsLoading, setIsEventsLoading] = useState(true);
  const [isDocumentsLoading, setIsDocumentsLoading] = useState(true);
  const [orderError, setOrderError] = useState<OrderErrorState | null>(null);
  const [eventsError, setEventsError] = useState<OrderErrorState | null>(null);
  const [documentsError, setDocumentsError] = useState<OrderErrorState | null>(null);
  const [isSupportOpen, setIsSupportOpen] = useState(false);

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
        setOrderError({ message: err instanceof Error ? err.message : "Не удалось загрузить заказ" });
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
        setEventsError({ message: err instanceof Error ? err.message : "Не удалось загрузить события" });
      })
      .finally(() => setIsEventsLoading(false));
  }, [user, orderId]);

  useEffect(() => {
    if (!user || !orderId) return;
    setDocumentsError(null);
    setIsDocumentsLoading(true);
    fetchMarketplaceOrderDocuments(user, orderId)
      .then((data) => setDocuments(data.items ?? []))
      .catch((err: unknown) => {
        if (err instanceof ApiError) {
          setDocumentsError({ message: err.message, status: err.status, correlationId: err.correlationId });
          return;
        }
        setDocumentsError({ message: err instanceof Error ? err.message : "Не удалось загрузить документы" });
      })
      .finally(() => setIsDocumentsLoading(false));
  }, [user, orderId]);

  const timeline = useMemo(() => events.slice().sort((a, b) => a.created_at.localeCompare(b.created_at)), [events]);

  if (!user) {
    return <AppForbiddenState message="Нет доступа к заказу." />;
  }

  if (orderError?.status === 403) {
    return <AppForbiddenState message="Просмотр заказа запрещён." />;
  }

  return (
    <div className="stack">
      <div className="card">
        <div className="card__header">
          <div>
            <h2>Детали заказа</h2>
            <p className="muted">Статусы, события и документы по заказу.</p>
          </div>
          <div className="actions">
            <button type="button" className="secondary" onClick={() => setIsSupportOpen(true)}>
              Сообщить о проблеме
            </button>
            <Link to="/marketplace/orders" className="link-button">
              Назад к заказам
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
              <div className="muted small">Статус заказа</div>
              <div className={statusClass(order.status)}>{order.status ?? "—"}</div>
              <div className="muted small">Дата</div>
              <div>{order.created_at ? formatDate(order.created_at) : "—"}</div>
            </div>
            <div className="card muted-card">
              <div className="muted small">Услуга</div>
              <div>{order.service_title ?? "—"}</div>
              <div className="muted small">Партнёр</div>
              <div>{order.partner_name ?? "—"}</div>
              <div className="muted small">Сумма</div>
              <div>
                {order.total_amount !== undefined && order.total_amount !== null
                  ? <MoneyValue amount={order.total_amount} currency={order.currency ?? "RUB"} />
                  : "—"}
              </div>
            </div>
          </div>
        ) : null}
      </div>

      <div className="card">
        <div className="section-title">
          <h3>Таймлайн заказа</h3>
        </div>
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
          <AppEmptyState title="События не найдены" description="История заказа пока не сформирована." />
        ) : null}
        {!eventsError && !isEventsLoading && timeline.length > 0 ? (
          <ul className="timeline">
            {timeline.map((event) => (
              <li key={event.id}>
                <div className="timeline__marker" />
                <div>
                  <strong>{event.type}</strong>
                  <div className="muted small">{event.created_at ? formatDateTime(event.created_at) : "—"}</div>
                  {event.note ? <div className="muted">{event.note}</div> : null}
                </div>
              </li>
            ))}
          </ul>
        ) : null}
      </div>

      <div className="card">
        <div className="section-title">
          <h3>Документы</h3>
        </div>
        {documentsError ? (
          <AppErrorState
            message={documentsError.message}
            status={documentsError.status}
            correlationId={documentsError.correlationId}
          />
        ) : null}
        {isDocumentsLoading ? (
          <div className="skeleton-stack">
            <div className="skeleton-line" />
            <div className="skeleton-line" />
          </div>
        ) : null}
        {!documentsError && !isDocumentsLoading && documents.length === 0 ? (
          <AppEmptyState title="Документы не найдены" description="Документы будут доступны после обработки заказа." />
        ) : null}
        {!documentsError && !isDocumentsLoading && documents.length > 0 ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Тип</th>
                <th>Статус</th>
                <th>Подпись</th>
                <th>ЭДО</th>
                <th>Файлы</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <tr key={doc.id}>
                  <td>{doc.type}</td>
                  <td>{doc.status ?? "—"}</td>
                  <td>{doc.signature_status ?? "—"}</td>
                  <td>{doc.edo_status ?? "—"}</td>
                  <td>
                    {doc.url ? (
                      <a href={doc.url} target="_blank" rel="noreferrer">
                        Скачать
                      </a>
                    ) : null}
                    {doc.files?.length ? (
                      <ul className="stack">
                        {doc.files.map((file) => (
                          <li key={file.id}>
                            {file.url ? (
                              <a href={file.url} target="_blank" rel="noreferrer">
                                {file.name ?? "Скачать"}
                              </a>
                            ) : (
                              file.name ?? "Файл"
                            )}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                    {!doc.url && !doc.files?.length ? "—" : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </div>
      {order ? (
        <SupportRequestModal
          isOpen={isSupportOpen}
          onClose={() => setIsSupportOpen(false)}
          subjectType="ORDER"
          subjectId={order.id}
          defaultTitle={`Проблема с заказом ${order.id}`}
        />
      ) : null}
    </div>
  );
}
