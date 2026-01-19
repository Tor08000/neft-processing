export type CommercialSubscription = {
  plan_code: string | null;
  plan_version: number | null;
  status: string | null;
  billing_cycle: string | null;
  support_plan: string | null;
  slo_tier: string | null;
};

export type CommercialAddon = {
  addon_code: string;
  status: string;
  price_override?: number | null;
  starts_at?: string | null;
  ends_at?: string | null;
  config_json?: Record<string, unknown> | null;
};

export type CommercialOverride = {
  feature_key: string;
  availability: string;
  limits_json?: Record<string, unknown> | null;
};

export type CommercialSnapshot = {
  hash: string | null;
  computed_at: string | null;
  version: number | null;
};

export type CommercialOrgState = {
  org: {
    id: number;
    name?: string | null;
    status?: string | null;
  };
  subscription: CommercialSubscription | null;
  addons: CommercialAddon[];
  overrides: CommercialOverride[];
  entitlements_snapshot: CommercialSnapshot | null;
};

export type CommercialEntitlementsSnapshot = {
  version: number;
  hash: string;
  computed_at: string;
  entitlements: Record<string, unknown>;
};

export type CommercialEntitlementsSnapshotsResponse = {
  current: CommercialEntitlementsSnapshot | null;
  previous: CommercialEntitlementsSnapshot[];
};

export type CommercialPlanChangePayload = {
  plan_code: string;
  plan_version: number;
  billing_cycle: string;
  status: string;
  reason?: string | null;
};

export type CommercialAddonEnablePayload = {
  addon_code: string;
  status: string;
  price_override?: number | null;
  starts_at?: string | null;
  ends_at?: string | null;
  config_json?: Record<string, unknown> | null;
  reason?: string | null;
};

export type CommercialAddonDisablePayload = {
  addon_code: string;
  reason?: string | null;
};

export type CommercialOverrideUpsertPayload = {
  feature_key: string;
  availability: string;
  limits_json?: Record<string, unknown> | null;
  reason: string;
  confirm: boolean;
  expires_at?: string | null;
};

export type CommercialRecomputePayload = {
  reason?: string | null;
};
