interface StatusBadgeProps {
  status?: string | null;
}

const normalizeStatus = (status?: string | null) => (status ? status.toUpperCase() : "UNKNOWN");

export function StatusBadge({ status }: StatusBadgeProps) {
  const normalized = normalizeStatus(status);
  const className =
    normalized === "ACTIVE"
      ? "neft-chip neft-chip-ok"
      : normalized === "BLOCKED"
        ? "neft-chip neft-chip-warn"
        : "neft-chip neft-chip-muted";
  return <span className={className}>{normalized}</span>;
}
