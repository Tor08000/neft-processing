import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchClientDashboard } from "../api/portal";
import type { ClientDashboardResponse } from "../types/portal";
import { useAuth } from "../auth/AuthContext";
import { ApiError, UnauthorizedError } from "../api/http";
import { AppLoadingState, AppErrorState } from "../components/states";
import { DashboardRenderer } from "./dashboard/DashboardRenderer";
import { AccessState, mapBusinessErrorToAccessState } from "../access/accessState";
import { AccessStateView } from "../components/AccessGate";

const REFRESH_INTERVAL_MS = 60_000;

export function DashboardPage() {
  const { user, logout } = useAuth();
  const [dashboard, setDashboard] = useState<ClientDashboardResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<{ message: string; status?: number; correlationId?: string | null; requestId?: string | null } | null>(null);
  const [blockedState, setBlockedState] = useState<AccessState | null>(null);
  const lastFetchedRef = useRef(0);

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
          const businessState = mapBusinessErrorToAccessState(err.errorCode);
          if (businessState) {
            setBlockedState(businessState);
            return;
          }
          setError({
            message: "Не удалось загрузить дашборд. Попробуйте позже.",
            status: err.status,
            correlationId: err.correlationId,
            requestId: err.requestId,
          });
          return;
        }
        console.error("Не удалось загрузить дашборд", err);
        setError({ message: "Дашборд временно недоступен" });
      } finally {
        setIsLoading(false);
      }
    },
    [logout, user],
  );

  useEffect(() => {
    void loadDashboard(true);
  }, [loadDashboard]);

  const content = useMemo(() => {
    if (!dashboard && isLoading) {
      return <AppLoadingState label="Загружаем дашборд" />;
    }
    if (dashboard) {
      return <DashboardRenderer dashboard={dashboard} />;
    }
    return null;
  }, [dashboard, isLoading]);

  if (blockedState) {
    return <AccessStateView state={blockedState} title="Дашборд" />;
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
