import React from "react";

const COLORS: Record<string, { bg: string; color: string }> = {
  LOW: { bg: "#ecfdf3", color: "#15803d" },
  MEDIUM: { bg: "#fffbeb", color: "#b45309" },
  HIGH: { bg: "#fff7ed", color: "#ea580c" },
  BLOCK: { bg: "#fef2f2", color: "#dc2626" },
  UNKNOWN: { bg: "#e2e8f0", color: "#0f172a" },
};

export interface RiskBadgeProps {
  level?: string | null;
  score?: number | null;
}

export const RiskBadge: React.FC<RiskBadgeProps> = ({ level, score }) => {
  const normalized = (level || "").toUpperCase();
  const palette = COLORS[normalized] || COLORS.UNKNOWN;
  return (
    <span
      className="badge"
      style={{
        background: palette.bg,
        color: palette.color,
        minWidth: 64,
        justifyContent: "center",
      }}
    >
      {normalized || "N/A"}
      {typeof score === "number" && (
        <span style={{ marginLeft: 6, opacity: 0.8 }}>{(score * 100).toFixed(0)}</span>
      )}
    </span>
  );
};

export default RiskBadge;
