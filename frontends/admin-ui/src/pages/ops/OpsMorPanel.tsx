import React from "react";
import { Link } from "react-router-dom";
import type { OpsMorSummary } from "../../types/ops";

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

interface OpsMorPanelProps {
  mor: OpsMorSummary;
}

export const OpsMorPanel: React.FC<OpsMorPanelProps> = ({ mor }) => {
  const issueCount =
    mor.immutable_violations_24h + mor.payout_blocked_total_24h + mor.clawback_required_24h + mor.admin_overrides_24h;

  return (
    <section className="neft-card" style={{ padding: 16 }}>
      <h3 style={{ marginTop: 0 }}>MoR invariants</h3>
      <div style={{ display: "grid", gap: 8 }}>
        <MetricRow
          label="Immutable violations (24h)"
          value={mor.immutable_violations_24h}
          to="/runtime"
        />
        <MetricRow
          label="Payouts blocked (24h)"
          value={mor.payout_blocked_total_24h}
          to="/ops/payouts/blocked"
        />
        <MetricRow
          label="Clawback required (24h)"
          value={mor.clawback_required_24h}
          to="/finance"
        />
        <MetricRow
          label="Admin overrides (24h)"
          value={mor.admin_overrides_24h}
          to="/commercial"
        />
      </div>
      <div style={{ marginTop: 12 }}>
        <div style={{ fontWeight: 600, marginBottom: 6 }}>Top blocked reasons</div>
        {mor.payout_blocked_top_reasons.length ? (
          <ul style={{ margin: 0, paddingLeft: 16 }}>
            {mor.payout_blocked_top_reasons.map((item) => (
              <li key={item.reason}>
                {item.reason}: {formatNumber(item.count)}
              </li>
            ))}
          </ul>
        ) : (
          <div>No issues detected</div>
        )}
      </div>
      {issueCount === 0 ? <div style={{ marginTop: 12, color: "#16a34a" }}>No issues detected</div> : null}
    </section>
  );
};

export default OpsMorPanel;
