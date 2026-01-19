import React, { useEffect, useState } from "react";
import { fetchOpsSummary } from "../../api/ops";
import type { OpsSummaryResponse } from "../../types/ops";
import OpsSignalsPanel from "./OpsSignalsPanel";
import OpsQueuesPanel from "./OpsQueuesPanel";
import OpsMorPanel from "./OpsMorPanel";
import OpsBillingPanel from "./OpsBillingPanel";
import OpsReconciliationPanel from "./OpsReconciliationPanel";
import OpsExportsPanel from "./OpsExportsPanel";
import OpsSupportPanel from "./OpsSupportPanel";
import { formatDateTime } from "../../utils/format";
import { extractRequestId } from "./opsUtils";

export const OpsOverviewPage: React.FC = () => {
  const [summary, setSummary] = useState<OpsSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    setLoading(true);
    fetchOpsSummary()
      .then((data) => {
        setSummary(data);
        setError(null);
      })
      .catch((err: Error) => {
        setError(err);
      })
      .finally(() => setLoading(false));
  }, []);

  const requestId = error ? extractRequestId(error) : null;

  if (loading) {
    return <div>Loading ops summary…</div>;
  }

  if (!summary) {
    return (
      <div>
        <h1>Ops overview</h1>
        <div style={{ color: "#dc2626" }}>Failed to load ops summary: {error?.message ?? "Unknown error"}</div>
        {requestId ? <div style={{ marginTop: 8 }}>Request ID: {requestId}</div> : null}
      </div>
    );
  }

  return (
    <div style={{ display: "grid", gap: 20 }}>
      <div>
        <h1 style={{ marginBottom: 4 }}>Ops overview</h1>
        <div style={{ color: "#475569" }}>
          Env: {summary.env.name} · Build: {summary.env.build} · Updated: {formatDateTime(summary.time.now)}
        </div>
      </div>
      {error ? (
        <div style={{ color: "#dc2626" }}>
          {error.message}
          {requestId ? <div style={{ marginTop: 4 }}>Request ID: {requestId}</div> : null}
        </div>
      ) : null}
      <OpsSignalsPanel signals={summary.signals} />
      <div style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))" }}>
        <OpsQueuesPanel queues={summary.queues} />
        <OpsMorPanel mor={summary.mor} />
        <OpsBillingPanel billing={summary.billing} />
        <OpsReconciliationPanel reconciliation={summary.reconciliation} />
      </div>
      <div style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))" }}>
        <OpsExportsPanel exports={summary.exports} />
        <OpsSupportPanel support={summary.support} />
      </div>
    </div>
  );
};

export default OpsOverviewPage;
