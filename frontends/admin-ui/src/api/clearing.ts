import { apiGet, apiPost } from "./client";
import { ClearingBatch, ClearingBatchDetails, ClearingBatchOperation } from "../types/clearing";

export async function fetchClearingBatches(params: {
  date_from?: string;
  date_to?: string;
  merchant_id?: string;
  status?: string;
}): Promise<ClearingBatch[]> {
  return apiGet("/clearing/batches", params);
}

export async function fetchClearingBatchDetails(id: string): Promise<ClearingBatchDetails> {
  return apiGet(`/clearing/batches/${id}`);
}

export async function markBatchSent(id: string): Promise<ClearingBatch> {
  return apiPost(`/clearing/batches/${id}/mark-sent`);
}

export async function markBatchConfirmed(id: string): Promise<ClearingBatch> {
  return apiPost(`/clearing/batches/${id}/mark-confirmed`);
}
