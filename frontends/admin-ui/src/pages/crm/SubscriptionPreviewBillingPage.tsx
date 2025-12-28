import React, { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { previewSubscriptionBilling } from "../../api/crm";
import { useAuth } from "../../auth/AuthContext";
import { DateRangePicker } from "../../components/common/DateRangePicker";
import { DataTable, type DataColumn } from "../../components/common/DataTable";
import { JsonViewer } from "../../components/common/JsonViewer";
import { Toast } from "../../components/common/Toast";
import { useToast } from "../../components/Toast/useToast";
import { formatError } from "../../utils/apiErrors";

const buildColumns = (rows: Record<string, unknown>[]): DataColumn<Record<string, unknown>>[] => {
  if (!rows.length) return [];
  return Object.keys(rows[0]).map((key) => ({ key, title: key }));
};

export const SubscriptionPreviewBillingPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { accessToken } = useAuth();
  const { toast, showToast } = useToast();
  const [periodId, setPeriodId] = useState("");
  const [range, setRange] = useState({ start: "", end: "" });
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  const segments = useMemo(() => (Array.isArray(result?.segments) ? (result?.segments as Record<string, unknown>[]) : []), [result]);
  const usage = useMemo(() => (Array.isArray(result?.usage) ? (result?.usage as Record<string, unknown>[]) : []), [result]);
  const charges = useMemo(() => (Array.isArray(result?.charges) ? (result?.charges as Record<string, unknown>[]) : []), [result]);

  const handlePreview = async () => {
    if (!accessToken || !id) return;
    setLoading(true);
    try {
      const response = await previewSubscriptionBilling(accessToken, id, {
        period_id: periodId || undefined,
        period_from: range.start || undefined,
        period_to: range.end || undefined,
      });
      setResult(response);
      showToast("success", "Preview ready");
    } catch (error: unknown) {
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
        <div>
          <div style={{ fontWeight: 600, marginBottom: 6 }}>Or date range</div>
          <DateRangePicker start={range.start} end={range.end} onChange={setRange} />
        </div>
        <button type="button" onClick={handlePreview} disabled={loading}>
          {loading ? "Loading..." : "Preview"}
        </button>
      </div>

      {result && (
        <div style={{ display: "grid", gap: 16 }}>
          <div>
            <h3>Segments</h3>
            <DataTable data={segments} columns={buildColumns(segments)} emptyMessage="Нет сегментов" />
          </div>
          <div>
            <h3>Usage</h3>
            <DataTable data={usage} columns={buildColumns(usage)} emptyMessage="Нет usage" />
          </div>
          <div>
            <h3>Charges</h3>
            <DataTable data={charges} columns={buildColumns(charges)} emptyMessage="Нет charges" />
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
      )}
    </div>
  );
};

export default SubscriptionPreviewBillingPage;
