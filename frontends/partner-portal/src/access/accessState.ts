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

  if (!portal.access_state) {
    return { state: AccessState.TECH_ERROR, reason: (portal.access_reason as AccessReason) ?? "tech_error" };
  }

  if (!Object.values(AccessState).includes(portal.access_state as AccessState)) {
    return {
      state: AccessState.TECH_ERROR,
      reason: (portal.access_reason as AccessReason) ?? (portal.access_state as AccessReason),
    };
  }

  if (portal.access_state !== AccessState.ACTIVE) {
    return { state: portal.access_state as AccessState, reason: (portal.access_reason as AccessReason) ?? undefined };
  }

  const roleSet = new Set([...(portal.user_roles ?? []), ...(portal.org_roles ?? [])].map((role) => role.toUpperCase()));
  if (requiredRoles?.length && !requiredRoles.some((role) => roleSet.has(role.toUpperCase()))) {
    return { state: AccessState.FORBIDDEN_ROLE, reason: "forbidden_role" };
  }

  const capabilitySet = new Set((portal.capabilities ?? []).map((item) => item.toUpperCase()));
  if (capability && !capabilitySet.has(capability.toUpperCase())) {
    return { state: AccessState.MISSING_CAPABILITY, reason: "missing_capability" };
  }

  return { state: AccessState.ACTIVE };
};
