import React from "react";
import { Link } from "react-router-dom";
import type { OpsQueuesSummary } from "../../types/ops";
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

interface OpsQueuesPanelProps {
  queues: OpsQueuesSummary;
}

export const OpsQueuesPanel: React.FC<OpsQueuesPanelProps> = ({ queues }) => {
  const issueCount =
    queues.exports.failed_1h +
    queues.payouts.blocked +
    queues.emails.failed_1h +
    queues.helpdesk_outbox.failed_1h;

  return (
    <section className="neft-card" style={{ padding: 16 }}>
      <h3 style={{ marginTop: 0 }}>Queues</h3>
      <div style={{ display: "grid", gap: 8 }}>
        <MetricRow label="Exports queued" value={queues.exports.queued} to={buildPlaceholderLink("Exports queued")} />
        <MetricRow label="Exports running" value={queues.exports.running} to={buildPlaceholderLink("Exports running")} />
        <MetricRow label="Exports failed (1h)" value={queues.exports.failed_1h} to="/ops/exports/failed" />
        <MetricRow label="Payouts queued" value={queues.payouts.queued} to={buildPlaceholderLink("Payouts queued")} />
        <MetricRow label="Payouts blocked" value={queues.payouts.blocked} to="/ops/payouts/blocked" />
        <MetricRow
          label="Settlements queued"
          value={queues.settlements.queued}
          to={buildPlaceholderLink("Settlements queued")}
        />
        <MetricRow
          label="Settlements finalizing"
          value={queues.settlements.finalizing}
          to={buildPlaceholderLink("Settlements finalizing")}
        />
        <MetricRow label="Emails queued" value={queues.emails.queued} to={buildPlaceholderLink("Emails queued")} />
        <MetricRow label="Emails failed (1h)" value={queues.emails.failed_1h} to={buildPlaceholderLink("Emails failed")} />
        <MetricRow
          label="Helpdesk outbox queued"
          value={queues.helpdesk_outbox.queued}
          to={buildPlaceholderLink("Helpdesk outbox queued")}
        />
        <MetricRow
          label="Helpdesk outbox failed (1h)"
          value={queues.helpdesk_outbox.failed_1h}
          to={buildPlaceholderLink("Helpdesk outbox failed")}
        />
      </div>
      {issueCount === 0 ? <div style={{ marginTop: 12, color: "#16a34a" }}>No issues detected</div> : null}
    </section>
  );
};

export default OpsQueuesPanel;
