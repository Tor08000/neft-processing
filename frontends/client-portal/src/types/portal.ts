export interface PortalSlaSummary {
  status: string;
  violations: number;
}

export interface ClientDashboardSummary {
  active_contracts: number;
  invoices_due: number;
  invoices_due_amount: number;
  payments_last_30d: number;
  payments_last_30d_count: number;
  sla: PortalSlaSummary;
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
