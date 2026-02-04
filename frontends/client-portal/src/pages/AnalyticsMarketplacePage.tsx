import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchOrdersSummary } from "../api/analytics";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { AnalyticsChartPanel } from "../components/analytics/AnalyticsChartPanel";
import { AnalyticsKpiCard } from "../components/analytics/AnalyticsKpiCard";
import { AnalyticsTabs } from "../components/analytics/AnalyticsTabs";
import { FilterBar, type DateFilters } from "../components/analytics/FilterBar";
import { AppEmptyState, AppForbiddenState, AppLoadingState } from "../components/states";
import { ClientErrorState } from "../components/ClientErrorState";
import { DemoEmptyState } from "../components/DemoEmptyState";
import { useI18n } from "../i18n";
import type { AnalyticsOrdersSummaryResponse } from "../types/analytics";
import { buildDateRange } from "../utils/dateRange";
import { MoneyValue } from "../components/common/MoneyValue";
import { hasAnyRole } from "../utils/roles";
import { isDemoClient } from "@shared/demo/demo";

interface AnalyticsErrorState {
  status?: number;
}

export function AnalyticsMarketplacePage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [filters, setFilters] = useState<DateFilters>({ preset: "30d", from: "", to: "" });
  const [summary, setSummary] = useState<AnalyticsOrdersSummaryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<AnalyticsErrorState | null>(null);
  const [demoFallback, setDemoFallback] = useState(false);
  const hasData = Boolean(summary && summary.total > 0);

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
    fetchOrdersSummary(user, { clientId: user.clientId, from: filters.from, to: filters.to })
      .then((resp) => setSummary(resp))
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
      {error ? (
        <ClientErrorState
          title="Маркетплейс недоступен"
          description="Не удалось получить данные. Попробуйте обновить страницу."
          onRetry={() => setFilters((prev) => ({ ...prev }))}
        />
      ) : null}
      {demoFallback ? (
        <DemoEmptyState
          title="Данные в демо появятся позже"
          description="В рабочем контуре здесь будет аналитика маркетплейса."
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
            description="В рабочем контуре здесь будет аналитика маркетплейса."
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
