import { request } from "./http";

export type LegalRequiredItem = {
  code: string;
  title: string;
  locale: string;
  required_version: string;
  published_at: string | null;
  effective_from: string;
  content_hash: string;
  accepted: boolean;
  accepted_at: string | null;
};

export type LegalRequiredResponse = {
  subject: { type: string; id: string };
  required: LegalRequiredItem[];
  is_blocked: boolean;
};

export type LegalDocumentResponse = {
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

export async function fetchLegalRequired(token: string): Promise<LegalRequiredResponse> {
  return request<LegalRequiredResponse>("/legal/required", {}, { token, base: "core_root" });
}

export async function fetchLegalDocument(
  token: string,
  code: string,
  params?: { version?: string; locale?: string },
): Promise<LegalDocumentResponse> {
  const search = new URLSearchParams();
  if (params?.version) search.set("version", params.version);
  if (params?.locale) search.set("locale", params.locale);
  const suffix = search.toString() ? `?${search.toString()}` : "";
  return request<LegalDocumentResponse>(`/legal/documents/${code}${suffix}`, {}, { token, base: "core_root" });
}

export async function acceptLegalDocument(
  token: string,
  payload: { code: string; version: string; locale: string },
): Promise<LegalRequiredResponse> {
  return request<LegalRequiredResponse>(
    "/legal/accept",
    {
      method: "POST",
      body: JSON.stringify({ ...payload, accepted: true }),
    },
    { token, base: "core_root" },
  );
}
