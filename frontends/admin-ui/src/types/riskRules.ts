export type RuleScope = "GLOBAL" | "CLIENT" | "CARD" | "TARIFF";

export type MetricType =
  | "always"
  | "amount"
  | "quantity"
  | "count"
  | "total_amount"
  | "amount_spike"
  | "unusual_product";

export type RuleAction = "LOW" | "MEDIUM" | "HIGH" | "BLOCK" | "MANUAL_REVIEW";

export interface SelectorConfig {
  product_types?: string[] | null;
  merchant_ids?: string[] | null;
  terminal_ids?: string[] | null;
  geo?: string[] | null;
  hours?: number[] | null;
}

export interface WindowConfig {
  duration_seconds?: number | null;
  hours?: number | null;
}

export interface RuleConfig {
  name: string;
  scope: RuleScope;
  subject_id?: string | null;
  selector: SelectorConfig;
  window?: WindowConfig | null;
  metric: MetricType;
  value: number;
  action: RuleAction;
  priority?: number;
  enabled: boolean;
  reason?: string | null;
}

export interface RiskRule {
  id: number;
  description?: string | null;
  dsl: RuleConfig;
  enabled: boolean;
  created_at: string;
  updated_at: string;
  version: number;
}

export interface RiskRuleListResponse {
  items: RiskRule[];
  total: number;
  limit: number;
  offset: number;
}

export interface RiskRulePayload {
  description?: string | null;
  dsl: RuleConfig;
}

export interface RiskRulesQuery extends Record<string, unknown> {
  scope?: RuleScope;
  enabled?: boolean;
  subject_ref?: string;
  limit?: number;
  offset?: number;
}
