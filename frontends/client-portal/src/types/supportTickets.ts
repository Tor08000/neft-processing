export type SupportTicketStatus = "OPEN" | "IN_PROGRESS" | "CLOSED";

export type SupportTicketPriority = "LOW" | "NORMAL" | "HIGH";

export interface SupportTicketItem {
  id: string;
  org_id: string;
  created_by_user_id: string;
  subject: string;
  message: string;
  status: SupportTicketStatus;
  priority: SupportTicketPriority;
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
