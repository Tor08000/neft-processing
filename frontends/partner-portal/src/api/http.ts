import { AUTH_API_BASE, CORE_API_BASE } from "./base";

export { AUTH_API_BASE, CORE_API_BASE };

type ApiBase = "core" | "auth";

export type HttpHeaders = Record<string, string>;

export class UnauthorizedError extends Error {
  constructor(message = "Требуется повторный вход") {
    super(message);
    this.name = "UnauthorizedError";
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

export class ApiError extends Error {
  status: number;
  correlationId: string | null;

  constructor(message: string, status: number, correlationId: string | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.correlationId = correlationId;
  }
}

const buildHeaders = (token?: string): HttpHeaders => {
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

  const headers: HttpHeaders = { ...buildHeaders(token ?? undefined), ...(init.headers as HttpHeaders | undefined) };
  const apiBase = base === "auth" ? AUTH_API_BASE : CORE_API_BASE;
  const response = await fetch(`${apiBase}${path}`, { ...init, headers });
  const correlationId = response.headers.get("x-correlation-id") ?? response.headers.get("x-request-id");

  if (response.status === 401) {
    window.dispatchEvent(new Event("partner-auth-logout"));
    throw new UnauthorizedError();
  }
  if (response.status === 422) {
    const details = await response.json().catch(() => undefined);
    throw new ValidationError("Ошибка валидации", details);
  }
  if (!response.ok) {
    const text = await response.text();
    throw new ApiError(text || `Request failed with status ${response.status}`, response.status, correlationId);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json() as Promise<T>;
}

export interface ApiResponse<T> {
  data: T;
  correlationId: string | null;
  status: number;
}

export async function requestWithMeta<T>(
  path: string,
  init: RequestInit = {},
  tokenOrOptions?: string | null | RequestOptions,
  maybeBase?: ApiBase,
): Promise<ApiResponse<T>> {
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

  const headers: HttpHeaders = { ...buildHeaders(token ?? undefined), ...(init.headers as HttpHeaders | undefined) };
  const apiBase = base === "auth" ? AUTH_API_BASE : CORE_API_BASE;
  const response = await fetch(`${apiBase}${path}`, { ...init, headers });
  const correlationId = response.headers.get("x-correlation-id") ?? response.headers.get("x-request-id");

  if (response.status === 401) {
    window.dispatchEvent(new Event("partner-auth-logout"));
    throw new UnauthorizedError();
  }
  if (response.status === 422) {
    const details = await response.json().catch(() => undefined);
    throw new ValidationError("Ошибка валидации", details);
  }
  if (!response.ok) {
    const text = await response.text();
    throw new ApiError(text || `Request failed with status ${response.status}`, response.status, correlationId);
  }

  if (response.status === 204) {
    return { data: {} as T, correlationId, status: response.status };
  }

  const data = (await response.json()) as T;
  return { data, correlationId, status: response.status };
}
