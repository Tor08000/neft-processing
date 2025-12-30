import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchSpendDashboard } from "../api/spend";
import { fetchOperations } from "../api/operations";
import { useAuth } from "../auth/AuthContext";
import type { OperationSummary } from "../types/operations";
import type { SpendDashboardSummary } from "../types/spend";
import { formatMoney } from "../utils/format";

const TOP_LIMIT = 5;

const summarizeTop = (items: OperationSummary[], key: keyof OperationSummary) => {
  const tally = new Map<string, number>();
  items.forEach((item) => {
    const value = item[key];
    const label = typeof value === "string" && value ? value : "Не указано";
    tally.set(label, (tally.get(label) ?? 0) + 1);
  });
  return Array.from(tally.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, TOP_LIMIT);
};

export function DashboardPage() {
  const { user } = useAuth();
  const [summary, setSummary] = useState<SpendDashboardSummary | null>(null);
  const [operations, setOperations] = useState<OperationSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    setIsLoading(true);
    setError(null);
    fetchSpendDashboard(user)
      .then((data) => setSummary(data.summary))
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [user]);

  useEffect(() => {
    if (!user) return;
    fetchOperations(user, { limit: 100, offset: 0 })
      .then((resp) => setOperations(resp.items))
      .catch((err: Error) => setError(err.message));
  }, [user]);

  const topCategories = useMemo(() => summarizeTop(operations, "product_type"), [operations]);
  const topMerchants = useMemo(() => summarizeTop(operations, "merchant_id"), [operations]);
  const declinedShare = useMemo(() => {
    if (operations.length === 0) return 0;
    const declined = operations.filter((op) => op.status === "DECLINED").length;
    return Math.round((declined / operations.length) * 100);
  }, [operations]);

  const trendMax = Math.max(...(summary?.spending_trend ?? [0]));

  if (!user) {
    return null;
  }

  if (error) {
    return (
      <div className="card error" role="alert">
        {error}
      </div>
    );
  }

  return (
    <div className="stack" aria-live="polite">
      <section className="card">
        <div className="card__header">
          <div>
            <h2>Обзор расходов</h2>
            <p className="muted">Spend dashboard с ключевыми метриками по операциям.</p>
          </div>
          <Link className="ghost" to="/spend/transactions">
            Перейти к операциям
          </Link>
        </div>
        {isLoading ? (
          <div className="skeleton-stack">
            <div className="skeleton-line" />
            <div className="skeleton-line" />
            <div className="skeleton-line" />
          </div>
        ) : (
          <div className="stats-grid">
            <div className="stat">
              <div className="stat__label">Сумма расходов ({summary?.period ?? "период"})</div>
              <div className="stat__value">{formatMoney(summary?.total_amount ?? 0)}</div>
            </div>
            <div className="stat">
              <div className="stat__label">Кол-во операций</div>
              <div className="stat__value">{summary?.total_operations ?? operations.length}</div>
            </div>
            <div className="stat">
              <div className="stat__label">Активные лимиты</div>
              <div className="stat__value">{summary?.active_limits ?? "—"}</div>
            </div>
            <div className="stat">
              <div className="stat__label">Доля отказов</div>
              <div className="stat__value">{declinedShare}%</div>
            </div>
          </div>
        )}
      </section>

      <section className="grid two">
        <div className="card">
          <h3>Spending over time</h3>
          {summary?.spending_trend?.length ? (
            <div className="chart">
              {summary.spending_trend.map((value, index) => (
                <div className="chart-row" key={`${summary.dates[index]}-${value}`}>
                  <span className="muted small">{summary.dates[index]}</span>
                  <div className="chart-bar">
                    <span
                      className="chart-bar__fill"
                      style={{ width: `${trendMax ? Math.max(4, (value / trendMax) * 100) : 0}%` }}
                    />
                  </div>
                  <span className="small">{formatMoney(value)}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted">Нет данных по тренду расходов.</p>
          )}
        </div>
        <div className="card">
          <h3>Top merchants / stations</h3>
          {topMerchants.length ? (
            <ul className="bars">
              {topMerchants.map(([label, count]) => (
                <li key={label}>
                  <span className="muted small">{label}</span>
                  <div className="bar">
                    <span className="bar__fill" style={{ width: `${(count / operations.length) * 100}%` }} />
                  </div>
                  <span className="small">{count}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">Данных по мерчантам пока нет.</p>
          )}
        </div>
      </section>

      <section className="grid two">
        <div className="card">
          <h3>Top categories</h3>
          {topCategories.length ? (
            <ul className="bars">
              {topCategories.map(([label, count]) => (
                <li key={label}>
                  <span className="muted small">{label}</span>
                  <div className="bar">
                    <span className="bar__fill" style={{ width: `${(count / operations.length) * 100}%` }} />
                  </div>
                  <span className="small">{count}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">Нет данных по категориям.</p>
          )}
        </div>
        <div className="card">
          <h3>Explain readiness</h3>
          <p className="muted">
            Для каждой операции доступно Explain с причиной, действиями и SLA. Откройте любую операцию, чтобы
            увидеть детализацию.
          </p>
          <div className="actions">
            <Link className="ghost" to="/explain">
              Перейти к explain
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
