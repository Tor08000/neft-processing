export type BillingStatus = "PENDING" | "FINALIZED";

export interface BillingSummaryItem {
  id: string;
  date: string;
  merchant_id: string;
  total_captured_amount: number;
  operations_count: number;
  status: BillingStatus;
  hash?: string | null;
  generated_at: string;
  finalized_at?: string | null;
}
