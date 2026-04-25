import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchClientDashboard } from "../api/portal";
import type { ClientDashboardResponse } from "../types/portal";
import { useAuth } from "../auth/AuthContext";
import { ApiError, UnauthorizedError } from "../api/http";
import { AppLoadingState } from "../components/states";
import { DashboardRenderer } from "./dashboard/DashboardRenderer";
import { AccessState, resolveAccessState } from "../access/accessState";
import { AccessStateView, PortalStateView } from "../components/AccessGate";
import { useClient } from "../auth/ClientContext";
import { EmptyState } from "@shared/brand/components";

const REFRESH_INTERVAL_MS = 60_000;
const DASHBOARD_SUBTITLES: Record<string, string> = {
  OWNER: "Ключевые расходы, сервисное здоровье и следующие управленческие действия по вашему контуру.",
  ACCOUNTANT: "Документы, выгрузки и billing-сигналы, которые помогают закрыть период без лишних переходов.",
  FLEET_MANAGER: "Карты, лимиты и предупреждения собраны в одном рабочем контуре для fleet-менеджера.",
  DRIVER: "Быстрый доступ к картам, операциям и лимитам без лишнего операторского шума.",
};

const DASHBOARD_EMPTY_ACTIONS: Record<string, { label: string; to: string }> = {
  OWNER: { label: "Открыть аналитику", to: "/client/analytics" },
  ACCOUNTANT: { label: "Открыть документы", to: "/client/documents" },
  FLEET_MANAGER: { label: "Открыть карты", to: "/cards" },
  DRIVER: { label: "Открыть операции", to: "/operations" },
};

export function DashboardPage() {
  const { user, logout } = useAuth();
  const { client, isLoading: clientLoading, error: portalError, portalState, refresh } = useClient();
  const [dashboard, setDashboard] = useState<ClientDashboardResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<{ message: string; status?: number; correlationId?: string | null; requestId?: string | null } | null>(null);
  const [blockedState, setBlockedState] = useState<AccessState | null>(null);
  const lastFetchedRef = useRef(0);

  const accessDecision = useMemo(() => resolveAccessState({ client }), [client]);

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
      if (!dashboard.widgets.length) {
        const action = DASHBOARD_EMPTY_ACTIONS[dashboard.role] ?? DASHBOARD_EMPTY_ACTIONS.OWNER;
        return (
          <EmptyState
            title="Дашборд готов, но ещё не наполнен рабочими сигналами"
            description="Первые карточки появятся после документов, операций, тикетов или аналитики по вашей компании."
            hint="Откройте ближайший рабочий раздел или обновите страницу позже, когда появятся новые события."
            primaryAction={action}
          />
        );
      }
      return <DashboardRenderer dashboard={dashboard} />;
    }
    return null;
  }, [dashboard, isLoading]);

  if (clientLoading) {
    return <AppLoadingState label="Проверяем доступ..." />;
  }

  const portalStateView = PortalStateView({ state: portalState, error: portalError, onRetry: refresh, isDemo: false });
  if (portalStateView) {
    return portalStateView;
  }

  if (blockedState) {
    return <AccessStateView state={blockedState} title="Дашборд" error={portalError} isDemo={false} />;
  }

  if (error) {
    return (
      <EmptyState
        title="Дашборд временно недоступен"
        description={error.message}
        hint={
          <>
            {error.status ? <div>Код ошибки: {error.status}</div> : null}
            {error.requestId ? <div>Request ID: {error.requestId}</div> : null}
            {error.correlationId ? <div>Correlation ID: {error.correlationId}</div> : null}
          </>
        }
        primaryAction={{
          label: "Повторить",
          onClick: () => {
            void loadDashboard(true);
          },
        }}
      />
    );
  }

  return (
    <div className="stack">
      <div className="page-header">
        <div>
          <h1>Рабочий стол</h1>
          <p className="muted">
            {dashboard
              ? DASHBOARD_SUBTITLES[dashboard.role] ?? DASHBOARD_SUBTITLES.OWNER
              : "Показываем только реальные сигналы и следующие шаги по вашей компании."}
          </p>
        </div>
        <button type="button" className="ghost" onClick={() => loadDashboard(true)} disabled={isLoading}>
          {isLoading ? "Обновляем..." : "Обновить"}
        </button>
      </div>
      {content}
    </div>
  );
}
