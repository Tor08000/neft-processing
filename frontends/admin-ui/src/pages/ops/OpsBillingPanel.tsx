import React from "react";
import { Link } from "react-router-dom";
import type { OpsBillingSummary } from "../../types/ops";
import { formatAmount } from "../../utils/format";
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

interface OpsBillingPanelProps {
  billing: OpsBillingSummary;
}

export const OpsBillingPanel: React.FC<OpsBillingPanelProps> = ({ billing }) => {
  const issueCount = billing.overdue_orgs + (billing.overdue_amount > 0 ? 1 : 0) + billing.auto_suspends_24h;

  return (
    <section className="neft-card" style={{ padding: 16 }}>
      <h3 style={{ marginTop: 0 }}>Billing</h3>
      <div style={{ display: "grid", gap: 8 }}>
        <MetricRow
          label="Overdue orgs"
          value={formatNumber(billing.overdue_orgs)}
          to={buildPlaceholderLink("Overdue orgs")}
        />
        <MetricRow
          label="Overdue amount"
          value={formatAmount(billing.overdue_amount)}
          to={buildPlaceholderLink("Overdue amount")}
        />
        <MetricRow
          label="Dunning sent (24h)"
          value={formatNumber(billing.dunning_sent_24h)}
          to={buildPlaceholderLink("Dunning sent")}
        />
        <MetricRow
          label="Auto-suspends (24h)"
          value={formatNumber(billing.auto_suspends_24h)}
          to={buildPlaceholderLink("Auto suspends")}
        />
      </div>
      {issueCount === 0 ? <div style={{ marginTop: 12, color: "#16a34a" }}>No issues detected</div> : null}
    </section>
  );
};

export default OpsBillingPanel;
