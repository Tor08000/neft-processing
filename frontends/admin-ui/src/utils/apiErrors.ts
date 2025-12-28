import { ForbiddenError, UnauthorizedError, ValidationError } from "../api/http";

export interface ErrorSummary {
  message: string;
  details?: string;
  isForbidden?: boolean;
  isUnauthorized?: boolean;
}

export function describeError(error: unknown): ErrorSummary {
  if (error instanceof ForbiddenError) {
    return { message: error.message, isForbidden: true };
  }
  if (error instanceof UnauthorizedError) {
    return { message: error.message, isUnauthorized: true };
  }
  if (error instanceof ValidationError) {
    const details = error.details ? JSON.stringify(error.details, null, 2) : undefined;
    return { message: error.message, details };
  }
  if (error instanceof Error) {
    return { message: error.message };
  }
  if (typeof error === "string") {
    return { message: error };
  }
  return { message: "Неизвестная ошибка" };
}

export function formatError(error: unknown): string {
  const summary = describeError(error);
  if (summary.details) {
    return `${summary.message}: ${summary.details}`;
  }
  return summary.message;
}
