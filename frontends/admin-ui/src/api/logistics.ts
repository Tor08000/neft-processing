import { request } from "./http";
import type { LogisticsEtaSnapshot, LogisticsInspection } from "../types/logistics";

export async function fetchLogisticsInspection(token: string, orderId: string): Promise<LogisticsInspection> {
  return request<LogisticsInspection>(`/logistics/orders/${orderId}/inspection`, { method: "GET" }, token);
}

export async function recomputeLogisticsEta(token: string, orderId: string): Promise<LogisticsEtaSnapshot> {
  return request<LogisticsEtaSnapshot>(`/logistics/orders/${orderId}/eta/recompute`, { method: "POST" }, token);
}
