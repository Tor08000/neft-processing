const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "http://gateway").replace(/\/$/, "");
const clientBase = (import.meta.env.BASE_URL ?? "/client/").replace(/\/$/, "");
export const API_BASE = `${apiBase}${clientBase}/api/v1`;

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

const buildHeaders = (token?: string): HttpHeaders => {
  const headers: HttpHeaders = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
};

export async function request<T>(path: string, init: RequestInit = {}, token?: string): Promise<T> {
  const headers: HttpHeaders = { ...buildHeaders(token), ...(init.headers as HttpHeaders) };
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers });

  if (response.status === 401) {
    throw new UnauthorizedError();
  }
  if (response.status === 422) {
    const details = await response.json().catch(() => undefined);
    throw new ValidationError("Ошибка валидации", details);
  }
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with status ${response.status}`);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json() as Promise<T>;
}
