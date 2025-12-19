import { apiGet, apiPost } from "./client";
import type {
  BillingSummaryItem,
  Invoice,
  InvoiceStatus,
  TariffPlan,
  TariffPrice,
} from "../types/billing";

export async function fetchBillingSummary(params: {
  date_from?: string;
  date_to?: string;
  client_id?: string;
  merchant_id?: string;
  product_type?: string;
}): Promise<BillingSummaryItem[]> {
  return apiGet("/api/core/v1/admin/billing/summary", params);
}

export async function finalizeBillingSummary(id: string): Promise<BillingSummaryItem> {
  return apiPost(`/api/core/v1/admin/billing/summary/${id}/finalize`);
}

export async function fetchTariffs(params?: { limit?: number; offset?: number }) {
  return apiGet<{ items: TariffPlan[]; total: number; limit: number; offset: number }>(
    "/api/core/v1/admin/billing/tariffs",
    params,
  );
}

export async function fetchTariff(tariffId: string): Promise<TariffPlan> {
  return apiGet(`/api/core/v1/admin/billing/tariffs/${tariffId}`);
}

export async function fetchTariffPrices(tariffId: string): Promise<{ items: TariffPrice[] }> {
  return apiGet(`/api/core/v1/admin/billing/tariffs/${tariffId}/prices`);
}

export async function upsertTariffPrice(tariffId: string, payload: Partial<TariffPrice>) {
  return apiPost<TariffPrice>(`/api/core/v1/admin/billing/tariffs/${tariffId}/prices`, payload);
}

export async function fetchInvoices(params?: {
  client_id?: string;
  period_from?: string;
  period_to?: string;
  status?: InvoiceStatus;
}) {
  return apiGet<{ items: Invoice[]; total: number; limit: number; offset: number }>(
    "/api/core/v1/admin/billing/invoices",
    params,
  );
}

export async function fetchInvoice(invoiceId: string): Promise<Invoice> {
  return apiGet(`/api/core/v1/admin/billing/invoices/${invoiceId}`);
}

export async function generateInvoices(payload: { period_from: string; period_to: string }) {
  return apiPost<{ created_ids: string[] }>("/api/core/v1/admin/billing/invoices/generate", payload);
}

export async function updateInvoiceStatus(invoiceId: string, status: InvoiceStatus) {
  return apiPost<Invoice>(`/api/core/v1/admin/billing/invoices/${invoiceId}/status`, { status });
}
