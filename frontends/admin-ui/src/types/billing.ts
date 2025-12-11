export type BillingStatus = "PENDING" | "FINALIZED";
export type InvoiceStatus = "DRAFT" | "ISSUED" | "SENT" | "PAID" | "CANCELLED";

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

export interface TariffPlan {
  id: string;
  name: string;
  params?: Record<string, unknown> | null;
}

export interface TariffPrice {
  id: number;
  tariff_id: string;
  product_id: string;
  partner_id?: string | null;
  azs_id?: string | null;
  price_per_liter: string;
  cost_price_per_liter?: string | null;
  currency: string;
  valid_from?: string | null;
  valid_to?: string | null;
  priority: number;
}

export interface InvoiceLine {
  id: string;
  invoice_id: string;
  operation_id?: string | null;
  card_id?: string | null;
  product_id: string;
  liters?: string | null;
  unit_price?: string | null;
  line_amount: number;
  tax_amount: number;
  partner_id?: string | null;
  azs_id?: string | null;
}

export interface Invoice {
  id: string;
  client_id: string;
  period_from: string;
  period_to: string;
  currency: string;
  total_amount: number;
  tax_amount: number;
  total_with_tax: number;
  status: InvoiceStatus;
  created_at?: string;
  issued_at?: string | null;
  paid_at?: string | null;
  lines?: InvoiceLine[];
}
