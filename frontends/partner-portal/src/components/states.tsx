import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { PartnerErrorState } from "./PartnerErrorState";

interface StateProps {
  title: string;
  description?: string;
  action?: ReactNode;
  fullHeight?: boolean;
}

function StateContainer({ title, description, action, fullHeight = false }: StateProps) {
  return (
    <div className={`empty-state${fullHeight ? " empty-state--full" : ""}`}>
      <h1>{title}</h1>
      {description ? <p className="muted">{description}</p> : null}
      {action ? <div className="actions">{action}</div> : null}
    </div>
  );
}

export function LoadingState({ label = "Загружаем данные..." }: { label?: string }) {
  return <LoadingStateContent label={label} />;
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title?: string;
  description?: string;
  action?: ReactNode;
}) {
  const { t } = useTranslation();
  return (
    <StateContainer
      title={title ?? t("states.emptyTitle")}
      description={description ?? t("states.emptyDescription")}
      action={action}
    />
  );
}

export function ErrorState({
  title,
  description,
  correlationId,
  action,
  onRetry,
  retryLabel,
}: {
  title?: string;
  description?: string;
  correlationId?: string | null;
  action?: ReactNode;
  onRetry?: () => void;
  retryLabel?: string;
}) {
  return (
    <PartnerErrorState
      title={title}
      description={description}
      correlationId={correlationId}
      action={action}
      onRetry={onRetry}
      retryLabel={retryLabel}
    />
  );
}

export function ForbiddenState({
  title,
  description,
  action,
}: {
  title?: string;
  description?: string;
  action?: ReactNode;
}) {
  const { t } = useTranslation();
  return (
    <StateContainer
      title={title ?? t("states.forbiddenTitle")}
      description={description ?? t("states.forbiddenDescription")}
      action={action}
      fullHeight
    />
  );
}

function LoadingStateContent({ label }: { label?: string }) {
  const { t } = useTranslation();
  return <StateContainer title={label ?? t("common.loading")} fullHeight />;
}
