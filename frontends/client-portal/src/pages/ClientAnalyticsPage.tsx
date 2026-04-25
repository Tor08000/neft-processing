import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchClientAnalyticsSummary } from "../api/clientAnalytics";
import { ApiError, UnauthorizedError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { AnalyticsChartPanel } from "../components/analytics/AnalyticsChartPanel";
import { AnalyticsKpiCard } from "../components/analytics/AnalyticsKpiCard";
import { FilterBar, type DateFilters } from "../components/analytics/FilterBar";
import { MoneyValue } from "../components/common/MoneyValue";
import { ClientErrorState } from "../components/ClientErrorState";
import { DemoEmptyState } from "../components/DemoEmptyState";
import { AppEmptyState, AppForbiddenState, AppLoadingState } from "../components/states";
import { StatusPage } from "../components/StatusPage";
import type { ClientAnalyticsSummaryResponse } from "../types/clientAnalytics";
import { buildDateRange } from "../utils/dateRange";
import { formatDate, formatLiters } from "../utils/format";
import { hasAnyRole } from "../utils/roles";
import { isDemoClient } from "@shared/demo/demo";

interface AnalyticsErrorState {
  status?: number;
}

const presets = [
  { value: "7d", label: "Last 7 days" },
  { value: "30d", label: "Last 30 days" },
  { value: "90d", label: "Last 90 days" },
  { value: "custom", label: "Custom" },
] as const;

const formatMinutes = (value: number | null) => {
  if (value === null || Number.isNaN(value)) {
    return "—";
  }
  return `${Math.round(value)} мин`;
};

export function ClientAnalyticsPage() {
  const { user } = useAuth();
  const [filters, setFilters] = useState<DateFilters>({ preset: "30d", from: "", to: "" });
  const [scope, setScope] = useState("all");
  const [data, setData] = useState<ClientAnalyticsSummaryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<AnalyticsErrorState | null>(null);
  const [useDemoData, setUseDemoData] = useState(false);

  const canAccess = hasAnyRole(user, [
    "CLIENT_OWNER",
    "CLIENT_ADMIN",
    "CLIENT_ACCOUNTANT",
    "CLIENT_FLEET_MANAGER",
  ]);
  const isDemoClientAccount = isDemoClient(user?.email ?? null);

  useEffect(() => {
    if (filters.preset !== "custom") {
      const range = buildDateRange(filters.preset);
      setFilters((prev) => ({ ...prev, ...range }));
    }
  }, [filters.preset]);

  useEffect(() => {
    if (!user?.clientId || !filters.from || !filters.to) return;
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    setIsLoading(true);
    setError(null);
    setUseDemoData(false);
    fetchClientAnalyticsSummary(user, { from: filters.from, to: filters.to, scope, timezone })
      .then((resp) => setData(resp))
      .catch(async (err: unknown) => {
        console.error("Не удалось загрузить аналитику", err);
        const status = err instanceof ApiError ? err.status : undefined;
        if (isDemoClientAccount && status === 404) {
          const { demoClientAnalyticsSummary } = await import("../demo/demoData");
          setData(demoClientAnalyticsSummary);
          setUseDemoData(true);
          setError(null);
          return;
        }
        if (err instanceof UnauthorizedError) {
          setError({ status: 401 });
          return;
        }
        if (err instanceof ApiError) {
          setError({ status: err.status });
          return;
        }
        setError({ status });
      })
      .finally(() => setIsLoading(false));
  }, [user, filters.from, filters.to, scope, isDemoClientAccount]);

  const scopeOptions = useMemo(() => {
    const items = [{ value: "all", label: "All cards" }];
    if (data?.tops.cards?.length) {
      data.tops.cards.forEach((card) => {
        items.push({ value: `cards:${card.card_id}`, label: `Card · ${card.label}` });
      });
    }
    if (data?.tops.drivers?.length) {
      data.tops.drivers.forEach((driver) => {
        items.push({ value: `driver:${driver.user_id}`, label: `Driver · ${driver.label}` });
      });
    }
    if (!items.some((item) => item.value === scope) && scope !== "all") {
      const labelSuffix = scope.split(":", 2)[1] ?? scope;
      const labelPrefix = scope.startsWith("driver:") ? "Driver" : "Card";
      items.push({ value: scope, label: `${labelPrefix} · ${labelSuffix}` });
    }
    return items;
  }, [data, scope]);

  const hasData =
    (data?.summary.transactions_count ?? 0) > 0 ||
    (data?.summary.open_tickets ?? 0) > 0;

  const trendMax = useMemo(
    () => Math.max(...(data?.timeseries ?? []).map((item) => item.spend), 0),
    [data],
  );
  const topCardsMax = useMemo(
    () => Math.max(...(data?.tops.cards ?? []).map((item) => item.spend), 0),
    [data],
  );
  const topDriversMax = useMemo(
    () => Math.max(...(data?.tops.drivers ?? []).map((item) => item.spend), 0),
    [data],
  );
  const topStationsMax = useMemo(
    () => Math.max(...(data?.tops.stations ?? []).map((item) => item.spend), 0),
    [data],
  );

  if (!user || !canAccess) {
    return <AppForbiddenState message="Недостаточно прав для доступа к аналитике." />;
  }

  if (error?.status === 401 || error?.status === 403) {
    return <StatusPage title="Нет доступа" description="У вас нет прав для просмотра этой страницы." />;
  }

  if (error?.status && error.status >= 500) {
    return (
      <ClientErrorState
        title="Сервис временно недоступен"
        description="Попробуйте повторить запрос чуть позже."
        onRetry={() => setFilters((prev) => ({ ...prev }))}
        secondaryActionTo="/dashboard"
        secondaryActionLabel="Обзор"
      />
    );
  }

  return (
    <div className="stack" aria-live="polite">
      <section className="card">
        <div className="card__header">
          <div>
            <h2>Analytics</h2>
            <p className="muted">
              {useDemoData
                ? "Демо-режим: данные сформированы на основе типового сценария."
                : "Операционные инсайты по расходам, картам и поддержке."}
            </p>
          </div>
        </div>
        <FilterBar filters={filters} onChange={setFilters} presets={presets} />
        <div className="filters analytics-filters analytics-scope-filters">
          <div className="filter">
            <label htmlFor="scope">Card scope</label>
            <select id="scope" name="scope" value={scope} onChange={(event) => setScope(event.target.value)}>
              {scopeOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </section>

      {isLoading ? <AppLoadingState label="Loading analytics" /> : null}
      {error ? (
        <ClientErrorState
          title="Аналитика недоступна"
          description="Не удалось получить данные. Попробуйте обновить страницу."
          onRetry={() => setFilters((prev) => ({ ...prev }))}
        />
      ) : null}
      {!isLoading && !error && !hasData ? (
        isDemoClientAccount ? (
          <DemoEmptyState
            title="Данные в демо появятся позже"
            description="В рабочем контуре здесь будет CFO-дашборд по расходам и показателям."
            action={
              <Link className="ghost neft-btn-secondary" to="/dashboard">
                Перейти в обзор
              </Link>
            }
          />
        ) : (
          <AppEmptyState title="Нет данных" description="Нет данных за выбранный период." />
        )
      ) : null}

      {!isLoading && !error && hasData && data ? (
        <section className="grid analytics-kpi-grid">
          <AnalyticsKpiCard label="Total transactions" value={data.summary.transactions_count} />
          <AnalyticsKpiCard label="Total spend" value={<MoneyValue amount={data.summary.total_spend} />} />
          <AnalyticsKpiCard label="Total liters" value={formatLiters(data.summary.total_liters)} />
          <AnalyticsKpiCard label="Active cards" value={data.summary.active_cards} />
          <AnalyticsKpiCard label="Blocked cards" value={data.summary.blocked_cards} />
          <AnalyticsKpiCard label="Unique drivers" value={data.summary.unique_drivers} />
          <AnalyticsKpiCard label="Open tickets" value={data.summary.open_tickets} />
          <AnalyticsKpiCard label="SLA breaches" value={data.summary.sla_breaches_resolution + data.summary.sla_breaches_first} />
        </section>
      ) : null}

      {!isLoading && !error && hasData && data ? (
        <AnalyticsChartPanel
          title="Spend per day"
          subtitle="Сумма по дням"
          isEmpty={!data.timeseries.length}
          emptyDescription="Нет данных за выбранный период."
        >
          {data.timeseries.length ? (
            <div className="chart">
              {data.timeseries.map((point) => (
                <Link
                  className="chart-row chart-row--link"
                  key={`spend-${point.date}`}
                  to={`/client/analytics/day?date=${point.date}&period=${filters.preset}`}
                >
                  <span className="muted small">{formatDate(point.date)}</span>
                  <div className="chart-bar">
                    <span
                      className="chart-bar__fill"
                      style={{ width: `${trendMax ? Math.max(4, (point.spend / trendMax) * 100) : 0}%` }}
                    />
                  </div>
                  <div className="chart-meta">
                    <MoneyValue amount={point.spend} />
                    <div className="muted small">
                      {formatLiters(point.liters)} л · {point.count} tx
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          ) : null}
        </AnalyticsChartPanel>
      ) : null}

      {!isLoading && !error && hasData && data ? (
        <section className="grid analytics-top-grid">
          <AnalyticsChartPanel
            title="Top cards"
            subtitle="По сумме расходов"
            isEmpty={!data.tops.cards.length}
            emptyDescription="Нет данных по картам."
          >
            {data.tops.cards.length ? (
              <div className="chart">
                {data.tops.cards.map((card) => (
                  <div className="chart-row chart-row--wide" key={`card-${card.card_id}`}>
                    <div>
                      <Link
                        className="link-button"
                        to={`/client/analytics/card/${card.card_id}?from=${filters.from}&to=${filters.to}`}
                      >
                        {card.label}
                      </Link>
                      <div className="muted small">
                        {card.count} tx · {formatLiters(card.liters)} л
                      </div>
                    </div>
                    <div className="chart-bar">
                      <span
                        className="chart-bar__fill"
                        style={{ width: `${topCardsMax ? Math.max(4, (card.spend / topCardsMax) * 100) : 0}%` }}
                      />
                    </div>
                    <MoneyValue amount={card.spend} />
                  </div>
                ))}
              </div>
            ) : null}
          </AnalyticsChartPanel>

          <AnalyticsChartPanel
            title="Top drivers"
            subtitle="По сумме расходов"
            isEmpty={!data.tops.drivers.length}
            emptyDescription="Нет данных по водителям."
          >
            {data.tops.drivers.length ? (
              <div className="chart">
                {data.tops.drivers.map((driver) => (
                  <div className="chart-row chart-row--wide" key={`driver-${driver.user_id}`}>
                    <div>
                      <Link
                        className="link-button"
                        to={`/client/analytics/driver/${driver.user_id}?from=${filters.from}&to=${filters.to}`}
                      >
                        {driver.label}
                      </Link>
                      <div className="muted small">{driver.count} tx</div>
                    </div>
                    <div className="chart-bar">
                      <span
                        className="chart-bar__fill"
                        style={{ width: `${topDriversMax ? Math.max(4, (driver.spend / topDriversMax) * 100) : 0}%` }}
                      />
                    </div>
                    <MoneyValue amount={driver.spend} />
                  </div>
                ))}
              </div>
            ) : null}
          </AnalyticsChartPanel>

          <AnalyticsChartPanel
            title="Top stations"
            subtitle="По сумме расходов"
            isEmpty={!data.tops.stations.length}
            emptyDescription="Нет данных по станциям."
          >
            {data.tops.stations.length ? (
              <div className="chart">
                {data.tops.stations.map((station) => (
                  <div className="chart-row chart-row--wide" key={`station-${station.station_id}`}>
                    <div>
                      <strong>{station.label}</strong>
                      <div className="muted small">
                        {station.count} tx · {formatLiters(station.liters)} л
                      </div>
                    </div>
                    <div className="chart-bar">
                      <span
                        className="chart-bar__fill"
                        style={{ width: `${topStationsMax ? Math.max(4, (station.spend / topStationsMax) * 100) : 0}%` }}
                      />
                    </div>
                    <MoneyValue amount={station.spend} />
                  </div>
                ))}
              </div>
            ) : null}
          </AnalyticsChartPanel>
        </section>
      ) : null}

      {!isLoading && !error && hasData && data ? (
        <AnalyticsChartPanel
          title="Support health"
          subtitle="SLA и время реакции"
          isEmpty={false}
          action={
            <Link className="ghost" to={`/client/analytics/support?t=open&from=${filters.from}&to=${filters.to}`}>
              Открытые тикеты
            </Link>
          }
        >
          <div className="analytics-summary-grid">
            <div>
              <div className="muted small">Open tickets</div>
              <div className="analytics-summary__value">{data.support.open}</div>
            </div>
            <div>
              <div className="muted small">Avg first response</div>
              <div className="analytics-summary__value">{formatMinutes(data.support.avg_first_response_minutes)}</div>
            </div>
            <div>
              <div className="muted small">Avg resolve</div>
              <div className="analytics-summary__value">{formatMinutes(data.support.avg_resolve_minutes)}</div>
            </div>
            <div>
              <div className="muted small">SLA breaches</div>
              <div className="analytics-summary__value">
                {data.summary.sla_breaches_first + data.summary.sla_breaches_resolution}
              </div>
            </div>
          </div>
        </AnalyticsChartPanel>
      ) : null}
    </div>
  );
}
