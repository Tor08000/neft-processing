export interface PartnerBalance {
  partner_org_id: string;
  currency: string;
  balance_available: number;
  balance_pending: number;
  balance_blocked: number;
}

export interface PartnerLedgerEntry {
  id: string;
  partner_org_id: string;
  order_id?: string | null;
  entry_type: string;
  amount: number;
  currency: string;
  direction: string;
  meta_json?: Record<string, unknown> | null;
  created_at: string;
}

export interface PartnerLedgerListResponse {
  items: PartnerLedgerEntry[];
  totals?: {
    in?: number;
    out?: number;
    net?: number;
  } | null;
  next_cursor?: string | null;
  total?: number | null;
}

export interface PartnerLedgerExplain {
  entry_id: string;
  operation: string;
  amount: number;
  currency: string;
  direction: string;
  source_type?: string | null;
  source_id?: string | null;
  source_label?: string | null;
  formula?: string | null;
  settlement_snapshot_hash?: string | null;
  settlement_breakdown_url?: string | null;
  admin_actor_id?: string | null;
}

export interface PartnerPayoutRequest {
  id: string;
  partner_org_id: string;
  amount: number;
  currency: string;
  status: string;
  blocked_reason?: string | null;
  correlation_id?: string | null;
  requested_by?: string | null;
  approved_by?: string | null;
  created_at: string;
  processed_at?: string | null;
}

export interface PartnerPayoutListResponse {
  items: PartnerPayoutRequest[];
}

export interface PartnerDocument {
  id: string;
  partner_org_id: string;
  period_from: string;
  period_to: string;
  total_amount: number;
  currency: string;
  status: string;
  tax_context?: Record<string, unknown> | null;
  pdf_object_key?: string | null;
  created_at: string;
}

export interface PartnerDocumentListResponse {
  items: PartnerDocument[];
}

export interface PartnerPayoutPreview {
  partner_org_id: string;
  currency: string;
  available_amount: number;
  legal_status?: string | null;
  tax_context?: Record<string, unknown> | null;
  warnings?: string[];
}

export interface PartnerExportJob {
  id: string;
  org_id: string;
  created_by_user_id: string;
  report_type: string;
  format: string;
  status: string;
  filters: Record<string, unknown>;
  file_name?: string | null;
  content_type?: string | null;
  row_count?: number | null;
  processed_rows: number;
  progress_percent?: number | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  expires_at?: string | null;
}

export interface PartnerExportJobListResponse {
  items: PartnerExportJob[];
}

export interface PayoutTraceOrder {
  order_id: string;
  gross_amount: number;
  platform_fee: number;
  penalties: number;
  partner_net: number;
  currency: string;
  settlement_snapshot_id?: string | null;
  finalized_at?: string | null;
  hash?: string | null;
  settlement_breakdown_url?: string | null;
}

export interface PayoutTraceSummary {
  gross_total: number;
  fee_total: number;
  penalties_total: number;
  net_total: number;
}

export interface PartnerPayoutTrace {
  payout_id: string;
  payout_state: string;
  date_from: string;
  date_to: string;
  created_at: string;
  total_amount: number;
  summary: PayoutTraceSummary;
  orders: PayoutTraceOrder[];
}
