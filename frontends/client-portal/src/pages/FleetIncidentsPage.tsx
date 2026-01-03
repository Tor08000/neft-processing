import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n";
import { AppEmptyState, AppErrorState, AppForbiddenState } from "../components/states";
import { FleetUnavailableState } from "../components/FleetUnavailableState";
import { ApiError } from "../api/http";
import { listFleetCases } from "../api/fleetCases";
import type { FleetCaseListItem } from "../types/fleetCases";
import { formatDateTime } from "../utils/format";
import { canViewFleetIncidents } from "../utils/fleetPermissions";
import {
  getFleetCasePolicyActionBadgeClass,
  getFleetCaseSeverityBadgeClass,
  getFleetCaseStatusBadgeClass,
  getFleetCaseTriggerBadgeClass,
} from "../utils/fleetCases";

const severityOrder = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];

const toIsoDate = (value: string, endOfDay = false) => {
  if (!value) return undefined;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return undefined;
  if (endOfDay) {
    date.setHours(23, 59, 59, 999);
  }
  return date.toISOString();
};

const resolveScopeType = (item: FleetCaseListItem) => {
  if (item.scope_type) return item.scope_type;
  if (item.scope?.card_alias || item.scope?.card_id) return "CARD";
  if (item.scope?.group_name || item.scope?.group_id) return "GROUP";
  return "CLIENT";
};

const isAutoBlocked = (item: FleetCaseListItem) => {
  const action = item.policy_action?.toString().toUpperCase();
  return action ? action.includes("AUTO_BLOCK") : false;
};

export function FleetIncidentsPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [cases, setCases] = useState<FleetCaseListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isForbidden, setIsForbidden] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [statusFilter, setStatusFilter] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");
  const [scopeFilter, setScopeFilter] = useState("");
  const [triggerFilter, setTriggerFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const canView = canViewFleetIncidents(user);

  const loadCases = useCallback(async () => {
    if (!user?.token) return;
    setLoading(true);
    setError(null);
    setIsForbidden(false);
    setUnavailable(false);
    try {
      const response = await listFleetCases(user.token, {
        status: statusFilter || undefined,
        severity_min: severityFilter || undefined,
        from: toIsoDate(dateFrom),
        to: toIsoDate(dateTo, true),
        scope_type: scopeFilter || undefined,
      });
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      setCases(response.items);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setIsForbidden(true);
        return;
      }
      setError(err instanceof Error ? err.message : t("fleetIncidents.errors.loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [dateFrom, dateTo, scopeFilter, severityFilter, statusFilter, t, user?.token]);

  useEffect(() => {
    if (!canView) return;
    void loadCases();
  }, [canView, loadCases]);

  const filteredCases = useMemo(() => {
    return cases.filter((item) => {
      const triggerOk = triggerFilter ? item.source?.type === triggerFilter : true;
      const scopeOk = scopeFilter ? resolveScopeType(item) === scopeFilter : true;
      return triggerOk && scopeOk;
    });
  }, [cases, scopeFilter, triggerFilter]);

  const summary = useMemo(() => {
    const openCount = cases.filter((item) => item.status === "OPEN").length;
    const inProgressCount = cases.filter((item) => item.status === "IN_PROGRESS").length;
    const closedCount = cases.filter((item) => item.status === "CLOSED").length;
    const last7dAutoBlocked = cases.filter((item) => {
      if (!item.opened_at || !isAutoBlocked(item)) return false;
      const diff = Date.now() - new Date(item.opened_at).getTime();
      return diff >= 0 && diff <= 7 * 24 * 60 * 60 * 1000;
    }).length;
    return { openCount, inProgressCount, closedCount, last7dAutoBlocked };
  }, [cases]);

  const handleResetFilters = () => {
    setStatusFilter("");
    setSeverityFilter("");
    setScopeFilter("");
    setTriggerFilter("");
    setDateFrom("");
    setDateTo("");
  };

  if (!canView) {
    return <AppForbiddenState message={t("fleetIncidents.errors.noPermission")} />;
  }

  if (loading) {
    return (
      <div className="page">
        <div className="page-header">
          <h1>{t("fleetIncidents.title")}</h1>
        </div>
        <div className="card state">{t("common.loading")}</div>
      </div>
    );
  }

  if (isForbidden) {
    return <AppForbiddenState message={t("fleetIncidents.errors.noPermission")} />;
  }

  if (unavailable) {
    return <FleetUnavailableState />;
  }

  if (error) {
    return (
      <div className="page">
        <div className="page-header">
          <h1>{t("fleetIncidents.title")}</h1>
        </div>
        <AppErrorState message={error} onRetry={() => void loadCases()} />
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>{t("fleetIncidents.title")}</h1>
        <div className="actions">
          <button type="button" className="secondary" onClick={() => void loadCases()}>
            {t("actions.refresh")}
          </button>
        </div>
      </div>
      <div className="summary-chips">
        <span className="summary-chip">{t("fleetIncidents.summary.open", { count: summary.openCount })}</span>
        <span className="summary-chip">
          {t("fleetIncidents.summary.inProgress", { count: summary.inProgressCount })}
        </span>
        <span className="summary-chip">{t("fleetIncidents.summary.closed", { count: summary.closedCount })}</span>
        <span className="summary-chip">
          {t("fleetIncidents.summary.autoBlocked", { count: summary.last7dAutoBlocked })}
        </span>
      </div>
      <div className="filters">
        <div className="filter">
          <span className="label">{t("fleetIncidents.filters.status")}</span>
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="">{t("fleetIncidents.filters.statusAll")}</option>
            <option value="OPEN">{t("fleetIncidents.status.open")}</option>
            <option value="IN_PROGRESS">{t("fleetIncidents.status.inProgress")}</option>
            <option value="CLOSED">{t("fleetIncidents.status.closed")}</option>
          </select>
        </div>
        <div className="filter">
          <span className="label">{t("fleetIncidents.filters.severity")}</span>
          <select value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value)}>
            <option value="">{t("fleetIncidents.filters.severityAll")}</option>
            {severityOrder.map((severity) => (
              <option key={severity} value={severity}>
                {severity}
              </option>
            ))}
          </select>
        </div>
        <div className="filter">
          <span className="label">{t("fleetIncidents.filters.scope")}</span>
          <select value={scopeFilter} onChange={(event) => setScopeFilter(event.target.value)}>
            <option value="">{t("fleetIncidents.filters.scopeAll")}</option>
            <option value="CARD">{t("fleetIncidents.filters.scopeCard")}</option>
            <option value="GROUP">{t("fleetIncidents.filters.scopeGroup")}</option>
          </select>
        </div>
        <div className="filter">
          <span className="label">{t("fleetIncidents.filters.trigger")}</span>
          <select value={triggerFilter} onChange={(event) => setTriggerFilter(event.target.value)}>
            <option value="">{t("fleetIncidents.filters.triggerAll")}</option>
            <option value="LIMIT_BREACH">{t("fleetIncidents.triggers.limitBreach")}</option>
            <option value="ANOMALY">{t("fleetIncidents.triggers.anomaly")}</option>
          </select>
        </div>
        <div className="filter">
          <span className="label">{t("fleetIncidents.filters.dateFrom")}</span>
          <input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} />
        </div>
        <div className="filter">
          <span className="label">{t("fleetIncidents.filters.dateTo")}</span>
          <input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} />
        </div>
        <div className="filter filter-actions">
          <span className="label">&nbsp;</span>
          <button type="button" className="ghost" onClick={handleResetFilters}>
            {t("actions.resetFilters")}
          </button>
        </div>
      </div>
      {filteredCases.length === 0 ? (
        <AppEmptyState title={t("fleetIncidents.emptyTitle")} description={t("fleetIncidents.emptyDescription")} />
      ) : (
        <div className="card">
          <table className="data-table">
            <thead>
              <tr>
                <th>{t("fleetIncidents.table.status")}</th>
                <th>{t("fleetIncidents.table.severity")}</th>
                <th>{t("fleetIncidents.table.title")}</th>
                <th>{t("fleetIncidents.table.scope")}</th>
                <th>{t("fleetIncidents.table.trigger")}</th>
                <th>{t("fleetIncidents.table.openedAt")}</th>
                <th>{t("fleetIncidents.table.updatedAt")}</th>
                <th>{t("fleetIncidents.table.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {filteredCases.map((item) => {
                const scopeType = resolveScopeType(item);
                const scopeLabel =
                  scopeType === "CARD"
                    ? item.scope?.card_alias || t("fleetIncidents.scope.cardFallback")
                    : scopeType === "GROUP"
                      ? item.scope?.group_name || t("fleetIncidents.scope.groupFallback")
                      : t("fleetIncidents.scope.client");
                const trigger = item.source?.type;
                const triggerLabel =
                  trigger === "LIMIT_BREACH"
                    ? t("fleetIncidents.triggers.limitBreach")
                    : trigger === "ANOMALY"
                      ? t("fleetIncidents.triggers.anomaly")
                      : trigger ?? "—";
                const statusLabel =
                  item.status === "OPEN"
                    ? t("fleetIncidents.status.open")
                    : item.status === "IN_PROGRESS"
                      ? t("fleetIncidents.status.inProgress")
                      : item.status === "CLOSED"
                        ? t("fleetIncidents.status.closed")
                        : item.status ?? "—";
                return (
                  <tr key={item.case_id}>
                    <td>
                      <span className={getFleetCaseStatusBadgeClass(item.status)}>
                        {statusLabel}
                      </span>
                    </td>
                    <td>
                      <span className={getFleetCaseSeverityBadgeClass(item.severity)}>{item.severity ?? "—"}</span>
                    </td>
                    <td>{item.title}</td>
                    <td>
                      <div>{scopeLabel}</div>
                      <div className="muted small">{scopeType}</div>
                    </td>
                    <td>
                      <span className={getFleetCaseTriggerBadgeClass(trigger)}>{triggerLabel}</span>
                    </td>
                    <td>{item.opened_at ? formatDateTime(item.opened_at) : "—"}</td>
                    <td>{item.last_updated_at ? formatDateTime(item.last_updated_at) : "—"}</td>
                    <td>
                      <div className="actions">
                        <Link className="ghost" to={`/fleet/incidents/${item.case_id}`}>
                          {t("fleetIncidents.table.open")}
                        </Link>
                        {item.policy_action ? (
                          <span className={getFleetCasePolicyActionBadgeClass(item.policy_action)}>
                            {item.policy_action}
                          </span>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
