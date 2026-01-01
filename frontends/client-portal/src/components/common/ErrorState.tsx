interface ErrorStateProps {
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
  details?: string;
}

export function ErrorState({ title, description, actionLabel, onAction, details }: ErrorStateProps) {
  return (
    <div className="card error-state">
      <div className="error-state__content">
        <h3>{title}</h3>
        {description ? <p className="muted">{description}</p> : null}
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
}
