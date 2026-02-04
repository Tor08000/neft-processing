import type { ReactNode } from "react";

type EmptyStateAction = {
  label: string;
  onClick: () => void;
};

export type EmptyStateProps = {
  title: string;
  description?: string;
  hint?: string;
  primaryAction?: EmptyStateAction;
  secondaryAction?: EmptyStateAction;
  icon?: ReactNode;
};

export function EmptyState({ title, description, hint, primaryAction, secondaryAction, icon }: EmptyStateProps) {
  return (
    <div className="empty-state">
      {icon ? (
        <div className="empty-state__icon" aria-hidden>
          {icon}
        </div>
      ) : null}
      <h3 className="empty-state__title">{title}</h3>
      {description ? <p className="empty-state__description">{description}</p> : null}
      {hint ? <p className="empty-state__hint">{hint}</p> : null}
      {primaryAction || secondaryAction ? (
        <div className="empty-state__actions">
          {primaryAction ? (
            <button type="button" className="neft-button neft-btn-primary" onClick={primaryAction.onClick}>
              {primaryAction.label}
            </button>
          ) : null}
          {secondaryAction ? (
            <button type="button" className="neft-btn-secondary" onClick={secondaryAction.onClick}>
              {secondaryAction.label}
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export default EmptyState;
