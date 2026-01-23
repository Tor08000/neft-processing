import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { usePortal, type PortalState } from "../auth/PortalContext";
import { useAuth } from "../auth/AuthContext";
import { AccessState, resolveAccessState } from "../access/accessState";
import { ErrorState, ForbiddenState, LoadingState } from "./states";

type AccessGateProps = {
  capability?: string;
  requiredRoles?: string[];
  title?: string;
  children: ReactNode;
};

type AccessPresentation = {
  title: string;
  description: string;
  action?: ReactNode;
};

const PortalStateView = ({
  state,
  error,
}: {
  state: PortalState;
  error?: string | null;
}) => {
  switch (state) {
    case "AUTH_REQUIRED":
      return (
        <div className="empty-state">
          <h1>Требуется вход</h1>
          <p className="muted">Пожалуйста, войдите, чтобы продолжить.</p>
          <div className="actions">
            <Link className="ghost" to="/login">
              Перейти к входу
            </Link>
          </div>
        </div>
      );
    case "NO_SUBSCRIPTION":
      return (
        <div className="empty-state">
          <h1>Подключите продукт</h1>
          <p className="muted">Для доступа нужна активная подписка.</p>
        </div>
      );
    case "NO_MODULES_ENABLED":
      return (
        <div className="empty-state">
          <h1>Нет активных модулей</h1>
          <p className="muted">Подключите модули, чтобы открыть раздел.</p>
        </div>
      );
    case "SERVICE_UNAVAILABLE":
      return <ErrorState description="Сервис временно недоступен. Попробуйте позже." />;
    case "ERROR_FATAL":
      return <ErrorState description={error ?? "Ошибка приложения"} />;
    case "LOADING":
    case "READY":
    default:
      return null;
  }
};

const AccessStateView = ({
  state,
  title = "Раздел",
  reason,
}: {
  state: AccessState;
  title?: string;
  reason?: string | null;
}) => {
  if (state === AccessState.FORBIDDEN_ROLE) {
    return <ForbiddenState description="Недостаточно прав для просмотра раздела." />;
  }

  if (state === AccessState.TECH_ERROR) {
    return <ErrorState description="Сервис временно недоступен. Попробуйте позже." />;
  }

  const base: AccessPresentation = {
    title: `${title} недоступен`,
    description: "Доступ временно ограничен. Обратитесь к менеджеру или в поддержку.",
  };

  const byReason: Record<string, AccessPresentation> = {
    partner_onboarding: {
      title: "Завершите профиль партнёра",
      description: "Завершите онбординг, чтобы открыть раздел.",
      action: (
        <Link className="ghost" to="/marketplace/profile">
          Завершить профиль
        </Link>
      ),
    },
    legal_not_verified: {
      title: "Юридический профиль не подтверждён",
      description: "Заполните юридические данные и загрузите документы.",
      action: (
        <Link className="ghost" to="/legal">
          Перейти к юридическим данным
        </Link>
      ),
    },
    settlement_not_finalized: {
      title: "Ожидается финализация settlement",
      description: "Settlement ещё не финализирован. Проверьте позже.",
      action: (
        <Link className="ghost" to="/payouts">
          К settlements
        </Link>
      ),
    },
    billing_soft_blocked: {
      title: "Выплаты временно заблокированы",
      description: "Есть задолженность по оплате. Погасите счета или обратитесь к менеджеру.",
      action: (
        <Link className="ghost" to="/support/requests">
          Обратиться в поддержку
        </Link>
      ),
    },
    billing_hard_blocked: {
      title: "Выплаты приостановлены",
      description: "Доступ к выплатам приостановлен. Свяжитесь с поддержкой для разблокировки.",
      action: (
        <Link className="ghost" to="/support/requests">
          Обратиться в поддержку
        </Link>
      ),
    },
    feature_not_entitled: {
      title: "Функция недоступна",
      description: "Опция недоступна для вашего тарифа. Свяжитесь с менеджером.",
      action: (
        <Link className="ghost" to="/support/requests">
          Связаться с менеджером
        </Link>
      ),
    },
    org_not_active: {
      title: "Организация не активна",
      description: "Доступ будет открыт после активации организации.",
    },
  };

  const presentation = reason && byReason[reason] ? byReason[reason] : base;

  return (
    <div className="empty-state">
      <h1>{presentation.title}</h1>
      <p className="muted">{presentation.description}</p>
      {presentation.action ? <div className="actions">{presentation.action}</div> : null}
    </div>
  );
};

export const AccessGate = ({ capability, requiredRoles, title, children }: AccessGateProps) => {
  const { user } = useAuth();
  const { portal, isLoading, error, portalState } = usePortal();

  if (!user) {
    return null;
  }

  if (portalState === "LOADING" || isLoading) {
    return <LoadingState label="Проверяем доступ..." />;
  }

  const portalView = PortalStateView({ state: portalState, error });
  if (portalView) {
    return portalView;
  }

  const decision = resolveAccessState({ portal, requiredRoles, capability });
  if (decision.state !== AccessState.OK) {
    return <AccessStateView state={decision.state} title={title} reason={decision.reason} />;
  }

  return <>{children}</>;
};

export { AccessStateView };
