import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useClient, type PortalState } from "../auth/ClientContext";
import { useAuth } from "../auth/AuthContext";
import { AccessState, resolveAccessState } from "../access/accessState";
import { AppErrorState, AppForbiddenState, AppLoadingState } from "./states";
import { StatusPage } from "./StatusPage";
import { ModuleUnavailablePage } from "../pages/ModuleUnavailablePage";

type AccessGateProps = {
  capability?: string;
  module?: string;
  requiredRoles?: string[];
  fallbackMode?: "paywall" | "activation" | "forbidden" | "coming_soon";
  title?: string;
  children: ReactNode;
};

const PortalStateView = ({ state, error }: { state: PortalState; error?: string | null }) => {
  switch (state) {
    case "AUTH_REQUIRED":
      return (
        <StatusPage
          title="Требуется вход"
          description="Пожалуйста, войдите, чтобы продолжить."
          actionLabel="Перейти к входу"
          actionTo="/login"
        />
      );
    case "NO_SUBSCRIPTION":
      return (
        <StatusPage
          title="Подключите продукт"
          description="Для доступа необходима активная подписка."
          actionLabel="Перейти к подписке"
          actionTo="/subscription"
        />
      );
    case "NO_MODULES_ENABLED":
      return (
        <StatusPage
          title="Нет активных модулей"
          description="Подключите модули, чтобы открыть раздел."
          actionLabel="Перейти к подписке"
          actionTo="/subscription"
        />
      );
    case "SERVICE_UNAVAILABLE":
      return <AppErrorState message="Сервис временно недоступен. Попробуйте позже." />;
    case "ERROR_FATAL":
      return <AppErrorState message={error ?? "Ошибка приложения"} />;
    case "LOADING":
    case "READY":
    default:
      return null;
  }
};

const AccessStateView = ({
  state,
  title = "Раздел",
  requestId,
  correlationId,
}: {
  state: AccessState;
  title?: string;
  requestId?: string | null;
  correlationId?: string | null;
}) => {
  switch (state) {
    case AccessState.NEEDS_ONBOARDING:
      return (
        <StatusPage
          title="Подключить компанию"
          description="Завершите подключение компании, чтобы открыть этот раздел."
          actionLabel="Перейти к подключению"
          actionTo="/client/connect"
        />
      );
    case AccessState.NEEDS_PLAN:
      return (
        <StatusPage
          title="Выберите тариф"
          description="Для доступа к разделу нужен активный тариф."
          actionLabel="Выбрать тариф"
          actionTo="/subscription"
          secondaryAction={
            <Link className="ghost neft-btn-secondary" to="/client/support/new?topic=plan">
              Связаться с менеджером
            </Link>
          }
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
    case AccessState.FORBIDDEN_ROLE:
      return <AppForbiddenState message="Недостаточно прав для просмотра раздела." />;
    case AccessState.MISSING_CAPABILITY:
      return <ModuleUnavailablePage title={title} />;
    case AccessState.COMING_SOON:
      return (
        <StatusPage
          title="Скоро"
          description="Раздел ещё в разработке. Мы сообщим, когда он станет доступен."
          actionLabel="Вернуться на дашборд"
          actionTo="/dashboard"
        />
      );
    case AccessState.TECH_ERROR:
      return (
        <AppErrorState
          message={
            <>
              Сервис временно недоступен. Попробуйте позже.
              {requestId ? <div>Request ID: {requestId}</div> : null}
              {correlationId ? <div>Correlation ID: {correlationId}</div> : null}
            </>
          }
          correlationId={correlationId ?? undefined}
        />
      );
    case AccessState.OK:
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
  const { client, isLoading, error, portalState } = useClient();

  if (!user) {
    return null;
  }

  if (portalState === "LOADING" || isLoading) {
    return <AppLoadingState label="Проверяем доступ..." />;
  }

  const portalView = PortalStateView({ state: portalState, error });
  if (portalView) {
    return portalView;
  }

  let decision = resolveAccessState({ client, requiredRoles, capability, module });

  if (decision.state === AccessState.MISSING_CAPABILITY && fallbackMode !== "paywall") {
    decision =
      fallbackMode === "coming_soon"
        ? { state: AccessState.COMING_SOON }
        : fallbackMode === "forbidden"
          ? { state: AccessState.FORBIDDEN_ROLE }
          : { state: AccessState.NEEDS_ONBOARDING };
  }

  if (decision.state !== AccessState.OK) {
    return <AccessStateView state={decision.state} title={title} />;
  }

  return <>{children}</>;
};

export { AccessStateView };
