import { apiGet, apiPost } from "./client";
import type {
  FinanceInvoiceDetail,
  FinanceInvoiceListResponse,
  FinanceOverview,
  PaymentIntakeDetail,
  PaymentIntakeListResponse,
} from "../types/finance";
import type { PayoutDetail, PayoutQueueListResponse } from "../types/payouts";

export const fetchFinanceOverview = async (window: "24h" | "7d" = "24h"): Promise<FinanceOverview> =>
  apiGet("/api/core/v1/admin/finance/overview", { window });

export const fetchFinanceInvoices = async (params: {
  status?: string;
  org_id?: string;
  from?: string;
  to?: string;
  limit?: number;
  offset?: number;
}): Promise<FinanceInvoiceListResponse> => apiGet("/api/core/v1/admin/finance/invoices", params);

export const fetchFinanceInvoice = async (invoiceId: string): Promise<FinanceInvoiceDetail> =>
  apiGet(`/api/core/v1/admin/finance/invoices/${invoiceId}`);

export const markInvoicePaid = async (invoiceId: string, reason: string) =>
  apiPost(`/api/core/v1/admin/finance/invoices/${invoiceId}/mark-paid`, { reason });

export const voidInvoice = async (invoiceId: string, reason: string) =>
  apiPost(`/api/core/v1/admin/finance/invoices/${invoiceId}/void`, { reason });

export const markInvoiceOverdue = async (invoiceId: string, reason: string) =>
  apiPost(`/api/core/v1/admin/finance/invoices/${invoiceId}/mark-overdue`, { reason });

export const fetchPaymentIntakes = async (params: {
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<PaymentIntakeListResponse> => apiGet("/api/core/v1/admin/finance/payment-intakes", params);

export const fetchPaymentIntake = async (intakeId: number): Promise<PaymentIntakeDetail> =>
  apiGet(`/api/core/v1/admin/finance/payment-intakes/${intakeId}`);

export const approvePaymentIntake = async (intakeId: number, reason: string) =>
  apiPost(`/api/core/v1/admin/finance/payment-intakes/${intakeId}/approve`, { reason });

export const rejectPaymentIntake = async (intakeId: number, reason: string) =>
  apiPost(`/api/core/v1/admin/finance/payment-intakes/${intakeId}/reject`, { reason });

export const fetchPayoutQueue = async (params: {
  status?: string;
  blocked?: boolean;
  reason?: string;
  limit?: number;
  offset?: number;
}): Promise<PayoutQueueListResponse> => apiGet("/api/core/v1/admin/finance/payouts", params);

export const fetchPayoutDetail = async (payoutId: string): Promise<PayoutDetail> =>
  apiGet(`/api/core/v1/admin/finance/payouts/${payoutId}`);

export const approvePayout = async (payoutId: string, reason: string) =>
  apiPost(`/api/core/v1/admin/finance/payouts/${payoutId}/approve`, { reason });

export const rejectPayout = async (payoutId: string, reason: string) =>
  apiPost(`/api/core/v1/admin/finance/payouts/${payoutId}/reject`, { reason });

export const markPayoutPaid = async (payoutId: string, reason: string) =>
  apiPost(`/api/core/v1/admin/finance/payouts/${payoutId}/mark-paid`, { reason });
