import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n";
import { Table } from "../components/common/Table";
import type { Column } from "../components/common/Table";
import { AppErrorState, AppForbiddenState } from "../components/states";
import { FleetUnavailableState } from "../components/FleetUnavailableState";
import { ApiError } from "../api/http";
import { listExecutions } from "../api/fleetPolicies";
import type { FleetPolicyExecution } from "../types/fleetPolicies";
import { CopyButton } from "../components/CopyButton";
import { formatDateTime } from "../utils/format";
import { hasAnyRole } from "../utils/roles";
import { canViewExecutions, type FleetPolicyRole } from "../utils/fleetPolicyPermissions";

const getExecutionStatusClass = (status?: string | null) => {
  if (status === "APPLIED") return "badge badge-success";
  if (status === "FAILED") return "badge badge-error";
  if (status === "SKIPPED") return "badge badge-muted";
  return "badge badge-muted";
};

const getActionBadgeClass = (action?: string | null) => {
  if (action === "AUTO_BLOCK_CARD") return "badge badge-warning";
  if (action === "ESCALATE_CASE") return "badge badge-info";
  return "badge badge-muted";
};

const toIsoDate = (value: string, endOfDay = false) => {
  if (!value) return undefined;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return undefined;
  if (endOfDay) {
    date.setHours(23, 59, 59, 999);
  }
  return date.toISOString();
};

const formatDateInput = (value: Date) => value.toISOString().slice(0, 10);

const getPolicyRole = (user: ReturnType<typeof useAuth>["user"]): FleetPolicyRole => {
  if (hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_FLEET_MANAGER"])) return "admin";
  return "viewer";
};

const truncateReason = (value?: string | null, maxLength = 120) => {
  if (!value) return "";
  if (value.length <= maxLength) return value;
  return `${value.slice(0, maxLength - 1)}…`;
};

export function FleetPolicyExecutionsPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [executions, setExecutions] = useState<FleetPolicyExecution[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isForbidden, setIsForbidden] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [dateFrom, setDateFrom] = useState(() => formatDateInput(new Date(Date.now() - 7 * 24 * 60 * 60 * 1000)));
  const [dateTo, setDateTo] = useState(() => formatDateInput(new Date()));
  const [statusFilter, setStatusFilter] = useState("");
  const [actionFilter, setActionFilter] = useState("");
  const [triggerFilter, setTriggerFilter] = useState("");
  const [scopeFilter, setScopeFilter] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");

  const policyRole = useMemo(() => getPolicyRole(user), [user]);
  const canView = canViewExecutions(policyRole);

  const loadExecutions = useCallback(async () => {
    if (!user?.token) return;
    setLoading(true);
    setError(null);
    setIsForbidden(false);
    setUnavailable(false);
    try {
      const response = await listExecutions(user.token, {
        from: toIsoDate(dateFrom),
        to: toIsoDate(dateTo, true),
        status: statusFilter || undefined,
        action: actionFilter || undefined,
        trigger_type: triggerFilter || undefined,
        scope_type: scopeFilter || undefined,
        severity_min: severityFilter || undefined,
      });
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      setExecutions(response.items);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setIsForbidden(true);
        return;
      }
      setError(err instanceof Error ? err.message : t("fleetPolicies.errors.executionsFailed"));
    } finally {
      setLoading(false);
    }
  }, [actionFilter, dateFrom, dateTo, scopeFilter, severityFilter, statusFilter, t, triggerFilter, user?.token]);

  useEffect(() => {
    if (!canView) return;
    void loadExecutions();
  }, [canView, loadExecutions]);

  const columns: Column<FleetPolicyExecution>[] = useMemo(
    () => [
      {
        key: "time",
        title: t("fleetPolicies.executions.time"),
        render: (execution) => (execution.executed_at ? formatDateTime(execution.executed_at) : "—"),
      },
      {
        key: "status",
        title: t("fleetPolicies.executions.status"),
        render: (execution) => (
          <span className={getExecutionStatusClass(execution.status)}>
            {execution.status === "APPLIED"
              ? t("fleetPolicies.executions.statusApplied")
              : execution.status === "SKIPPED"
                ? t("fleetPolicies.executions.statusSkipped")
                : execution.status === "FAILED"
                  ? t("fleetPolicies.executions.statusFailed")
                  : execution.status ?? t("common.notAvailable")}
          </span>
        ),
      },
      {
        key: "trigger",
        title: t("fleetPolicies.executions.trigger"),
        render: (execution) => (
          <div className="policy-trigger">
            <div>
              {execution.trigger_type === "LIMIT_BREACH"
                ? t("fleetPolicies.triggerLimit")
                : execution.trigger_type === "ANOMALY"
                  ? t("fleetPolicies.triggerAnomaly")
                  : execution.trigger_type ?? t("common.notAvailable")}
            </div>
            {execution.severity ? <span className="badge badge-muted">{execution.severity}</span> : null}
          </div>
        ),
      },
      {
        key: "action",
        title: t("fleetPolicies.action"),
        render: (execution) => (
          <span className={getActionBadgeClass(execution.action)}>
            {execution.action === "NOTIFY_ONLY"
              ? t("fleetPolicies.actionNotify")
              : execution.action === "AUTO_BLOCK_CARD"
                ? t("fleetPolicies.actionAutoBlock")
                : execution.action === "ESCALATE_CASE"
                  ? t("fleetPolicies.actionEscalate")
                  : execution.action ?? t("common.notAvailable")}
          </span>
        ),
      },
      {
        key: "scope",
        title: t("fleetPolicies.scope"),
        render: (execution) => (
          <span className="badge badge-muted">
            {execution.scope_type === "CLIENT"
              ? t("fleetPolicies.scopeClient")
              : execution.scope_type === "GROUP"
                ? t("fleetPolicies.scopeGroup")
                : execution.scope_type === "CARD"
                  ? t("fleetPolicies.scopeCard")
                  : execution.scope_type ?? t("common.notAvailable")}
          </span>
        ),
      },
      {
        key: "scopeName",
        title: t("fleetPolicies.scopeName"),
        render: (execution) => {
          if (execution.scope_type === "CLIENT") return t("fleetPolicies.scopeClient");
          if (execution.scope_type === "GROUP") return execution.group_name ?? t("fleetPolicies.scopeGroupFallback");
          if (execution.scope_type === "CARD") return execution.card_alias ?? t("fleetPolicies.scopeCardFallback");
          return t("common.notAvailable");
        },
      },
      {
        key: "reason",
        title: t("fleetPolicies.executions.reason"),
        render: (execution) => {
          const reason = execution.reason ?? "";
          return (
            <div className="policy-reason">
              <span title={reason}>{truncateReason(reason) || "—"}</span>
              <details className="policy-explain">
                <summary>{t("fleetPolicies.executions.explain")}</summary>
                <div className="policy-explain__body">
                  <div className="muted">{t("fleetPolicies.executions.explainRule")}</div>
                  <ul>
                    <li>
                      {t("fleetPolicies.executions.explainTrigger", {
                        trigger:
                          execution.trigger_type === "LIMIT_BREACH"
                            ? t("fleetPolicies.triggerLimit")
                            : execution.trigger_type === "ANOMALY"
                              ? t("fleetPolicies.triggerAnomaly")
                              : execution.trigger_type ?? t("common.notAvailable"),
                        severity: execution.severity ?? "—",
                      })}
                    </li>
                    <li>
                      {t("fleetPolicies.executions.explainAction", {
                        action:
                          execution.action === "NOTIFY_ONLY"
                            ? t("fleetPolicies.actionNotify")
                            : execution.action === "AUTO_BLOCK_CARD"
                              ? t("fleetPolicies.actionAutoBlock")
                              : execution.action === "ESCALATE_CASE"
                                ? t("fleetPolicies.actionEscalate")
                                : execution.action ?? t("common.notAvailable"),
                      })}
                    </li>
                    <li>
                      {t("fleetPolicies.executions.explainReason", {
                        reason: execution.reason ?? t("fleetPolicies.executions.explainReasonFallback"),
                      })}
                    </li>
                    {execution.status === "SKIPPED" ? (
                      <li>{t("fleetPolicies.executions.explainSkipped")}</li>
                    ) : null}
                  </ul>
                </div>
              </details>
            </div>
          );
        },
      },
      {
        key: "links",
        title: t("fleetPolicies.executions.links"),
        render: (execution) => (
          <div className="policy-links">
            {execution.scope_type === "CARD" && execution.scope_id ? (
              <Link to={`/fleet/cards/${execution.scope_id}`}>{t("fleetPolicies.executions.openCard")}</Link>
            ) : null}
            {execution.scope_type === "GROUP" && execution.scope_id ? (
              <Link to={`/fleet/groups/${execution.scope_id}`}>{t("fleetPolicies.executions.openGroup")}</Link>
            ) : null}
            {execution.breach_id || execution.anomaly_id ? (
              <Link to={`/fleet/notifications?alert=${execution.breach_id ?? execution.anomaly_id}`}>
                {t("fleetPolicies.executions.openAlert")}
              </Link>
            ) : null}
            {execution.case_id ? <Link to={`/cases/${execution.case_id}`}>{t("fleetPolicies.executions.openCase")}</Link> : null}
          </div>
        ),
      },
      {
        key: "advanced",
        title: t("fleetPolicies.executions.advanced"),
        render: (execution) => (
          <details className="policy-advanced">
            <summary>{t("fleetPolicies.executions.advanced")}</summary>
            <div className="policy-advanced__content">
              {execution.policy_id ? (
                <div className="policy-advanced__row">
                  <div className="muted small">{t("fleetPolicies.executions.policyId")}</div>
                  <CopyButton value={execution.policy_id} label={t("fleetPolicies.executions.copyId")} />
                </div>
              ) : null}
              {execution.audit_event_id ? (
                <div className="policy-advanced__row">
                  <div className="muted small">{t("fleetPolicies.executions.eventId")}</div>
                  <CopyButton value={execution.audit_event_id} label={t("fleetPolicies.executions.copyEventId")} />
                </div>
              ) : null}
            </div>
          </details>
        ),
      },
    ],
    [t],
  );

  if (!canView) {
    return <AppForbiddenState message={t("fleetPolicies.executions.forbidden")} />;
  }

  if (loading) {
    return (
      <div className="page">
        <div className="page-header">
          <h1>{t("fleetPolicies.executions.title")}</h1>
        </div>
        <div className="card state">{t("common.loading")}</div>
      </div>
    );
  }

  if (unavailable) {
    return <FleetUnavailableState />;
  }

  if (isForbidden) {
    return <AppForbiddenState message={t("fleetPolicies.executions.forbidden")} />;
  }

  if (error) {
    return (
      <div className="page">
        <div className="page-header">
          <h1>{t("fleetPolicies.executions.title")}</h1>
        </div>
        <AppErrorState message={error} onRetry={() => void loadExecutions()} />
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>{t("fleetPolicies.executions.title")}</h1>
        <div className="actions">
          <Link to="/fleet/policies" className="secondary">
            {t("fleetPolicies.executions.backToPolicies")}
          </Link>
          <button type="button" className="secondary" onClick={() => void loadExecutions()}>
            {t("actions.refresh")}
          </button>
        </div>
      </div>
      <div className="card filters">
        <label className="filter">
          <span>{t("fleetPolicies.executions.dateFrom")}</span>
          <input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} />
        </label>
        <label className="filter">
          <span>{t("fleetPolicies.executions.dateTo")}</span>
          <input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} />
        </label>
        <label className="filter">
          <span>{t("fleetPolicies.executions.status")}</span>
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="">{t("fleetPolicies.executions.statusAll")}</option>
            <option value="APPLIED">{t("fleetPolicies.executions.statusApplied")}</option>
            <option value="SKIPPED">{t("fleetPolicies.executions.statusSkipped")}</option>
            <option value="FAILED">{t("fleetPolicies.executions.statusFailed")}</option>
          </select>
        </label>
        <label className="filter">
          <span>{t("fleetPolicies.trigger")}</span>
          <select value={triggerFilter} onChange={(event) => setTriggerFilter(event.target.value)}>
            <option value="">{t("fleetPolicies.triggerAll")}</option>
            <option value="LIMIT_BREACH">{t("fleetPolicies.triggerLimit")}</option>
            <option value="ANOMALY">{t("fleetPolicies.triggerAnomaly")}</option>
          </select>
        </label>
        <label className="filter">
          <span>{t("fleetPolicies.action")}</span>
          <select value={actionFilter} onChange={(event) => setActionFilter(event.target.value)}>
            <option value="">{t("fleetPolicies.actionAll")}</option>
            <option value="NOTIFY_ONLY">{t("fleetPolicies.actionNotify")}</option>
            <option value="AUTO_BLOCK_CARD">{t("fleetPolicies.actionAutoBlock")}</option>
            <option value="ESCALATE_CASE">{t("fleetPolicies.actionEscalate")}</option>
          </select>
        </label>
        <label className="filter">
          <span>{t("fleetPolicies.scope")}</span>
          <select value={scopeFilter} onChange={(event) => setScopeFilter(event.target.value)}>
            <option value="">{t("fleetPolicies.scopeAll")}</option>
            <option value="CLIENT">{t("fleetPolicies.scopeClient")}</option>
            <option value="GROUP">{t("fleetPolicies.scopeGroup")}</option>
            <option value="CARD">{t("fleetPolicies.scopeCard")}</option>
          </select>
        </label>
        <label className="filter">
          <span>{t("fleetPolicies.executions.severityMin")}</span>
          <select value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value)}>
            <option value="">{t("fleetPolicies.executions.severityAll")}</option>
            <option value="LOW">LOW</option>
            <option value="MED">MED</option>
            <option value="HIGH">HIGH</option>
            <option value="CRIT">CRIT</option>
          </select>
        </label>
      </div>
      <Table
        columns={columns}
        data={executions}
        emptyState={{
          title: t("fleetPolicies.executions.emptyTitle"),
          description: t("fleetPolicies.executions.emptyDescription"),
        }}
      />
    </div>
  );
}
