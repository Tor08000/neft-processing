import { useTranslation } from "react-i18next";

export type ProductStatus =
  | "DRAFT"
  | "PENDING_REVIEW"
  | "ACTIVE"
  | "SUSPENDED"
  | "ARCHIVED";

const LABEL_BY_STATUS: Record<ProductStatus, string> = {
  DRAFT: "Черновик",
  PENDING_REVIEW: "На модерации",
  ACTIVE: "Активно",
  SUSPENDED: "Приостановлено",
  ARCHIVED: "Архив",
};

const CLASS_BY_STATUS: Record<ProductStatus, string> = {
  DRAFT: "bg-gray-100 text-gray-700",
  PENDING_REVIEW: "bg-yellow-100 text-yellow-800",
  ACTIVE: "bg-green-100 text-green-800",
  SUSPENDED: "bg-orange-100 text-orange-800",
  ARCHIVED: "bg-slate-100 text-slate-700",
};

interface StatusBadgeProps {
  status: ProductStatus | string | null | undefined;
  tone?: "success" | "pending" | "error" | "neutral";
}

const toneMap: Record<string, StatusBadgeProps["tone"]> = {
  active: "success",
  online: "success",
  settled: "success",
  delivered: "success",
  paid: "success",
  completed: "success",
  confirmed: "success",
  confirmed_by_partner: "success",
  pending_payment: "pending",
  declined_by_partner: "error",
  canceled_by_client: "error",
  payment_failed: "error",
  closed: "success",
  accepted: "pending",
  approved: "success",
  calculated: "pending",
  signed: "success",
  ok: "success",
  sent: "pending",
  queued: "pending",
  draft: "pending",
  created: "pending",
  auth: "pending",
  in_progress: "pending",
  under_review: "pending",
  edo_pending: "pending",
  authorized: "success",
  declined: "error",
  cancelled: "error",
  refunded: "error",
  disputed: "error",
  denied: "error",
  failed: "error",
  inactive: "error",
  offline: "error",
  disabled: "error",
  paused: "pending",
  pending: "pending",
  pending_review: "pending",
  published: "success",
  suspended: "error",
  verified: "success",
  archived: "error",
  rejected: "error",
  dead: "error",
};

const statusLabelMap: Record<string, string> = {
  CREATED: "statuses.orders.CREATED",
  PENDING_PAYMENT: "statuses.orders.PENDING_PAYMENT",
  PAID: "statuses.orders.PAID",
  ACCEPTED: "statuses.orders.ACCEPTED",
  CONFIRMED: "statuses.orders.CONFIRMED",
  CONFIRMED_BY_PARTNER: "statuses.orders.CONFIRMED_BY_PARTNER",
  IN_PROGRESS: "statuses.orders.IN_PROGRESS",
  COMPLETED: "statuses.orders.COMPLETED",
  DECLINED_BY_PARTNER: "statuses.orders.DECLINED_BY_PARTNER",
  CANCELED_BY_CLIENT: "statuses.orders.CANCELED_BY_CLIENT",
  PAYMENT_FAILED: "statuses.orders.PAYMENT_FAILED",
  CLOSED: "statuses.orders.CLOSED",
  CANCELLED: "statuses.orders.CANCELLED",
  REFUNDED: "statuses.orders.REFUNDED",
  DRAFT: "statuses.documents.DRAFT",
  ISSUED: "statuses.documents.ISSUED",
  SIGNED: "statuses.documents.SIGNED",
  EDO_SENT: "statuses.documents.EDO_SENT",
  EDO_DELIVERED: "statuses.documents.EDO_DELIVERED",
  EDO_FAILED: "statuses.documents.EDO_FAILED",
  ACTIVE: "statuses.webhooks.ACTIVE",
  DISABLED: "statuses.webhooks.DISABLED",
  PAUSED: "statuses.webhooks.PAUSED",
  DELIVERED: "statuses.webhooks.DELIVERED",
  FAILED: "statuses.webhooks.FAILED",
  DEAD: "statuses.webhooks.DEAD",
  PENDING: "statuses.marketplace.PENDING",
  VERIFIED: "statuses.marketplace.VERIFIED",
  REJECTED: "statuses.marketplace.REJECTED",
};

const isProductStatus = (value: string): value is ProductStatus =>
  Object.prototype.hasOwnProperty.call(LABEL_BY_STATUS, value);

export function StatusBadge({ status, tone }: StatusBadgeProps) {
  const { t } = useTranslation();
  const normalized = status ?? t("common.notAvailable");
  const statusKey = status ? String(status).toUpperCase() : "";
  const isProduct = isProductStatus(statusKey);
  const label = isProduct
    ? LABEL_BY_STATUS[statusKey]
    : statusKey && statusLabelMap[statusKey]
      ? t(statusLabelMap[statusKey])
      : normalized;
  const resolvedTone = tone ?? toneMap[String(status).toLowerCase()] ?? "neutral";
  const className = isProduct ? CLASS_BY_STATUS[statusKey] : resolvedTone;
  return <span className={`badge ${className}`}>{label}</span>;
}
