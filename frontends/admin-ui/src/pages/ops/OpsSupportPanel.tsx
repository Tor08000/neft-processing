import React from "react";
import { Link } from "react-router-dom";
import type { OpsSupportSummary } from "../../types/ops";

const formatNumber = (value: number) => new Intl.NumberFormat("ru-RU").format(value);

type MetricRowProps = {
  label: string;
  value: number;
  to?: string;
};

const MetricRow: React.FC<MetricRowProps> = ({ label, value, to }) => (
  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
    <span>{label}</span>
    {to ? (
      <Link to={to} style={{ color: "var(--neft-primary)", fontWeight: 600 }}>
        {formatNumber(value)}
      </Link>
    ) : (
      <span style={{ fontWeight: 600 }}>{formatNumber(value)}</span>
    )}
  </div>
);

interface OpsSupportPanelProps {
  support: OpsSupportSummary;
}

export const OpsSupportPanel: React.FC<OpsSupportPanelProps> = ({ support }) => {
  return (
    <section className="neft-card" style={{ padding: 16 }}>
      <h3 style={{ marginTop: 0 }}>Support</h3>
      <div style={{ display: "grid", gap: 8 }}>
        <MetricRow label="Open tickets" value={support.open_tickets} to="/cases?queue=SUPPORT" />
        <MetricRow label="SLA breaches (24h)" value={support.sla_breaches_24h} to="/ops/support/breaches" />
      </div>
      {support.sla_breaches_24h === 0 ? (
        <div style={{ marginTop: 12, color: "#16a34a" }}>No issues detected</div>
      ) : null}
    </section>
  );
};

export default OpsSupportPanel;
