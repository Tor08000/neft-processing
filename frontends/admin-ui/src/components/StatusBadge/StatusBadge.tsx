import React from "react";

const variantMap: Record<string, string> = {
  ok: "ok",
  finalized: "ok",
  confirmed: "ok",
  capture: "ok",
  pending: "warn",
  sent: "warn",
  auth: "warn",
  failed: "err",
  error: "err",
  declined: "err",
  draft: "muted",
  unknown: "muted",
};

export const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const normalized = status.toLowerCase();
  const variant = variantMap[normalized] || "muted";
  return <span className={`neft-chip neft-chip-${variant}`}>{status}</span>;
};
