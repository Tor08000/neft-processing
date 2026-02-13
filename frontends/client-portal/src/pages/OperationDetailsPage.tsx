import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { fetchOperationDetails } from "../api/operations";
import { useAuth } from "../auth/AuthContext";
import { CopyButton } from "../components/CopyButton";
import { SupportRequestModal } from "../components/SupportRequestModal";
import { AppEmptyState, AppErrorState, AppLoadingState } from "../components/states";
import type { OperationDetails } from "../types/operations";
import { formatDateTime, formatLiters } from "../utils/format";
import { MoneyValue } from "../components/common/MoneyValue";

export function OperationDetailsPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [operation, setOperation] = useState<OperationDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isSupportOpen, setIsSupportOpen] = useState(false);

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
          <Link to={`/explain?kind=operation&id=${encodeURIComponent(operation.id)}`} className="ghost">
            Explain
          </Link>
          <Link to={`/explain?kind=operation&id=${encodeURIComponent(operation.id)}&diff=1`} className="ghost">
            Сравнить
          </Link>
          <Link to="/documents" className="ghost">
            Related documents
          </Link>
          <button type="button" className="secondary" onClick={() => setIsSupportOpen(true)}>
            Сообщить о проблеме
          </button>
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
          <dd>
            <MoneyValue amount={operation.amount} currency={operation.currency} />
          </dd>
        </div>
        <div>
          <dt className="label">Статус</dt>
          <dd>
            <span
              className={`pill pill--${
                operation.status === "APPROVED" ? "success" : operation.status === "DECLINED" ? "danger" : "warning"
              }`}
            >
              {operation.status}
            </span>
            {operation.primary_reason ? (
              <span className="pill pill--neutral" title={operation.primary_reason}>
                {operation.primary_reason}
              </span>
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
          <dd title={operation.risk_level ? `Risk level: ${operation.risk_level}` : undefined}>
            {operation.risk_level ?? "—"}
          </dd>
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

      {operation.station ? (
        <div className="card" style={{ marginTop: 16 }}>
          <h3>Станция</h3>
          <p><strong>{operation.station.name}</strong></p>
          <p>{operation.station.address ?? "Адрес не указан"}</p>
          <div className="actions">
            <button
              type="button"
              className="secondary"
              onClick={() => navigate(`/stations-map?station_id=${encodeURIComponent(operation.station!.id)}`)}
            >
              Показать на карте
            </button>
            <button
              type="button"
              className="secondary"
              disabled={!operation.station.nav_url}
              title={!operation.station.nav_url ? "Нет координат/URL станции" : undefined}
              onClick={() => operation.station?.nav_url && window.open(operation.station.nav_url, "_blank", "noopener,noreferrer")}
            >
              Проложить маршрут
            </button>
          </div>
        </div>
      ) : null}
      {operation ? (
        <SupportRequestModal
          isOpen={isSupportOpen}
          onClose={() => setIsSupportOpen(false)}
          defaultSubject={`Проблема с заказом ${operation.id}`}
        />
      ) : null}
    </div>
  );
}
