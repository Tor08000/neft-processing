import type { PortalMeResponse } from "../api/types";

export enum AccessState {
  OK = "OK",
  NEEDS_ONBOARDING = "NEEDS_ONBOARDING",
  NEEDS_PLAN = "NEEDS_PLAN",
  OVERDUE = "OVERDUE",
  SUSPENDED = "SUSPENDED",
  FORBIDDEN_ROLE = "FORBIDDEN_ROLE",
  MISSING_CAPABILITY = "MISSING_CAPABILITY",
  COMING_SOON = "COMING_SOON",
  TECH_ERROR = "TECH_ERROR",
}

export type AccessReason =
  | "partner_onboarding"
  | "legal_not_verified"
  | "settlement_not_finalized"
  | "billing_soft_blocked"
  | "billing_hard_blocked"
  | "feature_not_entitled"
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
  legal_not_verified: AccessState.NEEDS_ONBOARDING,
  settlement_not_finalized: AccessState.COMING_SOON,
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

  const partnerStatus = portal.partner?.status ?? null;
  if (partnerStatus && partnerStatus !== "ACTIVE") {
    return { state: AccessState.NEEDS_ONBOARDING, reason: "partner_onboarding" };
  }

  const meta = portal.partner?.profile?.meta_json ?? {};
  const legalStatus =
    typeof (meta as Record<string, unknown>).legal_status === "string"
      ? ((meta as Record<string, unknown>).legal_status as string)
      : null;
  if (legalStatus && legalStatus !== "VERIFIED") {
    return { state: AccessState.NEEDS_ONBOARDING, reason: "legal_not_verified" };
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

  return { state: AccessState.OK };
};
