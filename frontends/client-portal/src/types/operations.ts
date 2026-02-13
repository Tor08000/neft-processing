export interface OperationSummary {
  id: string;
  created_at: string;
  status: string;
  amount: number;
  currency: string;
  card_id: string;
  merchant_id?: string | null;
  terminal_id?: string | null;
  reason?: string | null;
  product_type?: string | null;
  quantity?: number | string | null;
  primary_reason?: string | null;
  risk_level?: string | null;
  vehicle_id?: string | null;
  driver_id?: string | null;
  document_ids?: string[] | null;
  request_id?: string | null;
  correlation_id?: string | null;
}

export interface OperationStation {
  id: string;
  name: string;
  address?: string | null;
  lat?: number | null;
  lon?: number | null;
  nav_url?: string | null;
}

export interface OperationDetails extends OperationSummary {
  station?: OperationStation | null;
}

export interface OperationsPage {
  items: OperationSummary[];
  total: number;
  limit: number;
  offset: number;
}
