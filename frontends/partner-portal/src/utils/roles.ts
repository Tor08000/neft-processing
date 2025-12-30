import type { PartnerRole } from "../api/types";

const privilegedRoles: PartnerRole[] = ["PARTNER_OWNER", "PARTNER_ACCOUNTANT"];

export const hasRole = (roles: string[] | undefined, role: PartnerRole): boolean =>
  Boolean(roles?.includes(role));

export const canManagePayouts = (roles: string[] | undefined): boolean =>
  Boolean(roles?.some((role) => privilegedRoles.includes(role as PartnerRole)));
