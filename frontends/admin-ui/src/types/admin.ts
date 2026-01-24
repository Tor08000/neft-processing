export type AdminRole =
  | "NEFT_OPS"
  | "NEFT_FINANCE"
  | "NEFT_SALES"
  | "NEFT_LEGAL"
  | "NEFT_SUPERADMIN"
  | "NEFT_ADMIN"
  | "ADMIN"
  | string;

export interface AdminPermission {
  read: boolean;
  write: boolean;
}

export interface AdminPermissions {
  ops: AdminPermission;
  finance: AdminPermission;
  sales: AdminPermission;
  legal: AdminPermission;
  superadmin: AdminPermission;
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
