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
  parent_operation_id?: string | null;
  daily_limit?: number;
  limit_per_tx?: number;
  used_today?: number;
  new_used_today?: number;
  authorized?: boolean;
  response_code?: string;
  response_message?: string;
}

export interface OperationListResponse {
  items: Operation[];
  total: number;
  limit: number;
  offset: number;
}
