import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchExportsSummary } from "../api/analytics";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { AnalyticsChartPanel } from "../components/analytics/AnalyticsChartPanel";
import { AnalyticsKpiCard } from "../components/analytics/AnalyticsKpiCard";
import { AnalyticsTabs } from "../components/analytics/AnalyticsTabs";
import { FilterBar, type DateFilters } from "../components/analytics/FilterBar";
import { AppEmptyState, AppErrorState, AppForbiddenState, AppLoadingState } from "../components/states";
import { useI18n } from "../i18n";
import type { AnalyticsExportsSummaryResponse } from "../types/analytics";
import { buildDateRange } from "../utils/dateRange";
import { formatDateTime } from "../utils/format";
import { canAccessFinance } from "../utils/roles";

interface AnalyticsErrorState {
  message: string;
  status?: number;
  correlationId?: string | null;
}

export function AnalyticsExportsPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [filters, setFilters] = useState<DateFilters>({ preset: "30d", from: "", to: "" });
  const [summary, setSummary] = useState<AnalyticsExportsSummaryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<AnalyticsErrorState | null>(null);
  const hasData = Boolean(summary && summary.total > 0);

  const financeAccess = canAccessFinance(user);

  useEffect(() => {
    if (filters.preset !== "custom") {
      const range = buildDateRange(filters.preset);
      setFilters((prev) => ({ ...prev, ...range }));
    }
  }, [filters.preset]);

  useEffect(() => {
    if (!user?.clientId || !filters.from || !filters.to || !financeAccess) return;
    setIsLoading(true);
    setError(null);
    fetchExportsSummary(user, { clientId: user.clientId, from: filters.from, to: filters.to })
      .then((resp) => setSummary(resp))
      .catch((err: unknown) => {
        if (err instanceof ApiError) {
          setError({ message: err.message, status: err.status, correlationId: err.correlationId });
          return;
        }
        setError({ message: err instanceof Error ? err.message : t("analytics.errors.loadFailed") });
      })
      .finally(() => setIsLoading(false));
  }, [user, filters.from, filters.to, financeAccess, t]);


  if (!user || !financeAccess) {
    return <AppForbiddenState message={t("analytics.forbiddenFinance")} />;
  }

  return (
    <div className="stack" aria-live="polite">
      <AnalyticsTabs />
      <section className="card">
        <div className="card__header">
          <div>
            <h2>{t("analytics.exports.title")}</h2>
            <p className="muted">{t("analytics.exports.subtitle")}</p>
          </div>
          <Link className="ghost" to="/exports">
            {t("analytics.exports.action")}
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
          <AnalyticsKpiCard label={t("analytics.exports.kpi.total")} value={summary.total} />
          <AnalyticsKpiCard label={t("analytics.exports.kpi.ok")} value={summary.ok} />
          <AnalyticsKpiCard label={t("analytics.exports.kpi.mismatch")} value={summary.mismatch} />
        </section>
      ) : null}

      {!isLoading && !error && summary ? (
        <AnalyticsChartPanel title={t("analytics.exports.recent")}> 
          {summary.items.length ? (
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t("analytics.exports.table.id")}</th>
                  <th>{t("analytics.exports.table.status")}</th>
                  <th>{t("analytics.exports.table.mapping")}</th>
                  <th>{t("analytics.exports.table.checksum")}</th>
                  <th>{t("analytics.exports.table.created")}</th>
                  <th>{t("analytics.exports.table.action")}</th>
                </tr>
              </thead>
              <tbody>
                {summary.items.map((item) => (
                  <tr key={item.id}>
                    <td>{item.id}</td>
                    <td>
                      <span className={item.status.toLowerCase().includes("ok") ? "badge success" : "badge pending"}>
                        {item.status}
                      </span>
                    </td>
                    <td>{item.mapping_version ?? t("common.notAvailable")}</td>
                    <td>{item.checksum ?? t("common.notAvailable")}</td>
                    <td>{formatDateTime(item.created_at)}</td>
                    <td>
                      <Link className="link-button" to={`/exports/${item.id}`}>
                        {t("analytics.exports.table.view")}
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="muted">{t("analytics.exports.empty")}</div>
          )}
        </AnalyticsChartPanel>
      ) : null}
    </div>
  );
}
