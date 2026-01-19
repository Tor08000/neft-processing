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
}

export interface PartnerPayoutRequest {
  id: string;
  partner_org_id: string;
  amount: number;
  currency: string;
  status: string;
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
