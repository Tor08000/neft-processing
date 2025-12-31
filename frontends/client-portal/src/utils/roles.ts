import type { AuthSession } from "../api/types";

export type ClientRole =
  | "CLIENT_ADMIN"
  | "CLIENT_OWNER"
  | "CLIENT_ACCOUNTANT"
  | "CLIENT_FLEET_MANAGER"
  | "CLIENT_USER";

const normalizeRoles = (user: AuthSession | null): ClientRole[] => (user?.roles ?? []) as ClientRole[];

export const hasRole = (user: AuthSession | null, role: ClientRole): boolean => normalizeRoles(user).includes(role);

export const hasAnyRole = (user: AuthSession | null, roles: ClientRole[]): boolean => {
  const current = normalizeRoles(user);
  return roles.some((role) => current.includes(role));
};

export const canAccessOps = (user: AuthSession | null): boolean =>
  hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_FLEET_MANAGER"]);

export const canAccessFinance = (user: AuthSession | null): boolean =>
  hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_ACCOUNTANT"]);
