import type { ReactNode } from "react";
import { useEffect } from "react";
import { useI18n } from "../i18n";

type PartnerErrorStateProps = {
  title?: string;
  description?: string;
  error?: unknown;
  action?: ReactNode;
};

export function PartnerErrorState({ title, description, error, action }: PartnerErrorStateProps) {
  const { t } = useI18n();

  useEffect(() => {
    if (error) {
      console.error("PartnerErrorState", error);
    }
  }, [error]);

  const resolvedTitle = title ?? t("errors.unavailableTitle");
  const resolvedDescription = description ?? t("errors.unavailableDescription");

  return (
    <div className="empty-state">
      <h1>{resolvedTitle}</h1>
      {resolvedDescription ? <p className="muted">{resolvedDescription}</p> : null}
      {action ? <div className="actions">{action}</div> : null}
    </div>
  );
}
