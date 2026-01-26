import { request } from "./http";

export type PartnerLegalProfileAdmin = {
  partner_id: string;
  legal_type?: string | null;
  country?: string | null;
  tax_residency?: string | null;
  tax_regime?: string | null;
  vat_applicable?: boolean | null;
  vat_rate?: number | null;
  legal_status?: string | null;
  details?: Record<string, unknown> | null;
  tax_context?: Record<string, unknown> | null;
};

export type PartnerLegalPack = {
  id: string;
  partner_id: string;
  format: string;
  object_key: string;
  pack_hash: string;
  metadata?: Record<string, unknown> | null;
  created_at: string;
  download_url?: string | null;
};

export async function fetchPartnerLegalProfile(token: string, partnerId: string) {
  return request<PartnerLegalProfileAdmin>(`/admin/partners/${partnerId}/legal-profile`, { method: "GET" }, token);
}

export async function updatePartnerLegalStatus(
  token: string,
  partnerId: string,
  payload: { status: string; reason: string; correlation_id: string; comment?: string | null },
) {
  return request<PartnerLegalProfileAdmin>(
    `/admin/partners/${partnerId}/legal-profile/status`,
    { method: "POST", body: JSON.stringify(payload) },
    token,
  );
}

export async function generatePartnerLegalPack(token: string, partnerId: string, format = "ZIP") {
  return request<PartnerLegalPack>(
    `/admin/partners/${partnerId}/legal-pack`,
    { method: "POST", body: JSON.stringify({ format }) },
    token,
  );
}

export async function fetchPartnerLegalPackHistory(token: string, partnerId: string) {
  const response = await request<{ items: PartnerLegalPack[] }>(
    `/admin/partners/${partnerId}/legal-pack/history`,
    { method: "GET" },
    token,
  );
  return response.items ?? [];
}
