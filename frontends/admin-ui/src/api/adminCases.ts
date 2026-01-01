import { apiGet, apiPost } from "./client";

export type CaseStatus = "OPEN" | "IN_PROGRESS" | "CLOSED";
export type CasePriority = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export type CaseItem = {
  id: string;
  status: CaseStatus;
  priority?: CasePriority;
  title?: string;
  note?: string;
  created_at: string;
  created_by?: string;
  updated_at?: string;
  closed_at?: string | null;
  closed_by?: string | null;
  kind?: string | null;
  snapshots?: unknown;
};

export type CaseSnapshot = {
  id: string;
  explain_snapshot?: unknown;
  diff_snapshot?: unknown | null;
  selected_actions?: { code: string; what_if?: unknown | null }[] | null;
  note?: string | null;
  created_at: string;
};

export type CaseEvent = {
  id: string;
  type: string;
  actor?: string | null;
  note?: string | null;
  created_at: string;
  metadata?: Record<string, unknown> | null;
};

export type CaseListResponse = {
  items: CaseItem[];
  total?: number;
  limit?: number;
  next_cursor?: string | null;
};

export type CaseDetailsResponse = {
  case: CaseItem;
  latest_snapshot?: CaseSnapshot | null;
  snapshots?: CaseSnapshot[] | null;
};

export type CaseClosePayload = {
  resolution_note: string;
  resolution_code?: string | null;
};

export class NotAvailableError extends Error {
  constructor(message = "Not available in this environment") {
    super(message);
    this.name = "NotAvailableError";
  }
}

const isNotAvailableMessage = (message?: string) => Boolean(message && /HTTP (404|501)\b/.test(message));

const ensureAvailability = (error: unknown): never => {
  if (error instanceof NotAvailableError) {
    throw error;
  }
  if (error instanceof Error && isNotAvailableMessage(error.message)) {
    throw new NotAvailableError();
  }
  throw error;
};

export const isNotAvailableError = (error: unknown): boolean => {
  if (error instanceof NotAvailableError) return true;
  if (error instanceof Error) {
    return isNotAvailableMessage(error.message);
  }
  return false;
};

export const fetchAdminCases = async (params: {
  status?: CaseStatus | string;
  priority?: CasePriority | string;
  q?: string;
  limit?: number;
  cursor?: string | null;
}): Promise<CaseListResponse> => {
  try {
    return await apiGet("/api/admin/cases", params);
  } catch (error) {
    return ensureAvailability(error);
  }
};

export const fetchAdminCaseDetails = async (caseId: string): Promise<CaseDetailsResponse> => {
  try {
    return await apiGet(`/api/admin/cases/${caseId}`);
  } catch (error) {
    return ensureAvailability(error);
  }
};

export const closeAdminCase = async (caseId: string, payload: CaseClosePayload): Promise<CaseItem | void> => {
  try {
    return await apiPost(`/api/admin/cases/${caseId}/close`, payload);
  } catch (error) {
    return ensureAvailability(error);
  }
};

export const updateAdminCaseStatus = async (caseId: string, status: CaseStatus): Promise<CaseItem | void> => {
  try {
    return await apiPost(`/api/admin/cases/${caseId}/status`, { status });
  } catch (error) {
    return ensureAvailability(error);
  }
};

export const fetchAdminCaseEvents = async (caseId: string): Promise<{ items: CaseEvent[] }> => {
  try {
    return await apiGet(`/api/admin/cases/${caseId}/events`);
  } catch (error) {
    return ensureAvailability(error);
  }
};
