import { apiGet, apiPost } from "./client";
import { ClearingBatch, ClearingBatchDetails, ClearingBatchOperation } from "../types/clearing";

export async function fetchClearingBatches(params: {
  date_from?: string;
  date_to?: string;
  merchant_id?: string;
  status?: string;
}): Promise<ClearingBatch[]> {
  return apiGet("/api/core/v1/admin/clearing/batches", params);
}

export async function fetchClearingBatchDetails(id: string): Promise<ClearingBatchDetails> {
  return apiGet(`/api/core/v1/admin/clearing/batches/${id}`);
}

export async function markBatchSent(id: string): Promise<ClearingBatch> {
  return apiPost(`/api/core/v1/admin/clearing/batches/${id}/mark-sent`);
}

export async function markBatchConfirmed(id: string): Promise<ClearingBatch> {
  return apiPost(`/api/core/v1/admin/clearing/batches/${id}/mark-confirmed`);
}
