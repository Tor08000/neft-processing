const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost/api";

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export async function login(email: string, password: string): Promise<LoginResponse> {
  const resp = await fetch(`${API_BASE_URL}/v1/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ email, password }),
  });

  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`Login failed: ${resp.status} ${text}`);
  }

  return resp.json();
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

interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

async function authorizedGet<T>(
  path: string,
  token: string,
): Promise<PaginatedResponse<T>> {
  const resp = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`Request failed: ${resp.status} ${text}`);
  }

  return resp.json();
}

export function getAdminOperations(params: {
  token: string;
  limit?: number;
  offset?: number;
  operation_type?: string;
  client_id?: string;
}): Promise<PaginatedResponse<AdminOperation>> {
  const search = new URLSearchParams();
  if (params.limit !== undefined) search.set("limit", String(params.limit));
  if (params.offset !== undefined) search.set("offset", String(params.offset));
  if (params.operation_type) search.set("operation_type", params.operation_type);
  if (params.client_id) search.set("client_id", params.client_id);

  const query = search.toString();
  const path = `/v1/admin/operations${query ? "?" + query : ""}`;

  return authorizedGet<AdminOperation>(path, params.token);
}

export function getAdminTransactions(params: {
  token: string;
  limit?: number;
  offset?: number;
  client_id?: string;
}): Promise<PaginatedResponse<AdminTransaction>> {
  const search = new URLSearchParams();
  if (params.limit !== undefined) search.set("limit", String(params.limit));
  if (params.offset !== undefined) search.set("offset", String(params.offset));
  if (params.client_id) search.set("client_id", params.client_id);

  const query = search.toString();
  const path = `/v1/admin/transactions${query ? "?" + query : ""}`;

  return authorizedGet<AdminTransaction>(path, params.token);
}
