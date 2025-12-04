import type { AuthSession, LoginRequest, LoginResponse, MeResponse } from "./types";

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost").replace(/\/$/, "");
const clientBase = (import.meta.env.VITE_CLIENT_BASE_PATH ?? "/client").replace(/\/$/, "");
const API_BASE = `${apiBase}${clientBase}/api/v1`;

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

async function handleJson<T>(response: Response): Promise<T> {
  if (response.status === 401) {
    throw new UnauthorizedError();
  }
  if (response.status === 422) {
    const details = await response.json().catch(() => undefined);
    throw new ValidationError("Ошибка валидации", details);
  }
  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function login(payload: LoginRequest): Promise<AuthSession> {
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const body = await handleJson<LoginResponse>(response);
  return {
    token: body.access_token,
    email: body.email,
    roles: body.roles,
    subjectType: body.subject_type,
    clientId: body.client_id ?? undefined,
    expiresAt: Date.now() + body.expires_in * 1000,
  };
}

export async function fetchMe(token: string): Promise<MeResponse> {
  const response = await fetch(`${API_BASE}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  return handleJson<MeResponse>(response);
}
