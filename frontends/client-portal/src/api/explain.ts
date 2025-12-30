import { request } from "./http";
import type { AuthSession } from "./types";
import type { ExplainInsightsResponse, UnifiedExplainResponse } from "../types/explain";

const withToken = (user: AuthSession | null): string | undefined => user?.token;

interface ExplainParams {
  fuelTxId?: string;
  orderId?: string;
  invoiceId?: string;
  view?: "FLEET" | "ACCOUNTANT" | "FULL";
  depth?: number;
}

export function fetchUnifiedExplain(user: AuthSession | null, params: ExplainParams): Promise<UnifiedExplainResponse> {
  const search = new URLSearchParams();
  if (params.fuelTxId) search.set("fuel_tx_id", params.fuelTxId);
  if (params.orderId) search.set("order_id", params.orderId);
  if (params.invoiceId) search.set("invoice_id", params.invoiceId);
  if (params.view) search.set("view", params.view);
  if (params.depth) search.set("depth", params.depth.toString());
  return request<UnifiedExplainResponse>(`/explain?${search.toString()}`, { method: "GET" }, withToken(user));
}

export function fetchExplainInsights(
  user: AuthSession | null,
  params: { from: string; to: string },
): Promise<ExplainInsightsResponse> {
  const search = new URLSearchParams({ from: params.from, to: params.to });
  return request<ExplainInsightsResponse>(`/explain/insights?${search.toString()}`, { method: "GET" }, withToken(user));
}
