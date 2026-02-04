import { useEffect, useMemo, useState } from "react";
import { createAnalyticsExport, fetchSpendSummary } from "../api/analytics";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { AnalyticsChartPanel } from "../components/analytics/AnalyticsChartPanel";
import { AnalyticsKpiCard } from "../components/analytics/AnalyticsKpiCard";
import { AnalyticsTabs } from "../components/analytics/AnalyticsTabs";
import { FilterBar, type DateFilters } from "../components/analytics/FilterBar";
import { AppEmptyState, AppErrorState, AppForbiddenState, AppLoadingState } from "../components/states";
import { useI18n } from "../i18n";
import type { AnalyticsSpendSummaryResponse } from "../types/analytics";
import { buildDateRange } from "../utils/dateRange";
import { MoneyValue } from "../components/common/MoneyValue";
import { hasAnyRole } from "../utils/roles";

interface AnalyticsErrorState {
  message: string;
  status?: number;
  correlationId?: string | null;
}

export function AnalyticsSpendPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [filters, setFilters] = useState<DateFilters>({ preset: "30d", from: "", to: "" });
  const [summary, setSummary] = useState<AnalyticsSpendSummaryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<AnalyticsErrorState | null>(null);
  const [exportStatus, setExportStatus] = useState<string | null>(null);
  const hasData = (summary?.total_spend ?? 0) > 0;

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
    fetchSpendSummary(user, { clientId: user.clientId, from: filters.from, to: filters.to })
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

  const trendMax = useMemo(() => Math.max(...(summary?.trend ?? []).map((point) => point.value), 0), [summary]);
  const topStationsMax = useMemo(
    () => Math.max(...(summary?.top_stations ?? []).map((item) => item.amount), 0),
    [summary],
  );
  const topMerchantsMax = useMemo(
    () => Math.max(...(summary?.top_merchants ?? []).map((item) => item.amount), 0),
    [summary],
  );
  const topCardsMax = useMemo(
    () => Math.max(...(summary?.top_cards ?? []).map((item) => item.amount), 0),
    [summary],
  );
  const topDriversMax = useMemo(
    () => Math.max(...(summary?.top_drivers ?? []).map((item) => item.amount), 0),
    [summary],
  );
  const productMax = useMemo(
    () => Math.max(...(summary?.product_breakdown ?? []).map((item) => item.amount), 0),
    [summary],
  );

  const handleExport = () => {
    if (!user || !summary?.export_available || !summary.export_dataset) return;
    setExportStatus(t("analytics.exports.exporting"));
    createAnalyticsExport(user, { dataset: summary.export_dataset, from: filters.from, to: filters.to })
      .then((resp) => {
        if (resp.download_url) {
          window.open(resp.download_url, "_blank", "noopener");
        }
        setExportStatus(t("analytics.exports.exportQueued"));
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError) {
          setExportStatus(`${t("analytics.errors.exportFailed")} (${err.status})`);
          return;
        }
        setExportStatus(t("analytics.errors.exportFailed"));
      });
  };

  if (!user || !canAccess) {
    return <AppForbiddenState message={t("analytics.forbidden")} />;
  }

  return (
    <div className="stack" aria-live="polite">
      <AnalyticsTabs />
      <section className="card">
        <div className="card__header">
          <div>
            <h2>{t("analytics.spend.title")}</h2>
            <p className="muted">{t("analytics.spend.subtitle")}</p>
          </div>
        </div>
        <FilterBar filters={filters} onChange={setFilters} />
      </section>

      {isLoading ? <AppLoadingState label={t("analytics.loading")} /> : null}
      {error ? <AppErrorState message={error.message} status={error.status} correlationId={error.correlationId} /> : null}
      {!isLoading && !error && !hasData ? (
        <AppEmptyState title={t("analytics.empty.title")} description={t("analytics.empty.description")} />
      ) : null}

      {!isLoading && !error && hasData && summary ? (
        <section className="grid analytics-kpi-grid">
          <AnalyticsKpiCard
            label={t("analytics.spend.kpi.total")}
            value={<MoneyValue amount={summary.total_spend} currency={summary.currency ?? "RUB"} />}
            hint={t("analytics.spend.kpi.period", { from: filters.from, to: filters.to })}
          />
          <AnalyticsKpiCard
            label={t("analytics.spend.kpi.avg")}
            value={<MoneyValue amount={summary.avg_daily_spend ?? 0} currency={summary.currency ?? "RUB"} />}
          />
        </section>
      ) : null}

      {!isLoading && !error && hasData && summary ? (
        <AnalyticsChartPanel
          title={t("analytics.spend.trend.title")}
          subtitle={t("analytics.spend.trend.subtitle")}
          isEmpty={!summary.trend.length}
          emptyTitle={t("analytics.empty.title")}
          emptyDescription={t("analytics.spend.trend.empty")}
          action={
            <button
              type="button"
              className="secondary"
              onClick={handleExport}
              disabled={!summary.export_available}
            >
              {summary.export_available ? t("analytics.spend.export") : t("analytics.spend.exportDisabled")}
            </button>
          }
        >
          {summary.trend.length ? (
            <div className="chart">
              {summary.trend.map((point) => (
                <div className="chart-row" key={`spend-${point.date}`}>
                  <span className="muted small">{point.date}</span>
                  <div className="chart-bar">
                    <span
                      className="chart-bar__fill"
                      style={{ width: `${trendMax ? Math.max(4, (point.value / trendMax) * 100) : 0}%` }}
                    />
                  </div>
                  <span className="small">
                    <MoneyValue amount={point.value} currency={summary.currency ?? "RUB"} />
                  </span>
                </div>
              ))}
            </div>
          ) : null}
          {exportStatus ? <div className="muted small analytics-export-status">{exportStatus}</div> : null}
        </AnalyticsChartPanel>
      ) : null}

      {!isLoading && !error && hasData && summary ? (
        <section className="grid two">
          <AnalyticsChartPanel
            title={t("analytics.spend.topStations")}
            isEmpty={!summary.top_stations.length}
            emptyTitle={t("analytics.empty.title")}
            emptyDescription={t("analytics.spend.emptyStations")}
          >
            {summary.top_stations.length ? (
              <ul className="bars">
                {summary.top_stations.map((item) => (
                  <li key={item.name}>
                    <span className="muted small">{item.name}</span>
                    <div className="bar">
                      <span
                        className="bar__fill"
                        style={{ width: `${topStationsMax ? Math.max(6, (item.amount / topStationsMax) * 100) : 0}%` }}
                      />
                    </div>
                    <span className="small">
                      <MoneyValue amount={item.amount} currency={summary.currency ?? "RUB"} />
                    </span>
                  </li>
                ))}
              </ul>
            ) : null}
          </AnalyticsChartPanel>

          <AnalyticsChartPanel
            title={t("analytics.spend.topMerchants")}
            isEmpty={!summary.top_merchants.length}
            emptyTitle={t("analytics.empty.title")}
            emptyDescription={t("analytics.spend.emptyMerchants")}
          >
            {summary.top_merchants.length ? (
              <ul className="bars">
                {summary.top_merchants.map((item) => (
                  <li key={item.name}>
                    <span className="muted small">{item.name}</span>
                    <div className="bar">
                      <span
                        className="bar__fill"
                        style={{ width: `${topMerchantsMax ? Math.max(6, (item.amount / topMerchantsMax) * 100) : 0}%` }}
                      />
                    </div>
                    <span className="small">
                      <MoneyValue amount={item.amount} currency={summary.currency ?? "RUB"} />
                    </span>
                  </li>
                ))}
              </ul>
            ) : null}
          </AnalyticsChartPanel>
        </section>
      ) : null}

      {!isLoading && !error && hasData && summary ? (
        <section className="grid two">
          <AnalyticsChartPanel
            title={t("analytics.spend.topCards")}
            isEmpty={!summary.top_cards.length}
            emptyTitle={t("analytics.empty.title")}
            emptyDescription={t("analytics.spend.emptyCards")}
          >
            {summary.top_cards.length ? (
              <ul className="bars">
                {summary.top_cards.map((item) => (
                  <li key={item.name}>
                    <span className="muted small">{item.name}</span>
                    <div className="bar">
                      <span
                        className="bar__fill"
                        style={{ width: `${topCardsMax ? Math.max(6, (item.amount / topCardsMax) * 100) : 0}%` }}
                      />
                    </div>
                    <span className="small">
                      <MoneyValue amount={item.amount} currency={summary.currency ?? "RUB"} />
                    </span>
                  </li>
                ))}
              </ul>
            ) : null}
          </AnalyticsChartPanel>

          <AnalyticsChartPanel
            title={t("analytics.spend.topDrivers")}
            isEmpty={!summary.top_drivers.length}
            emptyTitle={t("analytics.empty.title")}
            emptyDescription={t("analytics.spend.emptyDrivers")}
          >
            {summary.top_drivers.length ? (
              <ul className="bars">
                {summary.top_drivers.map((item) => (
                  <li key={item.name}>
                    <span className="muted small">{item.name}</span>
                    <div className="bar">
                      <span
                        className="bar__fill"
                        style={{ width: `${topDriversMax ? Math.max(6, (item.amount / topDriversMax) * 100) : 0}%` }}
                      />
                    </div>
                    <span className="small">
                      <MoneyValue amount={item.amount} currency={summary.currency ?? "RUB"} />
                    </span>
                  </li>
                ))}
              </ul>
            ) : null}
          </AnalyticsChartPanel>
        </section>
      ) : null}

      {!isLoading && !error && hasData && summary ? (
        <AnalyticsChartPanel
          title={t("analytics.spend.productBreakdown")}
          isEmpty={!summary.product_breakdown.length}
          emptyTitle={t("analytics.empty.title")}
          emptyDescription={t("analytics.spend.emptyProducts")}
        >
          {summary.product_breakdown.length ? (
            <ul className="bars">
              {summary.product_breakdown.map((item) => (
                <li key={item.product}>
                  <span className="muted small">{item.product}</span>
                  <div className="bar">
                    <span
                      className="bar__fill"
                      style={{ width: `${productMax ? Math.max(6, (item.amount / productMax) * 100) : 0}%` }}
                    />
                  </div>
                  <span className="small">
                    <MoneyValue amount={item.amount} currency={summary.currency ?? "RUB"} />
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
        </AnalyticsChartPanel>
      ) : null}
    </div>
  );
}
