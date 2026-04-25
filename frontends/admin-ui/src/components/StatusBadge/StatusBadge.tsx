import React from "react";

const variantMap: Record<string, string> = {
  ok: "ok",
  up: "ok",
  healthy: "ok",
  finalized: "ok",
  confirmed: "ok",
  configured: "warn",
  capture: "ok",
  pending: "warn",
  degraded: "warn",
  disabled: "warn",
  unsupported: "warn",
  timeout: "warn",
  rate_limited: "warn",
  sent: "warn",
  auth: "warn",
  auth_failed: "err",
  failed: "err",
  error: "err",
  down: "err",
  declined: "err",
  draft: "muted",
  unknown: "muted",
};

export const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const normalized = status.toLowerCase();
  const variant = variantMap[normalized] || "muted";
  return <span className={`neft-chip neft-chip-${variant}`}>{status}</span>;
};
