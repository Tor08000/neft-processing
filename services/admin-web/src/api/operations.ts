import { apiGet } from "./client";
import { Operation, OperationListResponse } from "../types/operations";

export async function fetchOperations(params: {
  limit?: number;
  offset?: number;
  operation_type?: string;
  status?: string;
  merchant_id?: string;
  date_from?: string;
  date_to?: string;
}): Promise<OperationListResponse> {
  return apiGet("/api/core/api/v1/admin/operations", params);
}

export async function fetchOperation(id: string): Promise<Operation> {
  return apiGet(`/api/core/api/v1/admin/operations/${id}`);
}

export async function fetchOperationChildren(id: string): Promise<Operation[]> {
  return apiGet(`/api/core/api/v1/admin/operations/${id}/children`);
}
