import React, { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, request } from "../../api/http";
import { useAuth } from "../../auth/AuthContext";
import { DateRangePicker } from "../../components/common/DateRangePicker";
import { EmptyState } from "../../components/common/EmptyState";
import { ErrorState } from "../../components/common/ErrorState";
import { Loader } from "../../components/Loader/Loader";
import { Toast } from "../../components/common/Toast";
import { useToast } from "../../components/Toast/useToast";

const formatDate = (date: Date) => date.toISOString().slice(0, 10);
const EMPTY_VALUE = "-";

type OpsKpiResponse = {
  by_reason: Record<
    string,
    {
      open: number;
      sla_violations?: number | null;
      avg_resolution_hours?: number | null;
    }
  >;
  by_team: Record<string, { open: number }>;
};

const ReasonTable: React.FC<{ data: OpsKpiResponse["by_reason"] }> = ({ data }) => {
  const rows = Object.entries(data);
  return (
    <div style={{ background: "#fff", borderRadius: 12, padding: 16 }}>
      <h3 style={{ marginTop: 0 }}>By primary reason</h3>
      {rows.length ? (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ textAlign: "left", borderBottom: "1px solid #e2e8f0" }}>
              <th style={{ padding: "8px 6px" }}>Primary reason</th>
              <th style={{ padding: "8px 6px" }}>Open</th>
              <th style={{ padding: "8px 6px" }}>SLA violations</th>
              <th style={{ padding: "8px 6px" }}>Avg resolution (hrs)</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([key, value]) => (
              <tr key={key}>
                <td style={{ padding: "6px" }}>{key}</td>
                <td style={{ padding: "6px" }}>{value.open}</td>
                <td style={{ padding: "6px" }}>{value.sla_violations ?? EMPTY_VALUE}</td>
                <td style={{ padding: "6px" }}>{value.avg_resolution_hours ?? EMPTY_VALUE}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div style={{ color: "#94a3b8" }}>No KPI data</div>
      )}
    </div>
  );
};

const TeamTable: React.FC<{ data: OpsKpiResponse["by_team"] }> = ({ data }) => {
  const rows = Object.entries(data);
  return (
    <div style={{ background: "#fff", borderRadius: 12, padding: 16 }}>
      <h3 style={{ marginTop: 0 }}>By team</h3>
      {rows.length ? (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ textAlign: "left", borderBottom: "1px solid #e2e8f0" }}>
              <th style={{ padding: "8px 6px" }}>Team</th>
              <th style={{ padding: "8px 6px" }}>Open</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([key, value]) => (
              <tr key={key}>
                <td style={{ padding: "6px" }}>{key}</td>
                <td style={{ padding: "6px" }}>{value.open}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div style={{ color: "#94a3b8" }}>No KPI data</div>
      )}
    </div>
  );
};

export const KpiPage: React.FC = () => {
  const { accessToken } = useAuth();
  const { toast, showToast } = useToast();
  const [range, setRange] = useState(() => {
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - 7);
    return { start: formatDate(start), end: formatDate(end) };
  });
  const [loading, setLoading] = useState(false);
  const [payload, setPayload] = useState<OpsKpiResponse | null>(null);
  const [loadError, setLoadError] = useState<Error | null>(null);

  const query = useMemo(() => {
    const params = new URLSearchParams();
    params.set("date_from", range.start);
    params.set("date_to", range.end);
    return params.toString();
  }, [range]);

  const loadKpi = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    setLoadError(null);
    setPayload(null);
    try {
      const data = await request<OpsKpiResponse>(`/ops/kpi?${query}`, {}, accessToken);
      setPayload(data);
    } catch (err) {
      const error = err instanceof Error ? err : new Error("Failed to load KPI");
      setLoadError(error);
      showToast("error", error.message);
    } finally {
      setLoading(false);
    }
  }, [accessToken, query, showToast]);

  useEffect(() => {
    loadKpi();
  }, [loadKpi]);

  const isEmptyPayload =
    payload !== null &&
    Object.keys(payload.by_reason ?? {}).length === 0 &&
    Object.keys(payload.by_team ?? {}).length === 0;

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <Toast toast={toast} />
      <div>
        <h1 style={{ fontSize: 24, fontWeight: 700 }}>Ops KPI</h1>
        <p style={{ color: "#475569" }}>SLA and primary-reason summary for the selected period.</p>
      </div>

      <div style={{ display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
        <DateRangePicker start={range.start} end={range.end} onChange={(next) => setRange(next)} />
        <button
          type="button"
          onClick={() => void loadKpi()}
          style={{ padding: "8px 14px", borderRadius: 8, border: "1px solid #cbd5e1" }}
        >
          Refresh
        </button>
      </div>

      {loading ? <Loader label="Loading KPI summary" /> : null}

      {!loading && loadError ? (
        <ErrorState
          title="Failed to load KPI summary"
          description={loadError.message}
          requestId={loadError instanceof ApiError ? loadError.requestId : null}
          correlationId={loadError instanceof ApiError ? loadError.correlationId : null}
          actionLabel="Retry"
          onAction={() => void loadKpi()}
        />
      ) : null}

      {!loading && !loadError && isEmptyPayload ? (
        <EmptyState
          title="No KPI data for the selected period"
          description="Adjust the date range or refresh after new operator activity is recorded."
          primaryAction={{ label: "Refresh", onClick: () => void loadKpi() }}
        />
      ) : null}

      {!loading && !loadError && payload && !isEmptyPayload ? (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 16 }}>
          <ReasonTable data={payload.by_reason} />
          <TeamTable data={payload.by_team} />
        </div>
      ) : null}
    </div>
  );
};

export default KpiPage;
