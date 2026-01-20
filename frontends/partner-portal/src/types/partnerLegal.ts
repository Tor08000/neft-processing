export interface PartnerLegalDetails {
  partner_id: string;
  legal_name?: string | null;
  inn?: string | null;
  kpp?: string | null;
  ogrn?: string | null;
  passport?: string | null;
  bank_account?: string | null;
  bank_bic?: string | null;
  bank_name?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export type PartnerTaxContext = {
  tax_rate?: number | string | null;
};

export interface PartnerLegalProfile {
  partner_id: string;
  legal_type: string;
  country?: string | null;
  tax_residency?: string | null;
  tax_regime?: string | null;
  vat_applicable: boolean;
  vat_rate?: number | null;
  legal_status: string;
  details?: PartnerLegalDetails | null;
  tax_context?: PartnerTaxContext | null;
}

export interface PartnerLegalChecklist {
  legal_profile: boolean;
  legal_details: boolean;
  verified: boolean;
}

export interface PartnerLegalProfileResponse {
  profile?: PartnerLegalProfile | null;
  checklist: PartnerLegalChecklist;
}

export interface PartnerLegalProfileUpdate {
  legal_type: string;
  country?: string | null;
  tax_residency?: string | null;
  tax_regime?: string | null;
  vat_applicable?: boolean;
  vat_rate?: number | null;
}

export interface PartnerLegalDetailsUpdate {
  legal_name?: string | null;
  inn?: string | null;
  kpp?: string | null;
  ogrn?: string | null;
  passport?: string | null;
  bank_account?: string | null;
  bank_bic?: string | null;
  bank_name?: string | null;
}
