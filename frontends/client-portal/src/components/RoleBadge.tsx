interface RoleBadgeProps {
  role?: string | null;
}

const normalizeRole = (role?: string | null) => (role ? role.toLowerCase() : "viewer");

export function RoleBadge({ role }: RoleBadgeProps) {
  const normalized = normalizeRole(role);
  const className = normalized === "admin" ? "badge badge-success" : normalized === "manager" ? "badge badge-info" : "badge badge-muted";
  return <span className={className}>{normalized}</span>;
}
