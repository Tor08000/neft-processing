import React from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchRuntimeSummary } from "../../api/runtimeSummary";
import { useAuth } from "../../auth/AuthContext";
import { useAdmin } from "../../admin/AdminContext";
import { StatusBadge } from "../../components/StatusBadge/StatusBadge";
import { Loader } from "../../components/Loader/Loader";
import type { CriticalEvent, RuntimeHealthSummary, RuntimeSummary } from "../../types/runtime";
import {
  AdminForbiddenPage,
  AdminLoadingPage,
  AdminServiceUnavailablePage,
  AdminTechErrorPage,
  AdminUnauthorizedPage,
} from "./AdminStatusPages";
import { ApiError, ForbiddenError, UnauthorizedError } from "../../api/http";

const DEFAULT_SUMMARY: RuntimeSummary = {
  ts: "",
  environment: "dev",
  read_only: false,
  health: {
    core_api: "UP",
    auth_host: "UP",
    gateway: "UP",
    postgres: "UP",
    redis: "UP",
    minio: "UP",
    clickhouse: "UP",
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
  },
  money_risk: {
    payouts_blocked: 0,
    settlements_pending: 0,
    overdue_clients: 0,
  },
  events: {
    critical_last_10: [],
  },
};

const resolveErrorScreen = (error: unknown) => {
  if (error instanceof UnauthorizedError) {
    return <AdminUnauthorizedPage />;
  }
  if (error instanceof ForbiddenError) {
    return <AdminForbiddenPage />;
  }
  if (error instanceof ApiError) {
    if (error.status === 502 || error.status === 503) {
      return <AdminServiceUnavailablePage requestId={error.requestId ?? undefined} />;
    }
    return <AdminTechErrorPage requestId={error.requestId ?? undefined} />;
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
    },
    money_risk: { ...DEFAULT_SUMMARY.money_risk, ...data?.money_risk },
    events: { ...DEFAULT_SUMMARY.events, ...data?.events },
  };

  const environment = summary.environment || profile?.env?.name || "dev";
  const readOnly = summary.read_only ?? profile?.read_only ?? false;
  const overallStatus = resolveOverallStatus(summary.health);

  const queueRows = [
    {
      label: "Settlement",
      depth: summary.queues.settlement.depth ?? 0,
      oldestAgeSec: summary.queues.settlement.oldest_age_sec ?? 0,
    },
    {
      label: "Payout",
      depth: summary.queues.payout.depth ?? 0,
      oldestAgeSec: summary.queues.payout.oldest_age_sec ?? 0,
    },
    {
      label: "Blocked payouts",
      depth: summary.queues.blocked_payouts.count ?? 0,
      oldestAgeSec: null,
    },
    {
      label: "Payment intakes pending",
      depth: summary.queues.payment_intakes_pending.count ?? 0,
      oldestAgeSec: null,
    },
  ];
  const hasQueuedWork = queueRows.some((row) => row.depth > 0 || (row.oldestAgeSec ?? 0) > 0);

  const violationRows = [
    {
      label: "Immutable",
      count: summary.violations.immutable.count ?? 0,
      top: summary.violations.immutable.top ?? [],
    },
    {
      label: "Invariants",
      count: summary.violations.invariants.count ?? 0,
      top: summary.violations.invariants.top ?? [],
    },
  ];
  const hasViolations = violationRows.some((row) => row.count > 0);

  const criticalEvents: CriticalEvent[] = summary?.events?.critical_last_10 ?? [];

  return (
    <div>
      <div className="page-header">
        <h1>Runtime Center</h1>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <button onClick={() => refetch()} disabled={isFetching}>
            Refresh
          </button>
          {(isLoading || isFetching) && <Loader label="Загрузка статуса" />}
          {error && <span style={{ color: "#dc2626" }}>{error.message}</span>}
        </div>
      </div>

      <div className="card" style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <strong>Status</strong>
          <StatusBadge status={overallStatus} />
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <strong>Env</strong>
          <span>{environment}</span>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <strong>Read-only</strong>
          <span>{readOnly ? "true" : "false"}</span>
        </div>
        {readOnly && <span className="neft-chip neft-chip-warn">READ-ONLY MODE</span>}
      </div>

      <div className="status-grid" style={{ marginTop: 16 }}>
        {Object.entries(summary.health).map(([service, status]) => (
          <div key={service} className="card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <strong>{service.replace("_", " ")}</strong>
              <StatusBadge status={status} />
            </div>
          </div>
        ))}
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h2>Queues</h2>
        {hasQueuedWork ? (
          <table className="table">
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
                  <td>{row.label}</td>
                  <td>{row.depth}</td>
                  <td>{row.oldestAgeSec ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p>Очередь пуста</p>
        )}
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h2>Violations</h2>
        {hasViolations ? (
          <div style={{ display: "grid", gap: 12 }}>
            {violationRows.map((row) => (
              <div key={row.label} className="card" style={{ background: "transparent" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <strong>{row.label}</strong>
                  <span>{row.count}</span>
                </div>
                {row.top.length ? (
                  <ul>
                    {row.top.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                ) : (
                  <p>Нет нарушений</p>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p>Нет нарушений</p>
        )}
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h2>Critical events (last 10)</h2>
        {criticalEvents.length ? (
          <table className="table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Kind</th>
                <th>Message</th>
                <th>Correlation</th>
              </tr>
            </thead>
            <tbody>
              {criticalEvents.map((event) => (
                <tr key={`${event.ts}-${event.kind}-${event.message}`}>
                  <td>{event.ts}</td>
                  <td>{event.kind}</td>
                  <td>{event.message}</td>
                  <td>{event.correlation_id ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p>Нет событий</p>
        )}
      </div>
    </div>
  );
};

export default RuntimeCenterPage;
