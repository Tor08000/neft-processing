const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost").replace(/\/$/, "");
const adminBase = (import.meta.env.VITE_ADMIN_BASE_PATH ?? "/admin").replace(/\/$/, "");
export const API_BASE = `${apiBase}${adminBase}/api/v1`;

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

export async function request<T>(path: string, init: RequestInit = {}, token?: string): Promise<T> {
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(init.headers as HeadersInit),
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

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
