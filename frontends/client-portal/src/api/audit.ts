import { request } from "./http";
import type { AuthSession } from "./types";
import type { ClientAuditList } from "../types/invoices";

const withToken = (user: AuthSession | null): string | undefined => user?.token;

export interface AuditFilters {
  dateFrom?: string;
  dateTo?: string;
  eventType?: string[];
  limit?: number;
  offset?: number;
}

export interface AuditSearchFilters extends AuditFilters {
  externalRef: string;
  provider?: string;
}

export const buildInvoiceAuditQuery = (filters: AuditFilters = {}): string => {
  const search = new URLSearchParams();
  if (filters.dateFrom) search.set("date_from", filters.dateFrom);
  if (filters.dateTo) search.set("date_to", filters.dateTo);
  if (filters.eventType && filters.eventType.length > 0) {
    filters.eventType.forEach((value) => search.append("event_type", value));
  }
  if (filters.limit) search.set("limit", String(filters.limit));
  if (filters.offset) search.set("offset", String(filters.offset));
  return search.toString();
};

export const buildAuditSearchQuery = (filters: AuditSearchFilters): string => {
  const search = new URLSearchParams();
  search.set("external_ref", filters.externalRef);
  if (filters.provider) search.set("provider", filters.provider);
  if (filters.dateFrom) search.set("date_from", filters.dateFrom);
  if (filters.dateTo) search.set("date_to", filters.dateTo);
  if (filters.eventType && filters.eventType.length > 0) {
    filters.eventType.forEach((value) => search.append("event_type", value));
  }
  if (filters.limit) search.set("limit", String(filters.limit));
  if (filters.offset) search.set("offset", String(filters.offset));
  return search.toString();
};

export function fetchInvoiceAudit(
  invoiceId: string,
  user: AuthSession | null,
  filters: AuditFilters = {},
): Promise<ClientAuditList> {
  const query = buildInvoiceAuditQuery(filters);
  const path = query ? `/invoices/${invoiceId}/audit?${query}` : `/invoices/${invoiceId}/audit`;
  return request<ClientAuditList>(path, { method: "GET" }, withToken(user));
}

export function searchAuditByExternalRef(
  user: AuthSession | null,
  filters: AuditSearchFilters,
): Promise<ClientAuditList> {
  const query = buildAuditSearchQuery(filters);
  const path = query ? `/audit/search?${query}` : "/audit/search";
  return request<ClientAuditList>(path, { method: "GET" }, withToken(user));
}
