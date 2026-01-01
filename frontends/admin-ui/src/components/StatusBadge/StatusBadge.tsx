import React from "react";

const variantMap: Record<string, string> = {
  ok: "success",
  finalized: "success",
  confirmed: "success",
  capture: "success",
  pending: "warning",
  sent: "warning",
  auth: "warning",
  failed: "error",
  error: "error",
  declined: "error",
  draft: "neutral",
  unknown: "neutral",
};

export const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const normalized = status.toLowerCase();
  const variant = variantMap[normalized] || "neutral";
  return <span className={`neft-badge ${variant}`}>{status}</span>;
};
