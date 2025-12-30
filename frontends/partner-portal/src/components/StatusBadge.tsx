interface StatusBadgeProps {
  status: string | null | undefined;
  tone?: "success" | "pending" | "error" | "neutral";
}

const toneMap: Record<string, StatusBadgeProps["tone"]> = {
  active: "success",
  online: "success",
  settled: "success",
  sent: "pending",
  queued: "pending",
  draft: "pending",
  authorized: "success",
  declined: "error",
  inactive: "error",
  offline: "error",
  failed: "error",
};

export function StatusBadge({ status, tone }: StatusBadgeProps) {
  const normalized = status ?? "—";
  const resolvedTone = tone ?? toneMap[String(status).toLowerCase()] ?? "neutral";
  return <span className={`badge ${resolvedTone}`}>{normalized}</span>;
}
