import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { withBase } from "@shared/lib/path";
import { AppLogo } from "./AppLogo";

export type EmptyStateAction = {
  label: ReactNode;
  onClick?: () => void;
  to?: string;
  href?: string;
  variant?: "primary" | "secondary" | "ghost";
};

export type EmptyStateProps = {
  title: ReactNode;
  description?: ReactNode;
  hint?: ReactNode;
  icon?: ReactNode;
  action?: ReactNode;
  primaryAction?: EmptyStateAction;
  secondaryAction?: EmptyStateAction;
  actionsClassName?: string;
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
      <a className={className} href={withBase(action.href)}>
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
  hint,
  icon,
  action,
  primaryAction,
  secondaryAction,
  actionsClassName,
}: EmptyStateProps) {
  const isPlainDescription = typeof description === "string" || typeof description === "number";
  const isPlainHint = typeof hint === "string" || typeof hint === "number";

  return (
    <div className="empty-state">
      {icon ? icon : <AppLogo size={48} className="empty-state__logo" />}
      <h2 className="empty-state__title">{title}</h2>
      {description ? (
        isPlainDescription ? (
          <p className="empty-state__description">{description}</p>
        ) : (
          <div className="empty-state__description">{description}</div>
        )
      ) : null}
      {hint ? (
        isPlainHint ? (
          <p className="empty-state__hint">{hint}</p>
        ) : (
          <div className="empty-state__hint">{hint}</div>
        )
      ) : null}
      {action ? <div className={["empty-state__actions", actionsClassName].filter(Boolean).join(" ")}>{action}</div> : null}
      {!action && (primaryAction || secondaryAction) ? (
        <div className={["empty-state__actions", actionsClassName].filter(Boolean).join(" ")}>
          {primaryAction ? renderAction(primaryAction, "primary") : null}
          {secondaryAction ? renderAction(secondaryAction, "secondary") : null}
        </div>
      ) : null}
    </div>
  );
}

export default EmptyState;
