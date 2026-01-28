import { request } from "./http";
import type { LegalPartnerDetail, LegalPartnerListResponse } from "../types/legalPartners";

function normalizeLegalPartnerList(raw: unknown): LegalPartnerListResponse {
  const r: any = raw ?? {};
  const container =
    r && typeof r === "object" && "data" in r && r.data ? r.data : r;
  const items: LegalPartnerDetail[] = Array.isArray(container?.items)
    ? container.items
    : [];
  const total: number =
    typeof container?.total === "number" ? container.total : items.length;
  const cursor: string | null =
    typeof container?.cursor === "string" || container?.cursor === null
      ? container.cursor
      : null;
  return { items, total, cursor };
}

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
  const raw = await request<unknown>(
    `/legal/partners${suffix}`,
    { method: "GET" },
    token,
  );
  return normalizeLegalPartnerList(raw);
}

export async function fetchLegalPartner(token: string, partnerId: string): Promise<LegalPartnerDetail> {
  return request<LegalPartnerDetail>(`/legal/partners/${partnerId}`, { method: "GET" }, token);
}

export async function updateLegalPartnerStatus(
  token: string,
  partnerId: string,
  payload: { status: string; reason: string; correlation_id: string },
) {
  return request<LegalPartnerDetail>(
    `/legal/partners/${partnerId}/status`,
    { method: "POST", body: JSON.stringify(payload) },
    token,
  );
}
