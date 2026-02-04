import { Link } from "react-router-dom";

type ClientErrorStateProps = {
  title?: string;
  description?: string;
  details?: string;
  onRetry?: () => void;
  retryLabel?: string;
  secondaryActionLabel?: string;
  secondaryActionTo?: string;
  supportActionLabel?: string;
  supportActionTo?: string;
};

export function ClientErrorState({
  title = "Что-то пошло не так",
  description = "Мы не смогли получить данные. Попробуйте обновить или напишите в поддержку.",
  details,
  onRetry,
  retryLabel = "Обновить",
  secondaryActionLabel,
  secondaryActionTo,
  supportActionLabel = "Сообщить в поддержку",
  supportActionTo = "/client/support/new",
}: ClientErrorStateProps) {
  return (
    <div className="card error-state">
      <div className="error-state__content">
        <h3>{title}</h3>
        {description ? <p className="muted">{description}</p> : null}
        <div className="actions">
          {onRetry ? (
            <button type="button" className="neft-button neft-btn-primary" onClick={onRetry}>
              {retryLabel}
            </button>
          ) : null}
          {secondaryActionTo ? (
            <Link className="ghost neft-btn-secondary" to={secondaryActionTo}>
              {secondaryActionLabel ?? "Обзор"}
            </Link>
          ) : null}
          {supportActionTo ? (
            <Link className="ghost neft-btn-secondary" to={supportActionTo}>
              {supportActionLabel}
            </Link>
          ) : null}
        </div>
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
