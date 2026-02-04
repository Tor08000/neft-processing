import type { ReactNode } from "react";
import { useEffect, useMemo } from "react";
import { ApiError, HtmlResponseError, ValidationError } from "../api/http";
import { ErrorState } from "./states";
import { useI18n } from "../i18n";

type PartnerErrorStateProps = {
  title?: string;
  description?: string;
  statusCode?: number;
  error?: unknown;
  action?: ReactNode;
};

type ErrorDetails = {
  message?: string;
  status?: number;
  correlationId?: string | null;
  requestId?: string | null;
  errorCode?: string | null;
};

const extractErrorDetails = (error: unknown): ErrorDetails => {
  if (!error) return {};
  if (typeof error === "string") return { message: error };
  if (error instanceof ApiError) {
    return {
      message: error.message,
      status: error.status,
      correlationId: error.correlationId,
      requestId: error.requestId,
      errorCode: error.errorCode,
    };
  }
  if (error instanceof HtmlResponseError) {
    return {
      message: error.message,
      status: error.status,
      correlationId: error.correlationId,
    };
  }
  if (error instanceof ValidationError) {
    return { message: error.message };
  }
  if (error instanceof Error) {
    return { message: error.message };
  }
  return {};
};

export function PartnerErrorState({ title, description, statusCode, error, action }: PartnerErrorStateProps) {
  const { t } = useI18n();
  const details = useMemo(() => extractErrorDetails(error), [error]);

  useEffect(() => {
    if (error) {
      console.error("PartnerErrorState", error);
    }
  }, [error]);

  const resolvedStatus = statusCode ?? details.status;
  const baseDescription = description ?? details.message ?? t("errors.actionFailedDescription");
  const metaParts: string[] = [];
  if (resolvedStatus) metaParts.push(`HTTP ${resolvedStatus}`);
  if (details.errorCode) metaParts.push(t("errors.errorCode", { code: details.errorCode }));
  if (details.requestId) metaParts.push(t("errors.requestId", { id: details.requestId }));
  if (details.correlationId) metaParts.push(t("errors.correlationId", { id: details.correlationId }));
  const meta = metaParts.length ? ` ${metaParts.join(" · ")}` : "";

  return <ErrorState title={title ?? t("errors.actionFailedTitle")} description={`${baseDescription}${meta}`} action={action} />;
}
