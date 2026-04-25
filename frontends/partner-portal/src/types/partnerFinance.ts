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

export interface PartnerContract {
  id: string;
  contract_number: string;
  contract_type: string;
  party_role: string;
  counterparty_type: string;
  counterparty_id: string;
  currency: string;
  status: string;
  effective_from: string;
  effective_to?: string | null;
  created_at: string;
}

export interface PartnerContractListResponse {
  items: PartnerContract[];
  total: number;
  limit: number;
  offset: number;
}

export interface PartnerSettlementItem {
  id: string;
  source_type: string;
  source_id: string;
  amount: number;
  direction: string;
  created_at: string;
}

export interface PartnerSettlementSnapshot {
  id: string;
  order_id: string;
  gross_amount: number;
  platform_fee: number;
  penalties: number;
  partner_net: number;
  currency: string;
  finalized_at?: string | null;
  hash?: string | null;
}

export interface PartnerSettlement {
  id: string;
  partner_id: string;
  currency: string;
  period_start: string;
  period_end: string;
  status: string;
  total_gross: number;
  total_fees: number;
  total_refunds: number;
  net_amount: number;
  period_hash?: string | null;
  snapshot_payload?: Record<string, unknown> | null;
  created_at: string;
  approved_at?: string | null;
  paid_at?: string | null;
  marketplace_snapshots_count: number;
  items?: PartnerSettlementItem[] | null;
  marketplace_snapshots?: PartnerSettlementSnapshot[] | null;
}

export interface PartnerSettlementListResponse {
  items: PartnerSettlement[];
  total: number;
  limit: number;
  offset: number;
}
