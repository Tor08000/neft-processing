import type { ReactNode } from "react";

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

export const AppLoadingState = ({ label = "Загружаем данные..." }: { label?: string }) => (
  <StateLayout title="Loading" description={label} />
);

export const AppEmptyState = ({
  title = "Данных пока нет",
  description,
  action,
}: {
  title?: string;
  description?: string;
  action?: ReactNode;
}) => <StateLayout title={title} description={description} action={action} />;

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
  <StateLayout
    title="Ошибка"
    description={message}
    meta={
      status || correlationId ? (
        <>
          {status ? `HTTP ${status}` : null}
          {status && correlationId ? " · " : null}
          {correlationId ? `Correlation ID: ${correlationId}` : null}
        </>
      ) : null
    }
    action={
      onRetry ? (
        <button type="button" className="secondary" onClick={onRetry}>
          Повторить
        </button>
      ) : null
    }
  />
);

export const AppForbiddenState = ({ message }: { message?: string }) => (
  <StateLayout title="Доступ запрещён" description={message ?? "Недостаточно прав для просмотра"} />
);
