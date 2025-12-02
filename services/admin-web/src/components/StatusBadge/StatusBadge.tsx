import React from "react";

const colorMap: Record<string, string> = {
  ok: "#16a34a",
  finalized: "#16a34a",
  confirmed: "#16a34a",
  capture: "#16a34a",
  pending: "#f59e0b",
  sent: "#f59e0b",
  auth: "#0ea5e9",
  failed: "#dc2626",
  error: "#dc2626",
  declined: "#dc2626",
};

export const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const normalized = status.toLowerCase();
  const background = colorMap[normalized] || "#475569";
  return (
    <span className="badge" style={{ background, color: "#fff" }}>
      {status}
    </span>
  );
};
