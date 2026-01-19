import React from "react";

interface AdminEnvBadgeProps {
  envName: string;
}

const normalizeLabel = (name: string) => {
  const upper = name.toUpperCase();
  if (upper.includes("PROD")) return "PROD";
  if (upper.includes("STAGE")) return "STAGE";
  if (upper.includes("DEV")) return "DEV";
  return upper;
};

export const AdminEnvBadge: React.FC<AdminEnvBadgeProps> = ({ envName }) => {
  const label = normalizeLabel(envName);
  return (
    <span className={`admin-env-badge admin-env-badge--${label.toLowerCase()}`}>
      {label}
    </span>
  );
};

export default AdminEnvBadge;
