export interface ClientInvoiceSummary {
  id: string;
  number: string;
  issued_at?: string | null;
  status: string;
  amount_total: number | string;
  amount_paid: number | string;
  amount_refunded: number | string;
  amount_due: number | string;
  currency: string;
}

export interface ClientInvoicePayment {
  id: string;
  amount: number | string;
  status: string;
  provider?: string | null;
  external_ref?: string | null;
  created_at: string;
}

export interface ClientInvoiceRefund {
  id: string;
  amount: number | string;
  status: string;
  provider?: string | null;
  external_ref?: string | null;
  created_at: string;
  reason?: string | null;
}

export interface ClientInvoiceDetails extends ClientInvoiceSummary {
  pdf_available: boolean;
  acknowledged: boolean;
  ack_at?: string | null;
  payments: ClientInvoicePayment[];
  refunds: ClientInvoiceRefund[];
}

export interface ClientInvoiceList {
  items: ClientInvoiceSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface ClientExportItem {
  type: string;
  title: string;
  created_at?: string | null;
  download_url: string;
}

export interface ClientExportList {
  items: ClientExportItem[];
}

export interface ClientAuditEvent {
  id: string;
  ts: string;
  event_type: string;
  entity_type: string;
  entity_id: string;
  action?: string | null;
  visibility?: "PUBLIC" | "INTERNAL" | null;
  actor_type?: string | null;
  actor_id?: string | null;
  external_refs?: { provider?: string | null; external_ref?: string | null } | null;
  before?: Record<string, unknown> | null;
  after?: Record<string, unknown> | null;
  hash?: string | null;
  prev_hash?: string | null;
}

export interface ClientAuditList {
  items: ClientAuditEvent[];
  total: number;
  limit: number;
  offset: number;
}

export interface InvoiceMessage {
  id: string;
  sender_type: "CLIENT" | "SUPPORT";
  sender_user_id?: string | null;
  sender_email?: string | null;
  message: string;
  created_at: string;
}

export interface InvoiceThreadMessages {
  thread_id?: string | null;
  status?: string | null;
  created_at?: string | null;
  closed_at?: string | null;
  last_message_at?: string | null;
  items: InvoiceMessage[];
  total: number;
  limit: number;
  offset: number;
}

export interface DocumentAcknowledgement {
  acknowledged: boolean;
  ack_at: string;
  document_type: string;
}
