import { CORE_API_BASE } from "./http";
import { request } from "./http";
import type { AuthSession } from "./types";
import type { ReconciliationRequest, ReconciliationRequestList } from "../types/reconciliation";

const withToken = (user: AuthSession | null): string | undefined => user?.token;

export interface ReconciliationFilters {
  status?: string[];
  dateFrom?: string;
  dateTo?: string;
  limit?: number;
  offset?: number;
}

export function buildReconciliationQuery(filters: ReconciliationFilters = {}): string {
  const search = new URLSearchParams();
  if (filters.status && filters.status.length > 0) {
    filters.status.forEach((value) => search.append("status", value));
  }
  if (filters.dateFrom) search.set("date_from", filters.dateFrom);
  if (filters.dateTo) search.set("date_to", filters.dateTo);
  if (filters.limit) search.set("limit", String(filters.limit));
  if (filters.offset) search.set("offset", String(filters.offset));
  return search.toString();
}

export function fetchReconciliationRequests(
  user: AuthSession | null,
  filters: ReconciliationFilters = {},
): Promise<ReconciliationRequestList> {
  const query = buildReconciliationQuery(filters);
  const path = query ? `/reconciliation-requests?${query}` : "/reconciliation-requests";
  return request<ReconciliationRequestList>(path, { method: "GET" }, withToken(user));
}

export function createReconciliationRequest(
  user: AuthSession | null,
  payload: { date_from: string; date_to: string; note?: string },
): Promise<ReconciliationRequest> {
  return request<ReconciliationRequest>(
    "/reconciliation-requests",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    withToken(user),
  );
}

const parseFilename = (header: string | null): string | null => {
  if (!header) return null;
  const match = header.match(/filename=\"?([^\";]+)\"?/i);
  return match?.[1] ?? null;
};

export async function downloadReconciliationResult(id: string, user: AuthSession | null): Promise<void> {
  const token = withToken(user);
  const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
  const response = await fetch(`${CORE_API_BASE}/reconciliation-requests/${id}/download`, { headers });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  const blob = await response.blob();
  const filename = parseFilename(response.headers.get("Content-Disposition")) ?? `reconciliation-${id}.pdf`;
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  window.URL.revokeObjectURL(url);
}
