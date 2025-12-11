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
}

export interface OperationDetails extends OperationSummary {
  limit_profile_id?: string | null;
  risk_result?: string | null;
}

export interface OperationsPage {
  items: OperationSummary[];
  total: number;
  limit: number;
  offset: number;
}
