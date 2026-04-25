import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../../api/http";
import { fetchOpsSummary } from "../../api/ops";
import { EmptyState } from "../../components/common/EmptyState";
import { ErrorState } from "../../components/common/ErrorState";
import { Loader } from "../../components/Loader/Loader";
import { AdminMisconfigPage } from "../admin/AdminStatusPages";
import type { OpsSummaryResponse } from "../../types/ops";
import { formatDateTime } from "../../utils/format";
import OpsBillingPanel from "./OpsBillingPanel";
import OpsExportsPanel from "./OpsExportsPanel";
import OpsMorPanel from "./OpsMorPanel";
import OpsQueuesPanel from "./OpsQueuesPanel";
import OpsReconciliationPanel from "./OpsReconciliationPanel";
import OpsSignalsPanel from "./OpsSignalsPanel";
import OpsSupportPanel from "./OpsSupportPanel";
import { extractRequestId } from "./opsUtils";

export const OpsOverviewPage: React.FC = () => {
  const [summary, setSummary] = useState<OpsSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const loadSummary = useCallback(() => {
    setLoading(true);
    setSummary(null);
    setError(null);
    fetchOpsSummary()
      .then((data) => {
        setSummary(data);
      })
      .catch((err: Error) => {
        setError(err);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  const requestId = error ? extractRequestId(error) : null;

  if (loading) {
    return <Loader label="Loading ops summary" />;
  }

  if (error instanceof ApiError && error.status === 404) {
    return <AdminMisconfigPage requestId={error.requestId ?? undefined} errorId={error.errorCode ?? undefined} />;
  }

  if (error) {
    return (
      <ErrorState
        title="Failed to load ops summary"
        description={error.message}
        requestId={requestId}
        actionLabel="Retry"
        onAction={() => void loadSummary()}
      />
    );
  }

  if (!summary) {
    return (
      <EmptyState
        title="Ops summary is not available"
        description="No operator summary payload was returned by the mounted owner route."
        primaryAction={{ label: "Retry", onClick: () => void loadSummary() }}
      />
    );
  }

  return (
    <div style={{ display: "grid", gap: 20 }}>
      <div>
        <h1 className="neft-h1">Ops overview</h1>
        <div className="neft-h1-subtitle">
          Env: {summary.env.name} | Build: {summary.env.build} | Updated: {formatDateTime(summary.time.now)}
        </div>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 8 }}>
          <Link to="/ops/escalations">Escalations</Link>
          <Link to="/ops/kpi">KPI</Link>
          <Link to="/logistics/inspection">Logistics inspection</Link>
        </div>
      </div>
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
