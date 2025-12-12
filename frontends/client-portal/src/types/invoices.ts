export interface ClientInvoiceSummary {
  id: string;
  period_from: string;
  period_to: string;
  currency: string;
  total_amount: number;
  tax_amount: number;
  total_with_tax: number;
  status: string;
  created_at?: string;
  issued_at?: string;
  paid_at?: string;
}

export interface ClientInvoiceLine {
  card_id?: string | null;
  product_id: string;
  liters?: string | number | null;
  amount: number;
  tax_amount: number;
}

export interface ClientInvoiceDetails extends ClientInvoiceSummary {
  lines: ClientInvoiceLine[];
}

export interface ClientInvoiceList {
  items: ClientInvoiceSummary[];
  total: number;
  limit: number;
  offset: number;
}
