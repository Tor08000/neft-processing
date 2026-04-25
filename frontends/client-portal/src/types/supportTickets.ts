export type SupportTicketStatus = "OPEN" | "IN_PROGRESS" | "CLOSED";

export type SupportTicketPriority = "LOW" | "NORMAL" | "HIGH";

export type SupportTicketSlaStatus = "OK" | "BREACHED" | "PENDING";

export interface SupportTicketItem {
  id: string;
  org_id: string;
  created_by_user_id: string;
  subject: string;
  message: string;
  status: SupportTicketStatus;
  priority: SupportTicketPriority;
  first_response_due_at: string | null;
  first_response_at: string | null;
  resolution_due_at: string | null;
  resolved_at: string | null;
  sla_first_response_status: SupportTicketSlaStatus;
  sla_resolution_status: SupportTicketSlaStatus;
  sla_first_response_remaining_minutes: number | null;
  sla_resolution_remaining_minutes: number | null;
  case_id?: string | null;
  case_status?: "TRIAGE" | "IN_PROGRESS" | "WAITING" | "RESOLVED" | "CLOSED" | null;
  case_queue?: "FRAUD_OPS" | "FINANCE_OPS" | "SUPPORT" | "GENERAL" | null;
  case_priority?: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" | null;
  case_updated_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface SupportTicketComment {
  user_id: string;
  message: string;
  created_at: string;
}

export interface SupportTicketDetail extends SupportTicketItem {
  comments: SupportTicketComment[];
}

export interface SupportTicketListResponse {
  items: SupportTicketItem[];
  next_cursor?: string | null;
}

export interface SupportTicketCreatePayload {
  subject: string;
  message: string;
  priority: SupportTicketPriority;
}

export interface SupportTicketCommentPayload {
  message: string;
}
