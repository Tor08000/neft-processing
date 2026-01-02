import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../api/http";
import { listPolicies as listActionPolicies, listExecutions } from "../api/fleetPolicies";
import {
  listChannels,
  listPolicies as listNotificationPolicies,
} from "../api/fleetNotifications";
import { AppErrorState, AppForbiddenState } from "../components/states";
import { FleetUnavailableState } from "../components/FleetUnavailableState";
import { PolicyCenterTabs } from "../components/PolicyCenterTabs";
import { useI18n } from "../i18n";
import type { FleetPolicyExecution } from "../types/fleetPolicies";
import { canAdminFleetNotifications } from "../utils/fleetPermissions";

const toIsoDate = (value: Date, endOfDay = false) => {
  const date = new Date(value);
  if (endOfDay) {
    date.setHours(23, 59, 59, 999);
  }
  return date.toISOString();
};

export function FleetPolicyCenterOverviewPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isForbidden, setIsForbidden] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [actionPoliciesCount, setActionPoliciesCount] = useState(0);
  const [notificationPoliciesCount, setNotificationPoliciesCount] = useState<number | null>(null);
  const [channelsCount, setChannelsCount] = useState<number | null>(null);
  const [executions, setExecutions] = useState<FleetPolicyExecution[]>([]);
  const canAdminNotifications = canAdminFleetNotifications(user);

  const loadSummary = useCallback(async () => {
    if (!user?.token) return;
    setLoading(true);
    setError(null);
    setIsForbidden(false);
    setUnavailable(false);

    const from = toIsoDate(new Date(Date.now() - 7 * 24 * 60 * 60 * 1000));
    const to = toIsoDate(new Date(), true);

    try {
      const actionPromise = listActionPolicies(user.token);
      const executionsPromise = listExecutions(user.token, { from, to });
      const notificationPromise = canAdminNotifications ? listNotificationPolicies(user.token) : Promise.resolve(null);
      const channelsPromise = canAdminNotifications ? listChannels(user.token) : Promise.resolve(null);

      const [actionResponse, executionsResponse, notificationResponse, channelsResponse] = await Promise.all([
        actionPromise,
        executionsPromise,
        notificationPromise,
        channelsPromise,
      ]);

      if (actionResponse.unavailable || executionsResponse.unavailable) {
        setUnavailable(true);
        return;
      }

      if (notificationResponse?.unavailable || channelsResponse?.unavailable) {
        setUnavailable(true);
        return;
      }

      const activeActions = actionResponse.items.filter((policy) => policy.status !== "DISABLED").length;
      setActionPoliciesCount(activeActions);
      setExecutions(executionsResponse.items);

      if (notificationResponse) {
        const activeNotifications = notificationResponse.items.filter((policy) => policy.status !== "DISABLED").length;
        setNotificationPoliciesCount(activeNotifications);
      } else {
        setNotificationPoliciesCount(null);
      }

      if (channelsResponse) {
        const activeChannels = channelsResponse.items.filter((channel) => channel.status !== "DISABLED").length;
        setChannelsCount(activeChannels);
      } else {
        setChannelsCount(null);
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setIsForbidden(true);
        return;
      }
      setError(err instanceof Error ? err.message : t("policyCenter.errors.loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [canAdminNotifications, t, user?.token]);

  useEffect(() => {
    void loadSummary();
  }, [loadSummary]);

  const activePolicies = useMemo(
    () => actionPoliciesCount + (notificationPoliciesCount ?? 0),
    [actionPoliciesCount, notificationPoliciesCount],
  );

  const autoBlockCount = useMemo(
    () => executions.filter((execution) => execution.action === "AUTO_BLOCK_CARD").length,
    [executions],
  );

  const failuresCount = useMemo(
    () => executions.filter((execution) => execution.status === "FAILED").length,
    [executions],
  );

  if (unavailable) {
    return <FleetUnavailableState />;
  }

  if (isForbidden) {
    return <AppForbiddenState message={t("policyCenter.errors.noPermission")} />;
  }

  if (error) {
    return (
      <div className="page">
        <div className="page-header">
          <h1>{t("policyCenter.title")}</h1>
        </div>
        <PolicyCenterTabs />
        <AppErrorState message={error} onRetry={() => void loadSummary()} />
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>{t("policyCenter.title")}</h1>
        <div className="actions">
          <Link to="/fleet/policy-center/actions" className="primary">
            {t("policyCenter.cta.createRule")}
          </Link>
          <Link to="/fleet/policy-center/channels" className="secondary">
            {t("policyCenter.cta.connectChannel")}
          </Link>
          <button type="button" className="secondary" onClick={() => void loadSummary()}>
            {t("actions.refresh")}
          </button>
        </div>
      </div>
      <PolicyCenterTabs />
      {loading ? (
        <div className="card state">{t("common.loading")}</div>
      ) : (
        <div className="stats-grid">
          <div className="stat">
            <div className="stat__label">{t("policyCenter.summary.activePolicies")}</div>
            <div className="stat__value">{activePolicies}</div>
          </div>
          <div className="stat">
            <div className="stat__label">{t("policyCenter.summary.channelsConnected")}</div>
            <div className="stat__value">
              {channelsCount === null ? t("policyCenter.summary.notAvailable") : channelsCount}
            </div>
          </div>
          <div className="stat">
            <div className="stat__label">{t("policyCenter.summary.autoBlocks")}</div>
            <div className="stat__value">{autoBlockCount}</div>
          </div>
          <div className="stat">
            <div className="stat__label">{t("policyCenter.summary.messagesSent")}</div>
            <div className="stat__value">{t("policyCenter.summary.notAvailable")}</div>
          </div>
          <div className="stat">
            <div className="stat__label">{t("policyCenter.summary.failures")}</div>
            <div className="stat__value">{failuresCount}</div>
          </div>
        </div>
      )}
    </div>
  );
}
