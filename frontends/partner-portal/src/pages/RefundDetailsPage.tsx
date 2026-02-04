import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../api/http";
import { approveRefund, denyRefund, fetchRefund } from "../api/refunds";
import { useAuth } from "../auth/AuthContext";
import { StatusBadge } from "../components/StatusBadge";
import { EmptyState, ErrorState, ForbiddenState, LoadingState } from "../components/states";
import type { RefundRequest } from "../types/marketplace";
import { formatCurrency, formatDateTime } from "../utils/format";
import { canManageRefunds, canReadRefunds } from "../utils/roles";

const describeError = (err: unknown, fallback: string) => {
  if (err instanceof ApiError) {
    return { message: fallback, correlationId: null };
  }
  if (err instanceof Error) {
    return { message: fallback, correlationId: null };
  }
  return { message: fallback, correlationId: null };
};

export function RefundDetailsPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [refund, setRefund] = useState<RefundRequest | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [correlationId, setCorrelationId] = useState<string | null>(null);
  const [actionModal, setActionModal] = useState<"approve" | "deny" | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionCorrelationId, setActionCorrelationId] = useState<string | null>(null);
  const [denyReason, setDenyReason] = useState("");
  const [approveAmount, setApproveAmount] = useState<string>("");
  const [approveNote, setApproveNote] = useState<string>("");

  const canRead = canReadRefunds(user?.roles);
  const canManage = canManageRefunds(user?.roles);
  const refundId = id ?? "";

  const loadRefund = useCallback(() => {
    if (!user || !refundId) return;
    setIsLoading(true);
    setError(null);
    setCorrelationId(null);
    fetchRefund(user.token, refundId)
      .then((data) => setRefund(data))
      .catch((err) => {
        console.error(err);
        const { message, correlationId: corr } = describeError(err, "Не удалось загрузить возврат");
        setError(message);
        setCorrelationId(corr);
      })
      .finally(() => setIsLoading(false));
  }, [user, refundId]);

  useEffect(() => {
    if (!canRead) return;
    loadRefund();
  }, [canRead, loadRefund]);

  const handleAction = async () => {
    if (!user || !refund) return;
    setActionError(null);
    setActionMessage(null);
    setActionCorrelationId(null);
    try {
      if (actionModal === "approve") {
        const amount = approveAmount ? Number(approveAmount) : undefined;
        const result = await approveRefund(user.token, refund.id, { amount, note: approveNote || undefined });
        setActionMessage("Возврат одобрен.");
        setActionCorrelationId(null);
      }
      if (actionModal === "deny") {
        const result = await denyRefund(user.token, refund.id, denyReason);
        setActionMessage("Возврат отклонён.");
        setActionCorrelationId(null);
      }
      setActionModal(null);
      setDenyReason("");
      setApproveAmount("");
      setApproveNote("");
      loadRefund();
    } catch (err) {
      console.error(err);
      const { message, correlationId: corr } = describeError(err, "Не удалось выполнить действие");
      setActionError(message);
      setActionCorrelationId(corr);
    }
  };

  if (!canRead) {
    return <ForbiddenState />;
  }

  if (isLoading) {
    return <LoadingState label="Загружаем возврат..." />;
  }

  if (error || !refund) {
    return (
      <ErrorState
        title="Не удалось загрузить возврат"
        description={error ?? "Возврат не найден"}
        correlationId={correlationId}
        action={
          <button type="button" className="secondary" onClick={loadRefund}>
            Повторить
          </button>
        }
      />
    );
  }

  const denyDisabled = actionModal === "deny" && denyReason.trim().length === 0;

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <h2>Возврат {refund.id}</h2>
          <Link className="ghost" to="/refunds">
            Назад к возвратам
          </Link>
        </div>
        <div className="meta-grid">
          <div>
            <div className="label">Статус</div>
            <StatusBadge status={refund.status} />
          </div>
          <div>
            <div className="label">Сумма</div>
            <div>{formatCurrency(refund.amount)}</div>
          </div>
          <div>
            <div className="label">Order ID</div>
            <Link className="link-button" to={`/orders/${refund.orderId}`}>
              {refund.orderId}
            </Link>
          </div>
          <div>
            <div className="label">Создан</div>
            <div>{formatDateTime(refund.createdAt)}</div>
          </div>
        </div>
        <div className="card__section">
          <div className="label">Причина</div>
          <div>{refund.reason ?? "—"}</div>
        </div>
      </section>

      <section className="card">
        <div className="section-title">
          <h3>Доказательства</h3>
        </div>
        {refund.evidence && refund.evidence.length > 0 ? (
          <ul className="bullets">
            {refund.evidence.map((item) => (
              <li key={item.id}>
                {item.url ? (
                  <a className="link-button" href={item.url} target="_blank" rel="noreferrer">
                    {item.name ?? item.id}
                  </a>
                ) : (
                  item.name ?? item.id
                )}
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState title="Нет вложений" description="Материалы не приложены." />
        )}
      </section>

      <section className="card">
        <div className="section-title">
          <h3>Таймлайн</h3>
        </div>
        {refund.events && refund.events.length > 0 ? (
          <div className="stack">
            {refund.events.map((event) => (
              <div key={event.id} className="invoice-thread__message">
                <div className="thread-header">
                  <strong>{event.status}</strong>
                  <span className="muted small">{formatDateTime(event.createdAt)}</span>
                </div>
                {event.note ? <div>{event.note}</div> : null}
              </div>
            ))}
          </div>
        ) : (
          <EmptyState title="Нет событий" description="История возврата будет доступна после обновлений." />
        )}
      </section>

      <section className="card">
        <div className="section-title">
          <h3>Действия</h3>
          <span className="muted">Требуется подтверждение, действия логируются.</span>
        </div>
        {!canManage ? (
          <EmptyState title="Действия недоступны" description="У вашей роли нет доступа к управлению возвратом." />
        ) : (
          <div className="actions">
            <button type="button" className="secondary" onClick={() => setActionModal("approve")}>
              Одобрить
            </button>
            <button type="button" className="secondary" onClick={() => setActionModal("deny")}>
              Отклонить
            </button>
          </div>
        )}
        {actionMessage ? <div className="notice">{actionMessage}</div> : null}
        {actionError ? (
          <div className="notice error">
            {actionError}
          </div>
        ) : null}
      </section>

      {actionModal ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal">
            <div className="section-title">
              <h3>{actionModal === "approve" ? "Одобрить возврат" : "Отклонить возврат"}</h3>
              <button type="button" className="ghost" onClick={() => setActionModal(null)}>
                Закрыть
              </button>
            </div>
            <div>Действие будет записано в audit. Проверьте данные перед подтверждением.</div>
            {actionModal === "approve" ? (
              <div className="stack">
                <label className="form-field">
                  Сумма (опционально)
                  <input
                    type="number"
                    value={approveAmount}
                    onChange={(event) => setApproveAmount(event.target.value)}
                    placeholder={refund.amount.toString()}
                  />
                </label>
                <label className="form-field">
                  Комментарий
                  <input type="text" value={approveNote} onChange={(event) => setApproveNote(event.target.value)} />
                </label>
              </div>
            ) : (
              <label className="form-field">
                Причина отказа
                <textarea
                  className="textarea"
                  value={denyReason}
                  onChange={(event) => setDenyReason(event.target.value)}
                  placeholder="Укажите причину"
                />
              </label>
            )}
            <div className="actions">
              <button type="button" className="secondary" onClick={() => setActionModal(null)}>
                Отмена
              </button>
              <button type="button" className="primary" onClick={handleAction} disabled={denyDisabled}>
                Подтвердить
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
