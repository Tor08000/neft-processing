import { request } from "./http";
import type { AuthSession } from "./types";
import type { OperationDetails, OperationsPage } from "../types/operations";

const withToken = (user: AuthSession | null): string | undefined => user?.token;

interface OperationFilters {
  status?: string;
  cardId?: string;
  from?: string;
  to?: string;
  limit?: number;
  offset?: number;
}

export function fetchOperations(user: AuthSession | null, filters: OperationFilters = {}): Promise<OperationsPage> {
  const search = new URLSearchParams();
  if (filters.status) search.set("status", filters.status);
  if (filters.cardId) search.set("card_id", filters.cardId);
  if (filters.from) search.set("from", filters.from);
  if (filters.to) search.set("to", filters.to);
  if (filters.limit) search.set("limit", filters.limit.toString());
  if (filters.offset) search.set("offset", filters.offset.toString());

  const query = search.toString();
  const path = query ? `/operations?${query}` : "/operations";
  return request<OperationsPage>(path, { method: "GET" }, withToken(user));
}

export function fetchOperationDetails(id: string, user: AuthSession | null): Promise<OperationDetails> {
  return request<OperationDetails>(`/operations/${id}`, { method: "GET" }, withToken(user));
}
