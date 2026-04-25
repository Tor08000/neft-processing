import type { PortalMeResponse } from "../api/types";

export type PartnerPortalKind =
  | "FINANCE_PARTNER"
  | "MARKETPLACE_PARTNER"
  | "SERVICE_PARTNER"
  | "FUEL_PARTNER"
  | "LOGISTICS_PARTNER"
  | "GENERAL_PARTNER";

export type PartnerWorkspaceCode =
  | "finance"
  | "marketplace"
  | "services"
  | "support"
  | "profile";

export type PartnerWorkspace = {
  code: PartnerWorkspaceCode;
  label: string;
  defaultRoute: string;
};

const PARTNER_ROLE_LABELS: Record<string, string> = {
  PARTNER_OWNER: "OWNER",
  PARTNER_ACCOUNTANT: "FINANCE_MANAGER",
  PARTNER_MANAGER: "MANAGER",
  PARTNER_SERVICE_MANAGER: "MANAGER",
  PARTNER_OPERATOR: "OPERATOR",
  PARTNER_VIEWER: "ANALYST",
  PARTNER_ANALYST: "ANALYST",
};

type PartnerPortalSurface = {
  kind: PartnerPortalKind;
  capabilities: Set<string>;
  partnerRoles: string[];
  primaryRole: string | null;
  workspaces: PartnerWorkspace[];
  workspaceCodes: Set<PartnerWorkspaceCode>;
  defaultRoute: string;
};

const WORKSPACE_ORDER: PartnerWorkspaceCode[] = ["finance", "marketplace", "services", "support", "profile"];

const DEFAULT_WORKSPACES: Record<PartnerWorkspaceCode, PartnerWorkspace> = {
  finance: { code: "finance", label: "Finance", defaultRoute: "/finance" },
  marketplace: { code: "marketplace", label: "Marketplace", defaultRoute: "/products" },
  services: { code: "services", label: "Services", defaultRoute: "/services" },
  support: { code: "support", label: "Support", defaultRoute: "/support/requests" },
  profile: { code: "profile", label: "Profile", defaultRoute: "/partner/profile" },
};

const normalizeValues = (values?: Array<string | null | undefined> | null) =>
  values
    ?.map((value) => String(value ?? "").trim().toUpperCase())
    .filter(Boolean) ?? [];

const normalizePartnerAccessRoles = (values?: Array<string | null | undefined> | null) =>
  normalizeValues(values).map((value) => PARTNER_ROLE_LABELS[value] ?? value);

const dedupeWorkspaces = (workspaces: PartnerWorkspace[]) => {
  const seen = new Set<string>();
  return workspaces.filter((workspace) => {
    if (seen.has(workspace.code)) {
      return false;
    }
    seen.add(workspace.code);
    return true;
  });
};

const resolveFallbackKind = (portal: PortalMeResponse | null, capabilities: Set<string>): PartnerPortalKind => {
  const partnerType = String(portal?.partner?.partner_type ?? "").trim().toUpperCase();
  if (partnerType === "MERCHANT") return "MARKETPLACE_PARTNER";
  if (partnerType === "SERVICE_PROVIDER") return "SERVICE_PARTNER";
  if (partnerType === "FUEL_NETWORK") return "FUEL_PARTNER";
  if (partnerType === "LOGISTICS_PROVIDER") return "LOGISTICS_PARTNER";
  if (
    capabilities.has("PARTNER_FINANCE_VIEW") &&
    !capabilities.has("PARTNER_PRICING") &&
    !capabilities.has("PARTNER_CATALOG") &&
    !capabilities.has("PARTNER_ORDERS")
  ) {
    return "FINANCE_PARTNER";
  }
  if (capabilities.has("PARTNER_PRICING") || capabilities.has("PARTNER_CATALOG") || capabilities.has("PARTNER_ORDERS")) {
    return "MARKETPLACE_PARTNER";
  }
  return "GENERAL_PARTNER";
};

const resolveFallbackWorkspaces = (
  kind: PartnerPortalKind,
  capabilities: Set<string>,
): PartnerWorkspace[] => {
  const workspaces: PartnerWorkspace[] = [];
  const append = (code: PartnerWorkspaceCode) => {
    workspaces.push(DEFAULT_WORKSPACES[code]);
  };
  if (kind === "MARKETPLACE_PARTNER") {
    append("marketplace");
  }
  if (kind === "SERVICE_PARTNER") {
    append("services");
  }
  if (
    capabilities.has("PARTNER_FINANCE_VIEW") ||
    capabilities.has("PARTNER_SETTLEMENTS") ||
    capabilities.has("PARTNER_PAYOUT_REQUEST") ||
    capabilities.has("PARTNER_DOCUMENTS_LIST")
  ) {
    append("finance");
  }
  append("support");
  append("profile");
  return dedupeWorkspaces(workspaces).sort(
    (left, right) => WORKSPACE_ORDER.indexOf(left.code) - WORKSPACE_ORDER.indexOf(right.code),
  );
};

export const resolveEffectivePartnerRoles = (
  portal: PortalMeResponse | null,
  fallbackRoles?: string[] | null,
): string[] => {
  const portalRoles = normalizeValues(portal?.user_roles);
  if (portalRoles.length) {
    return portalRoles;
  }
  return normalizeValues(fallbackRoles);
};

export const resolvePartnerAccessRoles = (
  portal: PortalMeResponse | null,
  fallbackRoles?: string[] | null,
): string[] => {
  const partnerRoles = normalizeValues(portal?.partner?.partner_roles);
  if (partnerRoles.length) {
    return partnerRoles;
  }
  return normalizePartnerAccessRoles(resolveEffectivePartnerRoles(portal, fallbackRoles));
};

export const canOperatePartnerFinance = (
  portal: PortalMeResponse | null,
  fallbackRoles?: string[] | null,
): boolean => {
  const effectiveRoles = resolvePartnerAccessRoles(portal, fallbackRoles);
  if (!effectiveRoles.length) {
    return true;
  }
  const roleSet = new Set(effectiveRoles);
  return roleSet.has("OWNER") || roleSet.has("FINANCE_MANAGER") || roleSet.has("MANAGER");
};

const hasPartnerAccessRole = (
  portal: PortalMeResponse | null,
  roles: string[],
  fallbackRoles?: string[] | null,
): boolean => {
  const effectiveRoles = resolvePartnerAccessRoles(portal, fallbackRoles);
  if (!effectiveRoles.length) {
    return true;
  }
  const roleSet = new Set(effectiveRoles);
  return roles.some((role) => roleSet.has(role));
};

export const canManagePartnerProfile = (
  portal: PortalMeResponse | null,
  fallbackRoles?: string[] | null,
): boolean => hasPartnerAccessRole(portal, ["OWNER", "MANAGER", "FINANCE_MANAGER"], fallbackRoles);

export const canManagePartnerLocations = (
  portal: PortalMeResponse | null,
  fallbackRoles?: string[] | null,
): boolean => hasPartnerAccessRole(portal, ["OWNER", "MANAGER"], fallbackRoles);

export const canManagePartnerUsers = (
  portal: PortalMeResponse | null,
  fallbackRoles?: string[] | null,
): boolean => hasPartnerAccessRole(portal, ["OWNER"], fallbackRoles);

export const resolvePartnerPortalSurface = (portal: PortalMeResponse | null): PartnerPortalSurface => {
  const capabilities = new Set(normalizeValues(portal?.capabilities));
  const partnerRoles = normalizeValues(portal?.partner?.partner_roles).length
    ? normalizeValues(portal?.partner?.partner_roles)
    : normalizeValues(portal?.user_roles);
  const primaryRole = portal?.partner?.partner_role ?? partnerRoles[0] ?? null;
  const explicitKind = String(portal?.partner?.kind ?? "").trim().toUpperCase() as PartnerPortalKind | "";
  const kind = explicitKind || resolveFallbackKind(portal, capabilities);
  const explicitWorkspaces = (portal?.partner?.workspaces ?? [])
    .map((workspace) => {
      const code = String(workspace.code ?? "").trim().toLowerCase() as PartnerWorkspaceCode;
      if (!code || !(code in DEFAULT_WORKSPACES)) {
        return null;
      }
      return {
        code,
        label: workspace.label ?? DEFAULT_WORKSPACES[code].label,
        defaultRoute: workspace.default_route ?? DEFAULT_WORKSPACES[code].defaultRoute,
      } satisfies PartnerWorkspace;
    })
    .filter((workspace): workspace is PartnerWorkspace => workspace !== null);
  const workspaces = explicitWorkspaces.length
    ? dedupeWorkspaces(explicitWorkspaces)
    : resolveFallbackWorkspaces(kind || "GENERAL_PARTNER", capabilities);
  const defaultRoute = portal?.partner?.default_route ?? workspaces[0]?.defaultRoute ?? "/partner/profile";
  return {
    kind: (kind || "GENERAL_PARTNER") as PartnerPortalKind,
    capabilities,
    partnerRoles,
    primaryRole,
    workspaces,
    workspaceCodes: new Set(workspaces.map((workspace) => workspace.code)),
    defaultRoute,
  };
};

export const hasPartnerWorkspace = (
  portal: PortalMeResponse | null,
  workspace: PartnerWorkspaceCode,
): boolean => resolvePartnerPortalSurface(portal).workspaceCodes.has(workspace);

export const hasPartnerCapability = (portal: PortalMeResponse | null, capability: string): boolean =>
  resolvePartnerPortalSurface(portal).capabilities.has(String(capability).trim().toUpperCase());
