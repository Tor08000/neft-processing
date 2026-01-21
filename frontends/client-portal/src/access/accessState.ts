import type { PortalMeResponse } from "../api/clientPortal";

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
  | "org_not_active"
  | "subscription_missing"
  | "billing_overdue"
  | "billing_suspended"
  | "forbidden_role"
  | "missing_capability"
  | "coming_soon"
  | "tech_error"
  | "business_block"
  | null;

export type AccessDecision = {
  state: AccessState;
  reason?: AccessReason;
};

const BUSINESS_ERROR_TO_STATE: Record<string, AccessState> = {
  billing_soft_blocked: AccessState.OVERDUE,
  billing_suspended: AccessState.SUSPENDED,
  feature_not_entitled: AccessState.MISSING_CAPABILITY,
  org_not_active: AccessState.NEEDS_ONBOARDING,
  admin_forbidden: AccessState.FORBIDDEN_ROLE,
};

export const mapBusinessErrorToAccessState = (errorCode?: string | null): AccessState | null => {
  if (!errorCode) return null;
  return BUSINESS_ERROR_TO_STATE[errorCode] ?? null;
};

const normalize = (value?: string | null) => value?.toUpperCase();

const OVERDUE_STATUSES = new Set(["OVERDUE", "PAST_DUE", "PASTDUE", "DELINQUENT"]);
const SUSPENDED_STATUSES = new Set(["SUSPENDED", "BLOCKED", "PAUSED"]);

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
    return { state: AccessState.TECH_ERROR, reason: "tech_error" };
  }

  const orgStatus = client.org_status ?? client.org?.status ?? null;
  if (orgStatus && orgStatus !== "ACTIVE") {
    return { state: AccessState.NEEDS_ONBOARDING, reason: "org_not_active" };
  }

  if (!client.subscription?.plan_code) {
    return { state: AccessState.NEEDS_PLAN, reason: "subscription_missing" };
  }

  const subscriptionStatus = normalize(client.subscription?.status);
  if (subscriptionStatus && OVERDUE_STATUSES.has(subscriptionStatus)) {
    return { state: AccessState.OVERDUE, reason: "billing_overdue" };
  }
  if (subscriptionStatus && SUSPENDED_STATUSES.has(subscriptionStatus)) {
    return { state: AccessState.SUSPENDED, reason: "billing_suspended" };
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
    const enabledModules = new Set(
      Object.entries(modulesPayload ?? {})
        .filter(([, payload]) => payload?.enabled)
        .map(([code]) => code.toUpperCase()),
    );
    if (!enabledModules.has(module.toUpperCase())) {
      return { state: AccessState.MISSING_CAPABILITY, reason: "missing_capability" };
    }
  }

  return { state: AccessState.OK };
};
