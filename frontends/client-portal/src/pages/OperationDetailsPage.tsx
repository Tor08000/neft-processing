import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchOperationDetails } from "../api/operations";
import { useAuth } from "../auth/AuthContext";
import { CopyButton } from "../components/CopyButton";
import { AppEmptyState, AppErrorState, AppLoadingState } from "../components/states";
import type { OperationDetails } from "../types/operations";
import { formatDateTime, formatLiters, formatMoney } from "../utils/format";

export function OperationDetailsPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [operation, setOperation] = useState<OperationDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    fetchOperationDetails(id, user)
      .then(setOperation)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id, user]);

  if (loading) {
    return <AppLoadingState label="Загружаем операцию..." />;
  }

  if (error) {
    return <AppErrorState message={error} />;
  }

  if (!operation) {
    return <AppEmptyState title="Операция не найдена" description="Проверьте идентификатор." />;
  }

  return (
    <div className="card">
      <div className="card__header">
        <div>
          <h2>Операция {operation.id}</h2>
          <p className="muted">Полная информация по транзакции</p>
        </div>
        <div className="actions">
          <Link to={`/explain/${operation.id}`} className="ghost">
            Explain
          </Link>
          <Link to="/documents" className="ghost">
            Related documents
          </Link>
          <button type="button" className="secondary" disabled>
            Скачать чек (если доступен)
          </button>
        </div>
      </div>

      <dl className="meta-grid">
        <div>
          <dt className="label">Дата</dt>
          <dd>{formatDateTime(operation.created_at)}</dd>
        </div>
        <div>
          <dt className="label">Карта</dt>
          <dd>{operation.card_id}</dd>
        </div>
        <div>
          <dt className="label">АЗС</dt>
          <dd>{operation.merchant_id ?? "—"}</dd>
        </div>
        <div>
          <dt className="label">Продукт</dt>
          <dd>{operation.product_type ?? "—"}</dd>
        </div>
        <div>
          <dt className="label">Литры</dt>
          <dd>{formatLiters(operation.quantity)}</dd>
        </div>
        <div>
          <dt className="label">Сумма</dt>
          <dd>{formatMoney(operation.amount, operation.currency)}</dd>
        </div>
        <div>
          <dt className="label">Статус</dt>
          <dd>
            <span className={`pill pill--${operation.status === "APPROVED" ? "success" : "warning"}`}>
              {operation.status}
            </span>
            {operation.primary_reason ? (
              <span className="pill pill--neutral">{operation.primary_reason}</span>
            ) : null}
          </dd>
        </div>
        {operation.reason && (
          <div>
            <dt className="label">Причина</dt>
            <dd>{operation.reason}</dd>
          </div>
        )}
        <div>
          <dt className="label">Primary reason</dt>
          <dd>{operation.primary_reason ?? "—"}</dd>
        </div>
        <div>
          <dt className="label">Risk level</dt>
          <dd>{operation.risk_level ?? "—"}</dd>
        </div>
        <div>
          <dt className="label">Correlation ID</dt>
          <dd className="stack-inline">
            <span className="muted small">{operation.correlation_id ?? "—"}</span>
            <CopyButton value={operation.correlation_id ?? undefined} label="Скопировать" />
          </dd>
        </div>
        <div>
          <dt className="label">Request ID</dt>
          <dd className="stack-inline">
            <span className="muted small">{operation.request_id ?? "—"}</span>
            <CopyButton value={operation.request_id ?? undefined} label="Скопировать" />
          </dd>
        </div>
        <div>
          <dt className="label">Документ/инвойс</dt>
          <dd className="muted">Если документ доступен, он появится в разделе Documents.</dd>
        </div>
        <div>
          <dt className="label">Связанный рейс</dt>
          <dd className="muted">Нет данных</dd>
        </div>
      </dl>
    </div>
  );
}
