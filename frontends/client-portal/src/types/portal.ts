export type ClientDashboardWidgetType = "kpi" | "chart" | "list" | "health" | "cta";

export interface ClientDashboardWidget {
  type: ClientDashboardWidgetType;
  key: string;
  data?: unknown;
}

export interface ClientDashboardResponse {
  role: string;
  timezone: string;
  widgets: ClientDashboardWidget[];
}

export interface ClientInvoiceSummary {
  invoice_number: string;
  period_start: string;
  period_end: string;
  amount_total: number;
  status: string;
  due_date?: string | null;
  currency: string;
}

export interface ClientInvoicePaymentSummary {
  amount: number;
  status: string;
  provider?: string | null;
  external_ref?: string | null;
  created_at: string;
}

export interface ClientInvoiceRefundSummary {
  amount: number;
  status: string;
  provider?: string | null;
  external_ref?: string | null;
  created_at: string;
  reason?: string | null;
}

export interface ClientInvoiceLine {
  line_type: string;
  ref_code?: string | null;
  description?: string | null;
  unit?: string | null;
  quantity?: number | null;
  unit_price?: number | null;
  amount?: number | null;
}

export interface ClientPaymentIntakeProof {
  object_key: string;
  file_name: string;
  content_type: string;
  size: number;
}

export interface ClientPaymentIntake {
  id: number;
  org_id: number;
  invoice_id: number;
  status: string;
  amount: number;
  currency: string;
  payer_name?: string | null;
  payer_inn?: string | null;
  bank_reference?: string | null;
  paid_at_claimed?: string | null;
  comment?: string | null;
  proof?: ClientPaymentIntakeProof | null;
  created_by_user_id: string;
  reviewed_by_admin?: string | null;
  reviewed_at?: string | null;
  review_note?: string | null;
  created_at: string;
}

export interface ClientInvoiceDetails {
  invoice_number: string;
  period_start: string;
  period_end: string;
  amount_total: number;
  amount_paid: number;
  amount_refunded: number;
  amount_due: number;
  status: string;
  due_date?: string | null;
  currency: string;
  download_url?: string | null;
  payments: ClientInvoicePaymentSummary[];
  refunds: ClientInvoiceRefundSummary[];
  lines?: ClientInvoiceLine[];
  payment_intakes?: ClientPaymentIntake[];
}

export interface ClientInvoiceListResponse {
  items: ClientInvoiceSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface ClientContractSummary {
  contract_number: string;
  contract_type: string;
  effective_from: string;
  effective_to?: string | null;
  status: string;
  sla_status: string;
  sla_violations: number;
}

export interface ClientContractsResponse {
  items: ClientContractSummary[];
}

export interface ContractObligationSummary {
  obligation_type: string;
  metric: string;
  threshold: number;
  comparison: string;
  window?: string | null;
  penalty_type: string;
  penalty_value: number;
}

export interface SlaResultSummary {
  period_start: string;
  period_end: string;
  status: string;
  measured_value: number;
}

export interface ClientContractDetails {
  contract_number: string;
  contract_type: string;
  effective_from: string;
  effective_to?: string | null;
  status: string;
  sla_status: string;
  sla_violations: number;
  penalties_total: number;
  obligations: ContractObligationSummary[];
  sla_results: SlaResultSummary[];
}
