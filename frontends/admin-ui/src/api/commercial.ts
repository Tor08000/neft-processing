import { request } from "./http";
import type {
  CommercialAddonDisablePayload,
  CommercialAddonEnablePayload,
  CommercialEntitlementsSnapshotsResponse,
  CommercialOrgState,
  CommercialOverrideUpsertPayload,
  CommercialPlanChangePayload,
  CommercialRecomputePayload,
} from "../types/commercial";

export async function getCommercialState(token: string, orgId: number): Promise<CommercialOrgState> {
  return request<CommercialOrgState>(`/admin/commercial/orgs/${orgId}`, { method: "GET" }, token);
}

export async function getCommercialEntitlements(
  token: string,
  orgId: number,
): Promise<CommercialEntitlementsSnapshotsResponse> {
  return request<CommercialEntitlementsSnapshotsResponse>(
    `/admin/commercial/orgs/${orgId}/entitlements`,
    { method: "GET" },
    token,
  );
}

export async function changeCommercialPlan(
  token: string,
  orgId: number,
  payload: CommercialPlanChangePayload,
): Promise<CommercialOrgState> {
  return request<CommercialOrgState>(
    `/admin/commercial/orgs/${orgId}/plan`,
    { method: "POST", body: JSON.stringify(payload) },
    token,
  );
}

export async function enableCommercialAddon(
  token: string,
  orgId: number,
  payload: CommercialAddonEnablePayload,
): Promise<CommercialOrgState> {
  return request<CommercialOrgState>(
    `/admin/commercial/orgs/${orgId}/addons/enable`,
    { method: "POST", body: JSON.stringify(payload) },
    token,
  );
}

export async function disableCommercialAddon(
  token: string,
  orgId: number,
  payload: CommercialAddonDisablePayload,
): Promise<CommercialOrgState> {
  return request<CommercialOrgState>(
    `/admin/commercial/orgs/${orgId}/addons/disable`,
    { method: "POST", body: JSON.stringify(payload) },
    token,
  );
}

export async function upsertCommercialOverride(
  token: string,
  orgId: number,
  payload: CommercialOverrideUpsertPayload,
): Promise<CommercialOrgState> {
  return request<CommercialOrgState>(
    `/admin/commercial/orgs/${orgId}/overrides`,
    { method: "POST", body: JSON.stringify(payload) },
    token,
  );
}

export async function removeCommercialOverride(
  token: string,
  orgId: number,
  featureKey: string,
  reason: string,
): Promise<CommercialOrgState> {
  const query = new URLSearchParams({ reason });
  return request<CommercialOrgState>(
    `/admin/commercial/orgs/${orgId}/overrides/${encodeURIComponent(featureKey)}?${query.toString()}`,
    { method: "DELETE" },
    token,
  );
}

export async function recomputeCommercialEntitlements(
  token: string,
  orgId: number,
  payload: CommercialRecomputePayload,
): Promise<{ hash: string; computed_at: string; version: number }> {
  return request<{ hash: string; computed_at: string; version: number }>(
    `/admin/commercial/orgs/${orgId}/entitlements/recompute`,
    { method: "POST", body: JSON.stringify(payload) },
    token,
  );
}
