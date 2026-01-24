export const ADMIN_ROLES = [
  "NEFT_OPS",
  "NEFT_FINANCE",
  "NEFT_SALES",
  "NEFT_LEGAL",
  "NEFT_SUPERADMIN",
  "NEFT_ADMIN",
  "ADMIN",
  "SUPERADMIN",
  "PLATFORM_ADMIN",
  "FINANCE",
] as const;
export const PAYOUT_ROLES = ["NEFT_FINANCE", "NEFT_SUPERADMIN", "NEFT_ADMIN", "ADMIN", "FINANCE", "SUPERADMIN"] as const;

export function hasAdminRole(roles: string[]): boolean {
  return roles.some((role) => ADMIN_ROLES.includes(role as (typeof ADMIN_ROLES)[number]));
}

export function hasPayoutAccess(roles: string[]): boolean {
  return roles.some((role) => PAYOUT_ROLES.includes(role as (typeof PAYOUT_ROLES)[number]));
}
