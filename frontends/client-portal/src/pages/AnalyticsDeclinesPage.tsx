import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchDeclines } from "../api/analytics";
import { fetchExplainInsights } from "../api/explain";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { AnalyticsChartPanel } from "../components/analytics/AnalyticsChartPanel";
import { AnalyticsTabs } from "../components/analytics/AnalyticsTabs";
import { FilterBar, type DateFilters } from "../components/analytics/FilterBar";
import { AppEmptyState, AppForbiddenState, AppLoadingState } from "../components/states";
import { ClientErrorState } from "../components/ClientErrorState";
import { DemoEmptyState } from "../components/DemoEmptyState";
import { useI18n } from "../i18n";
import type { AnalyticsDeclinesResponse } from "../types/analytics";
import type { ExplainInsightsResponse } from "../types/explain";
import { buildDateRange } from "../utils/dateRange";
import { MoneyValue } from "../components/common/MoneyValue";
import { hasAnyRole } from "../utils/roles";
import { isDemoClient } from "@shared/demo/demo";

interface AnalyticsErrorState {
  status?: number;
}

export function AnalyticsDeclinesPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [filters, setFilters] = useState<DateFilters>({ preset: "30d", from: "", to: "" });
  const [declines, setDeclines] = useState<AnalyticsDeclinesResponse | null>(null);
  const [insights, setInsights] = useState<ExplainInsightsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<AnalyticsErrorState | null>(null);
  const [demoFallback, setDemoFallback] = useState(false);
  const hasData = (declines?.total ?? 0) > 0;

  const canAccess = hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_ACCOUNTANT", "CLIENT_FLEET_MANAGER", "CLIENT_USER"]);
  const isDemoClientAccount = isDemoClient(user?.email ?? null);

  useEffect(() => {
    if (filters.preset !== "custom") {
      const range = buildDateRange(filters.preset);
      setFilters((prev) => ({ ...prev, ...range }));
    }
  }, [filters.preset]);

  useEffect(() => {
    if (!user?.clientId || !filters.from || !filters.to) return;
    setIsLoading(true);
    setError(null);
    setDemoFallback(false);
    Promise.all([
      fetchDeclines(user, { clientId: user.clientId, from: filters.from, to: filters.to }),
      fetchExplainInsights(user, { from: filters.from, to: filters.to }),
    ])
      .then(([declinesResponse, insightsResponse]) => {
        setDeclines(declinesResponse);
        setInsights(insightsResponse);
      })
      .catch((err: unknown) => {
        const status = err instanceof ApiError ? err.status : undefined;
        if (isDemoClientAccount && status === 404) {
          setDemoFallback(true);
          setError(null);
          return;
        }
        if (err instanceof ApiError) {
          setError({ status: err.status });
          return;
        }
        setError({ status });
      })
      .finally(() => setIsLoading(false));
  }, [user, filters.from, filters.to, t, isDemoClientAccount]);

  const reasonsMax = useMemo(() => Math.max(...(declines?.top_reasons ?? []).map((item) => item.count), 0), [declines]);
  const trendMax = useMemo(() => Math.max(...(declines?.trend ?? []).map((item) => item.count), 0), [declines]);

  if (!user || !canAccess) {
    return <AppForbiddenState message={t("analytics.forbidden")} />;
  }

  return (
    <div className="stack" aria-live="polite">
      <AnalyticsTabs />
      <section className="card">
        <div className="card__header">
          <div>
            <h2>{t("analytics.declines.title")}</h2>
            <p className="muted">{t("analytics.declines.subtitle")}</p>
          </div>
          <Link className="ghost" to="/operations?status=DECLINED">
            {t("analytics.declines.action")}
          </Link>
        </div>
        <FilterBar filters={filters} onChange={setFilters} />
      </section>

      {isLoading ? <AppLoadingState label={t("analytics.loading")} /> : null}
      {error ? (
        <ClientErrorState
          title="Отказы недоступны"
          description="Не удалось получить данные. Попробуйте обновить страницу."
          onRetry={() => setFilters((prev) => ({ ...prev }))}
        />
      ) : null}
      {demoFallback ? (
        <DemoEmptyState
          title="Данные в демо появятся позже"
          description="В рабочем контуре здесь будет аналитика отказов."
          action={
            <Link className="ghost neft-btn-secondary" to="/dashboard">
              Перейти в обзор
            </Link>
          }
        />
      ) : null}
      {!isLoading && !error && !hasData && !demoFallback ? (
        isDemoClientAccount ? (
          <DemoEmptyState
            title="Данные в демо появятся позже"
            description="В рабочем контуре здесь будет аналитика отказов."
            action={
              <Link className="ghost neft-btn-secondary" to="/dashboard">
                Перейти в обзор
              </Link>
            }
          />
        ) : (
          <AppEmptyState title={t("analytics.empty.title")} description={t("analytics.empty.description")} />
        )
      ) : null}

      {!isLoading && !error && hasData && declines ? (
        <section className="grid two">
          <AnalyticsChartPanel
            title={t("analytics.declines.topReasons")}
            isEmpty={!declines.top_reasons.length}
            emptyTitle={t("analytics.empty.title")}
            emptyDescription={t("analytics.declines.emptyReasons")}
          >
            {declines.top_reasons.length ? (
              <ul className="bars">
                {declines.top_reasons.map((item) => (
                  <li key={item.reason}>
                    <span className="muted small">{item.reason}</span>
                    <div className="bar">
                      <span
                        className="bar__fill"
                        style={{ width: `${reasonsMax ? Math.max(6, (item.count / reasonsMax) * 100) : 0}%` }}
                      />
                    </div>
                    <span className="small">{item.count}</span>
                  </li>
                ))}
              </ul>
            ) : null}
          </AnalyticsChartPanel>

          <AnalyticsChartPanel
            title={t("analytics.declines.trend")}
            isEmpty={!declines.trend.length}
            emptyTitle={t("analytics.empty.title")}
            emptyDescription={t("analytics.declines.emptyTrend")}
          >
            {declines.trend.length ? (
              <div className="chart">
                {declines.trend.map((item) => (
                  <div className="chart-row" key={`${item.date}-${item.reason}`}>
                    <span className="muted small">{item.date}</span>
                    <div className="chart-bar">
                      <span
                        className="chart-bar__fill"
                        style={{ width: `${trendMax ? Math.max(4, (item.count / trendMax) * 100) : 0}%` }}
                      />
                    </div>
                    <span className="small">{item.count}</span>
                  </div>
                ))}
              </div>
            ) : null}
          </AnalyticsChartPanel>
        </section>
      ) : null}

      {!isLoading && !error && hasData && declines ? (
        <section className="grid two">
          <AnalyticsChartPanel
            title={t("analytics.declines.expensive")}
            isEmpty={!declines.expensive.length}
            emptyTitle={t("analytics.empty.title")}
            emptyDescription={t("analytics.declines.emptyExpensive")}
          >
            {declines.expensive.length ? (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>{t("analytics.declines.table.reason")}</th>
                    <th>{t("analytics.declines.table.station")}</th>
                    <th>{t("analytics.declines.table.amount")}</th>
                    <th>{t("analytics.declines.table.action")}</th>
                  </tr>
                </thead>
                <tbody>
                  {declines.expensive.map((item) => (
                    <tr key={item.id}>
                      <td>{item.reason}</td>
                      <td>{item.station ?? t("common.notAvailable")}</td>
                      <td className="neft-num-cell">
                        <MoneyValue amount={item.amount} />
                      </td>
                      <td>
                        <Link className="link-button" to={`/operations?status=DECLINED`}>
                          {t("analytics.declines.table.view")}
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : null}
          </AnalyticsChartPanel>

          <AnalyticsChartPanel
            title={t("analytics.declines.insights")}
            isEmpty={!insights?.top_primary_reasons?.length}
            emptyTitle={t("analytics.empty.title")}
            emptyDescription={t("analytics.declines.emptyInsights")}
          >
            {insights?.top_primary_reasons?.length ? (
              <ul className="insights-list">
                {insights.top_primary_reasons.map((item) => (
                  <li key={item.reason}>
                    <strong>{item.reason}</strong>
                    <span className="muted">{t("analytics.declines.insightsCount", { count: item.count })}</span>
                  </li>
                ))}
              </ul>
            ) : null}
          </AnalyticsChartPanel>
        </section>
      ) : null}

      {!isLoading && !error && hasData && declines ? (
        <AnalyticsChartPanel
          title={t("analytics.declines.heatmap")}
          isEmpty={!declines.heatmap?.length}
          emptyTitle={t("analytics.empty.title")}
          emptyDescription={t("analytics.empty.description")}
        >
          <table className="data-table">
            <thead>
              <tr>
                <th>{t("analytics.declines.table.reason")}</th>
                <th>{t("analytics.declines.table.station")}</th>
                <th>{t("analytics.declines.table.count")}</th>
              </tr>
            </thead>
            <tbody>
              {declines.heatmap?.map((item, index) => (
                <tr key={`${item.reason}-${item.station}-${index}`}>
                  <td>{item.reason}</td>
                  <td>{item.station}</td>
                  <td>{item.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </AnalyticsChartPanel>
      ) : null}
    </div>
  );
}
