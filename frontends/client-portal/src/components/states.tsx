import type { ReactNode } from "react";
import { useI18n } from "../i18n";

type StateLayoutProps = {
  title: string;
  description?: string;
  action?: ReactNode;
  meta?: ReactNode;
};

const StateLayout = ({ title, description, action, meta }: StateLayoutProps) => (
  <div className="card state">
    <h2>{title}</h2>
    {description && <p className="muted">{description}</p>}
    {meta ? <div className="muted small">{meta}</div> : null}
    {action ? <div className="actions">{action}</div> : null}
  </div>
);

export const AppLoadingState = ({ label }: { label?: string }) => <LoadingStateContent label={label} />;

const LoadingStateContent = ({ label }: { label?: string }) => {
  const { t } = useI18n();
  return <StateLayout title={t("states.loadingTitle")} description={label ?? t("common.loading")} />;
};

export const AppEmptyState = ({
  title,
  description,
  action,
}: {
  title?: string;
  description?: string;
  action?: ReactNode;
}) => {
  const { t } = useI18n();
  return <StateLayout title={title ?? t("states.emptyTitle")} description={description} action={action} />;
};

export const AppErrorState = ({
  message,
  onRetry,
  status,
  correlationId,
}: {
  message: string;
  onRetry?: () => void;
  status?: number;
  correlationId?: string | null;
}) => (
  <ErrorStateContent message={message} onRetry={onRetry} status={status} correlationId={correlationId} />
);

const ErrorStateContent = ({
  message,
  onRetry,
  status,
  correlationId,
}: {
  message: string;
  onRetry?: () => void;
  status?: number;
  correlationId?: string | null;
}) => {
  const { t } = useI18n();
  const metaParts = [];
  if (status) {
    metaParts.push(t("errors.errorCode", { code: status }));
  }
  if (correlationId) {
    metaParts.push(t("errors.correlationId", { id: correlationId }));
  }
  return (
    <StateLayout
      title={t("errors.actionFailedTitle")}
      description={message}
      meta={metaParts.length ? metaParts.join(" · ") : undefined}
      action={
        onRetry ? (
          <button type="button" className="secondary" onClick={onRetry}>
            {t("errors.retry")}
          </button>
        ) : null
      }
    />
  );
};

export const AppForbiddenState = ({ message }: { message?: string }) => (
  <ForbiddenStateContent message={message} />
);

const ForbiddenStateContent = ({ message }: { message?: string }) => {
  const { t } = useI18n();
  return <StateLayout title={t("states.forbiddenTitle")} description={message ?? t("states.forbiddenDescription")} />;
};
