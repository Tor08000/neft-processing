import { useState, type ReactNode } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { useClient, type PortalError, type PortalState } from "../auth/ClientContext";
import { useAuth } from "../auth/AuthContext";
import { AccessState, resolveAccessState } from "../access/accessState";
import { DemoEmptyState } from "./DemoEmptyState";
import { AppErrorState, AppForbiddenState, AppLoadingState } from "./states";
import { StatusPage } from "./StatusPage";
import { ModuleUnavailablePage } from "../pages/ModuleUnavailablePage";
import { BillingOverdueState } from "./BillingOverdueState";
import { isDemoClient } from "@shared/demo/demo";
import { useClientJourney } from "../auth/ClientJourneyContext";
import { getPlanByCode } from "@shared/subscriptions/catalog";

type AccessGateProps = {
  capability?: string;
  module?: string;
  requiredRoles?: string[];
  fallbackMode?: "paywall" | "activation" | "forbidden";
  title?: string;
  children: ReactNode;
};

const DiagnosticsSummary = ({ error }: { error?: PortalError | null }) => {
  if (!error) return null;
  return (
    <div className="muted small">
      {error.path ? <div>Endpoint: {error.path}</div> : null}
      {error.status ? <div>Status: {error.status}</div> : null}
      {error.requestId ? <div>Request ID: {error.requestId}</div> : null}
    </div>
  );
};

const DiagnosticsDetails = ({ error }: { error?: PortalError | null }) => {
  const [isOpen, setIsOpen] = useState(false);
  if (!error) return null;
  if (!import.meta.env.DEV) {
    return <DiagnosticsSummary error={error} />;
  }
  return (
    <div className="stack">
      <DiagnosticsSummary error={error} />
      <button type="button" className="ghost neft-btn-secondary" onClick={() => setIsOpen((prev) => !prev)}>
        {isOpen ? "Скрыть диагностику" : "Показать диагностику"}
      </button>
      {isOpen ? (
        <div className="muted small">
          {error.message ? <div>Error: {error.message}</div> : null}
          {error.kind ? <div>Kind: {error.kind}</div> : null}
        </div>
      ) : null}
    </div>
  );
};

const PortalStateView = ({
  state,
  error,
  onRetry,
  isDemo,
}: {
  state: PortalState;
  error?: PortalError | null;
  onRetry?: () => void;
  isDemo: boolean;
}) => {
  switch (state) {
    case "AUTH_REQUIRED":
      return <Navigate to="/login" replace />;
    case "FORBIDDEN":
      if (isDemo) return null;
      return (
        <StatusPage
          title="Доступ ограничен"
          description={
            <>
              Недостаточно прав для доступа к порталу.
              <DiagnosticsDetails error={error} />
            </>
          }
          actionLabel="Вернуться на дашборд"
          actionTo="/dashboard"
        />
      );
    case "SERVICE_UNAVAILABLE":
      if (isDemo) return null;
      return (
        <AppErrorState
          message={
            <>
              Сервис временно недоступен. Попробуйте позже.
              <DiagnosticsDetails error={error} />
            </>
          }
          onRetry={onRetry}
          status={error?.status}
        />
      );
    case "NETWORK_DOWN":
      if (isDemo) return null;
      return (
        <AppErrorState
          message={
            <>
              Нет соединения с сервером. Проверьте подключение к интернету.
              <DiagnosticsDetails error={error} />
            </>
          }
          onRetry={onRetry}
          status={error?.status}
        />
      );
    case "API_MISCONFIGURED":
      if (isDemo) return null;
      return (
        <AppErrorState
          message={
            <>
              Версия API не совпала или маршрут недоступен.
              <DiagnosticsDetails error={error} />
            </>
          }
          onRetry={onRetry}
          status={error?.status}
        />
      );
    case "ERROR_FATAL":
      if (isDemo) return null;
      return (
        <AppErrorState
          message={
            <>
              {error?.message ?? "Ошибка приложения"}
              <DiagnosticsDetails error={error} />
            </>
          }
          onRetry={onRetry}
          status={error?.status}
        />
      );
    case "LOADING":
    case "READY":
    default:
      return null;
  }
};


const LimitedCabinetProgress = () => {
  const { state, nextRoute, draft } = useClientJourney();
  const plan = getPlanByCode(draft.selectedPlan);
  return (
    <div className="stack muted small" style={{ marginTop: 8 }}>
      <div>Current stage: {state}</div>
      <div>Selected plan: {plan?.title ?? "Not selected"}</div>
      <div>Customer type: {draft.customerType ?? "Not selected"}</div>
      <div>Next step: {nextRoute}</div>
    </div>
  );
};

const AccessStateView = ({
  state,
  title = "Раздел",
  reason,
  requestId,
  correlationId,
  error,
  homePath,
  isDemo = false,
}: {
  state: AccessState;
  title?: string;
  reason?: string | null;
  requestId?: string | null;
  correlationId?: string | null;
  error?: PortalError | null;
  homePath?: string;
  isDemo?: boolean;
}) => {
  const { user } = useAuth();
  const fallbackHome = homePath ?? (user ? "/" : "/login");
  switch (state) {
    case AccessState.NEEDS_ONBOARDING:
      return (
        <StatusPage
          title="Подключить компанию"
          description={<>Завершите подключение компании, чтобы открыть этот раздел.<LimitedCabinetProgress /></>}
          actionLabel="Перейти к подключению"
          actionTo="/connect"
        />
      );
    case AccessState.NEEDS_PLAN:
      return (
        <StatusPage
          title="Выберите тариф"
          description={<>Для доступа к разделу нужен активный тариф.<LimitedCabinetProgress /></>}
          actionLabel="Продолжить подключение"
          actionTo="/connect/plan"
          secondaryAction={
            <Link className="ghost neft-btn-secondary" to="/client/support/new?topic=plan">
              Связаться с менеджером
            </Link>
          }
        />
      );
    case AccessState.NEEDS_CONTRACT:
      return (
        <StatusPage
          title="Подпишите договор"
          description={<>Завершите подписание договора, чтобы открыть этот раздел.<LimitedCabinetProgress /></>}
          actionLabel="Перейти к подписанию"
          actionTo="/connect/sign"
        />
      );
    case AccessState.OVERDUE:
      return (
        <StatusPage
          title="Оплатите счёт"
          description="Доступ ограничен из-за просроченных счетов."
          actionLabel="Открыть счета"
          actionTo="/invoices"
        />
      );
    case AccessState.SUSPENDED:
      return (
        <StatusPage
          title="Доступ приостановлен"
          description="Оплата просрочена, доступ временно приостановлен."
          actionLabel="Написать в поддержку"
          actionTo="/client/support/new?topic=billing"
        />
      );
    case AccessState.LEGAL_PENDING:
      return (
        <StatusPage
          title="Проверка документов"
          description="Доступ временно ограничен до завершения проверки документов."
          actionLabel="Перейти к документам"
          actionTo="/documents"
        />
      );
    case AccessState.PAYOUT_BLOCKED:
      return (
        <StatusPage
          title="Выплаты заблокированы"
          description="Выплаты временно заблокированы. Обратитесь в поддержку для уточнения."
          actionLabel="Связаться с поддержкой"
          actionTo="/client/support/new?topic=payout"
        />
      );
    case AccessState.SLA_PENALTY:
      return (
        <StatusPage
          title="Санкции SLA"
          description="Доступ ограничен из-за санкций SLA. Свяжитесь с поддержкой."
          actionLabel="Связаться с поддержкой"
          actionTo="/client/support/new?topic=sla"
        />
      );
    case AccessState.FORBIDDEN_ROLE:
      return <AppForbiddenState message="Недостаточно прав для просмотра раздела." />;
    case AccessState.MODULE_DISABLED:
      if (isDemo) {
        return (
          <DemoEmptyState
            title="Раздел в демо недоступен"
            description={`В рабочем контуре здесь будут доступны возможности "${title}".`}
            action={
              <Link className="ghost neft-btn-secondary" to="/dashboard">
                Перейти в обзор
              </Link>
            }
          />
        );
      }
      return <ModuleUnavailablePage title={title} />;
    case AccessState.MISSING_CAPABILITY:
      if (isDemo) {
        return (
          <DemoEmptyState
            title="Раздел в демо недоступен"
            description={`В рабочем контуре здесь будут доступны возможности "${title}".`}
            action={
              <Link className="ghost neft-btn-secondary" to="/dashboard">
                Перейти в обзор
              </Link>
            }
          />
        );
      }
      return (
        <StatusPage
          title="Недоступно по подписке"
          description="Для доступа требуется расширенный тариф или подключение модуля."
          actionLabel="Перейти к подписке"
          actionTo="/subscription"
        />
      );
    case AccessState.SERVICE_UNAVAILABLE:
      return (
        <AppErrorState
          message={
            <>
              Сервис временно недоступен. Попробуйте позже.
              <DiagnosticsDetails error={error} />
              {requestId && requestId !== error?.requestId ? <div>Request ID: {requestId}</div> : null}
              {correlationId ? <div>Correlation ID: {correlationId}</div> : null}
            </>
          }
          correlationId={correlationId ?? undefined}
        />
      );
    case AccessState.MISCONFIG:
      return (
        <AppErrorState
          message={
            <>
              Конфигурация портала недоступна. Попробуйте позже или обратитесь в поддержку.
              <DiagnosticsDetails error={error} />
            </>
          }
          correlationId={correlationId ?? undefined}
        />
      );
    case AccessState.TECH_ERROR:
      return (
        <div className="stack">
          <AppErrorState
            message={
              <>
                Техническая ошибка. Попробуйте снова позже.
                <DiagnosticsDetails error={error} />
                {reason ? <div>Error ID: {reason}</div> : null}
              </>
            }
            correlationId={correlationId ?? undefined}
          />
          <div className="actions">
            <Link className="ghost neft-btn-secondary" to={fallbackHome}>
              На главную
            </Link>
          </div>
        </div>
      );
    case AccessState.AUTH_REQUIRED:
      return <Navigate to="/login" replace />;
    case AccessState.ACTIVE:
    default:
      return null;
  }
};

export const AccessGate = ({
  capability,
  module,
  requiredRoles,
  fallbackMode = "paywall",
  title,
  children,
}: AccessGateProps) => {
  const { user } = useAuth();
  const { client, isLoading, error, portalState, refresh } = useClient();
  const location = useLocation();

  if (!user) {
    return null;
  }

  if (portalState === "LOADING" || isLoading) {
    return <AppLoadingState label="Проверяем доступ..." />;
  }

  const isDemoClientAccount = isDemoClient(user.email ?? client?.user?.email ?? null);
  const portalView = PortalStateView({ state: portalState, error, onRetry: refresh, isDemo: isDemoClientAccount });
  if (portalView) {
    return portalView;
  }

  let decision = resolveAccessState({ client, requiredRoles, capability, module });
  if (isDemoClientAccount && decision.state !== AccessState.AUTH_REQUIRED) {
    // Demo-only showcase mode: ignore backend onboarding/entitlement gating and always render routes.
    decision = { state: AccessState.ACTIVE };
  }

  if (import.meta.env.DEV) {
    console.info("[access-gate:decision]", {
      route: location.pathname,
      portal_state: portalState,
      access_state: client?.access_state ?? null,
      resolved_state: decision.state,
      is_demo: isDemoClientAccount,
    });
  }

  if (
    (decision.state === AccessState.MISSING_CAPABILITY || decision.state === AccessState.MODULE_DISABLED) &&
    fallbackMode !== "paywall"
  ) {
    decision =
      fallbackMode === "forbidden" ? { state: AccessState.FORBIDDEN_ROLE } : { state: AccessState.NEEDS_ONBOARDING };
  }

  if (decision.state !== AccessState.ACTIVE) {
    if (import.meta.env.DEV) {
      console.info("[access-gate:redirect]", {
        route: location.pathname,
        state: decision.state,
      });
    }
    if (decision.state === AccessState.OVERDUE) {
      return <BillingOverdueState billing={client?.billing} />;
    }
    return <AccessStateView state={decision.state} title={title} reason={decision.reason} isDemo={isDemoClientAccount} />;
  }

  return <>{children}</>;
};

export { AccessStateView, PortalStateView };
