export interface LegalPartnerSummary {
  partner_id: string;
  partner_name?: string | null;
  legal_status?: string | null;
  payout_blocked?: boolean | null;
  updated_at?: string | null;
}

export interface LegalPartnerListResponse {
  items: LegalPartnerSummary[];
  total?: number;
  limit?: number;
  offset?: number;
}

export interface LegalPartnerDocument {
  id: string;
  title?: string | null;
  status?: string | null;
  url?: string | null;
  updated_at?: string | null;
}

export interface LegalPartnerDetail {
  partner_id: string;
  partner_name?: string | null;
  legal_status?: string | null;
  payout_blocks?: string[] | null;
  documents?: LegalPartnerDocument[] | null;
  profile?: Record<string, unknown> | null;
  raw?: Record<string, unknown> | null;
}
