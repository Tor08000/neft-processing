import React, { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { subscriptionCfoExplain } from "../../api/crm";
import { useAuth } from "../../auth/AuthContext";
import { DataTable, type DataColumn } from "../../components/common/DataTable";
import { JsonViewer } from "../../components/common/JsonViewer";
import { Toast } from "../../components/common/Toast";
import { useToast } from "../../components/Toast/useToast";
import type { MoneyExplainResponse } from "../../types/money";
import { formatError } from "../../utils/apiErrors";

export const SubscriptionCfoExplainPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const { accessToken } = useAuth();
  const { toast, showToast } = useToast();
  const [data, setData] = useState<MoneyExplainResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!accessToken || !id) return;
    const periodId = searchParams.get("period_id") ?? undefined;
    setLoading(true);
    subscriptionCfoExplain(accessToken, id, { period_id: periodId ?? undefined })
      .then((response) => setData(response as MoneyExplainResponse))
      .catch((error: unknown) => showToast("error", formatError(error)))
      .finally(() => setLoading(false));
  }, [accessToken, id, searchParams, showToast]);

  const links = Array.isArray(data?.money_flow_links) ? (data?.money_flow_links as Record<string, unknown>[]) : [];
  const segments = Array.isArray(data?.segments) ? (data?.segments as Record<string, unknown>[]) : [];
  const charges = Array.isArray(data?.charges) ? (data?.charges as Record<string, unknown>[]) : [];

  const buildColumns = (rows: Record<string, unknown>[]): DataColumn<Record<string, unknown>>[] => {
    if (!rows.length) return [];
    return Object.keys(rows[0]).map((key) => ({ key, title: key }));
  };

  if (loading) {
    return <div>Loading...</div>;
  }

  return (
    <div>
      <Toast toast={toast} />
      <h1>Subscription CFO explain</h1>
      {!data && <div>No data</div>}
      {data && (
        <div style={{ display: "grid", gap: 16 }}>
          <div>
            <h3>Totals</h3>
            <JsonViewer value={data.totals ?? {}} />
          </div>
          <div>
            <h3>Segments</h3>
            <DataTable data={segments} columns={buildColumns(segments)} emptyMessage="Нет сегментов" />
          </div>
          <div>
            <h3>Charges</h3>
            <DataTable data={charges} columns={buildColumns(charges)} emptyMessage="Нет charges" />
          </div>
          <div>
            <h3>Invoice IDs</h3>
            <div>{(data.invoice_ids ?? []).join(", ") || "-"}</div>
          </div>
          <div>
            <h3>Ledger summary</h3>
            <JsonViewer value={data.ledger_summary ?? {}} />
          </div>
          <div>
            <h3>Money flow links</h3>
            <DataTable data={links} columns={buildColumns(links)} emptyMessage="Нет links" />
          </div>
          <div>
            <h3>Snapshots</h3>
            <JsonViewer value={data.snapshots ?? {}} />
          </div>
          <div>
            <h3>Replay status</h3>
            <JsonViewer value={data.replay_status ?? {}} />
          </div>
          <details>
            <summary>Raw JSON</summary>
            <JsonViewer value={data} />
          </details>
        </div>
      )}
    </div>
  );
};

export default SubscriptionCfoExplainPage;
