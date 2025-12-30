import type { PartnerRole } from "../api/types";

const privilegedRoles: PartnerRole[] = ["PARTNER_OWNER", "PARTNER_ACCOUNTANT"];
const pricesReadRoles: PartnerRole[] = [
  "PARTNER_OWNER",
  "PARTNER_OPERATOR",
  "PARTNER_ACCOUNTANT",
  "PARTNER_SERVICE_MANAGER",
];

export const hasRole = (roles: string[] | undefined, role: PartnerRole): boolean =>
  Boolean(roles?.includes(role));

export const canManagePayouts = (roles: string[] | undefined): boolean =>
  Boolean(roles?.some((role) => privilegedRoles.includes(role as PartnerRole)));

export const canReadPrices = (roles: string[] | undefined): boolean =>
  Boolean(roles?.some((role) => pricesReadRoles.includes(role as PartnerRole)));

export const canCreateDraftPrices = (roles: string[] | undefined): boolean =>
  Boolean(
    roles?.some((role) =>
      ["PARTNER_OWNER", "PARTNER_OPERATOR"].includes(role as PartnerRole),
    ),
  );

export const canPublishPrices = (roles: string[] | undefined): boolean =>
  Boolean(roles?.some((role) => role === "PARTNER_OWNER"));
