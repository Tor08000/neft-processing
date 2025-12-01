const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? window.location.origin;
const AUTH_BASE_URL = import.meta.env.VITE_AUTH_BASE_URL ?? `${API_BASE_URL}/auth/api`;
const ADMIN_API_BASE_URL = import.meta.env.VITE_ADMIN_API_BASE_URL ?? `${API_BASE_URL}/api`;

export interface AdminLoginRequest {
  email: string;
  password: string;
}

export interface AdminLoginResponse {
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
  mcc: string | null;
  product_category: string | null;
  tx_type: string | null;
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
  mcc: string | null;
  product_category: string | null;
  tx_type: string | null;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export async function adminLogin(
  payload: AdminLoginRequest,
): Promise<AdminLoginResponse> {
  const resp = await fetch(`${AUTH_BASE_URL}/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!resp.ok) {
    throw new Error(`Login failed: ${resp.status}`);
  }

  return resp.json();
}

function buildUrl(base: string, path: string): URL {
  return new URL(`${base}${path}`, window.location.origin);
}

export async function getAdminOperations(params: {
  token: string;
  limit?: number;
  offset?: number;
  operation_type?: string;
  order_by?: string;
  client_id?: string;
}): Promise<PaginatedResponse<AdminOperation>> {
  const url = buildUrl(ADMIN_API_BASE_URL, "/v1/admin/operations");
  if (params.limit != null) url.searchParams.set("limit", String(params.limit));
  if (params.offset != null) url.searchParams.set("offset", String(params.offset));
  if (params.operation_type) url.searchParams.set("operation_type", params.operation_type);
  if (params.order_by) url.searchParams.set("order_by", params.order_by);
  if (params.client_id) url.searchParams.set("client_id", params.client_id);

  const resp = await fetch(url.toString().replace(window.location.origin, ""), {
    headers: { Authorization: `Bearer ${params.token}` },
  });

  if (!resp.ok) {
    throw new Error(`Failed to load operations: ${resp.status}`);
  }

  return resp.json();
}

export async function getAdminTransactions(params: {
  token: string;
  limit?: number;
  offset?: number;
  client_id?: string;
}): Promise<PaginatedResponse<AdminTransaction>> {
  const url = buildUrl(ADMIN_API_BASE_URL, "/v1/admin/transactions");
  if (params.limit != null) url.searchParams.set("limit", String(params.limit));
  if (params.offset != null) url.searchParams.set("offset", String(params.offset));
  if (params.client_id) url.searchParams.set("client_id", params.client_id);

  const resp = await fetch(url.toString().replace(window.location.origin, ""), {
    headers: { Authorization: `Bearer ${params.token}` },
  });

  if (!resp.ok) {
    throw new Error(`Failed to load transactions: ${resp.status}`);
  }

  return resp.json();
}
