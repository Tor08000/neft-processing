export type CaseKind = "operation" | "invoice" | "order" | "support" | "dispute" | "incident" | "kpi" | "fleet" | "booking";
export type CaseStatus = "TRIAGE" | "IN_PROGRESS" | "WAITING" | "RESOLVED" | "CLOSED";
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
  entity_type?: string | null;
  entity_id?: string | null;
  kpi_key?: string | null;
  window_days?: number | null;
  title: string;
  description?: string | null;
  status: CaseStatus;
  queue: CaseQueue;
  priority: CasePriority;
  escalation_level: number;
  first_response_due_at?: string | null;
  resolve_due_at?: string | null;
  sla_state?: CaseSlaState | null;
  client_id?: string | null;
  partner_id?: string | null;
  created_by?: string | null;
  assigned_to?: string | null;
  case_source_ref_type?: string | null;
  case_source_ref_id?: string | null;
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
  timeline: Array<{ status: CaseStatus; occurred_at: string }>;
  snapshots?: CaseSnapshot[] | null;
}
