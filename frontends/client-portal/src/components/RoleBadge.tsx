interface RoleBadgeProps {
  role?: string | null;
}

const normalizeRole = (role?: string | null) => (role ? role.toLowerCase() : "viewer");

export function RoleBadge({ role }: RoleBadgeProps) {
  const normalized = normalizeRole(role);
  const className =
    normalized === "admin"
      ? "neft-chip neft-chip-ok"
      : normalized === "manager"
        ? "neft-chip neft-chip-info"
        : "neft-chip neft-chip-muted";
  return <span className={className}>{normalized}</span>;
}
