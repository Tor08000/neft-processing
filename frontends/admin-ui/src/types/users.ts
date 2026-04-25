export interface AdminRoleCatalogEntry {
  code: string;
  label: string;
  description: string;
}

export const ADMIN_ROLE_CATALOG: AdminRoleCatalogEntry[] = [
  {
    code: "NEFT_SUPERADMIN",
    label: "Superadmin",
    description: "Full read, operate, approve, override and admin management across the platform.",
  },
  {
    code: "PLATFORM_ADMIN",
    label: "Platform Admin",
    description: "Cross-domain admin management and broad operator access without superadmin aliases.",
  },
  {
    code: "NEFT_FINANCE",
    label: "Finance Admin",
    description: "Finance inspection, approvals and controlled overrides without portal-wide admin management.",
  },
  {
    code: "NEFT_SUPPORT",
    label: "Support Admin",
    description: "Cases triage, escalation and onboarding operations with adjacent read access.",
  },
  {
    code: "NEFT_OPS",
    label: "Operations Admin",
    description: "Ops inspection, logistics visibility and runtime-adjacent read workflows.",
  },
  {
    code: "NEFT_SALES",
    label: "Commercial Admin",
    description: "Commercial and CRM operator workflows with onboarding support.",
  },
  {
    code: "NEFT_LEGAL",
    label: "Legal Admin",
    description: "Documents review, approvals and audit-adjacent legal visibility.",
  },
  {
    code: "ANALYST",
    label: "Analyst",
    description: "Read-only observer access across grounded admin surfaces.",
  },
];

export const LEGACY_ADMIN_ROLE_ALIASES: AdminRoleCatalogEntry[] = [
  {
    code: "ADMIN",
    label: "Legacy Admin",
    description: "Legacy superadmin-compatible alias kept for existing users and tokens.",
  },
  {
    code: "SUPERADMIN",
    label: "Legacy Superadmin",
    description: "Legacy superadmin alias kept for compatibility.",
  },
  {
    code: "NEFT_ADMIN",
    label: "Legacy NEFT Admin",
    description: "Legacy superadmin-compatible alias kept for compatibility.",
  },
  {
    code: "FINANCE",
    label: "Legacy Finance",
    description: "Legacy finance admin alias kept for compatibility.",
  },
  {
    code: "ADMIN_FINANCE",
    label: "Legacy Finance Admin",
    description: "Legacy finance admin alias kept for compatibility.",
  },
  {
    code: "SUPPORT",
    label: "Legacy Support",
    description: "Legacy support admin alias kept for compatibility.",
  },
  {
    code: "OPS",
    label: "Legacy Ops",
    description: "Legacy operations admin alias kept for compatibility.",
  },
  {
    code: "OPERATIONS",
    label: "Legacy Operations",
    description: "Legacy operations admin alias kept for compatibility.",
  },
  {
    code: "SALES",
    label: "Legacy Sales",
    description: "Legacy commercial admin alias kept for compatibility.",
  },
  {
    code: "CRM",
    label: "Legacy CRM",
    description: "Legacy commercial admin alias kept for compatibility.",
  },
  {
    code: "ADMIN_CRM",
    label: "Legacy CRM Admin",
    description: "Legacy commercial admin alias kept for compatibility.",
  },
  {
    code: "LEGAL",
    label: "Legacy Legal",
    description: "Legacy legal admin alias kept for compatibility.",
  },
  {
    code: "AUDITOR",
    label: "Auditor",
    description: "Read-only observer alias kept for compatibility.",
  },
  {
    code: "OBSERVER",
    label: "Observer",
    description: "Read-only observer alias kept for compatibility.",
  },
  {
    code: "READ_ONLY_ANALYST",
    label: "Read-only Analyst",
    description: "Read-only observer alias kept for compatibility.",
  },
  {
    code: "NEFT_OBSERVER",
    label: "NEFT Observer",
    description: "Read-only observer alias kept for compatibility.",
  },
];

export const ADMIN_ASSIGNABLE_ROLES = [
  ...ADMIN_ROLE_CATALOG,
  ...LEGACY_ADMIN_ROLE_ALIASES,
];

export const DEFAULT_ADMIN_ROLE_CODE = "ANALYST";

export function getAdminRoleEntry(role: string): AdminRoleCatalogEntry {
  return (
    ADMIN_ASSIGNABLE_ROLES.find((entry) => entry.code === role) ?? {
      code: role,
      label: role,
      description: "Unknown legacy role preserved as-is.",
    }
  );
}

export interface AdminUser {
  id: string;
  email: string;
  full_name?: string | null;
  is_active: boolean;
  created_at?: string | null;
  roles: string[];
}

export interface CreateUserPayload {
  email: string;
  password: string;
  full_name?: string;
  roles: string[];
  reason?: string;
  correlation_id?: string;
}

export interface UpdateUserPayload {
  full_name?: string | null;
  is_active?: boolean;
  roles?: string[];
  reason?: string;
  correlation_id?: string;
}
