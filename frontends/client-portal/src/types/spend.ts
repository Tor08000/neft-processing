export interface SpendDashboardSummary {
  total_operations: number;
  total_amount: number;
  period: string;
  active_limits: number;
  spending_trend: number[];
  dates: string[];
}

export interface SpendOperationSummary {
  id: string;
  date: string;
  type: string;
  status: string;
  amount: number;
  currency: string;
  card_ref?: string | null;
  fuel_type?: string | null;
}

export interface SpendDashboardResponse {
  summary: SpendDashboardSummary;
  recent_operations: SpendOperationSummary[];
}
