import { apiGet, apiPost } from "./client";
import { PayoutBatchDetail, PayoutBatchSummary, PayoutExportFile } from "../types/payouts";

export async function fetchPayoutBatches(params: {
  partner_id?: string;
  state?: string;
  date_from?: string;
  date_to?: string;
}): Promise<PayoutBatchSummary[]> {
  const response = await apiGet<{ items: PayoutBatchSummary[] }>("/api/core/api/v1/payouts/batches", params);
  return response.items ?? [];
}

export async function fetchPayoutBatchDetails(batchId: string): Promise<PayoutBatchDetail> {
  return apiGet(`/api/core/api/v1/payouts/batches/${batchId}`);
}

export async function fetchPayoutExports(batchId: string): Promise<PayoutExportFile[]> {
  const response = await apiGet<{ items: PayoutExportFile[] }>(
    `/api/core/api/v1/payouts/batches/${batchId}/exports`,
  );
  return response.items ?? [];
}

export async function createPayoutExport(
  batchId: string,
  payload: { format: "CSV" | "XLSX"; provider?: string; external_ref?: string },
): Promise<PayoutExportFile> {
  return apiPost(`/api/core/api/v1/payouts/batches/${batchId}/export`, payload);
}
