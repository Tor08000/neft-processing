import type { ReactNode } from "react";
import { useEffect } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

type PartnerErrorStateProps = {
  title?: string;
  description?: string;
  error?: unknown;
  correlationId?: string | null;
  action?: ReactNode;
  onRetry?: () => void;
  retryLabel?: string;
};

const DEBUG_PARTNER_ERROR_STATE = Boolean(import.meta.env.DEV && import.meta.env.VITE_PARTNER_DEBUG_ERRORS === "true");

export function PartnerErrorState({
  title,
  description,
  error,
  correlationId,
  action,
  onRetry,
  retryLabel,
}: PartnerErrorStateProps) {
  const { t } = useTranslation();

  useEffect(() => {
    if (DEBUG_PARTNER_ERROR_STATE && error) {
      console.error("PartnerErrorState", error);
    }
  }, [error]);

  const resolvedTitle = title ?? t("errors.unavailableTitle");
  const resolvedDescription = description ?? t("errors.unavailableDescription");
  const resolvedAction = (
    <>
      {action}
      <button type="button" className="secondary" onClick={onRetry ?? (() => window.location.reload())}>
        {retryLabel ?? t("actions.refresh")}
      </button>
      <Link className="ghost" to="/support/requests">
        {t("actions.contact")}
      </Link>
    </>
  );

  return (
    <div className="empty-state">
      <h1>{resolvedTitle}</h1>
      {resolvedDescription ? <p className="muted">{resolvedDescription}</p> : null}
      {correlationId ? <p className="muted small">{t("errors.correlationId", { id: correlationId })}</p> : null}
      <div className="actions">{resolvedAction}</div>
    </div>
  );
}
