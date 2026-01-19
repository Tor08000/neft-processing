import React from "react";
import { Link } from "react-router-dom";
import type { OpsExportsSummary } from "../../types/ops";
import { buildPlaceholderLink } from "./opsUtils";

const formatNumber = (value: number) => new Intl.NumberFormat("ru-RU").format(value);

type MetricRowProps = {
  label: string;
  value: string;
  to: string;
};

const MetricRow: React.FC<MetricRowProps> = ({ label, value, to }) => (
  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
    <span>{label}</span>
    <Link to={to} style={{ color: "var(--neft-primary)", fontWeight: 600 }}>
      {value}
    </Link>
  </div>
);

interface OpsExportsPanelProps {
  exports: OpsExportsSummary;
}

export const OpsExportsPanel: React.FC<OpsExportsPanelProps> = ({ exports }) => {
  const issueCount = exports.failed_24h;

  return (
    <section className="neft-card" style={{ padding: 16 }}>
      <h3 style={{ marginTop: 0 }}>Exports</h3>
      <div style={{ display: "grid", gap: 8 }}>
        <MetricRow label="Jobs (24h)" value={formatNumber(exports.jobs_24h)} to={buildPlaceholderLink("Exports jobs")} />
        <MetricRow
          label="Failed (24h)"
          value={formatNumber(exports.failed_24h)}
          to="/ops/exports/failed"
        />
        <MetricRow
          label="Avg duration (sec)"
          value={formatNumber(exports.avg_duration_sec)}
          to={buildPlaceholderLink("Exports duration")}
        />
      </div>
      {issueCount === 0 ? <div style={{ marginTop: 12, color: "#16a34a" }}>No issues detected</div> : null}
    </section>
  );
};

export default OpsExportsPanel;
