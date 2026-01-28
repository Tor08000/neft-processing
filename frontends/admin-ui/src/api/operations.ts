import { apiGet } from "./client";
import { Operation, OperationListResponse, OperationQuery } from "../types/operations";

export async function fetchOperations(params: OperationQuery): Promise<OperationListResponse> {
  return apiGet("/operations", params);
}

export async function fetchOperation(id: string): Promise<Operation> {
  return apiGet(`/operations/${id}`);
}

export async function fetchOperationChildren(id: string): Promise<Operation[]> {
  return apiGet(`/operations/${id}/children`);
}
