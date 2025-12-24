import { apiGet, apiPost } from "./client";
import {
  PayoutBatchDetail,
  PayoutBatchSummary,
  PayoutExportFile,
  PayoutExportFormatInfo,
} from "../types/payouts";

export async function fetchPayoutBatches(params: {
  partner_id?: string;
  state?: string;
  date_from?: string;
  date_to?: string;
}): Promise<PayoutBatchSummary[]> {
  const response = await apiGet<{ items: PayoutBatchSummary[] }>("/api/core/v1/payouts/batches", params);
  return response.items ?? [];
}

export async function fetchPayoutBatchDetails(batchId: string): Promise<PayoutBatchDetail> {
  return apiGet(`/api/core/v1/payouts/batches/${batchId}`);
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
