import type { ReactNode } from "react";
import { Link } from "react-router-dom";

type EmptyStateAction = {
  label: string;
  onClick?: () => void;
  to?: string;
  href?: string;
  variant?: "primary" | "secondary" | "ghost";
};

type EmptyStateProps = {
  title: string;
  description: string;
  icon?: ReactNode;
  primaryAction?: EmptyStateAction;
  secondaryAction?: EmptyStateAction;
  actionLabel?: string;
  actionOnClick?: () => void;
};

const renderAction = (action: EmptyStateAction, fallbackVariant: EmptyStateAction["variant"]) => {
  const className = action.variant ?? fallbackVariant ?? "secondary";
  if (action.to) {
    return (
      <Link className={className} to={action.to}>
        {action.label}
      </Link>
    );
  }
  if (action.href) {
    return (
      <a className={className} href={action.href}>
        {action.label}
      </a>
    );
  }
  return (
    <button type="button" className={className} onClick={action.onClick}>
      {action.label}
    </button>
  );
};

export function EmptyState({
  title,
  description,
  icon,
  primaryAction,
  secondaryAction,
  actionLabel,
  actionOnClick,
}: EmptyStateProps) {
  const primary = primaryAction ?? (actionLabel ? { label: actionLabel, onClick: actionOnClick } : undefined);
  return (
    <div className="card state">
      <div className="empty-state">
        {icon ? (
          <div className="empty-state__icon" aria-hidden>
            {icon}
          </div>
        ) : null}
        <h2>{title}</h2>
        <p className="muted">{description}</p>
        {(primary || secondaryAction) && (
          <div className="actions">
            {primary ? renderAction(primary, "primary") : null}
            {secondaryAction ? renderAction(secondaryAction, "secondary") : null}
          </div>
        )}
      </div>
    </div>
  );
}
