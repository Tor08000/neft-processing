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
