export type CrmStatus = string;

export interface CrmClient {
  id: string;
  client_id: string;
  tenant_id: number;
  legal_name: string;
  tax_id?: string | null;
  kpp?: string | null;
  status: CrmStatus;
  country: string;
  timezone: string;
  created_at?: string | null;
  updated_at?: string | null;
  meta?: Record<string, unknown> | null;
  active_contract_id?: string | null;
  active_subscription_id?: string | null;
  limit_profile_id?: string | null;
  risk_profile_id?: string | null;
}

export interface CrmContract {
  id: string;
  contract_id: string;
  tenant_id?: number | null;
  contract_number: string;
  client_id: string;
  status: CrmStatus;
  valid_from?: string | null;
  valid_to?: string | null;
  billing_mode?: string | null;
  currency?: string | null;
  risk_profile_id?: string | null;
  limit_profile_id?: string | null;
  documents_required?: boolean | null;
  crm_contract_version?: number | null;
  created_at?: string | null;
  meta?: Record<string, unknown> | null;
}

export interface CrmTariff {
  id: string;
  tariff_id: string;
  name: string;
  description?: string | null;
  status: CrmStatus;
  billing_period: string;
  base_fee_minor: number;
  currency: string;
  features?: Record<string, boolean> | null;
  limits_defaults?: Record<string, unknown> | null;
  definition?: Record<string, unknown> | null;
  created_at?: string | null;
}

export interface CrmSubscription {
  id: string;
  subscription_id: string;
  tenant_id?: number | null;
  client_id: string;
  tariff_plan_id: string;
  status: CrmStatus;
  billing_cycle?: string | null;
  billing_day?: number | null;
  started_at?: string | null;
  paused_at?: string | null;
  ended_at?: string | null;
  meta?: Record<string, unknown> | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface CrmProfile {
  id: string;
  tenant_id?: number | null;
  name?: string | null;
  status?: CrmStatus | null;
  definition?: Record<string, unknown> | null;
  created_at?: string | null;
}

export interface CrmRiskProfile extends CrmProfile {
  risk_policy_id?: string | null;
  threshold_set_id?: string | null;
  shadow_enabled?: boolean | null;
}

export interface CrmFeatureFlag {
  id?: string | null;
  tenant_id?: number | null;
  client_id?: string | null;
  feature: string;
  enabled: boolean;
  updated_at?: string | null;
  updated_by?: string | null;
}

export interface CrmDecisionContext {
  client_id: string;
  tenant_id: number;
  active_contract: CrmContract | null;
  tariff: CrmTariff | null;
  feature_flags: CrmFeatureFlag[];
  risk_profile: CrmRiskProfile | null;
  limit_profile: CrmProfile | null;
  enforcement_flags: Record<string, boolean>;
}

export interface CrmListResponse<T> {
  items: T[];
}
