import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchOrdersSummary } from "../api/analytics";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { AnalyticsChartPanel } from "../components/analytics/AnalyticsChartPanel";
import { AnalyticsKpiCard } from "../components/analytics/AnalyticsKpiCard";
import { AnalyticsTabs } from "../components/analytics/AnalyticsTabs";
import { FilterBar, type DateFilters } from "../components/analytics/FilterBar";
import { AppEmptyState, AppErrorState, AppForbiddenState, AppLoadingState } from "../components/states";
import { useI18n } from "../i18n";
import type { AnalyticsOrdersSummaryResponse } from "../types/analytics";
import { buildDateRange } from "../utils/dateRange";
import { MoneyValue } from "../components/common/MoneyValue";
import { hasAnyRole } from "../utils/roles";

interface AnalyticsErrorState {
  message: string;
  status?: number;
  correlationId?: string | null;
}

export function AnalyticsMarketplacePage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [filters, setFilters] = useState<DateFilters>({ preset: "30d", from: "", to: "" });
  const [summary, setSummary] = useState<AnalyticsOrdersSummaryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<AnalyticsErrorState | null>(null);
  const hasData = Boolean(summary && summary.total > 0);

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
    fetchOrdersSummary(user, { clientId: user.clientId, from: filters.from, to: filters.to })
      .then((resp) => setSummary(resp))
      .catch((err: unknown) => {
        if (err instanceof ApiError) {
          setError({ message: err.message, status: err.status, correlationId: err.correlationId });
          return;
        }
        setError({ message: err instanceof Error ? err.message : t("analytics.errors.loadFailed") });
      })
      .finally(() => setIsLoading(false));
  }, [user, filters.from, filters.to, t]);

  const statusMax = useMemo(
    () => Math.max(...(summary?.status_breakdown ?? []).map((item) => item.count), 0),
    [summary],
  );
  const topServicesMax = useMemo(
    () => Math.max(...(summary?.top_services ?? []).map((item) => item.orders), 0),
    [summary],
  );

  if (!user || !canAccess) {
    return <AppForbiddenState message={t("analytics.forbidden")} />;
  }

  return (
    <div className="stack" aria-live="polite">
      <AnalyticsTabs />
      <section className="card">
        <div className="card__header">
          <div>
            <h2>{t("analytics.marketplace.title")}</h2>
            <p className="muted">{t("analytics.marketplace.subtitle")}</p>
          </div>
          <Link className="ghost" to="/marketplace/orders">
            {t("analytics.marketplace.action")}
          </Link>
        </div>
        <FilterBar filters={filters} onChange={setFilters} />
      </section>

      {isLoading ? <AppLoadingState label={t("analytics.loading")} /> : null}
      {error ? <AppErrorState message={error.message} status={error.status} correlationId={error.correlationId} /> : null}
      {!isLoading && !error && !hasData ? (
        <AppEmptyState title={t("analytics.empty.title")} description={t("analytics.empty.description")} />
      ) : null}

      {!isLoading && !error && summary ? (
        <section className="grid analytics-kpi-grid">
          <AnalyticsKpiCard label={t("analytics.marketplace.kpi.total")} value={summary.total} />
          <AnalyticsKpiCard label={t("analytics.marketplace.kpi.completed")} value={summary.completed} />
          <AnalyticsKpiCard label={t("analytics.marketplace.kpi.cancelled")} value={summary.cancelled} />
          <AnalyticsKpiCard
            label={t("analytics.marketplace.kpi.refundsRate")}
            value={`${summary.refunds_rate}%`}
            hint={t("analytics.marketplace.kpi.refundsCount", { count: summary.refunds_count })}
          />
          <AnalyticsKpiCard
            label={t("analytics.marketplace.kpi.avg")}
            value={<MoneyValue amount={summary.avg_order_value} />}
          />
        </section>
      ) : null}

      {!isLoading && !error && summary ? (
        <section className="grid two">
          <AnalyticsChartPanel
            title={t("analytics.marketplace.statusDistribution")}
            isEmpty={!summary.status_breakdown.length}
            emptyTitle={t("analytics.empty.title")}
            emptyDescription={t("analytics.marketplace.emptyStatus")}
          >
            {summary.status_breakdown.length ? (
              <ul className="bars">
                {summary.status_breakdown.map((item) => (
                  <li key={item.status}>
                    <span className="muted small">{item.status}</span>
                    <div className="bar">
                      <span
                        className="bar__fill"
                        style={{ width: `${statusMax ? Math.max(6, (item.count / statusMax) * 100) : 0}%` }}
                      />
                    </div>
                    <span className="small">{item.count}</span>
                  </li>
                ))}
              </ul>
            ) : null}
          </AnalyticsChartPanel>

          <AnalyticsChartPanel
            title={t("analytics.marketplace.topServices")}
            isEmpty={!summary.top_services.length}
            emptyTitle={t("analytics.empty.title")}
            emptyDescription={t("analytics.marketplace.emptyServices")}
          >
            {summary.top_services.length ? (
              <ul className="bars">
                {summary.top_services.map((item) => (
                  <li key={item.name}>
                    <span className="muted small">{item.name}</span>
                    <div className="bar">
                      <span
                        className="bar__fill"
                        style={{ width: `${topServicesMax ? Math.max(6, (item.orders / topServicesMax) * 100) : 0}%` }}
                      />
                    </div>
                    <span className="small">{item.orders}</span>
                  </li>
                ))}
              </ul>
            ) : null}
          </AnalyticsChartPanel>
        </section>
      ) : null}
    </div>
  );
}
