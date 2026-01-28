import { request } from "./http";

export type PolicyType = "fleet" | "finance" | "marketplace";
export type PolicyStatus = "enabled" | "disabled";

export interface PolicyScope {
  tenant_id: number | null;
  client_id: string | null;
}

export interface PolicyExplainRef {
  kind: string;
  id: string;
  type: PolicyType;
}

export interface PolicyIndexItem {
  id: string;
  type: PolicyType;
  title: string;
  status: PolicyStatus;
  scope: PolicyScope;
  actions: string[];
  explain_ref: PolicyExplainRef;
  updated_at?: string | null;
  toggle_supported: boolean;
}

export interface PolicyIndexResponse {
  items: PolicyIndexItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface PolicyHeader {
  id: string;
  type: PolicyType;
  title: string;
  status: PolicyStatus;
  scope: PolicyScope;
  actions: string[];
  updated_at?: string | null;
  toggle_supported: boolean;
}

export interface PolicyDetailResponse {
  header: PolicyHeader;
  policy: Record<string, unknown> | null;
  explain?: Record<string, unknown> | null;
}

export interface PolicyExecution {
  id: string;
  policy_id: string;
  event_type: string;
  event_id: string;
  action: string;
  status: string;
  reason?: string | null;
  created_at: string;
}

export interface PolicyExecutionResponse {
  items: PolicyExecution[];
}

export async function listPolicies(
  token: string,
  params: { type?: PolicyType; status?: PolicyStatus; q?: string; limit?: number; offset?: number },
): Promise<PolicyIndexResponse> {
  const query = new URLSearchParams();
  if (params.type) query.set("type", params.type);
  if (params.status) query.set("status", params.status);
  if (params.q) query.set("q", params.q);
  if (params.limit) query.set("limit", String(params.limit));
  if (params.offset) query.set("offset", String(params.offset));
  const suffix = query.toString();
  return request<PolicyIndexResponse>(`/policies${suffix ? `?${suffix}` : ""}`, { method: "GET" }, { token });
}

export async function fetchPolicyDetail(token: string, type: PolicyType, id: string): Promise<PolicyDetailResponse> {
  return request<PolicyDetailResponse>(`/policies/${type}/${id}`, { method: "GET" }, { token });
}

export async function fetchPolicyExecutions(
  token: string,
  type: PolicyType,
  id: string,
): Promise<PolicyExecutionResponse> {
  return request<PolicyExecutionResponse>(`/policies/${type}/${id}/executions`, { method: "GET" }, { token });
}

export async function enablePolicy(token: string, type: PolicyType, id: string): Promise<PolicyHeader> {
  return request<PolicyHeader>(`/policies/${type}/${id}/enable`, { method: "POST" }, { token });
}

export async function disablePolicy(token: string, type: PolicyType, id: string): Promise<PolicyHeader> {
  return request<PolicyHeader>(`/policies/${type}/${id}/disable`, { method: "POST" }, { token });
}
