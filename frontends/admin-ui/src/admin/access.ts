import type { AdminPermission, AdminPermissionKey, AdminPermissions, AdminRole, AdminRoleLevel } from "../types/admin";

const PERMISSION_KEYS: AdminPermissionKey[] = [
  "access",
  "ops",
  "runtime",
  "finance",
  "revenue",
  "cases",
  "commercial",
  "crm",
  "marketplace",
  "legal",
  "onboarding",
  "audit",
];
const PLATFORM_PERMISSION_KEYS = PERMISSION_KEYS.filter((key) => key !== "revenue");

const SUPERADMIN_ROLES = new Set(["ADMIN", "NEFT_ADMIN", "NEFT_SUPERADMIN", "SUPERADMIN"]);
const PLATFORM_ADMIN_ROLES = new Set(["PLATFORM_ADMIN"]);
const FINANCE_ADMIN_ROLES = new Set(["NEFT_FINANCE", "FINANCE", "ADMIN_FINANCE"]);
const SUPPORT_ADMIN_ROLES = new Set(["NEFT_SUPPORT", "SUPPORT"]);
const OPS_ADMIN_ROLES = new Set(["NEFT_OPS", "OPS", "OPERATIONS"]);
const COMMERCIAL_ADMIN_ROLES = new Set(["NEFT_SALES", "SALES", "CRM", "ADMIN_CRM"]);
const LEGAL_ADMIN_ROLES = new Set(["NEFT_LEGAL", "LEGAL"]);
const OBSERVER_ADMIN_ROLES = new Set(["AUDITOR", "ANALYST", "OBSERVER", "READ_ONLY_ANALYST", "NEFT_OBSERVER"]);

const DEFAULT_PERMISSION: AdminPermission = {
  read: false,
  operate: false,
  approve: false,
  override: false,
  manage: false,
  write: false,
};

const createEmptyPermissions = (): AdminPermissions =>
  Object.fromEntries(PERMISSION_KEYS.map((key) => [key, { ...DEFAULT_PERMISSION }])) as unknown as AdminPermissions;

const grant = (
  permissions: AdminPermissions,
  capabilities: AdminPermissionKey[],
  actions: Partial<Omit<AdminPermission, "write">>,
) => {
  capabilities.forEach((capability) => {
    const current = permissions[capability];
    current.read = current.read || Boolean(actions.read);
    current.operate = current.operate || Boolean(actions.operate);
    current.approve = current.approve || Boolean(actions.approve);
    current.override = current.override || Boolean(actions.override);
    current.manage = current.manage || Boolean(actions.manage);
    current.write = current.operate || current.approve || current.override || current.manage;
  });
};

export const normalizeAdminRoles = (roles: AdminRole[]): Set<string> =>
  new Set(roles.map((role) => String(role).trim().toUpperCase()).filter(Boolean));

const intersects = (roles: Set<string>, allowed: Set<string>) => [...allowed].some((role) => roles.has(role));

export const isAdminRoleSet = (rawRoles: AdminRole[]): boolean => {
  const roles = normalizeAdminRoles(rawRoles);
  return [
    SUPERADMIN_ROLES,
    PLATFORM_ADMIN_ROLES,
    FINANCE_ADMIN_ROLES,
    SUPPORT_ADMIN_ROLES,
    OPS_ADMIN_ROLES,
    COMMERCIAL_ADMIN_ROLES,
    LEGAL_ADMIN_ROLES,
    OBSERVER_ADMIN_ROLES,
  ].some((allowed) => intersects(roles, allowed));
};

export const resolveAdminRoleLevels = (rawRoles: AdminRole[]): AdminRoleLevel[] => {
  const roles = normalizeAdminRoles(rawRoles);
  const levels: AdminRoleLevel[] = [];
  if (intersects(roles, SUPERADMIN_ROLES)) levels.push("superadmin");
  if (intersects(roles, PLATFORM_ADMIN_ROLES)) levels.push("platform_admin");
  if (intersects(roles, FINANCE_ADMIN_ROLES)) levels.push("finance_admin");
  if (intersects(roles, SUPPORT_ADMIN_ROLES)) levels.push("support_admin");
  if (intersects(roles, OPS_ADMIN_ROLES)) levels.push("operator");
  if (intersects(roles, COMMERCIAL_ADMIN_ROLES)) levels.push("commercial_admin");
  if (intersects(roles, LEGAL_ADMIN_ROLES)) levels.push("legal_admin");
  if (intersects(roles, OBSERVER_ADMIN_ROLES)) levels.push("observer");
  return levels.length ? levels : ["observer"];
};

export const buildAdminPermissions = (rawRoles: AdminRole[]): AdminPermissions => {
  const roles = normalizeAdminRoles(rawRoles);
  const permissions = createEmptyPermissions();

  if (intersects(roles, SUPERADMIN_ROLES)) {
    grant(permissions, PERMISSION_KEYS, {
      read: true,
      operate: true,
      approve: true,
      override: true,
      manage: true,
    });
    return permissions;
  }

  if (intersects(roles, PLATFORM_ADMIN_ROLES)) {
    grant(permissions, PLATFORM_PERMISSION_KEYS, {
      read: true,
      operate: true,
      approve: true,
      manage: true,
    });
    grant(permissions, ["finance", "commercial", "legal"], { override: true });
  }

  if (intersects(roles, FINANCE_ADMIN_ROLES)) {
    grant(permissions, ["finance"], { read: true, operate: true, approve: true, override: true });
    grant(permissions, ["revenue"], { read: true });
    grant(permissions, ["runtime", "cases", "commercial", "audit"], { read: true });
  }

  if (intersects(roles, SUPPORT_ADMIN_ROLES)) {
    grant(permissions, ["cases"], { read: true, operate: true, approve: true });
    grant(permissions, ["onboarding"], { read: true, operate: true, manage: true });
    grant(permissions, ["marketplace", "finance", "commercial", "legal", "runtime", "audit"], { read: true });
  }

  if (intersects(roles, OPS_ADMIN_ROLES)) {
    grant(permissions, ["ops"], { read: true, operate: true });
    grant(permissions, ["runtime", "finance", "cases", "marketplace", "onboarding"], { read: true });
  }

  if (intersects(roles, COMMERCIAL_ADMIN_ROLES)) {
    grant(permissions, ["commercial"], { read: true, operate: true, approve: true, override: true, manage: true });
    grant(permissions, ["crm"], { read: true, operate: true });
    grant(permissions, ["onboarding"], { read: true, operate: true });
    grant(permissions, ["revenue"], { read: true });
    grant(permissions, ["cases", "marketplace"], { read: true });
  }

  if (intersects(roles, LEGAL_ADMIN_ROLES)) {
    grant(permissions, ["legal"], { read: true, operate: true, approve: true });
    grant(permissions, ["audit", "cases", "runtime"], { read: true });
  }

  if (intersects(roles, OBSERVER_ADMIN_ROLES)) {
    grant(permissions, ["runtime", "finance", "cases", "commercial", "crm", "marketplace", "legal", "audit"], {
      read: true,
    });
  }

  return permissions;
};

export const primaryAdminRoleLevel = (roles: AdminRole[]): AdminRoleLevel => resolveAdminRoleLevels(roles)[0];

export const ADMIN_SURFACE_LABELS: Record<AdminPermissionKey, string> = {
  access: "Admins",
  ops: "Ops",
  runtime: "Runtime",
  finance: "Finance",
  revenue: "Revenue",
  cases: "Cases",
  commercial: "Commercial",
  crm: "CRM",
  marketplace: "Marketplace",
  legal: "Legal",
  onboarding: "Onboarding",
  audit: "Audit",
};
