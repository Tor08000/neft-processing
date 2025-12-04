export type BillingStatus = "PENDING" | "FINALIZED";

export interface BillingSummaryItem {
  billing_date: string;
  client_id: string;
  merchant_id: string;
  product_type: string;
  currency: string;
  total_amount: number;
  total_quantity: number;
  operations_count: number;
  commission_amount: number;
  status?: BillingStatus | null;
  id?: string | null;
}
