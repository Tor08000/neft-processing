import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchDeclines, fetchDailyMetrics, fetchDocumentsSummary, fetchExportsSummary } from "../api/analytics";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { AnalyticsChartPanel } from "../components/analytics/AnalyticsChartPanel";
import { AnalyticsKpiCard } from "../components/analytics/AnalyticsKpiCard";
import { AnalyticsTabs } from "../components/analytics/AnalyticsTabs";
import { AttentionList } from "../components/analytics/AttentionList";
import { FilterBar, type DateFilters } from "../components/analytics/FilterBar";
import { AppEmptyState, AppErrorState, AppForbiddenState, AppLoadingState } from "../components/states";
import { useI18n } from "../i18n";
import type {
  AnalyticsDeclinesResponse,
  AnalyticsDailyMetricsResponse,
  AnalyticsDocumentsSummaryResponse,
  AnalyticsExportsSummaryResponse,
} from "../types/analytics";
import { buildDateRange } from "../utils/dateRange";
import { MoneyValue } from "../components/common/MoneyValue";
import { canAccessFinance, hasAnyRole } from "../utils/roles";

interface AnalyticsErrorState {
  message: string;
  status?: number;
  correlationId?: string | null;
}

const extractMax = (series: Array<{ value: number }>) => Math.max(...series.map((item) => item.value), 0);

export function AnalyticsDashboardPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [filters, setFilters] = useState<DateFilters>({
    preset: "30d",
    from: "",
    to: "",
  });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<AnalyticsErrorState | null>(null);
  const [dailyMetrics, setDailyMetrics] = useState<AnalyticsDailyMetricsResponse | null>(null);
  const [declines, setDeclines] = useState<AnalyticsDeclinesResponse | null>(null);
  const [documentsSummary, setDocumentsSummary] = useState<AnalyticsDocumentsSummaryResponse | null>(null);
  const [exportsSummary, setExportsSummary] = useState<AnalyticsExportsSummaryResponse | null>(null);

  const canAccess = hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_ACCOUNTANT", "CLIENT_FLEET_MANAGER", "CLIENT_USER"]);
  const financeAccess = canAccessFinance(user);

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
    const requests: Array<Promise<unknown>> = [
      fetchDailyMetrics(user, {
        scopeType: "CLIENT",
        scopeId: user.clientId,
        from: filters.from,
        to: filters.to,
      }),
      fetchDeclines(user, { clientId: user.clientId, from: filters.from, to: filters.to }),
      fetchDocumentsSummary(user, { clientId: user.clientId, from: filters.from, to: filters.to }),
    ];
    if (financeAccess) {
      requests.push(fetchExportsSummary(user, { clientId: user.clientId, from: filters.from, to: filters.to }));
    }

    Promise.all(requests)
      .then((responses) => {
        const [metricsResponse, declinesResponse, documentsResponse, exportsResponse] = responses as [
          AnalyticsDailyMetricsResponse,
          AnalyticsDeclinesResponse,
          AnalyticsDocumentsSummaryResponse,
          AnalyticsExportsSummaryResponse | undefined,
        ];
        setDailyMetrics(metricsResponse);
        setDeclines(declinesResponse);
        setDocumentsSummary(documentsResponse);
        setExportsSummary(exportsResponse ?? null);
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError) {
          setError({ message: err.message, status: err.status, correlationId: err.correlationId });
          return;
        }
        setError({ message: err instanceof Error ? err.message : t("analytics.errors.loadFailed") });
      })
      .finally(() => setIsLoading(false));
  }, [user, filters.from, filters.to, financeAccess, t]);

  const spendMax = useMemo(() => extractMax(dailyMetrics?.spend.series ?? []), [dailyMetrics]);
  const ordersMax = useMemo(() => extractMax(dailyMetrics?.orders.series ?? []), [dailyMetrics]);
  const declinesMax = useMemo(() => {
    if (!declines?.top_reasons?.length) return 0;
    return Math.max(...declines.top_reasons.map((item) => item.count), 0);
  }, [declines]);
  const docsMax = useMemo(() => {
    if (!documentsSummary) return 0;
    return Math.max(documentsSummary.issued, documentsSummary.signed, documentsSummary.edo_pending, documentsSummary.edo_failed);
  }, [documentsSummary]);

  const hasContent = Boolean(dailyMetrics || declines || documentsSummary || exportsSummary);

  if (!user || !canAccess) {
    return <AppForbiddenState message={t("analytics.forbidden") } />;
  }

  return (
    <div className="stack" aria-live="polite">
      <AnalyticsTabs />
      <section className="card">
        <div className="card__header">
          <div>
            <h2>{t("analytics.dashboard.title")}</h2>
            <p className="muted">{t("analytics.dashboard.subtitle")}</p>
          </div>
        </div>
        <FilterBar filters={filters} onChange={setFilters} />
      </section>

      {isLoading ? <AppLoadingState label={t("analytics.loading") } /> : null}
      {error ? (
        <AppErrorState message={error.message} status={error.status} correlationId={error.correlationId} />
      ) : null}
      {!isLoading && !error && !hasContent ? (
        <AppEmptyState
          title={t("analytics.empty.title")}
          description={t("analytics.empty.description")}
        />
      ) : null}

      {!isLoading && !error && dailyMetrics ? (
        <section className="grid analytics-kpi-grid">
          <AnalyticsKpiCard
            label={t("analytics.dashboard.kpi.spendTotal")}
            value={<MoneyValue amount={dailyMetrics.spend.total} currency={dailyMetrics.currency ?? "RUB"} />}
            hint={t("analytics.dashboard.kpi.spendHint", { from: dailyMetrics.from, to: dailyMetrics.to })}
          />
          <AnalyticsKpiCard
            label={t("analytics.dashboard.kpi.ordersTotal")}
            value={`${dailyMetrics.orders.total} · ${dailyMetrics.orders.completed}`}
            hint={t("analytics.dashboard.kpi.ordersHint")}
          />
          <AnalyticsKpiCard
            label={t("analytics.dashboard.kpi.refunds")}
            value={dailyMetrics.orders.refunds}
          />
          <AnalyticsKpiCard
            label={t("analytics.dashboard.kpi.declines")}
            value={`${dailyMetrics.declines.total} · ${dailyMetrics.declines.top_reason ?? t("common.notAvailable")}`}
          />
          <AnalyticsKpiCard
            label={t("analytics.dashboard.kpi.documents")}
            value={dailyMetrics.documents.attention}
          />
          {financeAccess ? (
            <AnalyticsKpiCard
              label={t("analytics.dashboard.kpi.exports")}
              value={dailyMetrics.exports.attention}
            />
          ) : null}
        </section>
      ) : null}

      {!isLoading && !error && dailyMetrics ? (
        <section className="grid two">
          <AnalyticsChartPanel
            title={t("analytics.dashboard.charts.spend.title")}
            subtitle={t("analytics.dashboard.charts.spend.subtitle")}
            isEmpty={!dailyMetrics.spend.series.length}
            emptyTitle={t("analytics.empty.title")}
            emptyDescription={t("analytics.dashboard.charts.spend.empty")}
            action={
              <Link className="ghost" to="/analytics/spend">
                {t("analytics.dashboard.charts.spend.action")}
              </Link>
            }
          >
            {dailyMetrics.spend.series.length ? (
              <div className="chart">
                {dailyMetrics.spend.series.map((point) => (
                  <div className="chart-row" key={`spend-${point.date}`}>
                    <span className="muted small">{point.date}</span>
                    <div className="chart-bar">
                      <span
                        className="chart-bar__fill"
                        style={{ width: `${spendMax ? Math.max(4, (point.value / spendMax) * 100) : 0}%` }}
                      />
                    </div>
                    <span className="small">
                      <MoneyValue amount={point.value} currency={dailyMetrics.currency ?? "RUB"} />
                    </span>
                  </div>
                ))}
              </div>
            ) : null}
          </AnalyticsChartPanel>

          <AnalyticsChartPanel
            title={t("analytics.dashboard.charts.orders.title")}
            subtitle={t("analytics.dashboard.charts.orders.subtitle")}
            isEmpty={!dailyMetrics.orders.series.length}
            emptyTitle={t("analytics.empty.title")}
            emptyDescription={t("analytics.dashboard.charts.orders.empty")}
            action={
              <Link className="ghost" to="/analytics/marketplace">
                {t("analytics.dashboard.charts.orders.action")}
              </Link>
            }
          >
            {dailyMetrics.orders.series.length ? (
              <div className="chart">
                {dailyMetrics.orders.series.map((point) => (
                  <div className="chart-row" key={`orders-${point.date}`}>
                    <span className="muted small">{point.date}</span>
                    <div className="chart-bar">
                      <span
                        className="chart-bar__fill"
                        style={{ width: `${ordersMax ? Math.max(4, (point.value / ordersMax) * 100) : 0}%` }}
                      />
                    </div>
                    <span className="small">{point.value}</span>
                  </div>
                ))}
              </div>
            ) : null}
          </AnalyticsChartPanel>
        </section>
      ) : null}

      {!isLoading && !error ? (
        <section className="grid two">
          <AnalyticsChartPanel
            title={t("analytics.dashboard.charts.declines.title")}
            subtitle={t("analytics.dashboard.charts.declines.subtitle")}
            isEmpty={!declines?.top_reasons?.length}
            emptyTitle={t("analytics.empty.title")}
            emptyDescription={t("analytics.dashboard.charts.declines.empty")}
            action={
              <Link className="ghost" to="/analytics/declines">
                {t("analytics.dashboard.charts.declines.action")}
              </Link>
            }
          >
            {declines?.top_reasons?.length ? (
              <ul className="bars">
                {declines.top_reasons.map((item) => (
                  <li key={item.reason}>
                    <span className="muted small">{item.reason}</span>
                    <div className="bar">
                      <span
                        className="bar__fill"
                        style={{ width: `${declinesMax ? Math.max(6, (item.count / declinesMax) * 100) : 0}%` }}
                      />
                    </div>
                    <span className="small">{item.count}</span>
                  </li>
                ))}
              </ul>
            ) : null}
          </AnalyticsChartPanel>

          <AnalyticsChartPanel
            title={t("analytics.dashboard.charts.documents.title")}
            subtitle={t("analytics.dashboard.charts.documents.subtitle")}
            isEmpty={!documentsSummary || docsMax === 0}
            emptyTitle={t("analytics.empty.title")}
            emptyDescription={t("analytics.dashboard.charts.documents.empty")}
            action={
              <Link className="ghost" to="/analytics/documents">
                {t("analytics.dashboard.charts.documents.action")}
              </Link>
            }
          >
            {documentsSummary ? (
              <ul className="bars">
                {[
                  { label: t("analytics.documents.status.issued"), value: documentsSummary.issued },
                  { label: t("analytics.documents.status.signed"), value: documentsSummary.signed },
                  { label: t("analytics.documents.status.edoPending"), value: documentsSummary.edo_pending },
                  { label: t("analytics.documents.status.edoFailed"), value: documentsSummary.edo_failed },
                ].map((item) => (
                  <li key={item.label}>
                    <span className="muted small">{item.label}</span>
                    <div className="bar">
                      <span
                        className="bar__fill"
                        style={{ width: `${docsMax ? Math.max(6, (item.value / docsMax) * 100) : 0}%` }}
                      />
                    </div>
                    <span className="small">{item.value}</span>
                  </li>
                ))}
              </ul>
            ) : null}
          </AnalyticsChartPanel>
        </section>
      ) : null}

      {!isLoading && !error && dailyMetrics ? (
        <AnalyticsChartPanel
          title={t("analytics.attention.title")}
          subtitle={t("analytics.attention.subtitle")}
          isEmpty={!dailyMetrics.attention?.length}
          emptyTitle={t("analytics.empty.title")}
          emptyDescription={t("analytics.attention.empty")}
        >
          <AttentionList items={dailyMetrics.attention ?? []} />
        </AnalyticsChartPanel>
      ) : null}

      {!isLoading && !error && financeAccess && exportsSummary ? (
        <AnalyticsChartPanel
          title={t("analytics.dashboard.exports.title")}
          subtitle={t("analytics.dashboard.exports.subtitle")}
          isEmpty={!exportsSummary}
          emptyTitle={t("analytics.empty.title")}
          emptyDescription={t("analytics.empty.description")}
          action={
            <Link className="ghost" to="/analytics/exports">
              {t("analytics.dashboard.exports.action")}
            </Link>
          }
        >
          <div className="analytics-summary-grid">
            <div>
              <div className="muted small">{t("analytics.exports.kpi.total")}</div>
              <div className="analytics-summary__value">{exportsSummary.total}</div>
            </div>
            <div>
              <div className="muted small">{t("analytics.exports.kpi.ok")}</div>
              <div className="analytics-summary__value">{exportsSummary.ok}</div>
            </div>
            <div>
              <div className="muted small">{t("analytics.exports.kpi.mismatch")}</div>
              <div className="analytics-summary__value">{exportsSummary.mismatch}</div>
            </div>
          </div>
        </AnalyticsChartPanel>
      ) : null}
    </div>
  );
}
