import type { ReactNode } from "react";

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
  return <StateContainer title={label} fullHeight />;
}

export function EmptyState({
  title = "Пока нет данных",
  description = "Как только появятся записи, они отобразятся здесь.",
  action,
}: {
  title?: string;
  description?: string;
  action?: ReactNode;
}) {
  return <StateContainer title={title} description={description} action={action} />;
}

export function ErrorState({
  title = "Не удалось загрузить данные",
  description = "Попробуйте обновить страницу или повторить запрос позже.",
  correlationId,
  action,
}: {
  title?: string;
  description?: string;
  correlationId?: string | null;
  action?: ReactNode;
}) {
  const details = correlationId ? `${description} Correlation ID: ${correlationId}` : description;
  return <StateContainer title={title} description={details} action={action} />;
}

export function ForbiddenState({
  title = "Доступ ограничен",
  description = "У вашей роли нет доступа к этому разделу.",
  action,
}: {
  title?: string;
  description?: string;
  action?: ReactNode;
}) {
  return <StateContainer title={title} description={description} action={action} fullHeight />;
}
