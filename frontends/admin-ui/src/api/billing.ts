import { apiGet, apiPost } from "./client";
import { BillingSummaryItem } from "../types/billing";

export async function fetchBillingSummary(params: {
  date_from?: string;
  date_to?: string;
  client_id?: string;
  merchant_id?: string;
  product_type?: string;
}): Promise<BillingSummaryItem[]> {
  return apiGet("/api/v1/admin/billing/summary", params);
}

export async function finalizeBillingSummary(id: string): Promise<BillingSummaryItem> {
  return apiPost(`/api/v1/admin/billing/summary/${id}/finalize`);
}
