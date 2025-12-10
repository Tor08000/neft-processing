import React from "react";

export interface RiskBadgeProps {
  level?: string | null;
  /**
   * Optional decision-level string (e.g. HARD_DECLINE / MANUAL_REVIEW) to display next to the severity.
   */
  decision?: string | null;
  score?: number | null;
  reasons?: string[] | null;
  source?: string | null;
}

type Palette = { bg: string; color: string; label: string };

const COLORS: Record<string, Palette> = {
  LOW: { bg: "#ecfdf3", color: "#15803d", label: "LOW" },
  MEDIUM: { bg: "#fffbeb", color: "#b45309", label: "MEDIUM" },
  HIGH: { bg: "#fff7ed", color: "#ea580c", label: "HIGH" },
  BLOCK: { bg: "#fef2f2", color: "#dc2626", label: "BLOCK" },
  HARD_DECLINE: { bg: "#fef2f2", color: "#dc2626", label: "DECLINE" },
  MANUAL_REVIEW: { bg: "#fff7ed", color: "#9a3412", label: "REVIEW" },
  APPROVED: { bg: "#ecfdf3", color: "#15803d", label: "APPROVED" },
  UNKNOWN: { bg: "#e2e8f0", color: "#0f172a", label: "UNKNOWN" },
};

function normalizeLevel(level?: string | null): string {
  return (level || "").toString().trim().toUpperCase();
}

function resolvePalette(level?: string | null): Palette {
  const normalized = normalizeLevel(level);
  if (COLORS[normalized]) {
    return COLORS[normalized];
  }
  // Map decision levels to severity colors
  if (["HARD_DECLINE", "BLOCK"].includes(normalized)) {
    return COLORS.BLOCK;
  }
  if (["MANUAL_REVIEW", "HIGH"].includes(normalized)) {
    return COLORS.HIGH;
  }
  if (normalized === "MEDIUM") {
    return COLORS.MEDIUM;
  }
  if (["LOW", "APPROVED"].includes(normalized)) {
    return COLORS.LOW;
  }
  return COLORS.UNKNOWN;
}

export const RiskBadge: React.FC<RiskBadgeProps> = ({ level, decision, score, reasons, source }) => {
  const palette = resolvePalette(level || decision);
  const label = palette.label || normalizeLevel(level) || "N/A";
  const decisionLabel = normalizeLevel(decision);

  const tooltipParts: string[] = [];
  if (reasons && reasons.length > 0) {
    tooltipParts.push(`Reasons: ${reasons.join(", ")}`);
  }
  if (source) {
    tooltipParts.push(`Source: ${source}`);
  }
  if (typeof score === "number") {
    tooltipParts.push(`Score: ${(score * 100).toFixed(1)}`);
  }

  return (
    <span
      className="badge"
      title={tooltipParts.join(" • ")}
      style={{
        background: palette.bg,
        color: palette.color,
        minWidth: 88,
        justifyContent: "center",
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
      }}
    >
      <span>{label}</span>
      {decisionLabel && decisionLabel !== label && <span style={{ opacity: 0.85 }}>· {decisionLabel}</span>}
      {typeof score === "number" && (
        <span style={{ padding: "0 4px", borderRadius: 4, background: "rgba(0,0,0,0.06)", opacity: 0.8 }}>
          {(score * 100).toFixed(0)}
        </span>
      )}
    </span>
  );
};

export default RiskBadge;
