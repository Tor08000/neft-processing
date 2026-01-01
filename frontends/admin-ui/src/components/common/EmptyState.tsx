import React from "react";

interface EmptyStateProps {
  title: string;
  description?: string;
  actionLabel?: string;
  actionOnClick?: () => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({ title, description, actionLabel, actionOnClick }) => {
  return (
    <div className="card empty-state">
      <div className="empty-state__content">
        <h3>{title}</h3>
        {description ? <p className="muted">{description}</p> : null}
        {actionLabel ? (
          <button type="button" className="neft-button neft-btn-primary" onClick={actionOnClick}>
            {actionLabel}
          </button>
        ) : null}
      </div>
    </div>
  );
};
