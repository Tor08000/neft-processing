import type { PortalMeResponse } from "../api/clientPortal";

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
  | "org_not_active"
  | "legal_not_verified"
  | "subscription_missing"
  | "billing_overdue"
  | "billing_suspended"
  | "forbidden_role"
  | "module_disabled"
  | "missing_capability"
  | "service_unavailable"
  | "business_block"
  | "partner_onboarding"
  | "payout_blocked"
  | "sla_penalty"
  | "tech_error"
  | null;

export type AccessDecision = {
  state: AccessState;
  reason?: AccessReason;
};

type ResolveAccessStateParams = {
  client: PortalMeResponse | null;
  requiredRoles?: string[];
  capability?: string;
  module?: string;
};

export const resolveAccessState = ({
  client,
  requiredRoles: _requiredRoles,
  capability: _capability,
  module: _module,
}: ResolveAccessStateParams): AccessDecision => {
  if (!client) {
    return { state: AccessState.TECH_ERROR, reason: "service_unavailable" };
  }

  if (!client.access_state) {
    return { state: AccessState.TECH_ERROR, reason: (client.access_reason as AccessReason) ?? "tech_error" };
  }

  if (!Object.values(AccessState).includes(client.access_state as AccessState)) {
    return {
      state: AccessState.TECH_ERROR,
      reason: (client.access_reason as AccessReason) ?? (client.access_state as AccessReason),
    };
  }

  if (client.access_state !== AccessState.ACTIVE) {
    return { state: client.access_state as AccessState, reason: (client.access_reason as AccessReason) ?? undefined };
  }

  return { state: AccessState.ACTIVE };
};
