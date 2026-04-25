import React from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchRuntimeSummary } from "../../api/runtimeSummary";
import { useAuth } from "../../auth/AuthContext";
import { useAdmin } from "../../admin/AdminContext";
import { StatusBadge } from "../../components/StatusBadge/StatusBadge";
import { Loader } from "../../components/Loader/Loader";
import type { RuntimeHealthSummary, RuntimeSummary } from "../../types/runtime";
import {
  AdminForbiddenPage,
  AdminLoadingPage,
  AdminMisconfigPage,
  AdminServiceUnavailablePage,
  AdminTechErrorPage,
  AdminUnauthorizedPage,
} from "./AdminStatusPages";
import { ApiError, ForbiddenError, UnauthorizedError } from "../../api/http";
import { CopyButton } from "../../components/CopyButton/CopyButton";
import { EmptyState, FinanceOverview } from "@shared/brand/components";
import { runtimeCenterCopy } from "./runtimeStatusCopy";

const DEFAULT_SUMMARY: RuntimeSummary = {
  ts: "",
  environment: "dev",
  read_only: false,
  health: {
    core_api: "DEGRADED",
    auth_host: "DEGRADED",
    gateway: "DEGRADED",
    integration_hub: "DEGRADED",
    document_service: "DEGRADED",
    logistics_service: "DEGRADED",
    ai_service: "DEGRADED",
    postgres: "DEGRADED",
    redis: "DEGRADED",
    minio: "DEGRADED",
    clickhouse: "DEGRADED",
    prometheus: "DEGRADED",
    grafana: "DEGRADED",
    loki: "DEGRADED",
    otel_collector: "DEGRADED",
  },
  queues: {
    settlement: { depth: 0, oldest_age_sec: 0 },
    payout: { depth: 0, oldest_age_sec: 0 },
    blocked_payouts: { count: 0 },
    payment_intakes_pending: { count: 0 },
  },
  violations: {
    immutable: { count: 0, top: [] },
    invariants: { count: 0, top: [] },
    sla_penalties: { count: 0, top: [] },
  },
  money_risk: {
    payouts_blocked: 0,
    settlements_pending: 0,
    overdue_clients: 0,
  },
  events: {
    critical_last_10: [],
  },
  warnings: [],
  missing_tables: [],
  external_providers: [],
};

type CriticalEvent = { ts: string; kind: string; message: string; correlation_id?: string };

const resolveErrorScreen = (error: unknown) => {
  if (error instanceof UnauthorizedError) {
    return <AdminUnauthorizedPage />;
  }
  if (error instanceof ForbiddenError) {
    return <AdminForbiddenPage />;
  }
  if (error instanceof ApiError) {
    if (error.status === 404) {
      return <AdminMisconfigPage requestId={error.requestId ?? undefined} errorId={error.errorCode ?? undefined} />;
    }
    if (error.status === 502 || error.status === 503) {
      return <AdminServiceUnavailablePage requestId={error.requestId ?? undefined} />;
    }
    return <AdminTechErrorPage requestId={error.requestId ?? undefined} errorId={error.errorCode ?? undefined} />;
  }
  if (error instanceof TypeError) {
    return <AdminServiceUnavailablePage />;
  }
  return <AdminTechErrorPage />;
};

const resolveOverallStatus = (health?: RuntimeHealthSummary) => {
  if (!health) {
    return "UNKNOWN";
  }
  const statuses = Object.values(health);
  if (statuses.includes("DOWN")) {
    return "DOWN";
  }
  if (statuses.includes("DEGRADED")) {
    return "DEGRADED";
  }
  return "UP";
};

const toneForStatus = (status: string) => {
  if (status === "DOWN") return "danger" as const;
  if (status === "DEGRADED") return "warning" as const;
  return "success" as const;
};

const humanizeServiceName = (service: string) => service.split("_").join(" ");

export const RuntimeCenterPage: React.FC = () => {
  const { accessToken } = useAuth();
  const { profile } = useAdmin();
  const {
    data,
    isLoading,
    isFetching,
    error,
    refetch,
  } = useQuery({
    queryKey: ["runtime-summary"],
    queryFn: () => fetchRuntimeSummary(accessToken ?? ""),
    enabled: Boolean(accessToken),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

  if (isLoading && !data) {
    return <AdminLoadingPage />;
  }

  if (error) {
    return resolveErrorScreen(error);
  }

  const summary = {
    ...DEFAULT_SUMMARY,
    ...data,
    health: { ...DEFAULT_SUMMARY.health, ...data?.health },
    queues: {
      ...DEFAULT_SUMMARY.queues,
      settlement: { ...DEFAULT_SUMMARY.queues.settlement, ...data?.queues?.settlement },
      payout: { ...DEFAULT_SUMMARY.queues.payout, ...data?.queues?.payout },
      blocked_payouts: { ...DEFAULT_SUMMARY.queues.blocked_payouts, ...data?.queues?.blocked_payouts },
      payment_intakes_pending: {
        ...DEFAULT_SUMMARY.queues.payment_intakes_pending,
        ...data?.queues?.payment_intakes_pending,
      },
    },
    violations: {
      immutable: { ...DEFAULT_SUMMARY.violations.immutable, ...data?.violations?.immutable },
      invariants: { ...DEFAULT_SUMMARY.violations.invariants, ...data?.violations?.invariants },
      sla_penalties: { ...DEFAULT_SUMMARY.violations.sla_penalties, ...data?.violations?.sla_penalties },
    },
    money_risk: { ...DEFAULT_SUMMARY.money_risk, ...data?.money_risk },
    events: { ...DEFAULT_SUMMARY.events, ...data?.events },
    warnings: data?.warnings ?? DEFAULT_SUMMARY.warnings,
    missing_tables: data?.missing_tables ?? DEFAULT_SUMMARY.missing_tables,
    external_providers: data?.external_providers ?? DEFAULT_SUMMARY.external_providers,
  };

  const environment = summary.environment || profile?.env?.name || "dev";
  const readOnly = summary.read_only ?? profile?.read_only ?? false;
  const overallStatus = resolveOverallStatus(summary.health);

  const queueRows = [
    {
      label: "Settlement",
      depth: summary.queues.settlement.depth ?? 0,
      oldestAgeSec: summary.queues.settlement.oldest_age_sec ?? 0,
      to: "/finance",
    },
    {
      label: "Payout",
      depth: summary.queues.payout.depth ?? 0,
      oldestAgeSec: summary.queues.payout.oldest_age_sec ?? 0,
      to: "/finance/payouts",
    },
    {
      label: "Blocked payouts",
      depth: summary.queues.blocked_payouts.count ?? 0,
      oldestAgeSec: null,
      to: "/ops/payouts/blocked",
    },
    {
      label: "Payment intakes pending",
      depth: summary.queues.payment_intakes_pending.count ?? 0,
      oldestAgeSec: null,
      to: "/finance/payment-intakes",
    },
  ];
  const totalQueuedWork = queueRows.reduce((sum, row) => sum + row.depth, 0);
  const oldestQueueAge = Math.max(...queueRows.map((row) => row.oldestAgeSec ?? 0));
  const hasQueuedWork = queueRows.some((row) => row.depth > 0 || (row.oldestAgeSec ?? 0) > 0);

  const violationRows = [
    {
      label: "Immutable",
      count: summary.violations.immutable.count ?? 0,
      top: summary.violations.immutable.top ?? [],
      to: "/audit",
    },
    {
      label: "Invariants",
      count: summary.violations.invariants.count ?? 0,
      top: summary.violations.invariants.top ?? [],
      to: "/audit",
    },
    {
      label: "SLA penalties",
      count: summary.violations.sla_penalties.count ?? 0,
      top: summary.violations.sla_penalties.top ?? [],
      to: "/ops/support/breaches",
    },
  ];
  const totalViolations = violationRows.reduce((sum, row) => sum + row.count, 0);
  const hasViolations = violationRows.some((row) => row.count > 0);
  const events: CriticalEvent[] = summary?.events?.critical_last_10 ?? [];
  const externalProviders = summary.external_providers ?? [];
  const drilldowns = [
    { label: "Ops overview", to: "/ops" },
    { label: "Escalations inbox", to: "/ops/escalations" },
    { label: "Ops KPI", to: "/ops/kpi" },
    { label: "Logistics inspection", to: "/logistics/inspection" },
    { label: "Audit activity", to: "/audit" },
  ];

  return (
    <div className="stack">
      <div className="page-header">
        <div>
          <h1>Runtime Center</h1>
          <p className="muted">{runtimeCenterCopy.subtitle}</p>
        </div>
      </div>

      <div className="surface-toolbar">
        <span className={readOnly ? "neft-chip neft-chip-warn" : `neft-chip ${overallStatus === "UP" ? "neft-chip-ok" : overallStatus === "DEGRADED" ? "neft-chip-warn" : "neft-chip-err"}`}>
          {overallStatus}
        </span>
        <span className="neft-chip neft-chip-muted">env: {environment}</span>
        <span className={readOnly ? "neft-chip neft-chip-warn" : "neft-chip neft-chip-ok"}>
          {readOnly ? "read-only" : "writes enabled"}
        </span>
        <button type="button" className="ghost" onClick={() => refetch()} disabled={isFetching}>
          {isFetching ? runtimeCenterCopy.refresh.pending : runtimeCenterCopy.refresh.idle}
        </button>
        {(isLoading || isFetching) && <Loader label={runtimeCenterCopy.refresh.loadingLabel} />}
      </div>

      <FinanceOverview
        items={[
          {
            id: "platform",
            label: "Platform status",
            value: <StatusBadge status={overallStatus} />,
            meta: `environment: ${environment}`,
            tone: toneForStatus(overallStatus),
          },
          {
            id: "queues",
            label: "Queue pressure",
            value: String(totalQueuedWork),
            meta:
              oldestQueueAge > 0
                ? `oldest age: ${oldestQueueAge} sec`
                : runtimeCenterCopy.overview.queuePressureClear,
            action: <Link to="/finance">{runtimeCenterCopy.overview.openFinanceQueues}</Link>,
            tone: totalQueuedWork > 0 ? "warning" : "success",
          },
          {
            id: "money-risk",
            label: "Money-adjacent risk",
            value: String(summary.money_risk.payouts_blocked ?? 0),
            meta: `settlements pending: ${summary.money_risk.settlements_pending ?? 0} · overdue clients: ${summary.money_risk.overdue_clients ?? 0}`,
            action: <Link to="/finance/payouts">{runtimeCenterCopy.overview.openPayouts}</Link>,
            tone: (summary.money_risk.payouts_blocked ?? 0) > 0 ? "danger" : "info",
          },
          {
            id: "violations",
            label: "Violations",
            value: String(totalViolations),
            meta: hasViolations
              ? runtimeCenterCopy.overview.violationsPresent
              : runtimeCenterCopy.overview.violationsClear,
            action: <Link to="/audit">{runtimeCenterCopy.overview.openAudit}</Link>,
            tone: hasViolations ? "warning" : "success",
          },
          {
            id: "events",
            label: "Critical events",
            value: String(events.length),
            meta: events.length
              ? runtimeCenterCopy.overview.eventsPresent
              : runtimeCenterCopy.overview.eventsClear,
            tone: events.length ? "warning" : "success",
          },
        ]}
      />

      <section className="card dashboard-widget">
        <div className="card__header">
          <div>
            <h2>Operator drilldowns</h2>
            <p className="muted">{runtimeCenterCopy.drilldowns.subtitle}</p>
          </div>
        </div>
        <div className="dashboard-actions">
          {drilldowns.map((item, index) => (
            <Link key={item.to} className={index === 0 ? "neft-button neft-btn-primary" : "ghost"} to={item.to}>
              {item.label}
            </Link>
          ))}
        </div>
      </section>

      <section className="card">
        <div className="card__header">
          <div>
            <h2>External provider diagnostics</h2>
            <p className="muted">Provider health is separated from internal owner health: configured, degraded, unsupported and disabled are all explicit.</p>
          </div>
        </div>
        {externalProviders.length > 0 ? (
          <div className="dashboard-grid">
            {externalProviders.map((provider) => (
              <section key={`${provider.service}-${provider.provider}`} className="card dashboard-widget">
                <div className="card__header">
                  <div>
                    <h3>{humanizeServiceName(provider.provider)}</h3>
                    <p className="muted">
                      {provider.service} / mode: {provider.mode} / {provider.configured ? "configured" : "not configured"}
                    </p>
                  </div>
                  <StatusBadge status={provider.status} />
                </div>
                <p className="muted">{provider.message ?? "No provider message reported"}</p>
                {provider.last_error_code ? (
                  <span className="neft-chip neft-chip-warn">last error: {provider.last_error_code}</span>
                ) : null}
                {provider.last_success_at ? (
                  <span className="neft-chip neft-chip-ok">last success: {provider.last_success_at}</span>
                ) : null}
              </section>
            ))}
          </div>
        ) : (
          <EmptyState
            title="No provider diagnostics yet"
            description="The runtime owner did not report external provider state. Treat this as not-configured evidence, not a green provider proof."
          />
        )}
      </section>

      <section className="card">
        <div className="card__header">
          <div>
            <h2>Service health</h2>
            <p className="muted">{runtimeCenterCopy.health.subtitle}</p>
          </div>
        </div>
        <div className="dashboard-grid">
          {Object.entries(summary.health).map(([service, status]) => (
            <section key={service} className="card dashboard-widget">
              <div className="card__header">
                <div>
                  <h3>{humanizeServiceName(service)}</h3>
                  <p className="muted">Runtime health snapshot</p>
                </div>
                <StatusBadge status={status} />
              </div>
            </section>
          ))}
        </div>
      </section>

      <section className="card">
        <div className="card__header">
          <div>
            <h2>Queues</h2>
            <p className="muted">{runtimeCenterCopy.queues.subtitle}</p>
          </div>
        </div>
        {hasQueuedWork ? (
          <div className="table-shell">
            <div className="table-scroll">
              <table className="neft-table">
                <thead>
                  <tr>
                    <th>Queue</th>
                    <th>Depth / Count</th>
                    <th>Oldest age (sec)</th>
                  </tr>
                </thead>
                <tbody>
                  {queueRows.map((row) => (
                    <tr key={row.label}>
                      <td>
                        <Link to={row.to}>{row.label}</Link>
                      </td>
                      <td>{row.depth}</td>
                      <td>{row.oldestAgeSec ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <EmptyState
            title={runtimeCenterCopy.queues.emptyTitle}
            description={runtimeCenterCopy.queues.emptyDescription}
            action={
              <Link className="neft-button neft-btn-primary" to="/finance">
                {runtimeCenterCopy.queues.emptyAction}
              </Link>
            }
          />
        )}
      </section>

      <section className="card">
        <div className="card__header">
          <div>
            <h2>Violations</h2>
            <p className="muted">{runtimeCenterCopy.violations.subtitle}</p>
          </div>
        </div>
        {hasViolations ? (
          <div className="dashboard-grid">
            {violationRows.map((row) => (
              <section key={row.label} className="card dashboard-widget">
                <div className="card__header">
                  <div>
                    <h3>{row.label}</h3>
                    <p className="muted">Count: {row.count}</p>
                  </div>
                  <Link className="ghost" to={row.to}>
                    {runtimeCenterCopy.violations.openAction}
                  </Link>
                </div>
                {row.top.length ? (
                  <ul className="dashboard-list">
                    {row.top.map((item) => (
                      <li key={item} className="dashboard-list__item">
                        <span className="dashboard-list__title">{item}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <EmptyState
                    title={runtimeCenterCopy.violations.topEvidenceEmptyTitle}
                    description={runtimeCenterCopy.violations.topEvidenceEmptyDescription}
                  />
                )}
              </section>
            ))}
          </div>
        ) : (
          <EmptyState
            title={runtimeCenterCopy.violations.emptyTitle}
            description={runtimeCenterCopy.violations.emptyDescription}
            action={
              <Link className="neft-button neft-btn-primary" to="/audit">
                {runtimeCenterCopy.violations.emptyAction}
              </Link>
            }
          />
        )}
      </section>

      {summary.warnings.length > 0 || summary.missing_tables.length > 0 ? (
        <section className="card">
          <div className="card__header">
            <div>
              <h2>Degraded evidence</h2>
              <p className="muted">{runtimeCenterCopy.degradedEvidence.subtitle}</p>
            </div>
          </div>
          <div className="dashboard-grid">
            {summary.warnings.length > 0 ? (
              <section className="card dashboard-widget">
                <div className="card__header">
                  <div>
                    <h3>Warnings</h3>
                    <p className="muted">Runtime degraded signals</p>
                  </div>
                </div>
                <ul className="dashboard-list">
                  {summary.warnings.map((warning) => (
                    <li key={warning} className="dashboard-list__item">
                      <span className="dashboard-list__title">{warning}</span>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
            {summary.missing_tables.length > 0 ? (
              <section className="card dashboard-widget">
                <div className="card__header">
                  <div>
                    <h3>Missing operational tables</h3>
                    <p className="muted">Schema gaps that already affect runtime visibility</p>
                  </div>
                </div>
                <ul className="dashboard-list">
                  {summary.missing_tables.map((tableName) => (
                    <li key={tableName} className="dashboard-list__item">
                      <span className="dashboard-list__title">{tableName}</span>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
          </div>
        </section>
      ) : null}

      <section className="card">
        <div className="card__header">
          <div>
            <h2>Critical events (last 10)</h2>
            <p className="muted">{runtimeCenterCopy.events.subtitle}</p>
          </div>
        </div>
        {events.length === 0 ? (
          <EmptyState
            title={runtimeCenterCopy.events.emptyTitle}
            description={runtimeCenterCopy.events.emptyDescription}
            action={
              <Link className="neft-button neft-btn-primary" to="/audit">
                {runtimeCenterCopy.events.emptyAction}
              </Link>
            }
          />
        ) : (
          <div className="dashboard-grid">
            {events.map((event) => (
              <section key={`${event.ts}-${event.kind}-${event.correlation_id ?? ""}`} className="card dashboard-widget">
                <div className="card__header">
                  <div>
                    <h3>{event.kind}</h3>
                    <p className="muted">{event.ts}</p>
                  </div>
                </div>
                <div>{event.message}</div>
                <div className="dashboard-actions">
                  {event.correlation_id ? <Link className="ghost" to={`/audit/${event.correlation_id}`}>Open audit</Link> : null}
                  {event.correlation_id ? <CopyButton value={event.correlation_id} label="Copy correlation_id" /> : null}
                </div>
              </section>
            ))}
          </div>
        )}
      </section>
    </div>
  );
};

export default RuntimeCenterPage;
