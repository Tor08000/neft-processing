import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { usePortal, type PortalState } from "../auth/PortalContext";
import { useAuth } from "../auth/AuthContext";
import { AccessState, resolveAccessState } from "../access/accessState";
import { ErrorState, ForbiddenState, LoadingState } from "./states";
import { isDemoPartner } from "@shared/demo/demo";

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

  if (state === AccessState.AUTH_REQUIRED) {
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
  }

  if (state === AccessState.MISCONFIG) {
    return <ErrorState description="Конфигурация портала недоступна. Обратитесь в поддержку." />;
  }

  if (state === AccessState.TECH_ERROR || state === AccessState.SERVICE_UNAVAILABLE) {
    return (
      <ErrorState
        description={`Сервис временно недоступен. Попробуйте позже.${reason ? ` Error ID: ${reason}` : ""}`}
      />
    );
  }

  if (state === AccessState.NEEDS_PLAN) {
    return (
      <div className="empty-state">
        <h1>Выберите тариф</h1>
        <p className="muted">Для доступа нужен активный тариф.</p>
        <div className="actions">
          <Link className="ghost" to="/support/requests">
            Связаться с менеджером
          </Link>
        </div>
      </div>
    );
  }

  if (state === AccessState.OVERDUE) {
    return (
      <div className="empty-state">
        <h1>Оплатите счёт</h1>
        <p className="muted">Доступ ограничен из-за просроченных счетов.</p>
        <div className="actions">
          <Link className="ghost" to="/support/requests">
            Связаться с поддержкой
          </Link>
        </div>
      </div>
    );
  }

  if (state === AccessState.SUSPENDED) {
    return (
      <div className="empty-state">
        <h1>Доступ приостановлен</h1>
        <p className="muted">Оплата просрочена, доступ временно приостановлен.</p>
        <div className="actions">
          <Link className="ghost" to="/support/requests">
            Связаться с поддержкой
          </Link>
        </div>
      </div>
    );
  }

  if (state === AccessState.LEGAL_PENDING) {
    return (
      <div className="empty-state">
        <h1>Проверка документов</h1>
        <p className="muted">Доступ ограничен до завершения проверки документов.</p>
        <div className="actions">
          <Link className="ghost" to="/legal">
            Перейти к документам
          </Link>
        </div>
      </div>
    );
  }

  if (state === AccessState.PAYOUT_BLOCKED) {
    return (
      <div className="empty-state">
        <h1>Выплаты заблокированы</h1>
        <p className="muted">Выплаты временно заблокированы. Обратитесь в поддержку.</p>
        <div className="actions">
          <Link className="ghost" to="/support/requests">
            Обратиться в поддержку
          </Link>
        </div>
      </div>
    );
  }

  if (state === AccessState.MODULE_DISABLED || state === AccessState.MISSING_CAPABILITY) {
    return (
      <div className="empty-state">
        <h1>Функция недоступна</h1>
        <p className="muted">Опция недоступна для вашего тарифа. Свяжитесь с менеджером.</p>
        <div className="actions">
          <Link className="ghost" to="/support/requests">
            Связаться с менеджером
          </Link>
        </div>
      </div>
    );
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
    org_not_active: {
      title: "Организация не активна",
      description: "Доступ будет открыт после активации организации.",
    },
    legal_not_verified: {
      title: "Проверка документов",
      description: "Доступ ограничен до завершения проверки документов.",
      action: (
        <Link className="ghost" to="/legal">
          Перейти к документам
        </Link>
      ),
    },
    subscription_missing: {
      title: "Выберите тариф",
      description: "Для доступа нужен активный тариф.",
      action: (
        <Link className="ghost" to="/support/requests">
          Связаться с менеджером
        </Link>
      ),
    },
    billing_overdue: {
      title: "Оплатите счёт",
      description: "Доступ ограничен из-за просроченных счетов.",
      action: (
        <Link className="ghost" to="/support/requests">
          Связаться с поддержкой
        </Link>
      ),
    },
    billing_suspended: {
      title: "Доступ приостановлен",
      description: "Оплата просрочена, доступ временно приостановлен.",
      action: (
        <Link className="ghost" to="/support/requests">
          Связаться с поддержкой
        </Link>
      ),
    },
    payout_blocked: {
      title: "Выплаты заблокированы",
      description: "Выплаты временно заблокированы. Обратитесь в поддержку.",
      action: (
        <Link className="ghost" to="/support/requests">
          Обратиться в поддержку
        </Link>
      ),
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

  let decision = resolveAccessState({ portal, requiredRoles, capability });
  const isDemoPartnerAccount = isDemoPartner(user.email ?? portal?.user?.email ?? null);
  if (
    isDemoPartnerAccount &&
    [AccessState.NEEDS_PLAN, AccessState.NEEDS_ONBOARDING, AccessState.MODULE_DISABLED, AccessState.MISSING_CAPABILITY].includes(
      decision.state,
    )
  ) {
    // Demo-only bypass: unlock partner modules without altering production checks.
    decision = { state: AccessState.ACTIVE };
  }
  if (decision.state !== AccessState.ACTIVE) {
    return <AccessStateView state={decision.state} title={title} reason={decision.reason} />;
  }

  return <>{children}</>;
};

export { AccessStateView };
