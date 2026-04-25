import type { MarketplaceOrderStatus } from "../types/marketplace";

const CANCELABLE_STATUSES = new Set<MarketplaceOrderStatus>(["CREATED", "PENDING_PAYMENT"]);

const SUCCESS_STATUSES = new Set<MarketplaceOrderStatus>([
  "PAID",
  "CONFIRMED",
  "CONFIRMED_BY_PARTNER",
  "IN_PROGRESS",
  "COMPLETED",
  "CLOSED",
  "REFUNDED",
]);

const ERROR_STATUSES = new Set<MarketplaceOrderStatus>([
  "DECLINED_BY_PARTNER",
  "CANCELED_BY_CLIENT",
  "CANCELLED",
  "PAYMENT_FAILED",
  "FAILED",
  "REJECTED",
]);

export const getMarketplaceOrderStatusClass = (status?: string | null): string => {
  if (!status) return "neft-chip neft-chip-warn";
  if (SUCCESS_STATUSES.has(status as MarketplaceOrderStatus)) return "neft-chip neft-chip-ok";
  if (ERROR_STATUSES.has(status as MarketplaceOrderStatus)) return "neft-chip neft-chip-err";
  return "neft-chip neft-chip-warn";
};

export const isCancelableMarketplaceOrderStatus = (status?: string | null): boolean =>
  status ? CANCELABLE_STATUSES.has(status as MarketplaceOrderStatus) : false;
