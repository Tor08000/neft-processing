import { request } from "./http";
import type { LegalPartnerDetail, LegalPartnerListResponse } from "../types/legalPartners";

const buildQuery = (params: Record<string, string | number | boolean | undefined>) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    query.append(key, String(value));
  });
  const suffix = query.toString();
  return suffix ? `?${suffix}` : "";
};

export async function fetchLegalPartners(
  token: string,
  params: { status?: string; search?: string; limit?: number; offset?: number } = {},
) {
  const suffix = buildQuery(params);
  const response = await request<
    | LegalPartnerListResponse
    | LegalPartnerDetail[]
    | { items?: LegalPartnerDetail[]; total?: number; cursor?: string | null; data?: { items?: LegalPartnerDetail[]; total?: number; cursor?: string | null } }
  >(
    `/admin/legal/partners${suffix}`,
    { method: "GET" },
    token,
  );
  const items = Array.isArray(response)
    ? response
    : response.items ?? response.data?.items ?? [];
  const total = Array.isArray(response)
    ? response.length
    : response.total ?? response.data?.total ?? items.length ?? 0;
  const cursor = Array.isArray(response)
    ? null
    : response.cursor ?? response.data?.cursor ?? null;
  return { items, total, cursor };
}

export async function fetchLegalPartner(token: string, partnerId: string): Promise<LegalPartnerDetail> {
  return request<LegalPartnerDetail>(`/admin/legal/partners/${partnerId}`, { method: "GET" }, token);
}

export async function updateLegalPartnerStatus(
  token: string,
  partnerId: string,
  payload: { status: string; reason: string; correlation_id: string },
) {
  return request<LegalPartnerDetail>(
    `/admin/legal/partners/${partnerId}/status`,
    { method: "POST", body: JSON.stringify(payload) },
    token,
  );
}
