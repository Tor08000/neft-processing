export type BillingInvoiceStatus = "ISSUED" | "PARTIALLY_PAID" | "PAID" | "VOID";
export type BillingPaymentStatus = "CAPTURED" | "FAILED" | "REFUNDED_PARTIAL" | "REFUNDED_FULL";
export type BillingRefundStatus = "REFUNDED" | "FAILED";
export type ReconciliationLinkStatus = "PENDING" | "MATCHED" | "MISMATCHED";
export type ReconciliationLinkDirection = "IN" | "OUT";
export type ReconciliationLinkEntityType = "invoice" | "payment" | "refund";

export interface BillingInvoice {
  id: string;
  invoice_number: string;
  client_id: string;
  case_id?: string | null;
  currency: string;
  amount_total: number;
  amount_paid: number;
  status: BillingInvoiceStatus;
  issued_at: string;
  due_at?: string | null;
  ledger_tx_id: string;
  audit_event_id: string;
  created_at: string;
}

export interface BillingPayment {
  id: string;
  invoice_id: string;
  provider: string;
  provider_payment_id?: string | null;
  currency: string;
  amount: number;
  captured_at: string;
  status: BillingPaymentStatus;
  ledger_tx_id: string;
  audit_event_id: string;
  created_at: string;
  reconciliation_status?: ReconciliationLinkStatus | null;
}

export interface BillingRefund {
  id: string;
  payment_id: string;
  invoice_id?: string | null;
  provider?: string | null;
  provider_refund_id?: string | null;
  currency: string;
  amount: number;
  refunded_at: string;
  status: BillingRefundStatus;
  ledger_tx_id: string;
  audit_event_id: string;
  created_at: string;
  reconciliation_status?: ReconciliationLinkStatus | null;
}

export interface BillingReconciliationLink {
  id: string;
  entity_type: ReconciliationLinkEntityType;
  entity_id: string;
  provider: string;
  currency: string;
  expected_amount: number;
  direction: ReconciliationLinkDirection;
  expected_at: string;
  status: ReconciliationLinkStatus;
  run_id?: string | null;
  match_key?: string | null;
  last_run_id?: string | null;
  discrepancy_id?: string | null;
  created_at?: string | null;
}

export interface BillingInvoiceListResponse {
  items: BillingInvoice[];
  total: number;
  limit: number;
  offset: number;
  unavailable?: boolean;
}

export interface BillingPaymentsListResponse {
  items: BillingPayment[];
  total: number;
  limit: number;
  offset: number;
  unavailable?: boolean;
}

export interface BillingRefundsListResponse {
  items: BillingRefund[];
  total: number;
  limit: number;
  offset: number;
  unavailable?: boolean;
}

export interface BillingLinksListResponse {
  items: BillingReconciliationLink[];
  total: number;
  limit: number;
  offset: number;
  unavailable?: boolean;
}

export interface BillingInvoiceResult {
  invoice: BillingInvoice | null;
  unavailable?: boolean;
}

export interface BillingPaymentResult {
  payment: BillingPayment | null;
  unavailable?: boolean;
}

export interface BillingRefundResult {
  refund: BillingRefund | null;
  unavailable?: boolean;
}
