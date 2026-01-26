import { apiGet, apiPost } from "./client";
import { request } from "./http";
import type {
  FinanceInvoiceDetail,
  FinanceInvoiceListResponse,
  FinanceOverview,
  PartnerLedgerSnapshot,
  PartnerSettlementSnapshot,
  PaymentIntakeDetail,
  PaymentIntakeListResponse,
} from "../types/finance";
import type { PayoutDetail, PayoutQueueListResponse } from "../types/payouts";

export const fetchFinanceOverview = async (window: "24h" | "7d" = "24h"): Promise<FinanceOverview> =>
  apiGet("/api/core/admin/finance/overview", { window });

export const fetchFinanceInvoices = async (params: {
  status?: string;
  org_id?: string;
  from?: string;
  to?: string;
  limit?: number;
  offset?: number;
}): Promise<FinanceInvoiceListResponse> => apiGet("/api/core/admin/finance/invoices", params);

export const fetchFinanceInvoice = async (invoiceId: string): Promise<FinanceInvoiceDetail> =>
  apiGet(`/api/core/admin/finance/invoices/${invoiceId}`);

export const markInvoicePaid = async (invoiceId: string, payload: { reason: string; correlation_id: string }) =>
  apiPost(`/api/core/admin/finance/invoices/${invoiceId}/mark-paid`, payload);

export const voidInvoice = async (invoiceId: string, payload: { reason: string; correlation_id: string }) =>
  apiPost(`/api/core/admin/finance/invoices/${invoiceId}/void`, payload);

export const markInvoiceOverdue = async (invoiceId: string, payload: { reason: string; correlation_id: string }) =>
  apiPost(`/api/core/admin/finance/invoices/${invoiceId}/mark-overdue`, payload);

export const fetchPaymentIntakes = async (params: {
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<PaymentIntakeListResponse> => apiGet("/api/core/admin/finance/payment-intakes", params);

export const fetchPaymentIntake = async (intakeId: number): Promise<PaymentIntakeDetail> =>
  apiGet(`/api/core/admin/finance/payment-intakes/${intakeId}`);

export const approvePaymentIntake = async (intakeId: number, payload: { reason: string; correlation_id: string }) =>
  apiPost(`/api/core/admin/finance/payment-intakes/${intakeId}/approve`, payload);

export const rejectPaymentIntake = async (intakeId: number, payload: { reason: string; correlation_id: string }) =>
  apiPost(`/api/core/admin/finance/payment-intakes/${intakeId}/reject`, payload);

export const fetchPayoutQueue = async (params: {
  status?: string;
  blocked?: boolean;
  reason?: string;
  limit?: number;
  offset?: number;
}): Promise<PayoutQueueListResponse> => apiGet("/api/core/admin/finance/payouts", params);

export const fetchPayoutDetail = async (payoutId: string): Promise<PayoutDetail> =>
  apiGet(`/api/core/admin/finance/payouts/${payoutId}`);

export const approvePayout = async (
  token: string,
  payoutId: string,
  payload: { reason: string; correlation_id: string },
) => request(`/admin/finance/payouts/${payoutId}/approve`, { method: "POST", body: JSON.stringify(payload) }, token);

export const rejectPayout = async (
  token: string,
  payoutId: string,
  payload: { reason: string; correlation_id: string },
) => request(`/admin/finance/payouts/${payoutId}/reject`, { method: "POST", body: JSON.stringify(payload) }, token);

export const markPayoutPaid = async (
  token: string,
  payoutId: string,
  payload: { reason: string; correlation_id: string },
) => request(`/admin/finance/payouts/${payoutId}/mark-paid`, { method: "POST", body: JSON.stringify(payload) }, token);

export const fetchPartnerLedger = async (partnerId: string): Promise<PartnerLedgerSnapshot> =>
  apiGet(`/api/core/admin/finance/partners/${partnerId}/ledger`);

export const fetchPartnerSettlement = async (partnerId: string): Promise<PartnerSettlementSnapshot> =>
  apiGet(`/api/core/admin/finance/partners/${partnerId}/settlement`);
