import type { PortalMeResponse } from "../api/types";

export enum AccessState {
  AUTH_REQUIRED = "AUTH_REQUIRED",
  NEEDS_ONBOARDING = "NEEDS_ONBOARDING",
  NEEDS_PLAN = "NEEDS_PLAN",
  ACTIVE = "ACTIVE",
  OVERDUE = "OVERDUE",
  SUSPENDED = "SUSPENDED",
  LEGAL_PENDING = "LEGAL_PENDING",
  PAYOUT_BLOCKED = "PAYOUT_BLOCKED",
  SLA_PENALTY = "SLA_PENALTY",
  FORBIDDEN_ROLE = "FORBIDDEN_ROLE",
  MODULE_DISABLED = "MODULE_DISABLED",
  MISSING_CAPABILITY = "MISSING_CAPABILITY",
  SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE",
  MISCONFIG = "MISCONFIG",
  TECH_ERROR = "TECH_ERROR",
}

export type AccessReason =
  | "partner_onboarding"
  | "legal_not_verified"
  | "subscription_missing"
  | "billing_overdue"
  | "billing_suspended"
  | "payout_blocked"
  | "org_not_active"
  | "missing_capability"
  | "forbidden_role"
  | "tech_error"
  | null;

export type AccessDecision = {
  state: AccessState;
  reason?: AccessReason;
};

const BUSINESS_ERROR_TO_STATE: Record<string, AccessState> = {
  partner_not_verified: AccessState.NEEDS_ONBOARDING,
  legal_not_verified: AccessState.LEGAL_PENDING,
  feature_not_entitled: AccessState.MISSING_CAPABILITY,
  admin_forbidden: AccessState.FORBIDDEN_ROLE,
  billing_soft_blocked: AccessState.OVERDUE,
  billing_hard_blocked: AccessState.SUSPENDED,
  billing_suspended: AccessState.SUSPENDED,
  org_not_active: AccessState.NEEDS_ONBOARDING,
};

export const mapBusinessErrorToAccessState = (errorCode?: string | null): AccessState | null => {
  if (!errorCode) return null;
  return BUSINESS_ERROR_TO_STATE[errorCode] ?? null;
};

export const mapBusinessErrorToAccessDecision = (errorCode?: string | null): AccessDecision | null => {
  if (!errorCode) return null;
  const state = BUSINESS_ERROR_TO_STATE[errorCode];
  if (!state) return null;
  return { state, reason: errorCode as AccessReason };
};

type ResolveAccessStateParams = {
  portal: PortalMeResponse | null;
  requiredRoles?: string[];
  capability?: string;
};

export const resolveAccessState = ({
  portal,
  requiredRoles,
  capability,
}: ResolveAccessStateParams): AccessDecision => {
  if (!portal) {
    return { state: AccessState.TECH_ERROR, reason: "tech_error" };
  }

  if (portal.access_state) {
    if (Object.values(AccessState).includes(portal.access_state as AccessState)) {
      if (portal.access_state !== AccessState.ACTIVE) {
        return { state: portal.access_state as AccessState, reason: (portal.access_reason as AccessReason) ?? undefined };
      }
    } else {
      return { state: AccessState.TECH_ERROR, reason: (portal.access_reason as AccessReason) ?? "tech_error" };
    }
  }

  if (requiredRoles?.length) {
    const roles = new Set(
      [...(portal.user_roles ?? []), ...(portal.org_roles ?? [])].map((role) => role.toUpperCase()),
    );
    const hasRole = requiredRoles.some((role) => roles.has(role.toUpperCase()));
    if (!hasRole) {
      return { state: AccessState.FORBIDDEN_ROLE, reason: "forbidden_role" };
    }
  }

  if (capability) {
    const caps = new Set((portal.capabilities ?? []).map((item) => item.toUpperCase()));
    if (!caps.has(capability.toUpperCase())) {
      return { state: AccessState.MISSING_CAPABILITY, reason: "missing_capability" };
    }
  }

  return { state: AccessState.ACTIVE };
};
