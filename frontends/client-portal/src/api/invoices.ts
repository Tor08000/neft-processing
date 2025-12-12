import { request } from "./http";
import type { AuthSession } from "./types";
import type { ClientInvoiceDetails, ClientInvoiceList } from "../types/invoices";

const withToken = (user: AuthSession | null): string | undefined => user?.token;

interface InvoiceFilters {
  from?: string;
  to?: string;
  status?: string;
}

export function fetchInvoices(user: AuthSession | null, filters: InvoiceFilters = {}): Promise<ClientInvoiceList> {
  const search = new URLSearchParams();
  if (filters.from) search.set("from", filters.from);
  if (filters.to) search.set("to", filters.to);
  if (filters.status) search.set("status", filters.status);

  const query = search.toString();
  const path = query ? `/invoices?${query}` : "/invoices";
  return request<ClientInvoiceList>(path, { method: "GET" }, withToken(user));
}

export function fetchInvoiceDetails(id: string, user: AuthSession | null): Promise<ClientInvoiceDetails> {
  return request<ClientInvoiceDetails>(`/invoices/${id}`, { method: "GET" }, withToken(user));
}
