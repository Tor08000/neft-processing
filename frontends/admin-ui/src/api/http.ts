const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "http://gateway").replace(/\/$/, "");
const adminBase = (import.meta.env.BASE_URL ?? "/admin/").replace(/\/$/, "");
export const API_BASE = `${apiBase}${adminBase}/api/v1`;

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

const buildHeaders = (token?: string | null): HttpHeaders => {
  const headers: HttpHeaders = {
    "Content-Type": "application/json",
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  return headers;
};

export async function request<T>(path: string, init: RequestInit = {}, token?: string | null): Promise<T> {
  const headers: HttpHeaders = {
    ...buildHeaders(token),
    ...(init.headers as HttpHeaders | undefined),
  };

  const response = await fetch(`${API_BASE}${path}`, { ...init, headers });

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
  if (!response.ok) {
    const details = await response.text();
    throw new Error(details || `Request failed with status ${response.status}`);
  }

  return response.json() as Promise<T>;
}
