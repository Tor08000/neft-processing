import { CORE_API_BASE, joinUrl } from "./base";
import { ApiError, UnauthorizedError, ValidationError, request as coreRequest } from "./http";
import type { AuthSession } from "./types";
import type { AccountingExportDetails, AccountingExportList } from "../types/exports";

export type ExportJobStatus = "QUEUED" | "RUNNING" | "DONE" | "FAILED" | "CANCELED" | "EXPIRED";
export type ExportJobReportType = "cards" | "users" | "transactions" | "documents" | "audit" | "support";
export type ExportJobFormat = "CSV";

export type ExportJobFilters = Record<string, string | number | boolean | string[] | null | undefined>;

export type ExportJob = {
  id: string;
  org_id: string;
  created_by_user_id: string;
  report_type: ExportJobReportType;
  format: ExportJobFormat;
  status: ExportJobStatus;
  filters: Record<string, unknown>;
  file_name?: string | null;
  content_type?: string | null;
  row_count?: number | null;
  error_message?: string | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  expires_at?: string | null;
};

export type ExportJobListResponse = {
  items: ExportJob[];
  next_cursor?: string | null;
};

const withToken = (user: AuthSession | null): string | undefined => user?.token;

const requestJson = async <T>(
  url: string,
  options: RequestInit,
  user: AuthSession | null,
): Promise<T> => {
  const token = withToken(user);
  const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
  const response = await fetch(url, { ...options, headers: { ...headers, ...(options.headers ?? {}) } });
  const correlationId = response.headers.get("x-correlation-id") ?? response.headers.get("x-request-id");

  if (response.status === 401) {
    window.dispatchEvent(new Event("client-auth-logout"));
    throw new UnauthorizedError();
  }
  if (response.status === 422) {
    const details = await response.text().catch(() => "");
    throw new ValidationError("Ошибка валидации", details);
  }
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new ApiError(text || `Request failed with status ${response.status}`, response.status, correlationId);
  }
  return (await response.json()) as T;
};

export async function createExportJob(
  reportType: ExportJobReportType,
  filters: ExportJobFilters,
  user: AuthSession | null,
): Promise<{ id: string; status: ExportJobStatus }> {
  const url = joinUrl(CORE_API_BASE, "/client/exports/jobs");
  return requestJson(
    url,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ report_type: reportType, format: "CSV", filters }),
    },
    user,
  );
}

export async function listExportJobs(
  params: {
    status?: ExportJobStatus;
    report_type?: ExportJobReportType;
    limit?: number;
    cursor?: string | null;
    only_my?: boolean;
  },
  user: AuthSession | null,
): Promise<ExportJobListResponse> {
  const url = new URL(joinUrl(CORE_API_BASE, "/client/exports/jobs"));
  if (params.status) url.searchParams.set("status", params.status);
  if (params.report_type) url.searchParams.set("report_type", params.report_type);
  if (params.limit) url.searchParams.set("limit", String(params.limit));
  if (params.cursor) url.searchParams.set("cursor", params.cursor);
  if (params.only_my) url.searchParams.set("only_my", "true");
  return requestJson(url.toString(), { method: "GET" }, user);
}

export function buildExportJobDownloadUrl(jobId: string): string {
  return joinUrl(CORE_API_BASE, `/client/exports/jobs/${jobId}/download`);
}

export function fetchExports(user: AuthSession | null): Promise<AccountingExportList> {
  return coreRequest<AccountingExportList>("/exports", { method: "GET" }, withToken(user));
}

export function fetchExportDetails(id: string, user: AuthSession | null): Promise<AccountingExportDetails> {
  return coreRequest<AccountingExportDetails>(`/exports/${id}`, { method: "GET" }, withToken(user));
}
