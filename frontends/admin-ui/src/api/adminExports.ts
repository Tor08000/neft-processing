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
};

export const createCaseExport = async (payload: CaseExportCreatePayload): Promise<CaseExportItem> => {
  return apiPost("/api/admin/exports", payload);
};

export const fetchCaseExport = async (exportId: string): Promise<CaseExportItem> => {
  return apiGet(`/api/admin/exports/${exportId}`);
};

export const downloadCaseExport = async (
  exportId: string,
): Promise<Required<Pick<CaseExportDownload, "url" | "expires_in">> & { content_sha256: string }> => {
  return apiPost(`/api/admin/exports/${exportId}/download`);
};

export const listCaseExports = async (caseId: string): Promise<{ items: CaseExportItem[] }> => {
  return apiGet(`/api/admin/cases/${caseId}/exports`);
};
