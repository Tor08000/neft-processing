import React from "react";
import { Link } from "react-router-dom";
import type { OpsReconciliationSummary } from "../../types/ops";
import { buildPlaceholderLink } from "./opsUtils";

const formatNumber = (value: number) => new Intl.NumberFormat("ru-RU").format(value);

type MetricRowProps = {
  label: string;
  value: number;
  to: string;
};

const MetricRow: React.FC<MetricRowProps> = ({ label, value, to }) => (
  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
    <span>{label}</span>
    <Link to={to} style={{ color: "var(--neft-primary)", fontWeight: 600 }}>
      {formatNumber(value)}
    </Link>
  </div>
);

interface OpsReconciliationPanelProps {
  reconciliation: OpsReconciliationSummary;
}

export const OpsReconciliationPanel: React.FC<OpsReconciliationPanelProps> = ({ reconciliation }) => {
  const issueCount = reconciliation.parse_failed_24h + reconciliation.unmatched_24h;

  return (
    <section className="neft-card" style={{ padding: 16 }}>
      <h3 style={{ marginTop: 0 }}>Reconciliation</h3>
      <div style={{ display: "grid", gap: 8 }}>
        <MetricRow
          label="Imports (24h)"
          value={reconciliation.imports_24h}
          to={buildPlaceholderLink("Reconciliation imports")}
        />
        <MetricRow
          label="Parse failed (24h)"
          value={reconciliation.parse_failed_24h}
          to="/ops/reconciliation/failed"
        />
        <MetricRow
          label="Unmatched (24h)"
          value={reconciliation.unmatched_24h}
          to={buildPlaceholderLink("Reconciliation unmatched")}
        />
        <MetricRow
          label="Auto-approved (24h)"
          value={reconciliation.auto_approved_24h}
          to={buildPlaceholderLink("Reconciliation auto-approved")}
        />
      </div>
      {issueCount === 0 ? <div style={{ marginTop: 12, color: "#16a34a" }}>No issues detected</div> : null}
    </section>
  );
};

export default OpsReconciliationPanel;
