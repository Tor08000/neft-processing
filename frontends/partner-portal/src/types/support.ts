export type SupportRequestStatus = "OPEN" | "IN_PROGRESS" | "WAITING" | "RESOLVED" | "CLOSED";

export type SupportRequestSubjectType =
  | "ORDER"
  | "DOCUMENT"
  | "PAYOUT"
  | "SETTLEMENT"
  | "INTEGRATION"
  | "OTHER";

export type SupportRequestScopeType = "CLIENT" | "PARTNER";

export type SupportRequestPriority = "LOW" | "NORMAL" | "HIGH";
export type SupportRequestCaseKind =
  | "order"
  | "support"
  | "dispute"
  | "incident"
  | "operation"
  | "invoice"
  | "kpi"
  | "fleet"
  | "booking";

export interface SupportRequestItem {
  id: string;
  tenant_id: number;
  client_id?: string | null;
  partner_id?: string | null;
  created_by_user_id?: string | null;
  scope_type: SupportRequestScopeType;
  subject_type: SupportRequestSubjectType;
  subject_id?: string | null;
  correlation_id?: string | null;
  event_id?: string | null;
  title: string;
  description: string;
  status: SupportRequestStatus;
  priority: SupportRequestPriority;
  created_at: string;
  updated_at: string;
  resolved_at?: string | null;
  case_kind?: SupportRequestCaseKind;
  case_queue?: string | null;
  case_source_ref_type?: string | null;
  case_source_ref_id?: string | null;
  case_first_response_due_at?: string | null;
  case_resolve_due_at?: string | null;
}

export interface SupportRequestTimelineEvent {
  status: SupportRequestStatus;
  occurred_at: string;
}

export interface SupportRequestDetail extends SupportRequestItem {
  timeline: SupportRequestTimelineEvent[];
}

export interface SupportRequestListResponse {
  items: SupportRequestItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface SupportRequestCreatePayload {
  scope_type: SupportRequestScopeType;
  subject_type: SupportRequestSubjectType;
  subject_id?: string | null;
  title: string;
  description: string;
  correlation_id?: string | null;
  event_id?: string | null;
}
