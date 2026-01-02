import React from "react";
import type {
  BillingInvoiceStatus,
  BillingPaymentStatus,
  BillingRefundStatus,
  ReconciliationLinkDirection,
  ReconciliationLinkEntityType,
  ReconciliationLinkStatus,
} from "../../types/billingFlows";

export const formatMoney = (amount?: number | string | null, currency?: string | null): string => {
  if (amount === null || amount === undefined) return "—";
  const value = typeof amount === "string" ? Number(amount) : amount;
  if (Number.isNaN(value)) return String(amount);
  const formatted = new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
  return currency ? `${formatted} ${currency}` : formatted;
};

export const invoiceStatusBadge = (status?: BillingInvoiceStatus | null) => {
  switch (status) {
    case "PAID":
      return "success";
    case "PARTIALLY_PAID":
      return "warning";
    case "VOID":
      return "neutral";
    case "ISSUED":
      return "accent";
    default:
      return "neutral";
  }
};

export const paymentStatusBadge = (status?: BillingPaymentStatus | null) => {
  switch (status) {
    case "CAPTURED":
      return "success";
    case "REFUNDED_PARTIAL":
      return "warning";
    case "REFUNDED_FULL":
      return "neutral";
    case "FAILED":
      return "error";
    default:
      return "neutral";
  }
};

export const refundStatusBadge = (status?: BillingRefundStatus | null) => {
  switch (status) {
    case "REFUNDED":
      return "success";
    case "FAILED":
      return "error";
    default:
      return "neutral";
  }
};

export const linkStatusBadge = (status?: ReconciliationLinkStatus | null) => {
  switch (status) {
    case "MATCHED":
      return "success";
    case "MISMATCHED":
      return "error";
    case "PENDING":
      return "warning";
    default:
      return "neutral";
  }
};

export const directionBadge = (direction?: ReconciliationLinkDirection | null) => {
  if (direction === "IN") return "success";
  if (direction === "OUT") return "warning";
  return "neutral";
};

export const entityTypeBadge = (type?: ReconciliationLinkEntityType | null) => {
  if (type === "invoice") return "accent";
  if (type === "payment") return "success";
  if (type === "refund") return "warning";
  return "neutral";
};

export const renderBadge = (label: string, tone: string) => (
  <span className={`neft-badge ${tone}`}>{label}</span>
);

export const toDateInputValue = (value?: string | null): string => {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toISOString().slice(0, 10);
};

export const toDateTimeInputValue = (value?: string | null): string => {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toISOString().slice(0, 16);
};
