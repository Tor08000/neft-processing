import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchExportDetails } from "../api/exports";
import { useAuth } from "../auth/AuthContext";
import { AppEmptyState, AppErrorState, AppLoadingState } from "../components/states";
import type { AccountingExportDetails } from "../types/exports";
import { formatDate, formatDateTime } from "../utils/format";
import { MoneyValue } from "../components/common/MoneyValue";

export function FinanceExportDetailsPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [details, setDetails] = useState<AccountingExportDetails | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionStatus, setActionStatus] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    if (!id) return;
    setIsLoading(true);
    setError(null);
    fetchExportDetails(id, user)
      .then((resp) => setDetails(resp))
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [id, user, retryKey]);

  if (!id) {
    return <AppEmptyState title="Экспорт не найден" description="Укажите корректный идентификатор экспорта." />;
  }

  if (isLoading) {
    return <AppLoadingState label="Загружаем детализацию экспорта..." />;
  }

  if (error) {
    return <AppErrorState message={error} onRetry={() => setRetryKey((prev) => prev + 1)} />;
  }

  if (!details) {
    return <AppEmptyState title="Нет данных" description="Экспорт отсутствует или недоступен." />;
  }

  return (
    <div className="stack">
      <section className="card">
        <div className="card__header">
          <div>
            <h2>Export detail</h2>
            <p className="muted">{details.type ?? details.title ?? "Выгрузка"}</p>
          </div>
          <Link className="ghost" to="/exports">
            Назад к списку
          </Link>
        </div>
        <dl className="meta-grid">
          <div>
            <dt className="label">Период</dt>
            <dd>
              {details.period_from || details.period_to
                ? `${formatDate(details.period_from)} — ${formatDate(details.period_to)}`
                : "—"}
            </dd>
          </div>
          <div>
            <dt className="label">Checksum</dt>
            <dd>{details.checksum ?? "—"}</dd>
          </div>
          <div>
            <dt className="label">Строк</dt>
            <dd>{details.line_count ?? "—"}</dd>
          </div>
          <div>
            <dt className="label">Mapping version</dt>
            <dd>{details.mapping_version ?? "—"}</dd>
          </div>
          <div>
            <dt className="label">Статус</dt>
            <dd>{details.status ?? "—"}</dd>
          </div>
          <div>
            <dt className="label">ERP статус</dt>
            <dd>{details.erp_status ?? "—"}</dd>
          </div>
        </dl>
      </section>

      <section className="card">
        <h3>Totals</h3>
        {details.totals && Object.keys(details.totals).length ? (
          <ul className="bullets">
            {Object.entries(details.totals).map(([key, value]) => (
              <li key={key}>
                {key}: <MoneyValue amount={value} />
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">Totals не доступны.</p>
        )}
      </section>

      <section className="card">
        <h3>ERP timeline</h3>
        {details.erp_timeline && details.erp_timeline.length ? (
          <div className="timeline-list">
            {details.erp_timeline.map((event, index) => (
              <div className="timeline-item" key={`${event.status}-${index}`}>
                <div className="timeline-item__meta">
                  <span className="timeline-item__title">{event.status}</span>
                  <span className="muted small">{formatDateTime(event.occurred_at)}</span>
                </div>
                {event.message ? <div className="timeline-item__body">{event.message}</div> : null}
              </div>
            ))}
          </div>
        ) : (
          <p className="muted">События ERP отсутствуют.</p>
        )}
      </section>

      <section className="card">
        <h3>Reconciliation</h3>
        {details.reconciliation ? (
          <dl className="meta-grid">
            <div>
              <dt className="label">Expected total</dt>
              <dd>
                <MoneyValue amount={details.reconciliation.expected_total ?? 0} />
              </dd>
            </div>
            <div>
              <dt className="label">Received total</dt>
              <dd>
                <MoneyValue amount={details.reconciliation.received_total ?? 0} />
              </dd>
            </div>
            <div>
              <dt className="label">Mismatch summary</dt>
              <dd>{details.reconciliation.mismatch_summary ?? "—"}</dd>
            </div>
          </dl>
        ) : (
          <p className="muted">Reconciliation не доступен.</p>
        )}
        <div className="actions">
          <button
            type="button"
            className="primary"
            onClick={() => setActionStatus("Request support queued")}
          >
            Request support
          </button>
        </div>
        {actionStatus ? <div className="muted small">{actionStatus}</div> : null}
      </section>
    </div>
  );
}
