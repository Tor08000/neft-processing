import { apiGet } from "./client";

export interface AccountBalance {
  id: number;
  client_id: string;
  card_id?: string | null;
  tariff_id?: string | null;
  currency: string;
  type: string;
  status: string;
  balance: number;
}

export interface AccountsPage {
  items: AccountBalance[];
  total: number;
}

export interface LedgerEntry {
  id: number;
  operation_id?: string;
  posted_at: string;
  direction: string;
  amount: number;
  currency: string;
  balance_after?: number;
}

export interface StatementResponse {
  account_id: number;
  entries: LedgerEntry[];
}

export function fetchAccounts(params?: { client_id?: string; status?: string; limit?: number; offset?: number }) {
  return apiGet<AccountsPage>("/api/core/v1/admin/accounts", params);
}

export function fetchClientBalances(clientId: string) {
  return apiGet<AccountBalance[]>(`/api/core/v1/admin/clients/${clientId}/balances`);
}

export function fetchAccountStatement(accountId: number, params?: { start_date?: string; end_date?: string }) {
  return apiGet<StatementResponse>(`/api/core/v1/admin/accounts/${accountId}/statement`, params);
}
