import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchDocumentsSummary } from "../api/analytics";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { AnalyticsChartPanel } from "../components/analytics/AnalyticsChartPanel";
import { AnalyticsKpiCard } from "../components/analytics/AnalyticsKpiCard";
import { AnalyticsTabs } from "../components/analytics/AnalyticsTabs";
import { FilterBar, type DateFilters } from "../components/analytics/FilterBar";
import { AppEmptyState, AppErrorState, AppForbiddenState, AppLoadingState } from "../components/states";
import { useI18n } from "../i18n";
import type { AnalyticsDocumentsSummaryResponse } from "../types/analytics";
import { buildDateRange } from "../utils/dateRange";
import { hasAnyRole } from "../utils/roles";

interface AnalyticsErrorState {
  message: string;
  status?: number;
  correlationId?: string | null;
}

export function AnalyticsDocumentsPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [filters, setFilters] = useState<DateFilters>({ preset: "30d", from: "", to: "" });
  const [summary, setSummary] = useState<AnalyticsDocumentsSummaryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<AnalyticsErrorState | null>(null);
  const hasData = Boolean(
    summary && (summary.issued > 0 || summary.signed > 0 || summary.edo_pending > 0 || summary.edo_failed > 0),
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
    fetchDocumentsSummary(user, { clientId: user.clientId, from: filters.from, to: filters.to })
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

  const statusMax = useMemo(() => {
    if (!summary) return 0;
    return Math.max(summary.issued, summary.signed, summary.edo_pending, summary.edo_failed);
  }, [summary]);

  if (!user || !canAccess) {
    return <AppForbiddenState message={t("analytics.forbidden")} />;
  }

  return (
    <div className="stack" aria-live="polite">
      <AnalyticsTabs />
      <section className="card">
        <div className="card__header">
          <div>
            <h2>{t("analytics.documents.title")}</h2>
            <p className="muted">{t("analytics.documents.subtitle")}</p>
          </div>
          <Link className="ghost" to="/documents?requiresAction=yes">
            {t("analytics.documents.action")}
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
          <AnalyticsKpiCard label={t("analytics.documents.kpi.issued")} value={summary.issued} />
          <AnalyticsKpiCard label={t("analytics.documents.kpi.signed")} value={summary.signed} />
          <AnalyticsKpiCard label={t("analytics.documents.kpi.edoPending")} value={summary.edo_pending} />
          <AnalyticsKpiCard label={t("analytics.documents.kpi.edoFailed")} value={summary.edo_failed} />
        </section>
      ) : null}

      {!isLoading && !error && summary ? (
        <section className="grid two">
          <AnalyticsChartPanel
            title={t("analytics.documents.statusDistribution")}
            isEmpty={statusMax === 0}
            emptyTitle={t("analytics.empty.title")}
            emptyDescription={t("analytics.empty.description")}
          >
            <ul className="bars">
              {[
                { label: t("analytics.documents.status.issued"), value: summary.issued },
                { label: t("analytics.documents.status.signed"), value: summary.signed },
                { label: t("analytics.documents.status.edoPending"), value: summary.edo_pending },
                { label: t("analytics.documents.status.edoFailed"), value: summary.edo_failed },
              ].map((item) => (
                <li key={item.label}>
                  <span className="muted small">{item.label}</span>
                  <div className="bar">
                    <span
                      className="bar__fill"
                      style={{ width: `${statusMax ? Math.max(6, (item.value / statusMax) * 100) : 0}%` }}
                    />
                  </div>
                  <span className="small">{item.value}</span>
                </li>
              ))}
            </ul>
          </AnalyticsChartPanel>

          <AnalyticsChartPanel
            title={t("analytics.documents.attention")}
            isEmpty={!summary.attention.length}
            emptyTitle={t("analytics.empty.title")}
            emptyDescription={t("analytics.documents.emptyAttention")}
          >
            {summary.attention.length ? (
              <ul className="attention-list">
                {summary.attention.map((item) => (
                  <li key={item.id} className="attention-list__item">
                    <Link to={`/documents/${item.id}`}>
                      <div className="attention-list__title">{item.title}</div>
                      <div className="muted small">{item.status}</div>
                    </Link>
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
