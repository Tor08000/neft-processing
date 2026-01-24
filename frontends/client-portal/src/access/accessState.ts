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

const BUSINESS_ERROR_TO_STATE: Record<string, AccessState> = {
  billing_soft_blocked: AccessState.OVERDUE,
  billing_hard_blocked: AccessState.SUSPENDED,
  billing_suspended: AccessState.SUSPENDED,
  feature_not_entitled: AccessState.MISSING_CAPABILITY,
  addon_required: AccessState.MISSING_CAPABILITY,
  org_not_active: AccessState.NEEDS_ONBOARDING,
  legal_not_verified: AccessState.LEGAL_PENDING,
  admin_forbidden: AccessState.FORBIDDEN_ROLE,
};

export const mapBusinessErrorToAccessState = (errorCode?: string | null): AccessState | null => {
  if (!errorCode) return null;
  return BUSINESS_ERROR_TO_STATE[errorCode] ?? null;
};

type ResolveAccessStateParams = {
  client: PortalMeResponse | null;
  requiredRoles?: string[];
  capability?: string;
  module?: string;
};

export const resolveAccessState = ({
  client,
  requiredRoles,
  capability,
  module,
}: ResolveAccessStateParams): AccessDecision => {
  if (!client) {
    return { state: AccessState.TECH_ERROR, reason: "service_unavailable" };
  }

  if (client.access_state) {
    if (Object.values(AccessState).includes(client.access_state as AccessState)) {
      if (client.access_state !== AccessState.ACTIVE) {
        return { state: client.access_state as AccessState, reason: (client.access_reason as AccessReason) ?? undefined };
      }
    } else {
      return { state: AccessState.TECH_ERROR, reason: (client.access_reason as AccessReason) ?? "tech_error" };
    }
  }

  if (requiredRoles?.length) {
    const roles = new Set(
      [...(client.user_roles ?? []), ...(client.org_roles ?? [])].map((role) => role.toUpperCase()),
    );
    const hasRole = requiredRoles.some((role) => roles.has(role.toUpperCase()));
    if (!hasRole) {
      return { state: AccessState.FORBIDDEN_ROLE, reason: "forbidden_role" };
    }
  }

  if (capability) {
    const caps = new Set((client.capabilities ?? []).map((item) => item.toUpperCase()));
    if (!caps.has(capability.toUpperCase())) {
      return { state: AccessState.MISSING_CAPABILITY, reason: "missing_capability" };
    }
  }

  if (module) {
    const modulesPayload = client.entitlements_snapshot?.modules as Record<string, { enabled?: boolean }> | undefined;
    const moduleKey = Object.keys(modulesPayload ?? {}).find((key) => key.toUpperCase() === module.toUpperCase());
    const entry = moduleKey ? modulesPayload?.[moduleKey] : undefined;
    if (entry && entry.enabled === false) {
      return { state: AccessState.MODULE_DISABLED, reason: "module_disabled" };
    }
    const enabledModules = new Set(
      Object.entries(modulesPayload ?? {})
        .filter(([, payload]) => payload?.enabled)
        .map(([code]) => code.toUpperCase()),
    );
    if (!enabledModules.has(module.toUpperCase())) {
      return { state: AccessState.MISSING_CAPABILITY, reason: "missing_capability" };
    }
  }

  return { state: AccessState.ACTIVE };
};
