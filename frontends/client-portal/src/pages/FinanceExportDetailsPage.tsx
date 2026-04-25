import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchExportDetails } from "../api/exports";
import { useAuth } from "../auth/AuthContext";
import { AppEmptyState, AppErrorState, AppLoadingState } from "../components/states";
import type { AccountingExportDetails } from "../types/exports";
import { formatDate, formatDateTime } from "../utils/format";
import { MoneyValue } from "../components/common/MoneyValue";
import { FinanceOverview } from "@shared/brand/components";

export function FinanceExportDetailsPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [details, setDetails] = useState<AccountingExportDetails | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
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
          <FinanceOverview
            compact
            items={Object.entries(details.totals).map(([key, value]) => ({
              id: key,
              label: key,
              value: <MoneyValue amount={value} />,
              tone: key.toLowerCase().includes("net")
                ? "success"
                : key.toLowerCase().includes("fee") || key.toLowerCase().includes("refund")
                  ? "warning"
                  : "info",
            }))}
          />
        ) : (
          <AppEmptyState
            title="Totals ещё не рассчитаны"
            description="Сводка появится после обработки строк выгрузки."
          />
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
          <AppEmptyState
            title="Событий ERP пока нет"
            description="Хронология появится после передачи выгрузки в ERP."
          />
        )}
      </section>

      <section className="card">
        <h3>Reconciliation</h3>
        {details.reconciliation ? (
          <FinanceOverview
            compact
            items={[
              {
                id: "expected-total",
                label: "Expected total",
                value: <MoneyValue amount={details.reconciliation.expected_total ?? 0} />,
                tone: "info",
              },
              {
                id: "received-total",
                label: "Received total",
                value: <MoneyValue amount={details.reconciliation.received_total ?? 0} />,
                tone: "success",
              },
              {
                id: "mismatch-summary",
                label: "Mismatch summary",
                value: details.reconciliation.mismatch_summary ?? "—",
                tone: details.reconciliation.mismatch_summary ? "warning" : "default",
              },
            ]}
          />
        ) : (
          <AppEmptyState
            title="Сверка пока недоступна"
            description="Сводка появится после обработки импортов и подтверждения в ERP."
          />
        )}
        <div className="actions">
          <Link className="primary" to="/client/support/new?topic=billing">
            Написать в поддержку
          </Link>
          <Link className="ghost" to="/exports">
            Вернуться к выгрузкам
          </Link>
        </div>
      </section>
    </div>
  );
}
