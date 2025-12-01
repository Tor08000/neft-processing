// services/admin-web/src/api/client.ts

// Базовые URL берём из Vite-ENV, с дефолтом на текущий origin
const AUTH_BASE_URL =
  import.meta.env.VITE_AUTH_BASE_URL ||
  `${window.location.origin}/auth/api`;

const ADMIN_API_BASE_URL =
  import.meta.env.VITE_ADMIN_API_BASE_URL ||
  `${window.location.origin}/api`;

// =========================
// Вспомогательные типы/утилиты
// =========================

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface AdminOperation {
  operation_id: string;
  created_at: string;
  operation_type: string;
  status: string;
  merchant_id: string;
  terminal_id: string;
  client_id: string;
  card_id: string;
  amount: number;
  currency: string;
  mcc?: string | null;
  product_category?: string | null;
  tx_type?: string | null;
}

export interface AdminTransaction {
  transaction_id: string;
  created_at: string;
  updated_at: string;
  client_id: string;
  card_id: string;
  merchant_id: string;
  terminal_id: string;
  status: string;
  authorized_amount: number;
  captured_amount: number;
  refunded_amount: number;
  currency: string;
  mcc?: string | null;
  product_category?: string | null;
  tx_type?: string | null;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

// Параметры для запросов админ-операций
export interface AdminOperationsQuery {
  token: string;
  limit?: number;
  offset?: number;
  operation_type?: string;
  client_id?: string;
  order_by?: string;
}

// Параметры для запросов админ-транзакций
export interface AdminTransactionsQuery {
  token: string;
  limit?: number;
  offset?: number;
  client_id?: string;
  order_by?: string;
}

// Утилита для сборки query-строки
function buildQuery(params: Record<string, string | number | undefined>) {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      sp.set(key, String(value));
    }
  });
  const qs = sp.toString();
  return qs ? `?${qs}` : "";
}

// Общий helper для fetch c проверкой ошибок
async function doFetch<T>(url: string, init: RequestInit): Promise<T> {
  const res = await fetch(url, init);

  if (!res.ok) {
    let detail: unknown = undefined;
    try {
      detail = await res.json();
    } catch {
      // ignore
    }
    const message = `HTTP ${res.status} ${
      res.statusText || ""
    }${detail ? `: ${JSON.stringify(detail)}` : ""}`;
    throw new Error(message);
  }

  return (await res.json()) as T;
}

// =========================
// API: логин администратора
// =========================

export async function adminLogin(
  email: string,
  password: string
): Promise<LoginResponse> {
  const url = `${AUTH_BASE_URL}/v1/auth/login`;

  return doFetch<LoginResponse>(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ email, password }),
  });
}

// =========================
// API: админ-операции
// =========================

export async function getAdminOperations(
  params: AdminOperationsQuery
): Promise<PaginatedResponse<AdminOperation>> {
  const { token, limit, offset, operation_type, client_id, order_by } = params;

  const qs = buildQuery({
    limit,
    offset,
    operation_type,
    client_id,
    order_by,
  });

  const url = `${ADMIN_API_BASE_URL}/v1/admin/operations${qs}`;

  return doFetch<PaginatedResponse<AdminOperation>>(url, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}

// =========================
// API: админ-транзакции
// =========================

export async function getAdminTransactions(
  params: AdminTransactionsQuery
): Promise<PaginatedResponse<AdminTransaction>> {
  const { token, limit, offset, client_id, order_by } = params;

  const qs = buildQuery({
    limit,
    offset,
    client_id,
    order_by,
  });

  const url = `${ADMIN_API_BASE_URL}/v1/admin/transactions${qs}`;

  return doFetch<PaginatedResponse<AdminTransaction>>(url, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}
