import React, { useCallback, useEffect, useMemo, useState } from "react";
import { request } from "../../api/http";
import { useAuth } from "../../auth/AuthContext";
import { DateRangePicker } from "../../components/common/DateRangePicker";
import { Toast } from "../../components/common/Toast";
import { useToast } from "../../components/Toast/useToast";

const formatDate = (date: Date) => date.toISOString().slice(0, 10);

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
                <td style={{ padding: "6px" }}>{value.sla_violations ?? "—"}</td>
                <td style={{ padding: "6px" }}>{value.avg_resolution_hours ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div style={{ color: "#94a3b8" }}>Нет данных</div>
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
        <div style={{ color: "#94a3b8" }}>Нет данных</div>
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

  const query = useMemo(() => {
    const params = new URLSearchParams();
    params.set("date_from", range.start);
    params.set("date_to", range.end);
    return params.toString();
  }, [range]);

  const loadKpi = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    try {
      const data = await request<OpsKpiResponse>(`/ops/kpi?${query}`, {}, accessToken);
      setPayload(data);
    } catch (err) {
      showToast("error", err instanceof Error ? err.message : "Не удалось загрузить KPI");
    } finally {
      setLoading(false);
    }
  }, [accessToken, query, showToast]);

  useEffect(() => {
    loadKpi();
  }, [loadKpi]);

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <Toast toast={toast} />
      <div>
        <h1 style={{ fontSize: 24, fontWeight: 700 }}>Ops KPI</h1>
        <p style={{ color: "#475569" }}>Сводка по SLA и причинам за период</p>
      </div>

      <div style={{ display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
        <DateRangePicker
          start={range.start}
          end={range.end}
          onChange={(next) => setRange(next)}
        />
        <button
          type="button"
          onClick={loadKpi}
          style={{ padding: "8px 14px", borderRadius: 8, border: "1px solid #cbd5e1" }}
        >
          Обновить
        </button>
      </div>

      {loading ? (
        <div>Loading...</div>
      ) : payload ? (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 16 }}>
            <ReasonTable data={payload.by_reason} />
            <TeamTable data={payload.by_team} />
          </div>
        </>
      ) : (
        <div style={{ color: "#94a3b8" }}>Нет данных</div>
      )}
    </div>
  );
};

export default KpiPage;
