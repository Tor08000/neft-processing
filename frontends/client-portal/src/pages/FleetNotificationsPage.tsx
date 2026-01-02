import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n";
import { AppEmptyState, AppErrorState, AppForbiddenState } from "../components/states";
import { FleetUnavailableState } from "../components/FleetUnavailableState";
import { ConfirmActionModal } from "../components/ConfirmActionModal";
import { Toast } from "../components/Toast/Toast";
import { useToast } from "../components/Toast/useToast";
import { ApiError } from "../api/http";
import { listAlerts, ackAlert, ignoreAlert, listChannels } from "../api/fleetNotifications";
import type { FleetAlert } from "../types/fleetNotifications";
import { canAckFleetNotifications, canAdminFleetNotifications, canViewFleetNotifications } from "../utils/fleetPermissions";
import { formatDateTime } from "../utils/format";

const severityOrder = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];

const getSeverityBadgeClass = (severity?: string | null) => {
  const normalized = severity?.toUpperCase();
  if (normalized === "LOW") return "badge badge-muted";
  if (normalized === "MEDIUM") return "badge badge-info";
  if (normalized === "HIGH") return "badge badge-warning";
  if (normalized === "CRITICAL") return "badge badge-error";
  return "badge badge-muted";
};

const getStatusBadgeClass = (status?: string | null) => {
  const normalized = status?.toUpperCase();
  if (normalized === "OPEN") return "badge badge-warning";
  if (normalized === "ACKED") return "badge badge-info";
  if (normalized === "IGNORED") return "badge badge-muted";
  return "badge badge-muted";
};

const formatRelativeTime = (value?: string | null) => {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const diffMs = date.getTime() - Date.now();
  const diffMinutes = Math.round(diffMs / (1000 * 60));
  const diffHours = Math.round(diffMs / (1000 * 60 * 60));
  const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24));
  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  if (Math.abs(diffMinutes) < 60) return formatter.format(diffMinutes, "minute");
  if (Math.abs(diffHours) < 24) return formatter.format(diffHours, "hour");
  return formatter.format(diffDays, "day");
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

const typeIcons: Record<string, string> = {
  LIMIT_BREACH: "⚠️",
  ANOMALY: "📈",
  INGEST_FAILED: "🔌",
};

export function FleetNotificationsPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const { toast, showToast } = useToast();
  const [alerts, setAlerts] = useState<FleetAlert[]>([]);
  const [channelsCount, setChannelsCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isForbidden, setIsForbidden] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [severityFilter, setSeverityFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [scopeFilter, setScopeFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [expandedAlerts, setExpandedAlerts] = useState<Record<string, boolean>>({});
  const [ignoreTarget, setIgnoreTarget] = useState<FleetAlert | null>(null);
  const [ignoreReason, setIgnoreReason] = useState("");

  const canView = canViewFleetNotifications(user);
  const canAck = canAckFleetNotifications(user);
  const canAdmin = canAdminFleetNotifications(user);

  const loadAlerts = useCallback(async () => {
    if (!user?.token) return;
    setLoading(true);
    setError(null);
    setIsForbidden(false);
    setUnavailable(false);
    try {
      const [alertsResponse, channelsResponse] = await Promise.all([
        listAlerts(user.token, {
          status: statusFilter || undefined,
          severity_min: severityFilter || undefined,
          from: toIsoDate(dateFrom),
          to: toIsoDate(dateTo, true),
        }),
        listChannels(user.token),
      ]);
      if (alertsResponse.unavailable || channelsResponse.unavailable) {
        setUnavailable(true);
        return;
      }
      setAlerts(alertsResponse.items);
      setChannelsCount(channelsResponse.items.length);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setIsForbidden(true);
        return;
      }
      setError(err instanceof Error ? err.message : t("fleetNotifications.errors.loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [dateFrom, dateTo, severityFilter, statusFilter, t, user?.token]);

  useEffect(() => {
    if (!canView) return;
    void loadAlerts();
  }, [canView, loadAlerts]);

  const filteredAlerts = useMemo(() => {
    return alerts.filter((alert) => {
      const typeOk = typeFilter ? alert.type === typeFilter : true;
      const scopeOk = scopeFilter ? alert.scope_type === scopeFilter : true;
      return typeOk && scopeOk;
    });
  }, [alerts, scopeFilter, typeFilter]);

  const summary = useMemo(() => {
    const openCount = alerts.filter((alert) => alert.status === "OPEN").length;
    const highCriticalCount = alerts.filter((alert) => ["HIGH", "CRITICAL"].includes(alert.severity ?? "")).length;
    const last24hCount = alerts.filter((alert) => {
      if (!alert.occurred_at) return false;
      const diff = Date.now() - new Date(alert.occurred_at).getTime();
      return diff >= 0 && diff <= 24 * 60 * 60 * 1000;
    }).length;
    return { openCount, highCriticalCount, last24hCount };
  }, [alerts]);

  const handleAck = useCallback(
    async (alert: FleetAlert) => {
      if (!user?.token) return;
      try {
        const response = await ackAlert(user.token, alert.id);
        if (response.unavailable) {
          setUnavailable(true);
          return;
        }
        const updated = response.item ?? { ...alert, status: "ACKED" };
        setAlerts((prev) => prev.map((item) => (item.id === alert.id ? { ...item, ...updated } : item)));
        showToast({ kind: "success", text: t("fleetNotifications.alerts.acked") });
      } catch (err) {
        if (err instanceof ApiError && err.status === 403) {
          showToast({ kind: "error", text: t("fleetNotifications.errors.noPermission") });
          return;
        }
        showToast({ kind: "error", text: err instanceof Error ? err.message : t("fleetNotifications.errors.actionFailed") });
      }
    },
    [showToast, t, user?.token],
  );

  const handleIgnoreConfirm = useCallback(async () => {
    if (!user?.token || !ignoreTarget) return;
    try {
      const response = await ignoreAlert(user.token, ignoreTarget.id, { reason: ignoreReason.trim() });
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      const updated = response.item ?? { ...ignoreTarget, status: "IGNORED" };
      setAlerts((prev) => prev.map((item) => (item.id === ignoreTarget.id ? { ...item, ...updated } : item)));
      showToast({ kind: "success", text: t("fleetNotifications.alerts.ignored") });
      setIgnoreTarget(null);
      setIgnoreReason("");
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        showToast({ kind: "error", text: t("fleetNotifications.errors.noPermission") });
        return;
      }
      showToast({ kind: "error", text: err instanceof Error ? err.message : t("fleetNotifications.errors.actionFailed") });
    }
  }, [ignoreReason, ignoreTarget, showToast, t, user?.token]);

  const handleResetFilters = () => {
    setSeverityFilter("");
    setStatusFilter("");
    setTypeFilter("");
    setScopeFilter("");
    setDateFrom("");
    setDateTo("");
  };

  if (!canView) {
    return <AppForbiddenState message={t("fleetNotifications.errors.noPermission")} />;
  }

  if (loading) {
    return (
      <div className="page">
        <div className="page-header">
          <h1>{t("fleetNotifications.alerts.title")}</h1>
        </div>
        <div className="card state">{t("common.loading")}</div>
      </div>
    );
  }

  if (isForbidden) {
    return <AppForbiddenState message={t("fleetNotifications.errors.noPermission")} />;
  }

  if (unavailable) {
    return <FleetUnavailableState />;
  }

  if (error) {
    return (
      <div className="page">
        <div className="page-header">
          <h1>{t("fleetNotifications.alerts.title")}</h1>
        </div>
        <AppErrorState message={error} onRetry={() => void loadAlerts()} />
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>{t("fleetNotifications.alerts.title")}</h1>
        <div className="actions">
          <button type="button" className="secondary" onClick={() => void loadAlerts()}>
            {t("actions.refresh")}
          </button>
        </div>
      </div>
      <div className="summary-chips">
        <span className="summary-chip">{t("fleetNotifications.alerts.summaryOpen", { count: summary.openCount })}</span>
        <span className="summary-chip">
          {t("fleetNotifications.alerts.summaryHighCritical", { count: summary.highCriticalCount })}
        </span>
        <span className="summary-chip">
          {t("fleetNotifications.alerts.summaryLast24h", { count: summary.last24hCount })}
        </span>
      </div>
      <div className="filters">
        <div className="filter">
          <span className="label">{t("fleetNotifications.alerts.severity")}</span>
          <select value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value)}>
            <option value="">{t("fleetNotifications.alerts.severityAll")}</option>
            {severityOrder.map((severity) => (
              <option key={severity} value={severity}>
                {severity}
              </option>
            ))}
          </select>
        </div>
        <div className="filter">
          <span className="label">{t("fleetNotifications.alerts.status")}</span>
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="">{t("fleetNotifications.alerts.statusAll")}</option>
            <option value="OPEN">{t("fleetNotifications.alerts.statusOpen")}</option>
            <option value="ACKED">{t("fleetNotifications.alerts.statusAcked")}</option>
            <option value="IGNORED">{t("fleetNotifications.alerts.statusIgnored")}</option>
          </select>
        </div>
        <div className="filter">
          <span className="label">{t("fleetNotifications.alerts.type")}</span>
          <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}>
            <option value="">{t("fleetNotifications.alerts.typeAll")}</option>
            <option value="LIMIT_BREACH">{t("fleetNotifications.alerts.typeLimit")}</option>
            <option value="ANOMALY">{t("fleetNotifications.alerts.typeAnomaly")}</option>
            <option value="INGEST_FAILED">{t("fleetNotifications.alerts.typeIngest")}</option>
          </select>
        </div>
        <div className="filter">
          <span className="label">{t("fleetNotifications.alerts.scope")}</span>
          <select value={scopeFilter} onChange={(event) => setScopeFilter(event.target.value)}>
            <option value="">{t("fleetNotifications.alerts.scopeAll")}</option>
            <option value="CARD">{t("fleetNotifications.alerts.scopeCard")}</option>
            <option value="GROUP">{t("fleetNotifications.alerts.scopeGroup")}</option>
          </select>
        </div>
        <div className="filter">
          <span className="label">{t("fleetNotifications.alerts.dateFrom")}</span>
          <input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} />
        </div>
        <div className="filter">
          <span className="label">{t("fleetNotifications.alerts.dateTo")}</span>
          <input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} />
        </div>
        <div className="filter filter-actions">
          <span className="label">&nbsp;</span>
          <button type="button" className="ghost" onClick={handleResetFilters}>
            {t("actions.resetFilters")}
          </button>
        </div>
      </div>
      {!filteredAlerts.length ? (
        <AppEmptyState
          title={
            channelsCount === 0
              ? t("fleetNotifications.alerts.emptyChannelsTitle")
              : t("fleetNotifications.alerts.emptyTitle")
          }
          description={
            channelsCount === 0
              ? t("fleetNotifications.alerts.emptyChannelsDescription")
              : t("fleetNotifications.alerts.emptyDescription")
          }
          action={
            channelsCount === 0 && canAdmin ? (
              <Link className="primary" to="/fleet/notifications/channels">
                {t("fleetNotifications.alerts.emptyChannelsAction")}
              </Link>
            ) : null
          }
        />
      ) : (
        <div className="alert-list">
          {filteredAlerts.map((alert) => {
            const typeLabel =
              alert.type === "LIMIT_BREACH"
                ? t("fleetNotifications.alerts.typeLimit")
                : alert.type === "ANOMALY"
                  ? t("fleetNotifications.alerts.typeAnomaly")
                  : alert.type === "INGEST_FAILED"
                    ? t("fleetNotifications.alerts.typeIngest")
                    : alert.type ?? "—";
            const icon = alert.type ? typeIcons[alert.type] : undefined;
            const scopeLabel =
              alert.scope_type === "CARD"
                ? alert.card_alias || t("fleetNotifications.alerts.scopeCardFallback")
                : alert.scope_type === "GROUP"
                  ? alert.group_name || t("fleetNotifications.alerts.scopeGroupFallback")
                  : t("fleetNotifications.alerts.scopeClient");
            const details = [
              alert.why,
              alert.rule_name ? t("fleetNotifications.alerts.ruleName", { rule: alert.rule_name }) : null,
              (alert.observed_value !== null && alert.observed_value !== undefined) ||
              (alert.baseline_value !== null && alert.baseline_value !== undefined)
                ? t("fleetNotifications.alerts.observedVsBaseline", {
                    observed: alert.observed_value ?? "—",
                    baseline: alert.baseline_value ?? "—",
                  })
                : null,
              alert.limit_value ? t("fleetNotifications.alerts.limitValue", { value: alert.limit_value }) : null,
              alert.merchant ? t("fleetNotifications.alerts.merchantValue", { value: alert.merchant }) : null,
              alert.category ? t("fleetNotifications.alerts.categoryValue", { value: alert.category }) : null,
            ].filter(Boolean);
            const isExpanded = expandedAlerts[alert.id];
            const occurredTooltip = alert.occurred_at ? formatDateTime(alert.occurred_at) : "";
            return (
              <div
                key={alert.id}
                className={`alert-card ${alert.status && alert.status !== "OPEN" ? "alert-card--resolved" : ""}`}
              >
                <div className="alert-card__header">
                  <div className="alert-card__meta">
                    <span className={getSeverityBadgeClass(alert.severity)}>{alert.severity ?? "—"}</span>
                    <span className="alert-type">
                      {icon ? <span className="alert-type__icon">{icon}</span> : null}
                      {typeLabel}
                    </span>
                  </div>
                  <div className="alert-card__status">
                    <span className={getStatusBadgeClass(alert.status)}>{alert.status ?? "—"}</span>
                  </div>
                </div>
                <div className="alert-card__summary">{alert.summary ?? t("fleetNotifications.alerts.summaryFallback")}</div>
                <div className="alert-card__scope">
                  <span>{t("fleetNotifications.alerts.scopeLabel", { value: scopeLabel })}</span>
                  <span className="alert-time" title={occurredTooltip}>
                    {formatRelativeTime(alert.occurred_at)}
                  </span>
                </div>
                <div className="alert-card__actions">
                  {alert.card_id ? (
                    <Link className="ghost" to={`/fleet/cards/${alert.card_id}`}>
                      {t("fleetNotifications.alerts.viewCard")}
                    </Link>
                  ) : null}
                  {alert.group_id ? (
                    <Link className="ghost" to={`/fleet/groups/${alert.group_id}`}>
                      {t("fleetNotifications.alerts.viewGroup")}
                    </Link>
                  ) : null}
                  <Link className="ghost" to="/fleet/spend">
                    {t("fleetNotifications.alerts.viewSpend")}
                  </Link>
                  <button type="button" className="link-button" onClick={() => setExpandedAlerts((prev) => ({ ...prev, [alert.id]: !isExpanded }))}>
                    {isExpanded ? t("fleetNotifications.alerts.hideDetails") : t("fleetNotifications.alerts.showDetails")}
                  </button>
                </div>
                {isExpanded ? (
                  <div className="alert-card__details">
                    <h4>{t("fleetNotifications.alerts.whyTitle")}</h4>
                    {details.length ? (
                      <ul>
                        {details.map((detail, index) => (
                          <li key={`${alert.id}-detail-${index}`}>{detail}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="muted">{t("fleetNotifications.alerts.whyEmpty")}</p>
                    )}
                  </div>
                ) : null}
                <div className="alert-card__footer">
                  {canAck ? (
                    <button type="button" className="secondary" onClick={() => void handleAck(alert)}>
                      {t("fleetNotifications.alerts.ack")}
                    </button>
                  ) : null}
                  {canAdmin ? (
                    <button
                      type="button"
                      className="ghost"
                      onClick={() => {
                        setIgnoreTarget(alert);
                        setIgnoreReason("");
                      }}
                    >
                      {t("fleetNotifications.alerts.ignore")}
                    </button>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      )}
      <ConfirmActionModal
        isOpen={!!ignoreTarget}
        title={t("fleetNotifications.alerts.ignoreTitle")}
        description={t("fleetNotifications.alerts.ignoreDescription")}
        confirmLabel={t("fleetNotifications.alerts.ignoreConfirm")}
        cancelLabel={t("actions.comeBackLater")}
        onConfirm={() => void handleIgnoreConfirm()}
        onCancel={() => setIgnoreTarget(null)}
        isConfirmDisabled={!ignoreReason.trim()}
      >
        <label className="form-field">
          <span>{t("fleetNotifications.alerts.ignoreReason")}</span>
          <textarea
            value={ignoreReason}
            onChange={(event) => setIgnoreReason(event.target.value)}
            placeholder={t("fleetNotifications.alerts.ignoreReasonPlaceholder")}
          />
        </label>
      </ConfirmActionModal>
      <Toast toast={toast} />
    </div>
  );
}
