import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchUnifiedExplain } from "../api/explain";
import { useAuth } from "../auth/AuthContext";
import { AppEmptyState, AppErrorState, AppLoadingState } from "../components/states";
import type { UnifiedExplainResponse } from "../types/explain";
import { formatDateTime } from "../utils/format";

const DEFAULT_VIEW = "ACCOUNTANT";

export function ExplainPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [operationId, setOperationId] = useState(id ?? "");
  const [payload, setPayload] = useState<UnifiedExplainResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadExplain = useCallback(
    async (targetId: string) => {
      if (!targetId || !user) return;
      setIsLoading(true);
      setError(null);
      try {
        const data = await fetchUnifiedExplain(user, { fuelTxId: targetId, view: DEFAULT_VIEW, depth: 3 });
        setPayload(data);
      } catch (err) {
        setError((err as Error).message);
        setPayload(null);
      } finally {
        setIsLoading(false);
      }
    },
    [user],
  );

  useEffect(() => {
    if (id) {
      void loadExplain(id);
    }
  }, [id, loadExplain]);

  const slaStatus = useMemo(() => {
    if (!payload?.sla) return null;
    return payload.sla.remaining_minutes > 0 ? "active" : "expired";
  }, [payload?.sla]);

  return (
    <div className="card">
      <div className="card__header">
        <div>
          <h2>Explain</h2>
          <p className="muted">Explain центр: причина → действия → SLA.</p>
        </div>
        <Link className="ghost" to="/operations">
          Назад к операциям
        </Link>
      </div>

      <div className="filters">
        <div className="filter">
          <label htmlFor="operationId">ID операции</label>
          <input
            id="operationId"
            name="operationId"
            type="text"
            value={operationId}
            onChange={(event) => setOperationId(event.target.value)}
            placeholder="Введите ID операции"
          />
        </div>
        <div className="filter">
          <button
            type="button"
            className="primary"
            onClick={() => void loadExplain(operationId)}
            disabled={!operationId || isLoading}
          >
            Загрузить Explain
          </button>
        </div>
      </div>

      {isLoading ? <AppLoadingState label="Загружаем explain..." /> : null}

      {error ? <AppErrorState message={error} /> : null}

      {!isLoading && !error && !payload ? (
        <AppEmptyState title="Нет данных" description="Введите ID операции для объяснения." />
      ) : null}

      {payload ? (
        <div className="stack">
          <section className="card__section">
            <h3>Primary reason</h3>
            <div className="explain-primary">
              <span className="pill pill--warning">{payload.primary_reason}</span>
              <div className="muted">Confidence: {payload.confidence ?? "—"}</div>
            </div>
          </section>

          <section className="card__section">
            <h3>Secondary reasons</h3>
            {payload.secondary_reasons.length ? (
              <details>
                <summary>Показать детали</summary>
                <ul className="bullets">
                  {payload.secondary_reasons.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              </details>
            ) : (
              <p className="muted">Secondary reasons не зафиксированы.</p>
            )}
          </section>

          <section className="card__section">
            <h3>Actions</h3>
            {payload.actions.length ? (
              <div className="action-list">
                {payload.actions.map((action) => (
                  <div className="action-card" key={action.code}>
                    <div className="stack-inline">
                      <span className={`pill pill--${action.severity === "REQUIRED" ? "danger" : "neutral"}`}>
                        {action.severity}
                      </span>
                      <strong>{action.title}</strong>
                    </div>
                    <p className="muted small">{action.description}</p>
                    {action.target ? (
                      <div className="muted small">Escalation target: {action.target}</div>
                    ) : null}
                    <button type="button" className="ghost" disabled>
                      Запросить действие (read-only)
                    </button>
                  </div>
                ))}
              </div>
            ) : payload.recommendations.length ? (
              <ul className="bullets">
                {payload.recommendations.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : (
              <p className="muted">Action hints отсутствуют.</p>
            )}
          </section>

          <section className="card__section">
            <h3>SLA</h3>
            {payload.sla ? (
              <div className="meta-grid">
                <div>
                  <div className="label">Статус</div>
                  <span className={`pill pill--${slaStatus === "active" ? "success" : "danger"}`}>
                    {slaStatus === "active" ? "Активен" : "Истек"}
                  </span>
                </div>
                <div>
                  <div className="label">Начало</div>
                  <div>{formatDateTime(payload.sla.started_at)}</div>
                </div>
                <div>
                  <div className="label">Окончание</div>
                  <div>{formatDateTime(payload.sla.expires_at)}</div>
                </div>
                <div>
                  <div className="label">Осталось</div>
                  <div>{payload.sla.remaining_minutes} мин</div>
                </div>
              </div>
            ) : (
              <p className="muted">SLA не задан.</p>
            )}
            {payload.escalation ? (
              <div className="muted small">Escalation target: {payload.escalation.target}</div>
            ) : null}
          </section>

          <section className="card__section">
            <h3>Timeline</h3>
            {payload.timeline && payload.timeline.length ? (
              <div className="timeline-list">
                {payload.timeline.map((event) => (
                  <div className="timeline-item" key={event.id}>
                    <div className="timeline-item__meta">
                      <span className="timeline-item__title">{event.stage}</span>
                      <span className="muted small">{formatDateTime(event.at)}</span>
                    </div>
                    <div className="timeline-item__body">
                      <span className="muted small">{event.label}</span>
                      {event.details ? <span className="muted small">{event.details}</span> : null}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted">Timeline недоступен.</p>
            )}
          </section>
        </div>
      ) : null}
    </div>
  );
}
