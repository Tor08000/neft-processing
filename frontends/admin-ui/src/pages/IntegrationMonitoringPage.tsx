import React, { useEffect, useMemo, useState } from "react";
import {
  fetchAzsHeatmap,
  fetchIntegrationRequests,
  fetchPartnerStatuses,
  fetchRecentDeclines,
} from "../api/integrationMonitoring";

const quickWindows = [5, 15, 60];

const badgeColor = (status: string) => {
  if (status === "ONLINE") return "#16a34a";
  if (status === "DEGRADED") return "#f59e0b";
  return "#ef4444";
};

const SectionCard: React.FC<{ title: string; children: React.ReactNode }>
 = ({ title, children }) => (
  <div style={{ background: "#fff", borderRadius: 12, padding: 16, boxShadow: "0 1px 3px rgba(0,0,0,0.08)" }}>
    <div style={{ fontWeight: 700, marginBottom: 12 }}>{title}</div>
    {children}
  </div>
);

const Table: React.FC<{ headers: string[]; children: React.ReactNode }> = ({ headers, children }) => (
  <table style={{ width: "100%", borderCollapse: "collapse" }}>
    <thead>
      <tr>
        {headers.map((h) => (
          <th key={h} style={{ textAlign: "left", padding: "8px 6px", color: "#475569", fontSize: 12 }}>
            {h}
          </th>
        ))}
      </tr>
    </thead>
    <tbody>{children}</tbody>
  </table>
);

const IntegrationMonitoringPage: React.FC = () => {
  const [windowMinutes, setWindowMinutes] = useState<number>(15);
  const [partnerFilter, setPartnerFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [reasonFilter, setReasonFilter] = useState<string>("");

  const [partnerStatuses, setPartnerStatuses] = useState<any[]>([]);
  const [azsHeatmap, setAzsHeatmap] = useState<any[]>([]);
  const [requests, setRequests] = useState<any[]>([]);
  const [declines, setDeclines] = useState<any[]>([]);
  const [lastSince, setLastSince] = useState<string | undefined>(undefined);

  useEffect(() => {
    fetchPartnerStatuses(windowMinutes).then((res) => setPartnerStatuses(res.items ?? res));
    fetchAzsHeatmap(windowMinutes, partnerFilter || undefined).then((res) => setAzsHeatmap(res.items ?? res));
  }, [windowMinutes, partnerFilter]);

  useEffect(() => {
    fetchIntegrationRequests({ partner_id: partnerFilter || undefined, status: statusFilter || undefined, limit: 20 }).then(
      (res) => setRequests(res.items ?? res)
    );
  }, [partnerFilter, statusFilter]);

  useEffect(() => {
    const sinceParam = lastSince ?? new Date(Date.now() - 5 * 60 * 1000).toISOString();
    fetchRecentDeclines({ partner_id: partnerFilter || undefined, reason_category: reasonFilter || undefined, since: sinceParam })
      .then((res) => {
        setDeclines(res.items ?? res);
        if (res.items && res.items[0]) {
          setLastSince(res.items[0].created_at);
        }
      })
      .catch(() => undefined);
    const interval = setInterval(() => {
      const since = lastSince ?? new Date(Date.now() - 5 * 60 * 1000).toISOString();
      fetchRecentDeclines({ partner_id: partnerFilter || undefined, reason_category: reasonFilter || undefined, since })
        .then((res) => setDeclines(res.items ?? res))
        .catch(() => undefined);
    }, 5000);
    return () => clearInterval(interval);
  }, [partnerFilter, reasonFilter, lastSince]);

  const declineTitle = useMemo(() => `Realtime Declines (${reasonFilter || "all"})`, [reasonFilter]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <span>Window:</span>
        {quickWindows.map((m) => (
          <button
            key={m}
            onClick={() => setWindowMinutes(m)}
            style={{ padding: "6px 10px", borderRadius: 8, border: windowMinutes === m ? "2px solid #0ea5e9" : "1px solid #cbd5e1" }}
          >
            {m}m
          </button>
        ))}
        <input
          placeholder="Partner"
          value={partnerFilter}
          onChange={(e) => setPartnerFilter(e.target.value)}
          style={{ padding: 8, borderRadius: 8, border: "1px solid #cbd5e1", minWidth: 160 }}
        />
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={{ padding: 8, borderRadius: 8 }}>
          <option value="">Status (any)</option>
          <option value="APPROVED">APPROVED</option>
          <option value="DECLINED">DECLINED</option>
          <option value="ERROR">ERROR</option>
        </select>
        <select value={reasonFilter} onChange={(e) => setReasonFilter(e.target.value)} style={{ padding: 8, borderRadius: 8 }}>
          <option value="">Reason (any)</option>
          <option value="RISK">RISK</option>
          <option value="LIMIT">LIMIT</option>
          <option value="TECHNICAL">TECHNICAL</option>
          <option value="PARTNER_ERROR">PARTNER_ERROR</option>
        </select>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <SectionCard title="Partner Status">
          <Table headers={["Partner", "Status", "Requests", "Error rate", "Avg latency"]}>
            {partnerStatuses.map((p) => (
              <tr key={p.partner_id} style={{ borderTop: "1px solid #e2e8f0" }}>
                <td style={{ padding: 8 }}>{p.partner_name}</td>
                <td style={{ padding: 8 }}>
                  <span
                    style={{
                      background: badgeColor(p.status),
                      color: "white",
                      padding: "4px 8px",
                      borderRadius: 12,
                      fontSize: 12,
                    }}
                  >
                    {p.status}
                  </span>
                </td>
                <td style={{ padding: 8 }}>{p.total_requests}</td>
                <td style={{ padding: 8 }}>{(p.error_rate * 100).toFixed(1)}%</td>
                <td style={{ padding: 8 }}>{Math.round(p.avg_latency_ms)} ms</td>
              </tr>
            ))}
          </Table>
        </SectionCard>

        <SectionCard title="AZS Heatmap">
          <Table headers={["AZS", "Requests", "Declines", "Error rate"]}>
            {azsHeatmap.map((h) => (
              <tr key={h.azs_id} style={{ borderTop: "1px solid #e2e8f0", background: "rgba(14,165,233,0.05)" }}>
                <td style={{ padding: 8 }}>{h.azs_id}</td>
                <td style={{ padding: 8 }}>{h.total_requests}</td>
                <td style={{ padding: 8 }}>{h.declines_total}</td>
                <td style={{ padding: 8 }}>{(h.error_rate * 100).toFixed(1)}%</td>
              </tr>
            ))}
          </Table>
        </SectionCard>

        <SectionCard title="Incoming Requests">
          <Table headers={["Time", "Partner", "AZS", "Type", "Amount", "Status", "Reason"]}>
            {requests.map((r) => (
              <tr key={r.id} style={{ borderTop: "1px solid #e2e8f0" }}>
                <td style={{ padding: 8 }}>{new Date(r.created_at).toLocaleTimeString()}</td>
                <td style={{ padding: 8 }}>{r.partner_id}</td>
                <td style={{ padding: 8 }}>{r.azs_id}</td>
                <td style={{ padding: 8 }}>{r.request_type}</td>
                <td style={{ padding: 8 }}>{r.amount}</td>
                <td style={{ padding: 8 }}>{r.status}</td>
                <td style={{ padding: 8 }}>{r.reason_category || "-"}</td>
              </tr>
            ))}
          </Table>
        </SectionCard>

        <SectionCard title={declineTitle}>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 320, overflow: "auto" }}>
            {declines.map((d) => (
              <div
                key={d.id}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  background: "#fff7ed",
                  border: "1px solid #fed7aa",
                  borderRadius: 8,
                  padding: "8px 10px",
                  fontSize: 13,
                }}
              >
                <span>{new Date(d.created_at).toLocaleTimeString()}</span>
                <span>{d.partner_id}</span>
                <span>{d.azs_id}</span>
                <span>{d.reason_category || d.risk_code || d.limit_code}</span>
                <span>{d.amount}</span>
              </div>
            ))}
          </div>
        </SectionCard>
      </div>
    </div>
  );
};

export default IntegrationMonitoringPage;
