import { apiGet, apiPost } from "./client";
import { ClearingBatch, ClearingBatchOperation } from "../types/clearing";

export async function fetchClearingBatches(params: {
  date_from?: string;
  date_to?: string;
  merchant_id?: string;
  status?: string;
}): Promise<ClearingBatch[]> {
  return apiGet("/api/v1/admin/clearing/batches", params);
}

export async function fetchClearingBatch(id: string): Promise<ClearingBatch> {
  return apiGet(`/api/v1/admin/clearing/batches/${id}`);
}

export async function fetchClearingBatchOperations(id: string): Promise<ClearingBatchOperation[]> {
  return apiGet(`/api/v1/admin/clearing/batches/${id}/operations`);
}

export async function markBatchSent(id: string): Promise<ClearingBatch> {
  return apiPost(`/api/v1/admin/clearing/batches/${id}/mark-sent`);
}

export async function markBatchConfirmed(id: string): Promise<ClearingBatch> {
  return apiPost(`/api/v1/admin/clearing/batches/${id}/mark-confirmed`);
}
