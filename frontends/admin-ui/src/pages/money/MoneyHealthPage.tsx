import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { moneyHealth } from "../../api/moneyFlow";
import { useAuth } from "../../auth/AuthContext";
import { DataTable, type DataColumn } from "../../components/common/DataTable";
import { JsonViewer } from "../../components/common/JsonViewer";
import { Toast } from "../../components/common/Toast";
import { useToast } from "../../components/Toast/useToast";
import type { MoneyHealthOffender, MoneyHealthResponse } from "../../types/money";
import { formatError } from "../../utils/apiErrors";

export const MoneyHealthPage: React.FC = () => {
  const navigate = useNavigate();
  const { accessToken } = useAuth();
  const { toast, showToast } = useToast();
  const [data, setData] = useState<MoneyHealthResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!accessToken) return;
    setLoading(true);
    moneyHealth(accessToken)
      .then((response) => setData(response))
      .catch((error: unknown) => showToast("error", formatError(error)))
      .finally(() => setLoading(false));
  }, [accessToken, showToast]);

  const offenders = (data?.top_offenders ?? []) as MoneyHealthOffender[];
  const columns: DataColumn<MoneyHealthOffender>[] = [
    { key: "id", title: "ID" },
    { key: "flow_type", title: "Flow type" },
    { key: "flow_ref_id", title: "Ref ID" },
    { key: "issue", title: "Issue" },
    { key: "details", title: "Details" },
  ];

  if (loading) {
    return <div>Loading...</div>;
  }

  return (
    <div>
      <Toast toast={toast} />
      <h1>Money Health</h1>
      {data && (
        <div style={{ display: "grid", gap: 12, marginBottom: 16 }}>
          <div>Orphan links: {data.orphan_ledger_transactions ?? 0}</div>
          <div>Missing snapshots: {data.missing_snapshots ?? data.missing_ledger_postings ?? 0}</div>
          <div>Broken chains: {data.broken_chains ?? data.invariant_violations ?? 0}</div>
          <div>Stuck authorized: {data.stuck_authorized ?? 0}</div>
          <div>Stuck pending settlement: {data.stuck_pending_settlement ?? 0}</div>
          <button type="button" onClick={() => navigate("/money/replay")}>Run replay (dry-run)</button>
        </div>
      )}
      <h3>Top offenders</h3>
      <DataTable data={offenders} columns={columns} emptyMessage="No offenders" />
      {data && (
        <details style={{ marginTop: 16 }}>
          <summary>Raw JSON</summary>
          <JsonViewer value={data} />
        </details>
      )}
    </div>
  );
};

export default MoneyHealthPage;
