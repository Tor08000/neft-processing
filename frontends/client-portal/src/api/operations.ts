import { request } from "./http";
import type { AuthSession } from "./types";
import type { OperationDetails, OperationsPage } from "../types/operations";

const withToken = (user: AuthSession | null): string | undefined => user?.token;

export function fetchOperations(user: AuthSession | null): Promise<OperationsPage> {
  return request<OperationsPage>("/operations", { method: "GET" }, withToken(user));
}

export function fetchOperationDetails(id: string, user: AuthSession | null): Promise<OperationDetails> {
  return request<OperationDetails>(`/operations/${id}`, { method: "GET" }, withToken(user));
}
