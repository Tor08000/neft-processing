export type SubscriptionStatus = "FREE" | "ACTIVE" | "PAUSED" | "GRACE" | "EXPIRED" | "CANCELLED";

export type SubscriptionModuleCode =
  | "FUEL_CORE"
  | "AI_ASSISTANT"
  | "EXPLAIN"
  | "PENALTIES"
  | "MARKETPLACE"
  | "ANALYTICS"
  | "SLA"
  | "BONUSES";

export interface SubscriptionPlanModule {
  id?: number;
  module_code: SubscriptionModuleCode;
  enabled: boolean;
  tier?: string | null;
  limits?: Record<string, unknown> | null;
}

export interface SubscriptionPlan {
  id: string;
  code: string;
  title: string;
  description?: string | null;
  is_active: boolean;
  billing_period_months: number;
  price_cents: number;
  currency: string;
  modules: SubscriptionPlanModule[];
}

export interface ClientSubscription {
  id: string;
  tenant_id: number;
  client_id: string;
  plan_id: string;
  status: SubscriptionStatus;
  start_at: string;
  end_at?: string | null;
  auto_renew: boolean;
  grace_until?: string | null;
  plan?: SubscriptionPlan | null;
}

export interface SubscriptionBenefits {
  plan: SubscriptionPlan;
  modules: SubscriptionPlanModule[];
  unavailable_modules: SubscriptionPlanModule[];
}

export interface GamificationSummary {
  as_of: string;
  plan_code: string;
  bonuses: Record<string, unknown>[];
  streaks: Record<string, unknown>[];
  achievements: Record<string, unknown>[];
  preview?: Record<string, unknown> | null;
}
