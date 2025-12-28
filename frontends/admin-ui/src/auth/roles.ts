export const ADMIN_ROLES = ["ADMIN", "SUPERADMIN", "PLATFORM_ADMIN", "FINANCE"] as const;
export const PAYOUT_ROLES = ["FINANCE", "PLATFORM_ADMIN", "SUPERADMIN"] as const;

export function hasAdminRole(roles: string[]): boolean {
  return roles.some((role) => ADMIN_ROLES.includes(role as (typeof ADMIN_ROLES)[number]));
}

export function hasPayoutAccess(roles: string[]): boolean {
  return roles.some((role) => PAYOUT_ROLES.includes(role as (typeof PAYOUT_ROLES)[number]));
}
