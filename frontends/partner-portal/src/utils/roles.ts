import type { PartnerRole } from "../api/types";

const privilegedRoles: PartnerRole[] = ["PARTNER_OWNER", "PARTNER_ACCOUNTANT"];
const pricesReadRoles: PartnerRole[] = [
  "PARTNER_OWNER",
  "PARTNER_OPERATOR",
  "PARTNER_ACCOUNTANT",
  "PARTNER_SERVICE_MANAGER",
];
const priceAnalyticsRoles: PartnerRole[] = [
  "PARTNER_OWNER",
  "PARTNER_ACCOUNTANT",
  "PARTNER_SERVICE_MANAGER",
];
const servicesReadRoles: PartnerRole[] = [
  "PARTNER_OWNER",
  "PARTNER_OPERATOR",
  "PARTNER_ACCOUNTANT",
  "PARTNER_SERVICE_MANAGER",
];
const servicesManageRoles: PartnerRole[] = ["PARTNER_OWNER", "PARTNER_SERVICE_MANAGER"];
const ordersReadRoles: PartnerRole[] = [
  "PARTNER_OWNER",
  "PARTNER_OPERATOR",
  "PARTNER_ACCOUNTANT",
  "PARTNER_SERVICE_MANAGER",
];
const ordersLifecycleRoles: PartnerRole[] = [
  "PARTNER_OWNER",
  "PARTNER_OPERATOR",
  "PARTNER_SERVICE_MANAGER",
];
const ordersCancelRoles: PartnerRole[] = ["PARTNER_OWNER", "PARTNER_SERVICE_MANAGER"];
const refundsReadRoles: PartnerRole[] = ["PARTNER_OWNER", "PARTNER_SERVICE_MANAGER", "PARTNER_ACCOUNTANT"];
const refundsManageRoles: PartnerRole[] = ["PARTNER_OWNER", "PARTNER_SERVICE_MANAGER"];

export const hasRole = (roles: string[] | undefined, role: PartnerRole): boolean =>
  Boolean(roles?.includes(role));

export const canManagePayouts = (roles: string[] | undefined): boolean =>
  Boolean(roles?.some((role) => privilegedRoles.includes(role as PartnerRole)));

export const canReadPrices = (roles: string[] | undefined): boolean =>
  Boolean(roles?.some((role) => pricesReadRoles.includes(role as PartnerRole)));

export const canReadPriceAnalytics = (roles: string[] | undefined): boolean =>
  Boolean(roles?.some((role) => priceAnalyticsRoles.includes(role as PartnerRole)));

export const canCreateDraftPrices = (roles: string[] | undefined): boolean =>
  Boolean(
    roles?.some((role) =>
      ["PARTNER_OWNER", "PARTNER_OPERATOR"].includes(role as PartnerRole),
    ),
  );

export const canPublishPrices = (roles: string[] | undefined): boolean =>
  Boolean(roles?.some((role) => role === "PARTNER_OWNER"));

export const canReadServices = (roles: string[] | undefined): boolean =>
  Boolean(roles?.some((role) => servicesReadRoles.includes(role as PartnerRole)));

export const canManageServices = (roles: string[] | undefined): boolean =>
  Boolean(roles?.some((role) => servicesManageRoles.includes(role as PartnerRole)));

export const canReadOrders = (roles: string[] | undefined): boolean =>
  Boolean(roles?.some((role) => ordersReadRoles.includes(role as PartnerRole)));

export const canManageOrderLifecycle = (roles: string[] | undefined): boolean =>
  Boolean(roles?.some((role) => ordersLifecycleRoles.includes(role as PartnerRole)));

export const canCancelOrders = (roles: string[] | undefined): boolean =>
  Boolean(roles?.some((role) => ordersCancelRoles.includes(role as PartnerRole)));

export const canReadRefunds = (roles: string[] | undefined): boolean =>
  Boolean(roles?.some((role) => refundsReadRoles.includes(role as PartnerRole)));

export const canManageRefunds = (roles: string[] | undefined): boolean =>
  Boolean(roles?.some((role) => refundsManageRoles.includes(role as PartnerRole)));
