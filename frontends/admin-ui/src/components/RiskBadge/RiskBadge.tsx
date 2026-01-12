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

type Palette = { label: string; variant: string };

const COLORS: Record<string, Palette> = {
  LOW: { label: "LOW", variant: "ok" },
  MEDIUM: { label: "MEDIUM", variant: "warn" },
  HIGH: { label: "HIGH", variant: "warn" },
  BLOCK: { label: "BLOCK", variant: "err" },
  HARD_DECLINE: { label: "DECLINE", variant: "err" },
  MANUAL_REVIEW: { label: "REVIEW", variant: "warn" },
  APPROVED: { label: "APPROVED", variant: "ok" },
  UNKNOWN: { label: "UNKNOWN", variant: "muted" },
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
      className={`neft-chip neft-chip-${palette.variant}`}
      title={tooltipParts.join(" • ")}
      style={{ minWidth: 88, justifyContent: "center" }}
    >
      <span>{label}</span>
      {decisionLabel && decisionLabel !== label && <span style={{ opacity: 0.85 }}>· {decisionLabel}</span>}
      {typeof score === "number" && (
        <span
          style={{
            padding: "0 4px",
            borderRadius: 4,
            background: "color-mix(in srgb, var(--neft-border) 35%, transparent)",
            opacity: 0.8,
          }}
        >
          {(score * 100).toFixed(0)}
        </span>
      )}
    </span>
  );
};

export default RiskBadge;
