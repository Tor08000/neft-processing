export type CrmStatus = string;

export interface CrmClient {
  client_id: string;
  tenant_id?: number | null;
  legal_name?: string | null;
  status?: CrmStatus | null;
  country?: string | null;
  timezone?: string | null;
  active_contract_id?: string | null;
  active_subscription_id?: string | null;
  limit_profile_id?: string | null;
  risk_profile_id?: string | null;
  features?: Record<string, boolean> | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface CrmContract {
  id?: string | null;
  contract_id?: string | null;
  contract_number?: string | null;
  client_id?: string | null;
  status?: CrmStatus | null;
  valid_from?: string | null;
  valid_to?: string | null;
  tariff_plan_id?: string | null;
  risk_profile_id?: string | null;
  limit_profile_id?: string | null;
  documents_required?: boolean | null;
  features?: Record<string, boolean> | null;
  audit?: Record<string, unknown> | null;
  apply_result?: Record<string, unknown> | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface CrmTariff {
  tariff_id?: string | null;
  id?: string | null;
  name?: string | null;
  status?: CrmStatus | null;
  base_fee?: number | string | null;
  domains?: Record<string, boolean> | null;
  included_summary?: string | null;
  definition?: Record<string, unknown> | null;
}

export interface CrmSubscription {
  id?: string | null;
  subscription_id?: string | null;
  client_id?: string | null;
  tariff_id?: string | null;
  status?: CrmStatus | null;
  billing_day?: number | null;
  started_at?: string | null;
  next_run_at?: string | null;
  last_period_id?: string | null;
  segments?: unknown[] | null;
  usage?: unknown[] | null;
  charges?: unknown[] | null;
  invoices?: string[] | null;
  money_links?: unknown[] | null;
}

export interface CrmProfile {
  id: string;
  name?: string | null;
  description?: string | null;
  definition?: Record<string, unknown> | null;
}

export interface CrmFeatureFlag {
  feature: string;
  enabled: boolean;
}

export interface CrmListResponse<T> {
  items: T[];
  total?: number;
  limit?: number;
  offset?: number;
}
