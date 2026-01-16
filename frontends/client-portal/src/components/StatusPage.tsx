import { Link } from "react-router-dom";
import { EmptyState } from "@shared/brand/components";
import type { ReactNode } from "react";

type StatusPageProps = {
  title: string;
  description: ReactNode;
  actionLabel?: string;
  actionTo?: string;
  secondaryAction?: ReactNode;
};

export function StatusPage({
  title,
  description,
  actionLabel = "Вернуться на дашборд",
  actionTo = "/",
  secondaryAction,
}: StatusPageProps) {
  return (
    <EmptyState
      title={title}
      description={description}
      action={
        <div className="actions">
          <Link className="ghost neft-btn-secondary" to={actionTo}>
            {actionLabel}
          </Link>
          {secondaryAction}
        </div>
      }
    />
  );
}
