import type { AdminRole } from "../types/admin";
import { isAdminRoleSet } from "../admin/access";

export const PAYOUT_ROLES = [
  "NEFT_FINANCE",
  "NEFT_SUPERADMIN",
  "NEFT_ADMIN",
  "ADMIN",
  "FINANCE",
  "SUPERADMIN",
  "PLATFORM_ADMIN",
] as const;

export function hasAdminRole(roles: string[]): boolean {
  return isAdminRoleSet(roles as AdminRole[]);
}

export function hasPayoutAccess(roles: string[]): boolean {
  return roles.some((role) => PAYOUT_ROLES.includes(role as (typeof PAYOUT_ROLES)[number]));
}
