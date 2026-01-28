import { apiGet } from "./client";

export type IntegrationRequestQuery = {
  partner_id?: string;
  azs_id?: string;
  status?: string;
  reason_category?: string;
  from?: string;
  to?: string;
  limit?: number;
  offset?: number;
};

export async function fetchIntegrationRequests(params: IntegrationRequestQuery): Promise<any> {
  return apiGet<any>("/integration/requests", params);
}

export async function fetchPartnerStatuses(window_minutes = 15): Promise<any> {
  return apiGet<any>("/integration/partners/status", { window_minutes });
}

export async function fetchAzsHeatmap(window_minutes = 15, partner_id?: string): Promise<any> {
  return apiGet<any>("/integration/azs/heatmap", { window_minutes, partner_id });
}

export async function fetchRecentDeclines(params: { since?: string; partner_id?: string; reason_category?: string }): Promise<any> {
  return apiGet<any>("/integration/declines/recent", params);
}
