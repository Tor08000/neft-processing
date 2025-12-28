import { apiGet, apiPost } from "./client";
import {
  PayoutBatchDetail,
  PayoutBatchListResponse,
  PayoutBatchSummary,
  PayoutExportFile,
  PayoutExportFormatInfo,
  PayoutReconcileResult,
} from "../types/payouts";

export type PayoutBatchQuery = {
  partner_id?: string;
  state?: string | string[];
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
  sort?: string;
};

export function buildPayoutBatchesQuery(params: PayoutBatchQuery): Record<string, unknown> {
  return {
    ...params,
    state: Array.isArray(params.state) ? params.state.join(",") : params.state,
  };
}

export async function fetchPayoutBatches(params: PayoutBatchQuery): Promise<PayoutBatchListResponse> {
  return apiGet("/api/core/v1/payouts/batches", buildPayoutBatchesQuery(params));
}

export async function fetchPayoutBatchDetails(batchId: string): Promise<PayoutBatchDetail> {
  return apiGet(`/api/core/v1/payouts/batches/${batchId}`);
}

export async function reconcilePayoutBatch(batchId: string): Promise<PayoutReconcileResult> {
  return apiGet(`/api/core/v1/payouts/batches/${batchId}/reconcile`);
}

export async function markPayoutSent(
  batchId: string,
  payload: { provider: string; external_ref: string },
): Promise<PayoutBatchSummary> {
  return apiPost(`/api/core/v1/payouts/batches/${batchId}/mark-sent`, payload);
}

export async function markPayoutSettled(
  batchId: string,
  payload: { provider: string; external_ref: string },
): Promise<PayoutBatchSummary> {
  return apiPost(`/api/core/v1/payouts/batches/${batchId}/mark-settled`, payload);
}

export async function fetchPayoutExports(batchId: string): Promise<PayoutExportFile[]> {
  const response = await apiGet<{ items: PayoutExportFile[] }>(`/api/core/v1/payouts/batches/${batchId}/exports`);
  return response.items ?? [];
}

export async function createPayoutExport(
  batchId: string,
  payload: { format: "CSV" | "XLSX"; provider?: string; external_ref?: string; bank_format_code?: string },
): Promise<PayoutExportFile> {
  return apiPost(`/api/core/v1/payouts/batches/${batchId}/export`, payload);
}

export async function fetchPayoutExportFormats(): Promise<PayoutExportFormatInfo[]> {
  const response = await apiGet<{ items: PayoutExportFormatInfo[] }>("/api/core/v1/payouts/export-formats");
  return response.items ?? [];
}
