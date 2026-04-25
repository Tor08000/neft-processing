import { getPlanByCode } from "@shared/subscriptions/catalog";
import type { PortalMeResponse } from "../api/clientPortal";

export type ClientKind = "INDIVIDUAL" | "BUSINESS";
export type ClientSubscriptionTier = "FREE" | "STANDARD" | "PRO" | "ENTERPRISE";

export type ClientWorkspace = {
  clientKind: ClientKind;
  subscriptionTier: ClientSubscriptionTier;
  hasMarketplaceWorkspace: boolean;
  hasFinanceWorkspace: boolean;
  hasDocumentsWorkspace: boolean;
  hasSupportWorkspace: boolean;
  hasTeamWorkspace: boolean;
  hasFleetWorkspace: boolean;
  hasAnalyticsWorkspace: boolean;
};

const BUSINESS_TYPES = new Set(["LEGAL", "IP", "LEGAL_ENTITY", "SOLE_PROPRIETOR", "BUSINESS"]);
const FLEET_CAPABILITY_TOKENS = ["FLEET", "LOGISTICS", "CLIENT_FLEET", "CLIENT_LOGISTICS", "CLIENT_CORE"];
const ANALYTICS_CAPABILITY_TOKENS = ["CLIENT_ANALYTICS", "ANALYTICS"];
const MARKETPLACE_CAPABILITY_TOKENS = ["MARKETPLACE", "CLIENT_MARKETPLACE"];
const TEAM_ROLES = new Set(["CLIENT_OWNER", "CLIENT_MANAGER", "CLIENT_ADMIN"]);

const hasEnabledFlag = (container: unknown, key: string): boolean => {
  if (!container || typeof container !== "object") return false;
  const value = (container as Record<string, unknown>)[key];
  if (typeof value === "boolean") return value;
  if (value && typeof value === "object" && "enabled" in value) {
    return Boolean((value as Record<string, unknown>).enabled);
  }
  return false;
};

const normalizeCustomerType = (value?: string | null): string | null => {
  if (!value) return null;
  return value.trim().toUpperCase();
};

export const resolveClientKind = (params: {
  client: PortalMeResponse | null;
}): ClientKind => {
  const orgType = normalizeCustomerType(params.client?.org?.org_type);
  return BUSINESS_TYPES.has(orgType ?? "") ? "BUSINESS" : "INDIVIDUAL";
};

export const resolveClientSubscriptionTier = (planCode?: string | null): ClientSubscriptionTier => {
  const normalized = planCode?.trim().toUpperCase() ?? "";
  if (!normalized || normalized.includes("FREE")) return "FREE";
  if (normalized.includes("ENTERPRISE")) return "ENTERPRISE";
  if (normalized.includes("PRO")) return "PRO";
  return "STANDARD";
};

export const resolveClientWorkspace = (params: {
  client: PortalMeResponse | null;
}): ClientWorkspace => {
  const { client } = params;
  const clientKind = resolveClientKind({ client });
  const planCode = client?.subscription?.plan_code ?? null;
  const subscriptionPlan = getPlanByCode(planCode);
  const modules = client?.modules;
  const entitlements = client?.entitlements_snapshot;
  const capabilities = client?.capabilities ?? [];
  const navSections = client?.nav_sections ?? [];
  const roles = [...(client?.org_roles ?? []), ...(client?.user_roles ?? []), ...(client?.roles ?? [])];
  const isActivated = Boolean(client?.org?.id || client?.org_status);

  const hasFleetWorkspace =
    clientKind === "BUSINESS" &&
    (Boolean(subscriptionPlan?.modules.fleet || subscriptionPlan?.modules.logistics) ||
      hasEnabledFlag(modules, "fleet") ||
      hasEnabledFlag(modules, "logistics") ||
      hasEnabledFlag(entitlements, "fleet") ||
      hasEnabledFlag(entitlements, "logistics") ||
      capabilities.some((item) => FLEET_CAPABILITY_TOKENS.includes(item)) ||
      navSections.some((section) => section.code.toLowerCase().includes("fleet") || section.code.toLowerCase().includes("logistics")));

  const hasAnalyticsWorkspace =
    clientKind === "BUSINESS" &&
    (Boolean(subscriptionPlan?.modules.analytics) ||
      hasEnabledFlag(modules, "analytics") ||
      hasEnabledFlag(entitlements, "analytics") ||
      capabilities.some((item) => ANALYTICS_CAPABILITY_TOKENS.includes(item)) ||
      navSections.some((section) => section.code.toLowerCase().includes("analytics")));

  const hasMarketplaceWorkspace =
    isActivated ||
    Boolean(subscriptionPlan?.modules.dashboard) ||
    capabilities.some((item) => MARKETPLACE_CAPABILITY_TOKENS.includes(item)) ||
    navSections.some((section) => section.code.toLowerCase().includes("market"));

  const hasTeamWorkspace =
    clientKind === "BUSINESS" &&
    (Boolean(subscriptionPlan?.modules.users) ||
      hasEnabledFlag(modules, "users") ||
      hasEnabledFlag(entitlements, "users") ||
      roles.some((role) => TEAM_ROLES.has(role)));

  const hasFinanceWorkspace = clientKind === "BUSINESS" && isActivated;

  return {
    clientKind,
    subscriptionTier: resolveClientSubscriptionTier(planCode),
    hasMarketplaceWorkspace,
    hasFinanceWorkspace,
    hasDocumentsWorkspace: true,
    hasSupportWorkspace: true,
    hasTeamWorkspace,
    hasFleetWorkspace,
    hasAnalyticsWorkspace,
  };
};
