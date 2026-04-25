export type AdminRole =
  | "NEFT_SUPPORT"
  | "SUPPORT"
  | "NEFT_OPS"
  | "OPS"
  | "OPERATIONS"
  | "NEFT_FINANCE"
  | "FINANCE"
  | "ADMIN_FINANCE"
  | "NEFT_SALES"
  | "SALES"
  | "CRM"
  | "ADMIN_CRM"
  | "NEFT_LEGAL"
  | "LEGAL"
  | "AUDITOR"
  | "ANALYST"
  | "OBSERVER"
  | "READ_ONLY_ANALYST"
  | "NEFT_OBSERVER"
  | "NEFT_SUPERADMIN"
  | "NEFT_ADMIN"
  | "ADMIN"
  | "SUPERADMIN"
  | "PLATFORM_ADMIN"
  | string;

export type AdminRoleLevel =
  | "superadmin"
  | "platform_admin"
  | "finance_admin"
  | "support_admin"
  | "operator"
  | "commercial_admin"
  | "legal_admin"
  | "observer";

export interface AdminPermission {
  read: boolean;
  operate: boolean;
  approve: boolean;
  override: boolean;
  manage: boolean;
  write: boolean;
}

export type AdminPermissionKey =
  | "access"
  | "ops"
  | "runtime"
  | "finance"
  | "revenue"
  | "cases"
  | "commercial"
  | "crm"
  | "marketplace"
  | "legal"
  | "onboarding"
  | "audit";

export interface AdminPermissions {
  access: AdminPermission;
  ops: AdminPermission;
  runtime: AdminPermission;
  finance: AdminPermission;
  revenue: AdminPermission;
  cases: AdminPermission;
  commercial: AdminPermission;
  crm: AdminPermission;
  marketplace: AdminPermission;
  legal: AdminPermission;
  onboarding: AdminPermission;
  audit: AdminPermission;
}

export interface AdminEnv {
  name: "dev" | "stage" | "prod" | string;
  build: string;
  region: string;
}

export interface AdminUserProfile {
  id: string;
  email?: string | null;
  roles: AdminRole[];
  issuer?: string | null;
}

export interface AdminMeResponse {
  admin_user: AdminUserProfile;
  roles: AdminRole[];
  primary_role_level: AdminRoleLevel;
  role_levels: AdminRoleLevel[];
  permissions: AdminPermissions;
  env: AdminEnv;
  environment?: AdminEnv;
  read_only?: boolean;
  audit_context?: {
    require_reason: boolean;
    require_correlation_id: boolean;
  };
}

export interface AdminErrorPayload {
  error: string;
  message: string;
  status?: number;
  request_id?: string | null;
  required_roles?: string[];
}
