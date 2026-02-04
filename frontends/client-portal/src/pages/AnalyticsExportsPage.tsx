import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchExportsSummary } from "../api/analytics";
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
import type { AnalyticsExportsSummaryResponse } from "../types/analytics";
import { buildDateRange } from "../utils/dateRange";
import { formatDateTime } from "../utils/format";
import { canAccessFinance } from "../utils/roles";
import { isDemoClient } from "@shared/demo/demo";

interface AnalyticsErrorState {
  status?: number;
}

export function AnalyticsExportsPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [filters, setFilters] = useState<DateFilters>({ preset: "30d", from: "", to: "" });
  const [summary, setSummary] = useState<AnalyticsExportsSummaryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<AnalyticsErrorState | null>(null);
  const [demoFallback, setDemoFallback] = useState(false);
  const hasData = Boolean(summary && summary.total > 0);

  const financeAccess = canAccessFinance(user);
  const isDemoClientAccount = isDemoClient(user?.email ?? null);

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
    setDemoFallback(false);
    fetchExportsSummary(user, { clientId: user.clientId, from: filters.from, to: filters.to })
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
  }, [user, filters.from, filters.to, financeAccess, t, isDemoClientAccount]);


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
      {error ? (
        <ClientErrorState
          title="Экспорты недоступны"
          description="Не удалось получить данные. Попробуйте обновить страницу."
          onRetry={() => setFilters((prev) => ({ ...prev }))}
        />
      ) : null}
      {demoFallback ? (
        <DemoEmptyState
          title="Данные в демо появятся позже"
          description="В рабочем контуре здесь будут метрики по экспортам."
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
            description="В рабочем контуре здесь будут метрики по экспортам."
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
          <AnalyticsKpiCard label={t("analytics.exports.kpi.total")} value={summary.total} />
          <AnalyticsKpiCard label={t("analytics.exports.kpi.ok")} value={summary.ok} />
          <AnalyticsKpiCard label={t("analytics.exports.kpi.mismatch")} value={summary.mismatch} />
        </section>
      ) : null}

      {!isLoading && !error && summary ? (
        <AnalyticsChartPanel
          title={t("analytics.exports.recent")}
          isEmpty={!summary.items.length}
          emptyTitle={t("analytics.empty.title")}
          emptyDescription={t("analytics.exports.empty")}
        >
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
                      <span
                        className={
                          item.status.toLowerCase().includes("ok")
                            ? "neft-chip neft-chip-ok"
                            : "neft-chip neft-chip-warn"
                        }
                      >
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
          ) : null}
        </AnalyticsChartPanel>
      ) : null}
    </div>
  );
}
