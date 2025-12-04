export type RoleOption =
  | "PLATFORM_ADMIN"
  | "CLIENT_OWNER"
  | "CLIENT_MANAGER"
  | "CLIENT_VIEWER";

export interface AdminUser {
  id: string;
  email: string;
  full_name?: string | null;
  is_active: boolean;
  created_at?: string | null;
  roles: RoleOption[];
}

export interface CreateUserPayload {
  email: string;
  password: string;
  full_name?: string;
  roles: RoleOption[];
}

export interface UpdateUserPayload {
  full_name?: string | null;
  is_active?: boolean;
  roles?: RoleOption[];
}
