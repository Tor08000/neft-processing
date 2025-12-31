import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchDeclines } from "../api/analytics";
import { fetchExplainInsights } from "../api/explain";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { AnalyticsChartPanel } from "../components/analytics/AnalyticsChartPanel";
import { AnalyticsTabs } from "../components/analytics/AnalyticsTabs";
import { FilterBar, type DateFilters } from "../components/analytics/FilterBar";
import { AppEmptyState, AppErrorState, AppForbiddenState, AppLoadingState } from "../components/states";
import { useI18n } from "../i18n";
import type { AnalyticsDeclinesResponse } from "../types/analytics";
import type { ExplainInsightsResponse } from "../types/explain";
import { buildDateRange } from "../utils/dateRange";
import { formatMoney } from "../utils/format";
import { hasAnyRole } from "../utils/roles";

interface AnalyticsErrorState {
  message: string;
  status?: number;
  correlationId?: string | null;
}

export function AnalyticsDeclinesPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [filters, setFilters] = useState<DateFilters>({ preset: "30d", from: "", to: "" });
  const [declines, setDeclines] = useState<AnalyticsDeclinesResponse | null>(null);
  const [insights, setInsights] = useState<ExplainInsightsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<AnalyticsErrorState | null>(null);
  const hasData = Boolean(
    declines &&
      (declines.total > 0 ||
        declines.top_reasons.length ||
        declines.trend.length ||
        declines.expensive.length ||
        insights?.top_primary_reasons.length),
  );

  const canAccess = hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_ACCOUNTANT", "CLIENT_FLEET_MANAGER", "CLIENT_USER"]);

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
    Promise.all([
      fetchDeclines(user, { clientId: user.clientId, from: filters.from, to: filters.to }),
      fetchExplainInsights(user, { from: filters.from, to: filters.to }),
    ])
      .then(([declinesResponse, insightsResponse]) => {
        setDeclines(declinesResponse);
        setInsights(insightsResponse);
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError) {
          setError({ message: err.message, status: err.status, correlationId: err.correlationId });
          return;
        }
        setError({ message: err instanceof Error ? err.message : t("analytics.errors.loadFailed") });
      })
      .finally(() => setIsLoading(false));
  }, [user, filters.from, filters.to, t]);

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
      {error ? <AppErrorState message={error.message} status={error.status} correlationId={error.correlationId} /> : null}
      {!isLoading && !error && !hasData ? (
        <AppEmptyState title={t("analytics.empty.title")} description={t("analytics.empty.description")} />
      ) : null}

      {!isLoading && !error && declines ? (
        <section className="grid two">
          <AnalyticsChartPanel title={t("analytics.declines.topReasons")}> 
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
            ) : (
              <div className="muted">{t("analytics.declines.emptyReasons")}</div>
            )}
          </AnalyticsChartPanel>

          <AnalyticsChartPanel title={t("analytics.declines.trend")}> 
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
            ) : (
              <div className="muted">{t("analytics.declines.emptyTrend")}</div>
            )}
          </AnalyticsChartPanel>
        </section>
      ) : null}

      {!isLoading && !error && declines ? (
        <section className="grid two">
          <AnalyticsChartPanel title={t("analytics.declines.expensive")}> 
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
                      <td>{formatMoney(item.amount)}</td>
                      <td>
                        <Link className="link-button" to={`/operations?status=DECLINED`}>
                          {t("analytics.declines.table.view")}
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="muted">{t("analytics.declines.emptyExpensive")}</div>
            )}
          </AnalyticsChartPanel>

          <AnalyticsChartPanel title={t("analytics.declines.insights")}> 
            {insights?.top_primary_reasons?.length ? (
              <ul className="insights-list">
                {insights.top_primary_reasons.map((item) => (
                  <li key={item.reason}>
                    <strong>{item.reason}</strong>
                    <span className="muted">{t("analytics.declines.insightsCount", { count: item.count })}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="muted">{t("analytics.declines.emptyInsights")}</div>
            )}
          </AnalyticsChartPanel>
        </section>
      ) : null}

      {!isLoading && !error && declines?.heatmap?.length ? (
        <AnalyticsChartPanel title={t("analytics.declines.heatmap")}> 
          <table className="data-table">
            <thead>
              <tr>
                <th>{t("analytics.declines.table.reason")}</th>
                <th>{t("analytics.declines.table.station")}</th>
                <th>{t("analytics.declines.table.count")}</th>
              </tr>
            </thead>
            <tbody>
              {declines.heatmap.map((item, index) => (
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
