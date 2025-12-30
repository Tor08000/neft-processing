import { useI18n } from "../i18n";

interface StatusBadgeProps {
  status: string | null | undefined;
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
  approved: "success",
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
  dead: "error",
};

const statusLabelMap: Record<string, string> = {
  CREATED: "statuses.orders.CREATED",
  PAID: "statuses.orders.PAID",
  CONFIRMED: "statuses.orders.CONFIRMED",
  IN_PROGRESS: "statuses.orders.IN_PROGRESS",
  COMPLETED: "statuses.orders.COMPLETED",
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
};

export function StatusBadge({ status, tone }: StatusBadgeProps) {
  const { t } = useI18n();
  const normalized = status ?? t("common.notAvailable");
  const key = status ? statusLabelMap[String(status).toUpperCase()] : null;
  const label = key ? t(key) : normalized;
  const resolvedTone = tone ?? toneMap[String(status).toLowerCase()] ?? "neutral";
  return <span className={`badge ${resolvedTone}`}>{label}</span>;
}
