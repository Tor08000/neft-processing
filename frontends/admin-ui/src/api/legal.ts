import { request } from "./http";

export type LegalDocument = {
  id: string;
  code: string;
  version: string;
  title: string;
  locale: string;
  effective_from: string;
  status: string;
  content_type: string;
  content: string;
  content_hash: string;
  published_at: string | null;
  created_at: string;
  updated_at: string;
};

export type LegalAcceptance = {
  id: string;
  subject_type: string;
  subject_id: string;
  document_code: string;
  document_version: string;
  document_locale: string;
  accepted_at: string;
  ip: string | null;
  user_agent: string | null;
  acceptance_hash: string;
  signature: Record<string, unknown> | null;
  meta: Record<string, unknown> | null;
};

export async function listLegalDocuments(token: string, params?: Record<string, string>): Promise<LegalDocument[]> {
  const search = new URLSearchParams(params ?? {}).toString();
  const suffix = search ? `?${search}` : "";
  const response = await request<{ items: LegalDocument[] }>(`/admin/legal/documents${suffix}`, { method: "GET" }, token);
  return response.items ?? [];
}

export async function createLegalDocument(token: string, payload: Omit<LegalDocument, "id" | "status" | "content_hash" | "published_at" | "created_at" | "updated_at">) {
  return request<LegalDocument>(
    "/admin/legal/documents",
    { method: "POST", body: JSON.stringify(payload) },
    token,
  );
}

export async function updateLegalDocument(token: string, id: string, payload: Partial<LegalDocument>) {
  return request<LegalDocument>(`/admin/legal/documents/${id}`, { method: "PUT", body: JSON.stringify(payload) }, token);
}

export async function publishLegalDocument(token: string, id: string) {
  return request<LegalDocument>(`/admin/legal/documents/${id}/publish`, { method: "POST" }, token);
}

export async function listLegalAcceptances(token: string, params?: Record<string, string>): Promise<LegalAcceptance[]> {
  const search = new URLSearchParams(params ?? {}).toString();
  const suffix = search ? `?${search}` : "";
  const response = await request<{ items: LegalAcceptance[] }>(
    `/admin/legal/acceptances${suffix}`,
    { method: "GET" },
    token,
  );
  return response.items ?? [];
}

export async function fetchLegalRequired(token: string) {
  return request<{ required: unknown[]; is_blocked: boolean; enabled?: boolean }>("/legal/required", { method: "GET" }, token);
}

export async function acceptLegalDocument(token: string, payload: { code: string; version: string; locale: string }) {
  return request("/legal/accept", { method: "POST", body: JSON.stringify({ ...payload, accepted: true }) }, token);
}
