export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  email: string;
  subject_type: string;
  partner_id?: string | null;
  roles: string[];
}

export interface LoginRequest {
  email: string;
  password: string;
  portal?: "partner";
}

export interface MeResponse {
  email: string;
  roles: string[];
  subject: string;
  subject_type: string;
  partner_id?: string | null;
}

export interface PortalMeResponse {
  actor_type?: string;
  context?: string | null;
  user: {
    id: string;
    email?: string | null;
    subject_type?: string | null;
    timezone?: string | null;
  };
  org?: {
    id: string;
    name?: string | null;
    status?: string | null;
  } | null;
  org_roles: string[];
  user_roles: string[];
  roles?: string[] | null;
  memberships?: string[] | null;
  subscription?: {
    plan_code?: string | null;
    status?: string | null;
    billing_cycle?: string | null;
    support_plan?: string | null;
    slo_tier?: string | null;
    addons?: Array<Record<string, unknown>> | null;
  } | null;
  entitlements_snapshot?: Record<string, unknown> | null;
  capabilities: string[];
  nav_sections?: Array<{ code: string; label: string }> | null;
  gating?: {
    onboarding_enabled: boolean;
    legal_gate_enabled: boolean;
  } | null;
  features?: {
    onboarding_enabled?: boolean;
    legal_gate_enabled?: boolean;
  } | null;
  partner?: {
    status?: string | null;
    profile?: {
      display_name?: string | null;
      contacts_json?: Record<string, unknown> | null;
      meta_json?: Record<string, unknown> | null;
    } | null;
  } | null;
  access_state: string;
  access_reason?: string | null;
}

export interface AuthSession {
  token: string;
  email: string;
  roles: string[];
  subjectType: string;
  partnerId?: string | null;
  expiresAt: number;
}

export type PartnerRole =
  | "PARTNER_OWNER"
  | "PARTNER_ACCOUNTANT"
  | "PARTNER_OPERATOR"
  | "PARTNER_SERVICE_MANAGER";
