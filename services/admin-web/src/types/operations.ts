export type OperationType = "AUTH" | "CAPTURE" | "REFUND" | "REVERSAL";
export type OperationStatus = string;

export interface Operation {
  operation_id: string;
  created_at: string;
  operation_type: OperationType;
  status: OperationStatus;
  merchant_id: string;
  terminal_id: string;
  client_id: string;
  card_id: string;
  amount: number;
  currency: string;
  captured_amount: number;
  refunded_amount: number;
  parent_operation_id?: string | null;
  product_code?: string | null;
  product_category?: string | null;
  tx_type?: string | null;
  mcc?: string | null;
  daily_limit?: number;
  limit_per_tx?: number;
  used_today?: number;
  new_used_today?: number;
  authorized?: boolean;
  response_code?: string;
  response_message?: string;
  reason?: string | null;
}

export interface OperationListResponse {
  items: Operation[];
  total: number;
  limit: number;
  offset: number;
}

export interface OperationQuery extends Record<string, unknown> {
  limit?: number;
  offset?: number;
  operation_type?: string;
  status?: string;
  merchant_id?: string;
  terminal_id?: string;
  client_id?: string;
  card_id?: string;
  date_from?: string;
  date_to?: string;
  from_created_at?: string;
  to_created_at?: string;
}
