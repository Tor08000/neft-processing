import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchClientDashboard } from "../api/portal";
import type { ClientDashboardResponse } from "../types/portal";
import { useAuth } from "../auth/AuthContext";
import { ApiError, UnauthorizedError } from "../api/http";
import { AppLoadingState, AppErrorState } from "../components/states";
import { DashboardRenderer } from "./dashboard/DashboardRenderer";
import { AccessState, resolveAccessState } from "../access/accessState";
import { AccessStateView, PortalStateView } from "../components/AccessGate";
import { useClient } from "../auth/ClientContext";
import { isDemoClient } from "@shared/demo/demo";

const REFRESH_INTERVAL_MS = 60_000;

export function DashboardPage() {
  const { user, logout } = useAuth();
  const { client, isLoading: clientLoading, error: portalError, portalState, refresh } = useClient();
  const [dashboard, setDashboard] = useState<ClientDashboardResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<{ message: string; status?: number; correlationId?: string | null; requestId?: string | null } | null>(null);
  const [blockedState, setBlockedState] = useState<AccessState | null>(null);
  const lastFetchedRef = useRef(0);

  const accessDecision = useMemo(() => resolveAccessState({ client }), [client]);
  const isDemoClientAccount = isDemoClient(user?.email ?? client?.user?.email ?? null);

  const loadDashboard = useCallback(
    async (force = false) => {
      if (!user) return;
      if (!force && Date.now() - lastFetchedRef.current < REFRESH_INTERVAL_MS) {
        return;
      }
      setIsLoading(true);
      setError(null);
      setBlockedState(null);
      try {
        const response = await fetchClientDashboard(user);
        lastFetchedRef.current = Date.now();
        setDashboard(response);
      } catch (err) {
        if (err instanceof UnauthorizedError) {
          logout();
          return;
        }
        if (err instanceof ApiError) {
          setError({
            message: "Не удалось загрузить дашборд. Попробуйте позже.",
            status: err.status,
            correlationId: err.correlationId,
            requestId: err.requestId,
          });
          return;
        }
        console.error("Не удалось загрузить дашборд", err);
        setError({ message: "Ошибка приложения" });
      } finally {
        setIsLoading(false);
      }
    },
    [logout, user],
  );

  useEffect(() => {
    if (!user || clientLoading) {
      return;
    }
    if (portalState !== "READY") {
      return;
    }
    if (accessDecision.state !== AccessState.ACTIVE) {
      setBlockedState(accessDecision.state);
      return;
    }
    void loadDashboard(true);
  }, [accessDecision.state, clientLoading, loadDashboard, portalState, user]);

  const content = useMemo(() => {
    if (!dashboard && isLoading) {
      return <AppLoadingState label="Загружаем дашборд" />;
    }
    if (dashboard) {
      return <DashboardRenderer dashboard={dashboard} />;
    }
    return null;
  }, [dashboard, isLoading]);

  if (clientLoading) {
    return <AppLoadingState label="Проверяем доступ..." />;
  }

  const portalStateView = PortalStateView({ state: portalState, error: portalError, onRetry: refresh, isDemo: isDemoClientAccount });
  if (portalStateView) {
    return portalStateView;
  }

  if (blockedState) {
    return <AccessStateView state={blockedState} title="Дашборд" error={portalError} />;
  }

  if (error) {
    return (
      <AppErrorState
        message={
          <>
            {error.message}
            {error.requestId ? <div>Request ID: {error.requestId}</div> : null}
          </>
        }
        status={error.status}
        correlationId={error.correlationId ?? undefined}
        onRetry={() => loadDashboard(true)}
      />
    );
  }

  return <div className="stack">{content}</div>;
}
