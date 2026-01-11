import { AUTH_API_BASE, CORE_API_BASE } from "./base";

type ApiBase = "core" | "auth";

export type HttpHeaders = Record<string, string>;

export class UnauthorizedError extends Error {
  constructor(message = "Необходим повторный вход") {
    super(message);
    this.name = "UnauthorizedError";
  }
}

export class ForbiddenError extends Error {
  constructor(message = "Недостаточно прав") {
    super(message);
    this.name = "ForbiddenError";
  }
}

export class ValidationError extends Error {
  details?: unknown;

  constructor(message = "Ошибка валидации", details?: unknown) {
    super(message);
    this.name = "ValidationError";
    this.details = details;
  }
}

export class LegalRequiredError extends Error {
  status: number;
  details: unknown;

  constructor(message: string, status: number, details: unknown) {
    super(message);
    this.name = "LegalRequiredError";
    this.status = status;
    this.details = details;
  }
}

const buildHeaders = (token?: string | null): HttpHeaders => {
  const headers: HttpHeaders = {
    "Content-Type": "application/json",
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  return headers;
};

type RequestOptions = {
  token?: string | null;
  base?: ApiBase;
};

export async function request<T>(
  path: string,
  init: RequestInit = {},
  tokenOrOptions?: string | null | RequestOptions,
  maybeBase?: ApiBase,
): Promise<T> {
  let token: string | null | undefined;
  let base: ApiBase = "core";

  if (tokenOrOptions && typeof tokenOrOptions === "object" && !Array.isArray(tokenOrOptions)) {
    token = tokenOrOptions.token ?? undefined;
    base = tokenOrOptions.base ?? base;
  } else {
    token = (tokenOrOptions as string | null | undefined) ?? undefined;
    if (typeof maybeBase === "string") {
      base = maybeBase;
    }
  }

  const headers: HttpHeaders = {
    ...buildHeaders(token),
    ...(init.headers as HttpHeaders | undefined),
  };

  const apiBase = base === "auth" ? AUTH_API_BASE : CORE_API_BASE;

  const response = await fetch(`${apiBase}${path}`, { ...init, headers });

  if (response.status === 401) {
    throw new UnauthorizedError();
  }
  if (response.status === 403) {
    throw new ForbiddenError();
  }
  if (response.status === 422) {
    const details = await response.json().catch(() => undefined);
    throw new ValidationError("Ошибка валидации", details);
  }
  if (response.status === 428) {
    const details = await response.json().catch(() => undefined);
    window.dispatchEvent(new CustomEvent("legal-required", { detail: details }));
    throw new LegalRequiredError("Legal documents must be accepted before performing this action.", 428, details);
  }
  if (!response.ok) {
    const details = await response.text();
    throw new Error(details || `Request failed with status ${response.status}`);
  }

  return response.json() as Promise<T>;
}
