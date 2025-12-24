import { CORE_API_BASE } from "./http";
import { request } from "./http";
import type { AuthSession } from "./types";
import type { ClientInvoiceDetails, ClientInvoiceList } from "../types/invoices";

const withToken = (user: AuthSession | null): string | undefined => user?.token;

export interface InvoiceFilters {
  dateFrom?: string;
  dateTo?: string;
  status?: string[];
  limit?: number;
  offset?: number;
  sort?: string;
}

export function buildInvoiceQuery(filters: InvoiceFilters = {}): string {
  const search = new URLSearchParams();
  if (filters.dateFrom) search.set("date_from", filters.dateFrom);
  if (filters.dateTo) search.set("date_to", filters.dateTo);
  if (filters.status && filters.status.length > 0) {
    filters.status.forEach((value) => search.append("status", value));
  }
  if (filters.limit) search.set("limit", String(filters.limit));
  if (filters.offset) search.set("offset", String(filters.offset));
  if (filters.sort) search.set("sort", filters.sort);
  return search.toString();
}

export function fetchInvoices(user: AuthSession | null, filters: InvoiceFilters = {}): Promise<ClientInvoiceList> {
  const query = buildInvoiceQuery(filters);
  const path = query ? `/invoices?${query}` : "/invoices";
  return request<ClientInvoiceList>(path, { method: "GET" }, withToken(user));
}

export async function fetchInvoiceDetails(id: string, user: AuthSession | null): Promise<ClientInvoiceDetails> {
  const token = withToken(user);
  const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
  const response = await fetch(`${CORE_API_BASE}/invoices/${id}`, { headers });

  if (response.status === 404) {
    throw new Error("invoice_not_found");
  }
  if (response.status === 403) {
    throw new Error("invoice_forbidden");
  }
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<ClientInvoiceDetails>;
}

const parseFilename = (header: string | null): string | null => {
  if (!header) return null;
  const match = header.match(/filename=\"?([^\";]+)\"?/i);
  return match?.[1] ?? null;
};

export async function downloadInvoicePdf(id: string, user: AuthSession | null): Promise<void> {
  const token = withToken(user);
  const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
  const response = await fetch(`${CORE_API_BASE}/invoices/${id}/pdf`, { headers });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  const blob = await response.blob();
  const filename = parseFilename(response.headers.get("Content-Disposition")) ?? `invoice-${id}.pdf`;
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  window.URL.revokeObjectURL(url);
}
