import { apiGet, apiPatch, apiPost } from "./client";

export type CaseKind = "operation" | "invoice" | "order" | "kpi";
export type CaseStatus = "TRIAGE" | "IN_PROGRESS" | "RESOLVED" | "CLOSED";
export type CasePriority = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type CaseQueue = "FRAUD_OPS" | "FINANCE_OPS" | "SUPPORT" | "GENERAL";
export type CaseSlaState = "ON_TRACK" | "WARNING" | "BREACHED";

export interface CaseSnapshot {
  id: string;
  explain_snapshot: Record<string, unknown>;
  diff_snapshot?: Record<string, unknown> | null;
  selected_actions?: { code: string; what_if?: Record<string, unknown> | null }[] | null;
  note?: string | null;
  created_at: string;
}

export interface CaseComment {
  id: string;
  author?: string | null;
  type: "user" | "system";
  body: string;
  created_at: string;
}

export interface CaseItem {
  id: string;
  tenant_id: number;
  kind: CaseKind;
  entity_id?: string | null;
  kpi_key?: string | null;
  window_days?: number | null;
  title: string;
  status: CaseStatus;
  queue: CaseQueue;
  priority: CasePriority;
  escalation_level: number;
  first_response_due_at?: string | null;
  resolve_due_at?: string | null;
  sla_state?: CaseSlaState | null;
  created_by?: string | null;
  assigned_to?: string | null;
  created_at: string;
  updated_at: string;
  last_activity_at: string;
}

export interface CaseListResponse {
  items: CaseItem[];
  total: number;
  limit: number;
  next_cursor?: string | null;
}

export interface CaseDetailsResponse {
  case: CaseItem;
  latest_snapshot?: CaseSnapshot | null;
  comments: CaseComment[];
  snapshots?: CaseSnapshot[] | null;
}

export interface CaseCreatePayload {
  kind: CaseKind;
  entity_id?: string | null;
  kpi_key?: string | null;
  window_days?: number | null;
  title?: string | null;
  priority: CasePriority;
  note?: string | null;
  explain?: Record<string, unknown> | null;
  diff?: Record<string, unknown> | null;
  selected_actions?: { code: string; what_if?: Record<string, unknown> | null }[] | null;
}

export interface CaseUpdatePayload {
  status?: CaseStatus;
  assigned_to?: string | null;
  priority?: CasePriority;
}

export interface CaseCommentPayload {
  body: string;
}

export function fetchCases(params: {
  status?: CaseStatus;
  kind?: CaseKind;
  priority?: CasePriority | string;
  queue?: CaseQueue;
  sla_state?: CaseSlaState;
  escalation_level_min?: number;
  assigned_to?: string;
  q?: string;
  limit?: number;
  cursor?: string;
}): Promise<CaseListResponse> {
  return apiGet("/cases", params);
}

export function fetchCaseDetails(caseId: string, includeSnapshots = false): Promise<CaseDetailsResponse> {
  return apiGet(`/cases/${caseId}`, { include_snapshots: includeSnapshots });
}

export function createCase(payload: CaseCreatePayload): Promise<CaseItem> {
  return apiPost("/cases", payload);
}

export function updateCase(caseId: string, payload: CaseUpdatePayload): Promise<CaseItem> {
  return apiPatch(`/cases/${caseId}`, payload);
}

export function addCaseComment(caseId: string, payload: CaseCommentPayload): Promise<CaseComment> {
  return apiPost(`/cases/${caseId}/comments`, payload);
}
