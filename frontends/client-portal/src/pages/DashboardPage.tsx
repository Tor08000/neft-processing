import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchSpendDashboard } from "../api/spend";
import { fetchOperations } from "../api/operations";
import { fetchDocuments } from "../api/documents";
import { fetchExports } from "../api/exports";
import { useAuth } from "../auth/AuthContext";
import type { OperationSummary } from "../types/operations";
import type { SpendDashboardSummary } from "../types/spend";
import { AppEmptyState, AppErrorState, AppLoadingState } from "../components/states";
import { MoneyValue } from "../components/common/MoneyValue";
import { canAccessFinance, canAccessOps } from "../utils/roles";

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
  const [docsAttention, setDocsAttention] = useState(0);
  const [exportsAttention, setExportsAttention] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    setIsLoading(true);
    setError(null);
    Promise.all([
      fetchSpendDashboard(user),
      fetchOperations(user, { limit: 100, offset: 0 }),
      fetchDocuments(user, { limit: 50, offset: 0 }),
      fetchExports(user),
    ])
      .then(([dashboard, ops, docs, exportsList]) => {
        setSummary(dashboard.summary);
        setOperations(ops.items);
        setDocsAttention(
          docs.items.filter(
            (doc) =>
              doc.signature_status !== "signed" ||
              doc.edo_status === "failed" ||
              doc.edo_status === "rejected",
          ).length,
        );
        setExportsAttention(
          exportsList.items.filter(
            (item) =>
              item.reconciliation_status === "mismatch" ||
              item.reconciliation_verdict === "MISMATCH" ||
              item.status === "FAILED",
          ).length,
        );
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [user]);

  const topCategories = useMemo(() => summarizeTop(operations, "product_type"), [operations]);
  const topMerchants = useMemo(() => summarizeTop(operations, "merchant_id"), [operations]);
  const topCards = useMemo(() => summarizeTop(operations, "card_id"), [operations]);
  const declinedShare = useMemo(() => {
    if (operations.length === 0) return 0;
    const declined = operations.filter((op) => op.status === "DECLINED").length;
    return Math.round((declined / operations.length) * 100);
  }, [operations]);
  const declinedCount = useMemo(() => operations.filter((op) => op.status === "DECLINED").length, [operations]);
  const topDeclineReason = useMemo(() => {
    const declined = operations.filter((op) => op.status === "DECLINED" && op.primary_reason);
    if (!declined.length) return "—";
    const counts = summarizeTop(declined, "primary_reason");
    return counts[0]?.[0] ?? "—";
  }, [operations]);
  const highRiskCount = useMemo(
    () => operations.filter((op) => ["HIGH", "CRITICAL"].includes(op.risk_level ?? "")).length,
    [operations],
  );

  const trendMax = Math.max(...(summary?.spending_trend ?? [0]));

  if (!user) {
    return null;
  }

  return (
    <div className="stack" aria-live="polite">
      <section className="card">
        <div className="card__header">
          <div>
            <h2>Обзор расходов</h2>
            <p className="muted">Spend dashboard с ключевыми метриками по операциям.</p>
          </div>
          {canAccessOps(user) ? (
            <Link className="ghost" to="/operations">
              Перейти к операциям
            </Link>
          ) : null}
        </div>
        {isLoading ? <AppLoadingState /> : null}
        {error ? <AppErrorState message={error} /> : null}
        {!isLoading && !error && summary ? (
          <div className="stats-grid">
            <div className="stat">
              <div className="stat__label">Total spend (MTD)</div>
              <div className="stat__value">
                <MoneyValue amount={summary.total_amount} />
              </div>
            </div>
            <div className="stat">
              <div className="stat__label">Total spend (selected period)</div>
              <div className="stat__value">
                <MoneyValue amount={summary.total_amount} />
              </div>
            </div>
            <div className="stat">
              <div className="stat__label">Δ к прошлому периоду</div>
              <div className="stat__value">{summary.active_limits ? `${summary.active_limits}%` : "—"}</div>
            </div>
            <div className="stat">
              <div className="stat__label">Declines</div>
              <div className="stat__value">
                {declinedCount} · {topDeclineReason}
              </div>
            </div>
            <div className="stat">
              <div className="stat__label">High-risk operations</div>
              <div className="stat__value">{highRiskCount}</div>
            </div>
            <div className="stat">
              <div className="stat__label">Documents requiring action</div>
              <div className="stat__value">{docsAttention}</div>
            </div>
            <div className="stat">
              <div className="stat__label">Exports requiring attention</div>
              <div className="stat__value">{exportsAttention}</div>
            </div>
            <div className="stat">
              <div className="stat__label">Declined share</div>
              <div className="stat__value">{declinedShare}%</div>
            </div>
          </div>
        ) : null}
        {!isLoading && !error && !summary ? <AppEmptyState description="Нет данных для обзора." /> : null}
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
                  <span className="small">
                    <MoneyValue amount={value} />
                  </span>
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
          <h3>Top cards / vehicles</h3>
          {topCards.length ? (
            <ul className="bars">
              {topCards.map(([label, count]) => (
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
            <p className="muted">Нет данных по картам.</p>
          )}
        </div>
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
      </section>

      <section className="card">
        <h3>Explain readiness</h3>
        <p className="muted">
          Для каждой операции доступно Explain с причиной, действиями и SLA. Откройте любую операцию, чтобы
          увидеть детализацию.
        </p>
        <div className="actions">
          <Link className="ghost" to="/explain">
            Перейти к explain
          </Link>
          {canAccessFinance(user) ? (
            <Link className="ghost" to="/exports">
              Проверить выгрузки
            </Link>
          ) : null}
        </div>
      </section>

      <section className="card">
        <h3>Доступно вам</h3>
        <div className="actions">
          {canAccessOps(user) ? <span className="pill pill--success">Operations</span> : null}
          {canAccessFinance(user) ? <span className="pill pill--success">Finance/Docs/Exports</span> : null}
          <span className="pill pill--neutral">Read-only</span>
        </div>
      </section>
    </div>
  );
}
