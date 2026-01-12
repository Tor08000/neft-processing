import React, { useEffect, useMemo, useState } from "react";
import {
  fetchAzsHeatmap,
  fetchIntegrationRequests,
  fetchPartnerStatuses,
  fetchRecentDeclines,
} from "../api/integrationMonitoring";

const quickWindows = [5, 15, 60];

const statusChipClass = (status: string) => {
  if (status === "ONLINE") return "neft-chip neft-chip-ok";
  if (status === "DEGRADED") return "neft-chip neft-chip-warn";
  return "neft-chip neft-chip-err";
};

const SectionCard: React.FC<{ title: string; children: React.ReactNode }>
 = ({ title, children }) => (
  <div className="neft-card" style={{ padding: 16 }}>
    <div style={{ fontWeight: 700, marginBottom: 12 }}>{title}</div>
    {children}
  </div>
);

const Table: React.FC<{ headers: string[]; children: React.ReactNode }> = ({ headers, children }) => (
  <table className="neft-table">
    <thead>
      <tr>
        {headers.map((h) => (
          <th key={h} style={{ textAlign: "left", padding: "8px 6px", color: "var(--neft-text-secondary)", fontSize: 12 }}>
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
    <div className="stack" style={{ gap: 16 }}>
      <div className="stack-inline" style={{ gap: 8, alignItems: "center" }}>
        <span>Window:</span>
        {quickWindows.map((m) => (
          <button
            key={m}
            onClick={() => setWindowMinutes(m)}
            className="neft-btn neft-btn-outline"
            style={{ borderWidth: windowMinutes === m ? 2 : 1 }}
          >
            {m}m
          </button>
        ))}
        <input
          placeholder="Partner"
          value={partnerFilter}
          onChange={(e) => setPartnerFilter(e.target.value)}
          className="neft-input"
          style={{ minWidth: 160 }}
        />
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="neft-input">
          <option value="">Status (any)</option>
          <option value="APPROVED">APPROVED</option>
          <option value="DECLINED">DECLINED</option>
          <option value="ERROR">ERROR</option>
        </select>
        <select value={reasonFilter} onChange={(e) => setReasonFilter(e.target.value)} className="neft-input">
          <option value="">Reason (any)</option>
          <option value="RISK">RISK</option>
          <option value="LIMIT">LIMIT</option>
          <option value="TECHNICAL">TECHNICAL</option>
          <option value="PARTNER_ERROR">PARTNER_ERROR</option>
        </select>
      </div>

      <div className="card-grid">
        <SectionCard title="Partner Status">
          <Table headers={["Partner", "Status", "Requests", "Error rate", "Avg latency"]}>
            {partnerStatuses.map((p) => (
              <tr key={p.partner_id} style={{ borderTop: "1px solid var(--neft-border)" }}>
                <td style={{ padding: 8 }}>{p.partner_name}</td>
                <td style={{ padding: 8 }}>
                  <span className={statusChipClass(p.status)}>{p.status}</span>
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
              <tr
                key={h.azs_id}
                style={{ borderTop: "1px solid var(--neft-border)", background: "var(--neft-table-hover)" }}
              >
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
              <tr key={r.id} style={{ borderTop: "1px solid var(--neft-border)" }}>
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
                  background: "color-mix(in srgb, var(--neft-warning) 12%, transparent)",
                  border: "1px solid color-mix(in srgb, var(--neft-warning) 35%, transparent)",
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
