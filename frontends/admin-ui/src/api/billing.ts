import { apiGet, apiPost } from "./client";
import type {
  BillingSummaryItem,
  Invoice,
  InvoiceStatus,
  TariffPlan,
  TariffPrice,
} from "../types/billing";
import type {
  BillingInvoice,
  BillingInvoiceListResponse,
  BillingInvoiceResult,
  BillingLinksListResponse,
  BillingPayment,
  BillingPaymentResult,
  BillingPaymentsListResponse,
  BillingRefund,
  BillingRefundResult,
  BillingRefundsListResponse,
} from "../types/billingFlows";
import type { BillingPaymentIntake, BillingPaymentIntakeListResponse } from "../types/paymentIntakes";

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

const BILLING_FLOW_BASE = "/api/admin/billing/flows";
const RECONCILIATION_LINKS_BASE = "/api/admin/reconciliation/links";
const BILLING_PAYMENT_INTAKES_BASE = "/api/core/v1/admin/billing/payment-intakes";

const isNotAvailableMessage = (message?: string) => Boolean(message && /HTTP (404|501)\b/.test(message));

const handleAvailability = <T>(error: unknown, fallback: T): T => {
  if (error instanceof Error && isNotAvailableMessage(error.message)) {
    return fallback;
  }
  throw error;
};

export async function listInvoices(params?: {
  client_id?: string;
  status?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}): Promise<BillingInvoiceListResponse> {
  try {
    return await apiGet<BillingInvoiceListResponse>(`${BILLING_FLOW_BASE}/invoices`, params);
  } catch (error) {
    return handleAvailability(error, { items: [], total: 0, limit: 0, offset: 0, unavailable: true });
  }
}

export async function getInvoice(id: string): Promise<BillingInvoiceResult> {
  try {
    const invoice = await apiGet<BillingInvoice>(`${BILLING_FLOW_BASE}/invoices/${id}`);
    return { invoice };
  } catch (error) {
    return handleAvailability(error, { invoice: null, unavailable: true });
  }
}

export async function createInvoice(payload: {
  client_id: string;
  case_id?: string | null;
  currency: string;
  amount_total: number;
  due_at?: string | null;
  idempotency_key: string;
}): Promise<BillingInvoiceResult> {
  try {
    const invoice = await apiPost<BillingInvoice>(`${BILLING_FLOW_BASE}/invoices`, payload);
    return { invoice };
  } catch (error) {
    return handleAvailability(error, { invoice: null, unavailable: true });
  }
}

export async function listInvoicePayments(
  invoiceId: string,
  params?: { limit?: number; offset?: number },
): Promise<BillingPaymentsListResponse> {
  try {
    return await apiGet<BillingPaymentsListResponse>(`${BILLING_FLOW_BASE}/invoices/${invoiceId}/payments`, params);
  } catch (error) {
    return handleAvailability(error, { items: [], total: 0, limit: 0, offset: 0, unavailable: true });
  }
}

export async function captureInvoicePayment(
  invoiceId: string,
  payload: {
    provider: string;
    provider_payment_id?: string | null;
    amount: number;
    currency: string;
    idempotency_key: string;
  },
): Promise<BillingPaymentResult> {
  try {
    const payment = await apiPost<BillingPayment>(`${BILLING_FLOW_BASE}/invoices/${invoiceId}/capture`, payload);
    return { payment };
  } catch (error) {
    return handleAvailability(error, { payment: null, unavailable: true });
  }
}

export async function listPayments(params?: {
  provider?: string;
  status?: string;
  invoice_id?: string;
  date_from?: string;
  date_to?: string;
  search?: string;
  limit?: number;
  offset?: number;
}): Promise<BillingPaymentsListResponse> {
  try {
    return await apiGet<BillingPaymentsListResponse>(`${BILLING_FLOW_BASE}/payments`, params);
  } catch (error) {
    return handleAvailability(error, { items: [], total: 0, limit: 0, offset: 0, unavailable: true });
  }
}

export async function getPayment(id: string): Promise<BillingPaymentResult> {
  try {
    const payment = await apiGet<BillingPayment>(`${BILLING_FLOW_BASE}/payments/${id}`);
    return { payment };
  } catch (error) {
    return handleAvailability(error, { payment: null, unavailable: true });
  }
}

export async function listPaymentIntakes(params?: {
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<BillingPaymentIntakeListResponse> {
  return apiGet<BillingPaymentIntakeListResponse>(BILLING_PAYMENT_INTAKES_BASE, params);
}

export async function approvePaymentIntake(id: number, payload?: { review_note?: string | null }) {
  return apiPost<BillingPaymentIntake>(`${BILLING_PAYMENT_INTAKES_BASE}/${id}/approve`, payload ?? {});
}

export async function rejectPaymentIntake(id: number, payload: { review_note: string }) {
  return apiPost<BillingPaymentIntake>(`${BILLING_PAYMENT_INTAKES_BASE}/${id}/reject`, payload);
}

export async function refundPayment(
  paymentId: string,
  payload: {
    amount: number;
    currency: string;
    provider_refund_id?: string | null;
    idempotency_key: string;
  },
): Promise<BillingRefundResult> {
  try {
    const refund = await apiPost<BillingRefund>(`${BILLING_FLOW_BASE}/payments/${paymentId}/refund`, payload);
    return { refund };
  } catch (error) {
    return handleAvailability(error, { refund: null, unavailable: true });
  }
}

export async function listRefunds(params?: {
  provider?: string;
  status?: string;
  payment_id?: string;
  invoice_id?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}): Promise<BillingRefundsListResponse> {
  try {
    return await apiGet<BillingRefundsListResponse>(`${BILLING_FLOW_BASE}/refunds`, params);
  } catch (error) {
    return handleAvailability(error, { items: [], total: 0, limit: 0, offset: 0, unavailable: true });
  }
}

export async function listReconciliationLinks(params?: {
  provider?: string;
  status?: string;
  entity_type?: string;
  entity_id?: string;
  currency?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}): Promise<BillingLinksListResponse> {
  try {
    return await apiGet<BillingLinksListResponse>(RECONCILIATION_LINKS_BASE, params);
  } catch (error) {
    return handleAvailability(error, { items: [], total: 0, limit: 0, offset: 0, unavailable: true });
  }
}
