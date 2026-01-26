import { request } from "./http";
import type { AuditCorrelationResponse, AuditEvent, AuditFeedResponse } from "../types/audit";

const buildQuery = (params: Record<string, string | number | boolean | undefined>) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    query.append(key, String(value));
  });
  const suffix = query.toString();
  return suffix ? `?${suffix}` : "";
};

export async function fetchAuditFeed(
  token: string,
  params: { type?: string; correlation_id?: string; search?: string; limit?: number; offset?: number } = {},
): Promise<AuditFeedResponse> {
  const suffix = buildQuery(params);
  const response = await request<AuditFeedResponse | AuditEvent[]>(
    `/admin/audit${suffix}`,
    { method: "GET" },
    token,
  );
  if (Array.isArray(response)) {
    return { items: response };
  }
  return response;
}

export async function fetchAuditCorrelation(token: string, correlationId: string): Promise<AuditCorrelationResponse> {
  return request<AuditCorrelationResponse>(`/admin/audit/${correlationId}`, { method: "GET" }, token);
}
