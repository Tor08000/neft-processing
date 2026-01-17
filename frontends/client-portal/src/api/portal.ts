import { request } from "./http";
import type { AuthSession } from "./types";
import type {
  ClientContractDetails,
  ClientContractsResponse,
  ClientDashboardResponse,
  ClientInvoiceDetails,
  ClientInvoiceListResponse,
} from "../types/portal";

const withToken = (user: AuthSession | null) => ({ token: user?.token, base: "core_root" as const });

export type InvoiceFilters = {
  dateFrom?: string;
  dateTo?: string;
  status?: string[];
  limit?: number;
  offset?: number;
};

const buildInvoiceQuery = (filters: InvoiceFilters): string => {
  const params = new URLSearchParams();
  if (filters.dateFrom) params.set("date_from", filters.dateFrom);
  if (filters.dateTo) params.set("date_to", filters.dateTo);
  if (filters.status?.length) {
    filters.status.forEach((status) => params.append("status", status));
  }
  if (filters.limit !== undefined) params.set("limit", String(filters.limit));
  if (filters.offset !== undefined) params.set("offset", String(filters.offset));
  const query = params.toString();
  return query ? `?${query}` : "";
};

export const fetchClientDashboard = (user: AuthSession | null) =>
  request<ClientDashboardResponse>("/client/dashboard", { method: "GET" }, withToken(user));

export const fetchClientInvoices = (user: AuthSession | null, filters: InvoiceFilters = {}) =>
  request<ClientInvoiceListResponse>(`/client/invoices${buildInvoiceQuery(filters)}`, { method: "GET" }, withToken(user));

export const fetchClientInvoiceDetails = (user: AuthSession | null, invoiceRef: string) =>
  request<ClientInvoiceDetails>(`/client/invoices/${invoiceRef}`, { method: "GET" }, withToken(user));

export const fetchClientContracts = (user: AuthSession | null) =>
  request<ClientContractsResponse>("/client/contracts", { method: "GET" }, withToken(user));

export const fetchClientContractDetails = (user: AuthSession | null, contractId: string) =>
  request<ClientContractDetails>(`/client/contracts/${contractId}`, { method: "GET" }, withToken(user));
