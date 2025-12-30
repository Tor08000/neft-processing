import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchExplainInsights } from "../api/explain";
import { useAuth } from "../auth/AuthContext";
import { AppEmptyState, AppErrorState, AppLoadingState } from "../components/states";
import type { ExplainInsightsResponse } from "../types/explain";
import { formatDate } from "../utils/format";

const buildRange = (days: number) => {
  const to = new Date();
  const from = new Date();
  from.setDate(to.getDate() - days);
  return {
    from: from.toISOString().slice(0, 10),
    to: to.toISOString().slice(0, 10),
  };
};

export function ExplainInsightsPage() {
  const { user } = useAuth();
  const [range, setRange] = useState(buildRange(30));
  const [payload, setPayload] = useState<ExplainInsightsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    setIsLoading(true);
    setError(null);
    fetchExplainInsights(user, range)
      .then((resp) => setPayload(resp))
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [range, user]);

  const trendByReason = useMemo(() => {
    if (!payload) return new Map<string, number>();
    const summary = new Map<string, number>();
    payload.trend.forEach((item) => summary.set(item.reason, (summary.get(item.reason) ?? 0) + item.count));
    return summary;
  }, [payload]);

  if (!user) {
    return <AppEmptyState title="Нет доступа" description="Для просмотра аналитики требуется авторизация." />;
  }

  return (
    <div className="stack">
      <section className="card">
        <div className="card__header">
          <div>
            <h2>Explain Insights</h2>
            <p className="muted">Агрегированная аналитика по причинам и отказам.</p>
          </div>
          <Link className="ghost" to="/explain">
            Перейти к explain
          </Link>
        </div>
        <div className="filters">
          <div className="filter">
            <label htmlFor="from">Период с</label>
            <input
              id="from"
              type="date"
              value={range.from}
              onChange={(event) => setRange((prev) => ({ ...prev, from: event.target.value }))}
            />
          </div>
          <div className="filter">
            <label htmlFor="to">Период по</label>
            <input
              id="to"
              type="date"
              value={range.to}
              onChange={(event) => setRange((prev) => ({ ...prev, to: event.target.value }))}
            />
          </div>
        </div>
      </section>

      {isLoading ? <AppLoadingState /> : null}
      {error ? <AppErrorState message={error} onRetry={() => setRange({ ...range })} /> : null}

      {!isLoading && !error && payload ? (
        <div className="grid two">
          <div className="card">
            <h3>Top primary reasons</h3>
            {payload.top_primary_reasons.length ? (
              <ul className="bars">
                {payload.top_primary_reasons.map((item) => (
                  <li key={item.reason}>
                    <span className="muted small">{item.reason}</span>
                    <div className="bar">
                      <span
                        className="bar__fill"
                        style={{ width: `${Math.min(100, item.count * 8)}%` }}
                      />
                    </div>
                    <span className="small">{item.count}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <AppEmptyState title="Нет данных" description="Причины за период отсутствуют." />
            )}
          </div>
          <div className="card">
            <h3>Trend по primary reason</h3>
            {payload.trend.length ? (
              <ul className="bullets">
                {Array.from(trendByReason.entries()).map(([reason, count]) => (
                  <li key={reason}>
                    {reason} — {count}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">Тренд не сформирован.</p>
            )}
            <div className="muted small">
              Период: {formatDate(payload.from)} — {formatDate(payload.to)}
            </div>
          </div>
          <div className="card">
            <h3>Где мы теряем деньги</h3>
            {payload.top_decline_reasons.length ? (
              <ul className="bullets">
                {payload.top_decline_reasons.map((item) => (
                  <li key={item.reason}>
                    {item.reason} — {item.count}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">Нет данных по отказам.</p>
            )}
          </div>
          <div className="card">
            <h3>Топ станций по отказам</h3>
            {payload.top_decline_stations.length ? (
              <ul className="bullets">
                {payload.top_decline_stations.map((item) => (
                  <li key={item.reason}>
                    {item.reason} — {item.count}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">Нет данных по станциям.</p>
            )}
            <div className="actions">
              <Link className="ghost" to={`/operations?from=${range.from}&to=${range.to}&status=DECLINED`}>
                Открыть операции с отказами
              </Link>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
