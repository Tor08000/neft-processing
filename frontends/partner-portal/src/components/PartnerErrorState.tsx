import type { ReactNode } from "react";
import { useEffect, useMemo } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n";
import { isDemoPartner } from "@shared/demo/demo";

type PartnerErrorStateProps = {
  title?: string;
  description?: string;
  error?: unknown;
  action?: ReactNode;
  isDemo?: boolean;
};

export function PartnerErrorState({ title, description, error, action, isDemo }: PartnerErrorStateProps) {
  const { t } = useI18n();
  const { user } = useAuth();
  const isDemoPartnerAccount = useMemo(
    () => (typeof isDemo === "boolean" ? isDemo : isDemoPartner(user?.email ?? null)),
    [isDemo, user?.email],
  );

  useEffect(() => {
    if (error) {
      console.error("PartnerErrorState", error);
    }
  }, [error]);

  const resolvedTitle = title ?? t("errors.unavailableTitle");
  const resolvedDescription = isDemoPartnerAccount
    ? t("errors.unavailableDemoDescription")
    : description ?? t("errors.unavailableDescription");
  const resolvedAction = (
    <>
      {action}
      <button type="button" className="secondary" onClick={() => window.location.reload()}>
        {t("actions.refresh")}
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
      <div className="actions">{resolvedAction}</div>
    </div>
  );
}
