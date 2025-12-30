import { StatusBadge } from "../components/StatusBadge";
import { EmptyState, ErrorState, LoadingState } from "../components/states";
import type { MarketplaceOrderEvent } from "../types/marketplace";
import { formatDateTime } from "../utils/format";

const eventLabels: Record<string, string> = {
  CREATED: "Создан",
  PAID: "Оплачен",
  AUTHORIZED: "Авторизован",
  CONFIRMED: "Подтверждён",
  CONFIRMED_BY_PARTNER: "Подтверждён партнёром",
  IN_PROGRESS: "В работе",
  COMPLETED: "Завершён",
  CANCELLED: "Отменён",
  REFUND_OPENED: "Открыт возврат",
  REFUND_APPROVED: "Возврат одобрен",
  REFUND_DENIED: "Возврат отклонён",
  REFUNDED: "Возврат завершён",
  DISPUTED: "Открыт спор",
};

interface OrderTimelinePanelProps {
  events: MarketplaceOrderEvent[];
  isLoading: boolean;
  error: string | null;
  correlationId?: string | null;
  onRetry?: () => void;
}

export function OrderTimelinePanel({
  events,
  isLoading,
  error,
  correlationId,
  onRetry,
}: OrderTimelinePanelProps) {
  if (isLoading) {
    return <LoadingState label="Загружаем таймлайн заказа..." />;
  }

  if (error) {
    return (
      <ErrorState
        title="Не удалось загрузить таймлайн"
        description={error}
        correlationId={correlationId}
        action={
          onRetry ? (
            <button type="button" className="secondary" onClick={onRetry}>
              Повторить
            </button>
          ) : null
        }
      />
    );
  }

  if (events.length === 0) {
    return <EmptyState title="История пока пуста" description="События заказа появятся здесь." />;
  }

  return (
    <div className="stack">
      {events.map((event) => (
        <div key={event.id} className="invoice-thread__message">
          <div className="thread-header">
            <strong>{eventLabels[event.type] ?? event.type}</strong>
            <StatusBadge status={event.status ?? event.type} />
          </div>
          {event.note ? <div>{event.note}</div> : null}
          <div className="muted small">{formatDateTime(event.createdAt)}</div>
        </div>
      ))}
    </div>
  );
}
