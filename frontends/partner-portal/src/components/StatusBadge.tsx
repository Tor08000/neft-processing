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
  dead: "error",
};

export function StatusBadge({ status, tone }: StatusBadgeProps) {
  const normalized = status ?? "—";
  const resolvedTone = tone ?? toneMap[String(status).toLowerCase()] ?? "neutral";
  return <span className={`badge ${resolvedTone}`}>{normalized}</span>;
}
