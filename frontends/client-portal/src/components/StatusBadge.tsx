interface StatusBadgeProps {
  status?: string | null;
}

const normalizeStatus = (status?: string | null) => (status ? status.toUpperCase() : "UNKNOWN");

export function StatusBadge({ status }: StatusBadgeProps) {
  const normalized = normalizeStatus(status);
  const className = normalized === "ACTIVE" ? "badge badge-success" : normalized === "BLOCKED" ? "badge badge-warning" : "badge badge-muted";
  return <span className={className}>{normalized}</span>;
}
