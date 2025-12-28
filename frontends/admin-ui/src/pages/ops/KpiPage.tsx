import React, { useCallback, useEffect, useMemo, useState } from "react";
import { request } from "../../api/http";
import { useAuth } from "../../auth/AuthContext";
import { DateRangePicker } from "../../components/common/DateRangePicker";
import { SummaryCard } from "../../components/SummaryCard/SummaryCard";
import { Toast } from "../../components/common/Toast";
import { useToast } from "../../components/Toast/useToast";

const formatDate = (date: Date) => date.toISOString().slice(0, 10);

const toNumber = (value: number | null | undefined) => (value === null || value === undefined ? "—" : value);

type OpsKpiResponse = {
  totals: {
    opened: number;
    acked: number;
    closed: number;
    overdue: number;
  };
  sla: {
    closed_within_sla: number;
    avg_time_to_ack_minutes: number | null;
    avg_time_to_close_minutes: number | null;
  };
  breakdown: {
    by_primary_reason: Record<string, number>;
    by_target: Record<string, number>;
    by_close_reason_code: Record<string, number>;
    by_ack_reason_code: Record<string, number>;
  };
};

const BreakdownTable: React.FC<{ title: string; data: Record<string, number> }> = ({ title, data }) => {
  const rows = Object.entries(data);
  return (
    <div style={{ background: "#fff", borderRadius: 12, padding: 16 }}>
      <h3 style={{ marginTop: 0 }}>{title}</h3>
      {rows.length ? (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ textAlign: "left", borderBottom: "1px solid #e2e8f0" }}>
              <th style={{ padding: "8px 6px" }}>Reason</th>
              <th style={{ padding: "8px 6px" }}>Count</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([key, value]) => (
              <tr key={key}>
                <td style={{ padding: "6px" }}>{key}</td>
                <td style={{ padding: "6px" }}>{value}</td>
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
      const data = await request<OpsKpiResponse>(`/api/v1/admin/ops/kpi?${query}`, {}, accessToken);
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
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12 }}>
            <SummaryCard title="Opened" value={payload.totals.opened} description="Открыто за период" />
            <SummaryCard title="Acked" value={payload.totals.acked} description="Подтверждено" />
            <SummaryCard title="Closed" value={payload.totals.closed} description="Закрыто" />
            <SummaryCard title="Overdue" value={payload.totals.overdue} description="Просрочено" />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12 }}>
            <SummaryCard
              title="Closed within SLA"
              value={payload.sla.closed_within_sla}
              description="Закрыто в SLA"
            />
            <SummaryCard
              title="Avg time to ACK (мин)"
              value={toNumber(payload.sla.avg_time_to_ack_minutes)}
              description="Среднее время подтверждения"
            />
            <SummaryCard
              title="Avg time to close (мин)"
              value={toNumber(payload.sla.avg_time_to_close_minutes)}
              description="Среднее время закрытия"
            />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 16 }}>
            <BreakdownTable title="By primary reason" data={payload.breakdown.by_primary_reason} />
            <BreakdownTable title="By target" data={payload.breakdown.by_target} />
            <BreakdownTable title="By close reason code" data={payload.breakdown.by_close_reason_code} />
            <BreakdownTable title="By ack reason code" data={payload.breakdown.by_ack_reason_code} />
          </div>
        </>
      ) : (
        <div style={{ color: "#94a3b8" }}>Нет данных</div>
      )}
    </div>
  );
};

export default KpiPage;
