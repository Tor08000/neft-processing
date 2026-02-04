import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchDocumentsSummary } from "../api/analytics";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { AnalyticsChartPanel } from "../components/analytics/AnalyticsChartPanel";
import { AnalyticsKpiCard } from "../components/analytics/AnalyticsKpiCard";
import { AnalyticsTabs } from "../components/analytics/AnalyticsTabs";
import { FilterBar, type DateFilters } from "../components/analytics/FilterBar";
import { ClientErrorState } from "../components/ClientErrorState";
import { DemoEmptyState } from "../components/DemoEmptyState";
import { AppEmptyState, AppForbiddenState, AppLoadingState } from "../components/states";
import { demoDocumentsSummary } from "../demo/demoData";
import { useI18n } from "../i18n";
import type { AnalyticsDocumentsSummaryResponse } from "../types/analytics";
import { buildDateRange } from "../utils/dateRange";
import { hasAnyRole } from "../utils/roles";
import { isDemoClient } from "@shared/demo/demo";

interface AnalyticsErrorState {
  status?: number;
}

export function AnalyticsDocumentsPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [filters, setFilters] = useState<DateFilters>({ preset: "30d", from: "", to: "" });
  const [summary, setSummary] = useState<AnalyticsDocumentsSummaryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<AnalyticsErrorState | null>(null);
  const [useDemoData, setUseDemoData] = useState(false);
  const hasData = Boolean(
    summary && (summary.issued > 0 || summary.signed > 0 || summary.edo_pending > 0 || summary.edo_failed > 0),
  );

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
    setUseDemoData(false);
    fetchDocumentsSummary(user, { clientId: user.clientId, from: filters.from, to: filters.to })
      .then((resp) => setSummary(resp))
      .catch((err: unknown) => {
        console.error("Не удалось загрузить аналитику документов", err);
        const status = err instanceof ApiError ? err.status : undefined;
        if (isDemoClientAccount && status === 404) {
          setSummary(demoDocumentsSummary);
          setUseDemoData(true);
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
            <p className="muted">
              {useDemoData ? "Демо-режим: показатели собраны на примере типовой компании." : t("analytics.documents.subtitle")}
            </p>
          </div>
          <Link className="ghost" to="/documents?requiresAction=yes">
            {t("analytics.documents.action")}
          </Link>
        </div>
        <FilterBar filters={filters} onChange={setFilters} />
      </section>

      {isLoading ? <AppLoadingState label={t("analytics.loading")} /> : null}
      {error ? (
        <ClientErrorState
          title="Аналитика документов недоступна"
          description="Данные временно недоступны. Попробуйте обновить страницу."
          onRetry={() => setFilters((prev) => ({ ...prev }))}
        />
      ) : null}
      {!isLoading && !error && !hasData ? (
        isDemoClientAccount ? (
          <DemoEmptyState
            title="Данные в демо появятся позже"
            description="В рабочем контуре здесь будут метрики по документообороту и ЭДО."
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
