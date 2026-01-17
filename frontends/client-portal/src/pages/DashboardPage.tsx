import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchClientDashboard } from "../api/portal";
import type { ClientDashboardResponse } from "../types/portal";
import { useAuth } from "../auth/AuthContext";
import { ApiError, UnauthorizedError } from "../api/http";
import { StatusPage } from "../components/StatusPage";
import { AppLoadingState } from "../components/states";
import { DashboardRenderer } from "./dashboard/DashboardRenderer";

const REFRESH_INTERVAL_MS = 60_000;

export function DashboardPage() {
  const { user, logout } = useAuth();
  const [dashboard, setDashboard] = useState<ClientDashboardResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lastFetchedRef = useRef(0);

  const loadDashboard = useCallback(
    async (force = false) => {
      if (!user) return;
      if (!force && Date.now() - lastFetchedRef.current < REFRESH_INTERVAL_MS) {
        return;
      }
      setIsLoading(true);
      setError(null);
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
          setError("Не удалось загрузить дашборд. Попробуйте позже.");
          return;
        }
        console.error("Не удалось загрузить дашборд", err);
        setError("Дашборд временно недоступен");
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

  if (error) {
    return (
      <StatusPage
        title="Дашборд недоступен"
        description={error}
        actionLabel="Попробовать снова"
        actionTo="/dashboard"
        secondaryAction={
          <button type="button" className="neft-button neft-btn-primary" onClick={() => loadDashboard(true)}>
            Обновить
          </button>
        }
      />
    );
  }

  return <div className="stack">{content}</div>;
}
