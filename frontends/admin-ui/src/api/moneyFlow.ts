import { request } from "./http";
import type { MoneyExplainResponse, MoneyHealthResponse, MoneyReplayResponse } from "../types/money";

const MONEY_BASE = "/v1/admin/money";

function buildQuery(params?: Record<string, string | number | undefined | null>): string {
  if (!params) return "";
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  });
  const qs = query.toString();
  return qs ? `?${qs}` : "";
}

export async function moneyHealth(token: string, params?: { stale_hours?: number }) {
  const query = buildQuery(params ? { stale_hours: params.stale_hours } : undefined);
  return request<MoneyHealthResponse>(`${MONEY_BASE}/health${query}`, { method: "GET" }, { token });
}

export async function moneyReplay(token: string, payload: {
  client_id: string;
  billing_period_id: string;
  scope: "SUBSCRIPTIONS" | "FUEL" | "ALL";
  mode: "DRY_RUN" | "COMPARE" | "REBUILD_LINKS";
}) {
  return request<MoneyReplayResponse>(`${MONEY_BASE}/replay`, { method: "POST", body: JSON.stringify(payload) }, { token });
}

export async function cfoExplainInvoice(token: string, invoiceId: string) {
  const query = buildQuery({ invoice_id: invoiceId });
  return request<MoneyExplainResponse>(`${MONEY_BASE}/cfo-explain${query}`, { method: "GET" }, { token });
}

export async function moneyExplain(token: string, params: { flow_type: string; flow_ref_id: string }) {
  const query = buildQuery({ flow_type: params.flow_type, flow_ref_id: params.flow_ref_id });
  return request<MoneyExplainResponse>(`${MONEY_BASE}/explain${query}`, { method: "GET" }, { token });
}
