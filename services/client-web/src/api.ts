import type { DashboardSummary, Limit, Operation, ClientUser } from "./types";

const API_BASE = "/client/api/v1";

interface TokenResponse {
  access_token: string;
  email: string;
  client_id?: string;
  subject_type?: string;
  expires_in: number;
}

export class UnauthorizedError extends Error {
  constructor(message = "Требуется повторный вход") {
    super(message);
    this.name = "UnauthorizedError";
  }
}

export function handleUnauthorized(error: unknown): boolean {
  if (error instanceof UnauthorizedError) {
    // При 401/403 сбрасываем токен и возвращаем пользователя на экран логина.
    localStorage.removeItem("client_token");
    window.location.href = "/client/";
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

export async function login(email: string, password: string): Promise<{ token: string; email: string; clientId?: string }>
{
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  const body = (await parseJsonOrThrow(response, "Неверные учётные данные")) as TokenResponse;
  return { token: body.access_token, email: body.email, clientId: body.client_id };
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
