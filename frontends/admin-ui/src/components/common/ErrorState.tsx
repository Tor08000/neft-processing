import React from "react";

interface ErrorStateProps {
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
  details?: string;
  requestId?: string | null;
  correlationId?: string | null;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title,
  description,
  actionLabel,
  onAction,
  details,
  requestId,
  correlationId,
}) => {
  const metaParts = [];
  if (requestId) metaParts.push(`request_id: ${requestId}`);
  if (correlationId) metaParts.push(`correlation_id: ${correlationId}`);
  const meta = metaParts.length ? metaParts.join(" · ") : null;
  return (
    <div className="card error-state">
      <div className="error-state__content">
        <h3>{title}</h3>
        {description ? <p className="muted">{description}</p> : null}
        {meta ? <p className="muted small">{meta}</p> : null}
        {actionLabel ? (
          <button type="button" className="neft-button neft-btn-primary" onClick={onAction}>
            {actionLabel}
          </button>
        ) : null}
        {details ? (
          <details className="error-state__details">
            <summary>Подробнее</summary>
            <pre>{details}</pre>
          </details>
        ) : null}
      </div>
    </div>
  );
};
