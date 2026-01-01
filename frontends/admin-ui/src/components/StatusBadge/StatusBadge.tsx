import React from "react";

const variantMap: Record<string, string> = {
  ok: "success",
  finalized: "success",
  confirmed: "success",
  capture: "success",
  pending: "warning",
  sent: "warning",
  auth: "info",
  failed: "danger",
  error: "danger",
  declined: "danger",
};

export const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const normalized = status.toLowerCase();
  const variant = variantMap[normalized] || "info";
  return (
    <span className={`neft-badge ${variant}`}>
      {status}
    </span>
  );
};
