export type CaseKind = "operation" | "invoice" | "order" | "kpi";
export type CaseStatus = "TRIAGE" | "IN_PROGRESS" | "RESOLVED" | "CLOSED";
export type CasePriority = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

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
  priority: CasePriority;
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
