import { apiGet, apiPost } from "./client";

export type CaseExportKind = "EXPLAIN" | "DIFF" | "CASE";

export type CaseExportDownload = {
  url: string;
  expires_in: number;
  content_sha256?: string;
};

export type CaseExportItem = {
  id: string;
  kind: CaseExportKind;
  case_id?: string | null;
  content_type: string;
  content_sha256: string;
  artifact_signature?: string | null;
  artifact_signature_alg?: string | null;
  artifact_signing_key_id?: string | null;
  artifact_signed_at?: string | null;
  size_bytes: number;
  created_at: string;
  deleted_at?: string | null;
  delete_reason?: string | null;
  download?: CaseExportDownload | null;
};

export type CaseExportCreatePayload = {
  kind: CaseExportKind;
  case_id?: string | null;
  payload: Record<string, unknown>;
  mastery_snapshot?: Record<string, unknown> | null;
};

export const createCaseExport = async (payload: CaseExportCreatePayload): Promise<CaseExportItem> => {
  return apiPost("/v1/admin/exports", payload);
};

export const fetchCaseExport = async (exportId: string): Promise<CaseExportItem> => {
  return apiGet(`/v1/admin/exports/${exportId}`);
};

export const downloadCaseExport = async (
  exportId: string,
): Promise<Required<Pick<CaseExportDownload, "url" | "expires_in">> & { content_sha256: string }> => {
  return apiPost(`/v1/admin/exports/${exportId}/download`);
};

export const listCaseExports = async (caseId: string): Promise<{ items: CaseExportItem[] }> => {
  return apiGet(`/v1/admin/cases/${caseId}/exports`);
};

export type CaseExportVerifyResult = {
  content_hash_verified: boolean;
  artifact_signature_verified: boolean;
  signed_by?: string | null;
  signed_at?: string | null;
  audit_chain_verified: boolean;
};

export const verifyCaseExport = async (exportId: string): Promise<CaseExportVerifyResult> => {
  return apiPost(`/v1/admin/exports/${exportId}/verify`);
};
