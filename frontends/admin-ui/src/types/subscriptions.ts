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

export interface RoleEntitlement {
  id?: number;
  role_code: string;
  entitlements?: Record<string, unknown> | null;
}

export interface BonusRule {
  id: number;
  plan_id?: string | null;
  rule_code: string;
  title: string;
  condition?: Record<string, unknown> | null;
  reward?: Record<string, unknown> | null;
  enabled: boolean;
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
  roles: RoleEntitlement[];
  bonus_rules: BonusRule[];
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

export interface SubscriptionPlanCreate {
  code: string;
  title: string;
  description?: string | null;
  is_active: boolean;
  billing_period_months: number;
  price_cents: number;
  currency: string;
  modules?: SubscriptionPlanModule[];
}

export interface SubscriptionPlanUpdate {
  code?: string;
  title?: string;
  description?: string | null;
  is_active?: boolean;
  billing_period_months?: number;
  price_cents?: number;
  currency?: string;
}

export interface AssignSubscriptionPayload {
  plan_id: string;
  duration_months?: number | null;
  auto_renew: boolean;
}
