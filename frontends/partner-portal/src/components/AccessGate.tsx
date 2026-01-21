import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { usePortal } from "../auth/PortalContext";
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
  const { portal, isLoading, error } = usePortal();

  if (!user) {
    return null;
  }

  if (isLoading) {
    return <LoadingState label="Проверяем доступ..." />;
  }

  if (error) {
    return <AccessStateView state={AccessState.TECH_ERROR} title={title} />;
  }

  const decision = resolveAccessState({ portal, requiredRoles, capability });
  if (decision.state !== AccessState.OK) {
    return <AccessStateView state={decision.state} title={title} reason={decision.reason} />;
  }

  return <>{children}</>;
};

export { AccessStateView };
