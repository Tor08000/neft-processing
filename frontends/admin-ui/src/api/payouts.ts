import { apiGet, apiPost } from "./client";
import {
  MarkPayoutPayload,
  PayoutBatchDetails,
  PayoutBatchesQuery,
  PayoutBatchesResponse,
  PayoutReconcileResult,
} from "../types/payouts";

export function buildPayoutBatchesQuery(filters: PayoutBatchesQuery): Record<string, string | number> {
  const params: Record<string, string | number> = {};

  if (filters.tenant_id) params.tenant_id = filters.tenant_id;
  if (filters.partner_id) params.partner_id = filters.partner_id;
  if (filters.date_from) params.date_from = filters.date_from;
  if (filters.date_to) params.date_to = filters.date_to;
  if (filters.limit !== undefined) params.limit = filters.limit;
  if (filters.offset !== undefined) params.offset = filters.offset;
  if (filters.sort) params.sort = filters.sort;
  if (filters.state && filters.state.length > 0) {
    params.state = filters.state.join(",");
  }

  return params;
}

export async function getPayoutBatches(filters: PayoutBatchesQuery): Promise<PayoutBatchesResponse> {
  return apiGet("/api/v1/payouts/batches", buildPayoutBatchesQuery(filters));
}

export async function getPayoutBatch(id: string): Promise<PayoutBatchDetails> {
  return apiGet(`/api/v1/payouts/batches/${id}`);
}

export async function reconcilePayoutBatch(id: string): Promise<PayoutReconcileResult> {
  return apiGet(`/api/v1/payouts/batches/${id}/reconcile`);
}

export async function markPayoutSent(id: string, payload: MarkPayoutPayload): Promise<void> {
  return apiPost(`/api/v1/payouts/batches/${id}/mark-sent`, payload);
}

export async function markPayoutSettled(id: string, payload: MarkPayoutPayload): Promise<void> {
  return apiPost(`/api/v1/payouts/batches/${id}/mark-settled`, payload);
}
