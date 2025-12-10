export type OperationType = "AUTH" | "CAPTURE" | "REFUND" | "REVERSAL";
export type OperationStatus = string;

export interface Operation {
  operation_id: string;
  created_at: string;
  operation_type: OperationType;
  status: OperationStatus;
  merchant_id?: string | null;
  terminal_id?: string | null;
  client_id?: string | null;
  card_id?: string | null;
  amount: number;
  currency: string;
  captured_amount: number;
  refunded_amount: number;
  parent_operation_id?: string | null;
  product_code?: string | null;
  product_category?: string | null;
  tx_type?: string | null;
  mcc?: string | null;
  risk_result?: string | null;
  risk_score?: number | null;
  risk_reasons?: string[] | null;
  risk_flags?: Record<string, unknown> | null;
  risk_source?: string | null;
  risk_level?: string | null;
  risk_rules_fired?: string[] | null;
  risk_payload?: RiskPayload | null;
  daily_limit?: number | null;
  limit_per_tx?: number | null;
  used_today?: number | null;
  new_used_today?: number | null;
  authorized?: boolean | null;
  response_code?: string | null;
  response_message?: string | null;
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
  min_amount?: number;
  max_amount?: number;
  risk_result?: string | string[];
  risk_min_score?: number;
  risk_max_score?: number;
  order_by?:
    | "created_at_desc"
    | "created_at_asc"
    | "amount_desc"
    | "amount_asc"
    | "risk_score_desc"
    | "risk_score_asc";
  risk_level?: string | string[];
  mcc?: string;
  product_category?: string;
  tx_type?: string;
}

export interface RiskDecisionPayload {
  level?: string;
  reason_codes?: string[];
  rules_fired?: string[];
  ai_score?: number;
  ai_model_version?: string;
}

export interface RiskPayload {
  decision?: RiskDecisionPayload;
  source?: string;
  flags?: Record<string, unknown>;
  [key: string]: unknown;
}
