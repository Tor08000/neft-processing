import { request } from "./http";
import type { CrmClient, CrmContract, CrmListResponse, CrmProfile, CrmSubscription, CrmTariff } from "../types/crm";

const CRM_BASE = "/crm";

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

export async function listClients(token: string, params?: Record<string, string | number | undefined | null>) {
  return request<CrmListResponse<CrmClient>>(`${CRM_BASE}/clients${buildQuery(params)}`, { method: "GET" }, { token });
}

export async function createClient(token: string, payload: Partial<CrmClient>) {
  return request<CrmClient>(`${CRM_BASE}/clients`, { method: "POST", body: JSON.stringify(payload) }, { token });
}

export async function getClient(token: string, clientId: string) {
  return request<CrmClient>(`${CRM_BASE}/clients/${clientId}`, { method: "GET" }, { token });
}

export async function updateClient(token: string, clientId: string, payload: Partial<CrmClient>) {
  return request<CrmClient>(`${CRM_BASE}/clients/${clientId}`, { method: "PATCH", body: JSON.stringify(payload) }, { token });
}

export async function listContracts(token: string, params?: Record<string, string | number | undefined | null>) {
  return request<CrmListResponse<CrmContract>>(`${CRM_BASE}/contracts${buildQuery(params)}`, { method: "GET" }, { token });
}

export async function getContract(token: string, contractId: string) {
  return request<CrmContract>(`${CRM_BASE}/contracts/${contractId}`, { method: "GET" }, { token });
}

export async function createContract(token: string, clientId: string, payload: Partial<CrmContract>) {
  return request<CrmContract>(
    `${CRM_BASE}/clients/${clientId}/contracts`,
    { method: "POST", body: JSON.stringify(payload) },
    { token },
  );
}

export async function updateContract(token: string, contractId: string, payload: Partial<CrmContract>) {
  return request<CrmContract>(`${CRM_BASE}/contracts/${contractId}`, { method: "PATCH", body: JSON.stringify(payload) }, { token });
}

export async function activateContract(token: string, contractId: string) {
  return request<CrmContract>(`${CRM_BASE}/contracts/${contractId}/activate`, { method: "POST" }, { token });
}

export async function pauseContract(token: string, contractId: string) {
  return request<CrmContract>(`${CRM_BASE}/contracts/${contractId}/pause`, { method: "POST" }, { token });
}

export async function terminateContract(token: string, contractId: string) {
  return request<CrmContract>(`${CRM_BASE}/contracts/${contractId}/terminate`, { method: "POST" }, { token });
}

export async function applyContract(token: string, contractId: string) {
  return request<Record<string, unknown>>(`${CRM_BASE}/contracts/${contractId}/apply`, { method: "POST" }, { token });
}

export async function listTariffs(token: string, params?: Record<string, string | number | undefined | null>) {
  return request<CrmListResponse<CrmTariff>>(`${CRM_BASE}/tariffs${buildQuery(params)}`, { method: "GET" }, { token });
}

export async function createTariff(token: string, payload: Partial<CrmTariff>) {
  return request<CrmTariff>(`${CRM_BASE}/tariffs`, { method: "POST", body: JSON.stringify(payload) }, { token });
}

export async function updateTariff(token: string, tariffId: string, payload: Partial<CrmTariff>) {
  return request<CrmTariff>(`${CRM_BASE}/tariffs/${tariffId}`, { method: "PATCH", body: JSON.stringify(payload) }, { token });
}

export async function listSubscriptions(token: string, params?: Record<string, string | number | undefined | null>) {
  return request<CrmListResponse<CrmSubscription>>(`${CRM_BASE}/subscriptions${buildQuery(params)}`, { method: "GET" }, { token });
}

export async function getSubscription(token: string, subscriptionId: string) {
  return request<CrmSubscription>(`${CRM_BASE}/subscriptions/${subscriptionId}`, { method: "GET" }, { token });
}

export async function createSubscription(token: string, clientId: string, payload: Partial<CrmSubscription>) {
  return request<CrmSubscription>(
    `${CRM_BASE}/clients/${clientId}/subscriptions`,
    { method: "POST", body: JSON.stringify(payload) },
    { token },
  );
}

export async function updateSubscription(token: string, subscriptionId: string, payload: Partial<CrmSubscription>) {
  return request<CrmSubscription>(
    `${CRM_BASE}/subscriptions/${subscriptionId}`,
    { method: "PATCH", body: JSON.stringify(payload) },
    { token },
  );
}

export async function pauseSubscription(token: string, subscriptionId: string) {
  return request<CrmSubscription>(`${CRM_BASE}/subscriptions/${subscriptionId}/pause`, { method: "POST" }, { token });
}

export async function resumeSubscription(token: string, subscriptionId: string) {
  return request<CrmSubscription>(`${CRM_BASE}/subscriptions/${subscriptionId}/resume`, { method: "POST" }, { token });
}

export async function cancelSubscription(token: string, subscriptionId: string) {
  return request<CrmSubscription>(`${CRM_BASE}/subscriptions/${subscriptionId}/cancel`, { method: "POST" }, { token });
}

export async function previewSubscriptionBilling(
  token: string,
  subscriptionId: string,
  params?: { period_id?: string; period_from?: string; period_to?: string },
) {
  const query = buildQuery({ period_id: params?.period_id, period_from: params?.period_from, period_to: params?.period_to });
  return request<Record<string, unknown>>(
    `${CRM_BASE}/subscriptions/${subscriptionId}/preview-billing${query}`,
    { method: "POST" },
    { token },
  );
}

export async function subscriptionCfoExplain(token: string, subscriptionId: string, params?: { period_id?: string }) {
  const query = buildQuery({ period_id: params?.period_id });
  return request<Record<string, unknown>>(
    `${CRM_BASE}/subscriptions/${subscriptionId}/cfo-explain${query}`,
    { method: "POST" },
    { token },
  );
}

export async function getClientFeatures(token: string, clientId: string) {
  return request<Record<string, boolean>>(`${CRM_BASE}/clients/${clientId}/features`, { method: "GET" }, { token });
}

export async function enableFeature(token: string, clientId: string, feature: string) {
  return request<Record<string, boolean>>(
    `${CRM_BASE}/clients/${clientId}/features/${feature}/enable`,
    { method: "POST" },
    { token },
  );
}

export async function disableFeature(token: string, clientId: string, feature: string) {
  return request<Record<string, boolean>>(
    `${CRM_BASE}/clients/${clientId}/features/${feature}/disable`,
    { method: "POST" },
    { token },
  );
}

export async function listLimitProfiles(token: string) {
  return request<CrmListResponse<CrmProfile>>(`${CRM_BASE}/limit-profiles`, { method: "GET" }, { token });
}

export async function listRiskProfiles(token: string) {
  return request<CrmListResponse<CrmProfile>>(`${CRM_BASE}/risk-profiles`, { method: "GET" }, { token });
}
