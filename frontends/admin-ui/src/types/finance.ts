export interface FinanceOverviewBlockedReason {
  reason: string;
  count: number;
}

export interface FinanceOverview {
  window: "24h" | "7d";
  overdue_orgs: number;
  overdue_amount: number | string;
  invoices_issued_24h: number;
  invoices_paid_24h: number;
  payment_intakes_pending: number;
  reconciliation_unmatched_24h: number;
  payout_queue_pending: number;
  payout_blocked_top_reasons: FinanceOverviewBlockedReason[];
  mor_immutable_violations_24h: number;
  clawback_required_24h: number;
}

export interface FinanceInvoiceSummary {
  id: string;
  org_id?: string | null;
  subscription_id?: string | null;
  status: string;
  period_start?: string | null;
  period_end?: string | null;
  due_at?: string | null;
  paid_at?: string | null;
  total?: number | string | null;
  currency?: string | null;
}

export interface FinanceInvoiceDetail extends FinanceInvoiceSummary {
  pdf_url?: string | null;
}

export interface FinanceInvoiceListResponse {
  items: FinanceInvoiceSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface PaymentIntakeDetail {
  id: number;
  org_id: number;
  invoice_id: number;
  status: string;
  amount: number | string;
  currency: string;
  payer_name?: string | null;
  payer_inn?: string | null;
  bank_reference?: string | null;
  paid_at_claimed?: string | null;
  comment?: string | null;
  proof?: {
    object_key: string;
    file_name: string;
    content_type: string;
    size: number;
  } | null;
  proof_url?: string | null;
  created_by_user_id?: string | null;
  reviewed_by_admin?: string | null;
  reviewed_at?: string | null;
  review_note?: string | null;
  created_at?: string | null;
  invoice_link?: string | null;
}

export interface PaymentIntakeListResponse {
  items: PaymentIntakeDetail[];
  total: number;
  limit: number;
  offset: number;
}
