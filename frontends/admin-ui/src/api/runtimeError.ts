import { ApiError } from "./http";

export type RuntimeErrorMeta = {
  description: string;
  details?: string;
  requestId?: string | null;
  correlationId?: string | null;
};

type StructuredErrorPayload = {
  error?: string;
  message?: string;
  request_id?: string;
  correlation_id?: string;
  error_id?: string;
  reason_code?: string;
};

const GENERIC_INTERNAL_DESCRIPTION =
  "Owner route returned an internal error. Retry or inspect request metadata below.";

const GENERIC_UNAVAILABLE_DESCRIPTION =
  "Owner route is temporarily unavailable in the current environment. Retry shortly or inspect request metadata below.";

const GENERIC_NOT_FOUND_DESCRIPTION =
  "Owner route is not available in the current environment. We do not replace it with synthetic demo content.";

const tryParseStructuredPayload = (message: string): StructuredErrorPayload | null => {
  const trimmed = message.trim();
  if (!trimmed.startsWith("{")) {
    return null;
  }
  try {
    const parsed = JSON.parse(trimmed) as StructuredErrorPayload;
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
};

const formatDetails = (payload: StructuredErrorPayload | null, rawMessage: string): string | undefined => {
  if (payload) {
    return JSON.stringify(payload, null, 2);
  }
  const trimmed = rawMessage.trim();
  return trimmed ? trimmed : undefined;
};

const getDescriptionForStatus = (status: number | undefined, fallback?: string): string => {
  if (status === 404) return fallback ?? GENERIC_NOT_FOUND_DESCRIPTION;
  if (status === 502 || status === 503) return fallback ?? GENERIC_UNAVAILABLE_DESCRIPTION;
  if (status && status >= 500) return fallback ?? GENERIC_INTERNAL_DESCRIPTION;
  return fallback ?? "Request failed. Retry or inspect request metadata below.";
};

export const describeRuntimeError = (error: unknown, fallback?: string): RuntimeErrorMeta => {
  if (error instanceof ApiError) {
    const payload = tryParseStructuredPayload(error.message);
    return {
      description: getDescriptionForStatus(error.status, fallback),
      details: formatDetails(payload, error.message),
      requestId: error.requestId ?? payload?.request_id ?? null,
      correlationId: error.correlationId ?? payload?.correlation_id ?? null,
    };
  }

  if (error instanceof Error) {
    const payload = tryParseStructuredPayload(error.message);
    return {
      description: fallback ?? (payload?.message || error.message || "Unexpected runtime error"),
      details: formatDetails(payload, error.message),
      requestId: payload?.request_id ?? null,
      correlationId: payload?.correlation_id ?? null,
    };
  }

  return {
    description: fallback ?? "Unexpected runtime error",
  };
};
