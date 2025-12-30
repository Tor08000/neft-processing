import type { ReactNode } from "react";

type StateLayoutProps = {
  title: string;
  description?: string;
  action?: ReactNode;
};

const StateLayout = ({ title, description, action }: StateLayoutProps) => (
  <div className="card state">
    <h2>{title}</h2>
    {description && <p className="muted">{description}</p>}
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

export const AppErrorState = ({ message, onRetry }: { message: string; onRetry?: () => void }) => (
  <StateLayout
    title="Ошибка"
    description={message}
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
