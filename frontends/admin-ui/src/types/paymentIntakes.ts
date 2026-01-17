export type BillingPaymentIntakeStatus = "SUBMITTED" | "UNDER_REVIEW" | "APPROVED" | "REJECTED";

export interface BillingPaymentIntakeProof {
  object_key: string;
  file_name: string;
  content_type: string;
  size: number;
}

export interface BillingPaymentIntake {
  id: number;
  org_id: number;
  invoice_id: number;
  status: BillingPaymentIntakeStatus;
  amount: number;
  currency: string;
  payer_name?: string | null;
  payer_inn?: string | null;
  bank_reference?: string | null;
  paid_at_claimed?: string | null;
  comment?: string | null;
  proof?: BillingPaymentIntakeProof | null;
  proof_url?: string | null;
  created_by_user_id: string;
  reviewed_by_admin?: string | null;
  reviewed_at?: string | null;
  review_note?: string | null;
  created_at: string;
}

export interface BillingPaymentIntakeListResponse {
  items: BillingPaymentIntake[];
  total: number;
  limit: number;
  offset: number;
}
