import type { ReactNode } from "react";
import { useI18n } from "../i18n";

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
  const { t } = useI18n();
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
}: {
  title?: string;
  description?: string;
  correlationId?: string | null;
  action?: ReactNode;
}) {
  const { t } = useI18n();
  const metaParts = [];
  if (correlationId) {
    metaParts.push(t("errors.correlationId", { id: correlationId }));
  }
  const details = metaParts.length ? `${description ?? ""} ${metaParts.join(" · ")}`.trim() : description;
  return (
    <StateContainer
      title={title ?? t("errors.actionFailedTitle")}
      description={details ?? t("common.loading")}
      action={action}
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
  const { t } = useI18n();
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
  const { t } = useI18n();
  return <StateContainer title={label ?? t("common.loading")} fullHeight />;
}
