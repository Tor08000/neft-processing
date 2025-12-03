export type BillingStatus = "PENDING" | "FINALIZED";

export interface BillingSummaryItem {
  id?: string | null;
  date: string;
  merchant_id: string;
  total_captured_amount: number;
  operations_count: number;
  status?: BillingStatus | null;
  hash?: string | null;
  generated_at?: string | null;
  finalized_at?: string | null;
}
