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
import { Toast } from "../components/Toast/Toast";
import { useToast } from "../components/Toast/useToast";
import { AchievementBadge } from "../features/achievements/components/AchievementBadge";
import { StreakWidget } from "../features/achievements/components/StreakWidget";
import { useAchievements } from "../features/achievements/useAchievements";
import { KpiCard } from "../features/kpi/components/KpiCard";
import { KpiHintList } from "../features/kpi/components/KpiHintList";
import { useKpis } from "../features/kpi/useKpis";
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
  const { toast, showToast } = useToast();
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

  const trendMax = Math.max(...(summary?.spending_trend ?? [0]));
  const {
    kpis,
    hints,
    error: kpiError,
    isLoading: kpiLoading,
    reload: reloadKpis,
  } = useKpis({ summary, operations, docsAttention, exportsAttention, showToast });
  const { problemKpis, healthyKpis } = useMemo(() => {
    const isProblem = (kpi: (typeof kpis)[number]) =>
      kpi.status === "bad" || (kpi.deltaValue !== undefined && kpi.deltaValue < 0);
    return {
      problemKpis: kpis.filter(isProblem),
      healthyKpis: kpis.filter((kpi) => !isProblem(kpi)),
    };
  }, [kpis]);
  const {
    badges,
    streak,
    error: achievementsError,
    isLoading: achievementsLoading,
    reload: reloadAchievements,
  } = useAchievements({ showToast });

  if (!user) {
    return null;
  }

  return (
    <div className="stack" aria-live="polite">
      <Toast toast={toast} />
      <section className="card">
        <div className="card__header">
          <div>
            <h2>Что сейчас не так</h2>
            <p className="muted">Сигналы, которые требуют реакции и Explain.</p>
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
          kpiError ? (
            <AppErrorState message={kpiError} onRetry={reloadKpis} />
          ) : kpiLoading ? (
            <AppLoadingState label="Загрузка KPI..." />
          ) : (
            <div className="kpi-grid">
              {problemKpis.length ? (
                problemKpis.map((kpi) => <KpiCard key={kpi.id} {...kpi} />)
              ) : (
                <AppEmptyState description="Пока нет тревожных сигналов. Мы сообщим, если появятся." />
              )}
            </div>
          )
        ) : null}
        {!isLoading && !error && !summary ? <AppEmptyState description="Нет данных для обзора." /> : null}
      </section>

      <section className="card">
        <div className="card__header">
          <div>
            <h3>Что под контролем</h3>
            <p className="muted">Показатели, которые идут в плановом режиме.</p>
          </div>
        </div>
        {kpiError ? (
          <AppErrorState message={kpiError} onRetry={reloadKpis} />
        ) : kpiLoading ? (
          <AppLoadingState label="Загрузка KPI..." />
        ) : healthyKpis.length ? (
          <div className="kpi-grid">
            {healthyKpis.map((kpi) => (
              <KpiCard key={kpi.id} {...kpi} />
            ))}
          </div>
        ) : (
          <AppEmptyState description="Пока нет стабильных KPI в выбранном периоде." />
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
        <h3>Прогресс и дисциплина</h3>
        {kpiError ? null : <KpiHintList hints={hints} />}
      </section>

      <section className="card">
        <h3>Достижения и серия</h3>
        {achievementsError ? (
          <AppErrorState message={achievementsError} onRetry={reloadAchievements} />
        ) : achievementsLoading ? (
          <AppLoadingState label="Загрузка достижений..." />
        ) : (
          <>
            <div className="achievement-grid">
              {badges.map((badge) => (
                <AchievementBadge key={badge.id} {...badge} />
              ))}
            </div>
            <div className="achievement-streak">
              <StreakWidget {...streak} />
            </div>
          </>
        )}
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
