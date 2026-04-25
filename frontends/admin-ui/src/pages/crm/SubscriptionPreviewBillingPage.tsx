import React, { useMemo, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { previewSubscriptionBilling } from "../../api/crm";
import { useAuth } from "../../auth/AuthContext";
import { DataTable, type DataColumn } from "../../components/common/DataTable";
import { EmptyState } from "../../components/common/EmptyState";
import { ErrorState } from "../../components/common/ErrorState";
import { JsonViewer } from "../../components/common/JsonViewer";
import { Loader } from "../../components/Loader/Loader";
import { Toast } from "../../components/common/Toast";
import { useToast } from "../../components/Toast/useToast";
import { describeError, formatError } from "../../utils/apiErrors";

const buildColumns = (rows: Record<string, unknown>[]): DataColumn<Record<string, unknown>>[] => {
  if (!rows.length) return [];
  return Object.keys(rows[0]).map((key) => ({ key, title: key }));
};

export const SubscriptionPreviewBillingPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const { accessToken } = useAuth();
  const { toast, showToast } = useToast();
  const [periodId, setPeriodId] = useState(searchParams.get("period_id") ?? "");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadErrorDetails, setLoadErrorDetails] = useState<string | undefined>(undefined);

  const segments = useMemo(
    () => (Array.isArray(result?.segments) ? (result.segments as Record<string, unknown>[]) : []),
    [result],
  );
  const usage = useMemo(
    () => (Array.isArray(result?.usage) ? (result.usage as Record<string, unknown>[]) : []),
    [result],
  );
  const charges = useMemo(
    () => (Array.isArray(result?.charges) ? (result.charges as Record<string, unknown>[]) : []),
    [result],
  );

  const handlePreview = async () => {
    if (!accessToken || !id) return;
    if (!periodId) {
      showToast("error", "Period ID is required");
      return;
    }
    setLoading(true);
    setLoadError(null);
    setLoadErrorDetails(undefined);
    setResult(null);
    try {
      const response = await previewSubscriptionBilling(accessToken, id, { period_id: periodId });
      setResult(response);
      showToast("success", "Preview ready");
    } catch (error: unknown) {
      const summary = describeError(error);
      setLoadError(summary.message);
      setLoadErrorDetails(summary.details);
      showToast("error", formatError(error));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <Toast toast={toast} />
      <h1>Preview billing</h1>
      <div style={{ display: "grid", gap: 12, marginBottom: 16 }}>
        <label>
          Period ID
          <input value={periodId} onChange={(event) => setPeriodId(event.target.value)} placeholder="2024-09" />
        </label>
        <button type="button" onClick={() => void handlePreview()} disabled={loading}>
          {loading ? "Loading preview..." : "Preview"}
        </button>
      </div>

      {!periodId && !loading && !result && !loadError ? (
        <EmptyState
          title="Period ID is required"
          description="Enter a billing period before previewing subscription charges."
        />
      ) : null}

      {loadError ? (
        <ErrorState
          title="Failed to preview billing"
          description={loadError}
          details={loadErrorDetails}
          actionLabel="Retry"
          onAction={() => void handlePreview()}
        />
      ) : null}

      {loading ? <Loader label="Loading billing preview" /> : null}

      {result ? (
        <div style={{ display: "grid", gap: 16 }}>
          <div>
            <h3>Segments</h3>
            <DataTable data={segments} columns={buildColumns(segments)} emptyMessage="No segments" />
          </div>
          <div>
            <h3>Usage</h3>
            <DataTable data={usage} columns={buildColumns(usage)} emptyMessage="No usage" />
          </div>
          <div>
            <h3>Charges</h3>
            <DataTable data={charges} columns={buildColumns(charges)} emptyMessage="No charges" />
          </div>
          <div>
            <h3>Total</h3>
            <JsonViewer value={result.total ?? result.totals ?? {}} />
          </div>
          <div>
            <h3>Explain</h3>
            <JsonViewer value={result.explain ?? result} />
          </div>
        </div>
      ) : null}
    </div>
  );
};

export default SubscriptionPreviewBillingPage;
