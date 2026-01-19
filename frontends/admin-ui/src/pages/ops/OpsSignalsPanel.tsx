import React from "react";
import type { OpsSignalsSummary } from "../../types/ops";

const STATUS_COLORS: Record<OpsSignalsSummary["status"], string> = {
  GREEN: "#16a34a",
  YELLOW: "#f59e0b",
  RED: "#dc2626",
};

interface OpsSignalsPanelProps {
  signals: OpsSignalsSummary;
}

export const OpsSignalsPanel: React.FC<OpsSignalsPanelProps> = ({ signals }) => {
  return (
    <section className="neft-card" style={{ padding: 20 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            padding: "6px 12px",
            borderRadius: 999,
            background: `${STATUS_COLORS[signals.status]}1A`,
            color: STATUS_COLORS[signals.status],
            fontWeight: 700,
          }}
        >
          {signals.status}
        </span>
        <span style={{ color: "#475569" }}>Ops signals</span>
      </div>
      {signals.reasons.length ? (
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          {signals.reasons.map((reason, idx) => (
            <li key={`${reason}-${idx}`}>{reason}</li>
          ))}
        </ul>
      ) : (
        <div>No issues detected</div>
      )}
    </section>
  );
};

export default OpsSignalsPanel;
