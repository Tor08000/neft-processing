import React, { useCallback, useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { subscriptionCfoExplain } from "../../api/crm";
import { useAuth } from "../../auth/AuthContext";
import { DataTable, type DataColumn } from "../../components/common/DataTable";
import { EmptyState } from "../../components/common/EmptyState";
import { ErrorState } from "../../components/common/ErrorState";
import { JsonViewer } from "../../components/common/JsonViewer";
import { Loader } from "../../components/Loader/Loader";
import { Toast } from "../../components/common/Toast";
import { useToast } from "../../components/Toast/useToast";
import type { MoneyExplainResponse } from "../../types/money";
import { describeError, formatError } from "../../utils/apiErrors";

export const SubscriptionCfoExplainPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const { accessToken } = useAuth();
  const { toast, showToast } = useToast();
  const [data, setData] = useState<MoneyExplainResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadErrorDetails, setLoadErrorDetails] = useState<string | undefined>(undefined);
  const periodId = searchParams.get("period_id") ?? undefined;

  const loadExplain = useCallback(() => {
    if (!accessToken || !id) {
      setLoading(false);
      return;
    }
    if (!periodId) {
      setData(null);
      setLoadError(null);
      setLoadErrorDetails(undefined);
      setLoading(false);
      return;
    }
    setLoading(true);
    setLoadError(null);
    setLoadErrorDetails(undefined);
    setData(null);
    subscriptionCfoExplain(accessToken, id, { period_id: periodId })
      .then((response) => setData(response as MoneyExplainResponse))
      .catch((error: unknown) => {
        const summary = describeError(error);
        setLoadError(summary.message);
        setLoadErrorDetails(summary.details);
        showToast("error", formatError(error));
      })
      .finally(() => setLoading(false));
  }, [accessToken, id, periodId, showToast]);

  useEffect(() => {
    loadExplain();
  }, [loadExplain]);

  const links = Array.isArray(data?.money_flow_links) ? (data.money_flow_links as Record<string, unknown>[]) : [];
  const segments = Array.isArray(data?.segments) ? (data.segments as Record<string, unknown>[]) : [];
  const charges = Array.isArray(data?.charges) ? (data.charges as Record<string, unknown>[]) : [];

  const buildColumns = (rows: Record<string, unknown>[]): DataColumn<Record<string, unknown>>[] => {
    if (!rows.length) return [];
    return Object.keys(rows[0]).map((key) => ({ key, title: key }));
  };

  if (loading) {
    return <Loader label="Loading subscription CFO explain" />;
  }

  if (!id) {
    return (
      <EmptyState
        title="Subscription ID is required"
        description="Open CFO explain from a subscription detail page."
      />
    );
  }

  if (!periodId) {
    return (
      <EmptyState
        title="Period ID is required"
        description="Select a billing period before opening the CFO explain view."
      />
    );
  }

  if (loadError) {
    return (
      <ErrorState
        title="Failed to load CFO explain"
        description={loadError}
        details={loadErrorDetails}
        actionLabel="Retry"
        onAction={() => void loadExplain()}
      />
    );
  }

  if (!data) {
    return (
      <EmptyState
        title="CFO explain is not available"
        description="No explain payload was returned for the selected subscription period."
      />
    );
  }

  return (
    <div>
      <Toast toast={toast} />
      <h1>Subscription CFO explain</h1>
      <div style={{ display: "grid", gap: 16 }}>
        <div>
          <h3>Totals</h3>
          <JsonViewer value={data.totals ?? {}} />
        </div>
        <div>
          <h3>Segments</h3>
          <DataTable data={segments} columns={buildColumns(segments)} emptyMessage="No segments" />
        </div>
        <div>
          <h3>Charges</h3>
          <DataTable data={charges} columns={buildColumns(charges)} emptyMessage="No charges" />
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
          <DataTable data={links} columns={buildColumns(links)} emptyMessage="No links" />
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
    </div>
  );
};

export default SubscriptionCfoExplainPage;
