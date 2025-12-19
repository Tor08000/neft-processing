import type { DashboardSummary, Limit, Operation, ClientUser } from "./types";

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "http://gateway").replace(/\/$/, "");
const clientBase = (import.meta.env.BASE_URL ?? "/client/").replace(/\/$/, "");
const API_BASE = `${apiBase}${clientBase}/api/v1`;

interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  email: string;
  subject_type: string;
  client_id?: string | null;
}

interface LoginResult {
  token: string;
  tokenType: string;
  expiresIn: number;
  email: string;
  clientId?: string;
  subjectType: string;
}

export class UnauthorizedError extends Error {
  constructor(message = "Требуется повторный вход") {
    super(message);
    this.name = "UnauthorizedError";
  }
}

export class InvalidLoginPayloadError extends Error {
  constructor(message = "Неверный формат данных для входа") {
    super(message);
    this.name = "InvalidLoginPayloadError";
  }
}

export function handleUnauthorized(error: unknown): boolean {
  if (error instanceof UnauthorizedError) {
    // При 401/403 сбрасываем токен и возвращаем пользователя на экран логина.
    localStorage.removeItem("client_token");
    window.location.href = `${clientBase}/`;
    return true;
  }
  return false;
}

async function parseJsonOrThrow(response: Response, errorMessage: string) {
  if (response.status === 401 || response.status === 403) {
    throw new UnauthorizedError();
  }
  if (!response.ok) {
    throw new Error(errorMessage);
  }
  return response.json();
}

export async function login(email: string, password: string): Promise<LoginResult> {
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (response.status === 401 || response.status === 403) {
    throw new UnauthorizedError();
  }

  if (response.status === 422) {
    try {
      const details = await response.json();
      console.error("Invalid login payload", details);
    } catch (error) {
      console.error("Invalid login payload", error);
    }
    throw new InvalidLoginPayloadError();
  }

  if (!response.ok) {
    throw new Error("Неверные учётные данные");
  }

  const body = (await response.json()) as TokenResponse;
  return {
    token: body.access_token,
    tokenType: body.token_type,
    expiresIn: body.expires_in,
    email: body.email,
    clientId: body.client_id ?? undefined,
    subjectType: body.subject_type,
  };
}

function authHeaders(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` };
}

export async function fetchMe(token: string): Promise<ClientUser> {
  const response = await fetch(`${API_BASE}/auth/me`, { headers: authHeaders(token) });
  const body = await parseJsonOrThrow(response, "Не удалось загрузить профиль");
  return {
    id: body.subject,
    email: body.email,
    fullName: body.email,
    role: "OWNER",
    status: "active",
    organization: {
      id: body.client_id ?? "demo-client",
      name: "Demo Logistics LLC",
      status: "active",
    },
  };
}

export async function fetchDashboard(token: string): Promise<{
  summary: DashboardSummary;
  recentOperations: Operation[];
  limits: Limit[];
}> {
  const response = await fetch(`${API_BASE}/dashboard`, { headers: authHeaders(token) });
  const body = await parseJsonOrThrow(response, "Не удалось загрузить дашборд");
  return {
    summary: {
      totalOperations: body.summary.total_operations,
      totalAmount: body.summary.total_amount,
      period: body.summary.period,
      activeLimits: body.summary.active_limits,
    },
    recentOperations: body.recent_operations.map((op: any) => ({
      id: op.id,
      date: op.date,
      type: op.type,
      status: op.status,
      amount: op.amount,
      fuelType: op.fuel_type,
      cardRef: op.card_ref,
    })),
    limits: body.limits.map((limit: any) => ({
      id: limit.id,
      type: limit.type,
      period: limit.period,
      amount: limit.amount,
      used: limit.used,
    })),
  };
}

export async function fetchOperations(token: string, params: { status?: string; limit?: number; offset?: number }) {
  const search = new URLSearchParams();
  if (params.status) search.set("status", params.status);
  if (params.limit) search.set("limit", params.limit.toString());
  if (params.offset) search.set("offset", params.offset.toString());

  const response = await fetch(`${API_BASE}/operations?${search.toString()}`, {
    headers: authHeaders(token),
  });
  const body = await parseJsonOrThrow(response, "Не удалось загрузить операции");
  return {
    items: (body.items as any[]).map((op) => ({
      id: op.id,
      date: op.date,
      type: op.type,
      status: op.status,
      amount: op.amount,
      fuelType: op.fuel_type,
      cardRef: op.card_ref,
    })),
    total: body.total as number,
    limit: body.limit as number,
    offset: body.offset as number,
  };
}

export async function fetchLimits(token: string): Promise<Limit[]> {
  const response = await fetch(`${API_BASE}/limits`, { headers: authHeaders(token) });
  const body = await parseJsonOrThrow(response, "Не удалось загрузить лимиты");
  return (body.items as any[]).map((item) => ({
    id: item.id,
    type: item.type,
    period: item.period,
    amount: item.amount,
    used: item.used,
  }));
}
