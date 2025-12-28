import React, { useCallback, useEffect, useMemo, useState } from "react";
import { request } from "../../api/http";
import { useAuth } from "../../auth/AuthContext";
import { Toast } from "../../components/common/Toast";
import { useToast } from "../../components/Toast/useToast";

type OpsEscalation = {
  id: string;
  client_id: string | null;
  target: string;
  status: string;
  priority: string;
  primary_reason: string;
  subject_type: string;
  subject_id: string;
  sla_expires_at: string | null;
  created_at: string;
};

type EscalationResponse = {
  items: OpsEscalation[];
  total: number;
  limit: number;
  offset: number;
};

const TARGET_OPTIONS = ["CRM", "COMPLIANCE", "LOGISTICS", "FINANCE"] as const;
const STATUS_OPTIONS = ["OPEN", "ACK", "CLOSED"] as const;

const formatRemainingMinutes = (expiresAt?: string | null) => {
  if (!expiresAt) return "—";
  const expires = new Date(expiresAt);
  const diffMinutes = Math.round((expires.getTime() - Date.now()) / 60000);
  return diffMinutes <= 0 ? "expired" : `${diffMinutes} мин`;
};

const buildExplainLink = (type: string, id: string) => {
  switch (type) {
    case "FUEL_TX":
      return `/explain?fuel_tx_id=${id}`;
    case "ORDER":
      return `/explain?order_id=${id}`;
    case "INVOICE":
      return `/explain?invoice_id=${id}`;
    default:
      return "/explain";
  }
};

export const EscalationsPage: React.FC = () => {
  const { accessToken } = useAuth();
  const { toast, showToast } = useToast();
  const [items, setItems] = useState<OpsEscalation[]>([]);
  const [loading, setLoading] = useState(true);
  const [target, setTarget] = useState<string>("");
  const [status, setStatus] = useState<string>("");
  const [clientId, setClientId] = useState("");

  const query = useMemo(() => {
    const params = new URLSearchParams();
    if (target) params.set("target", target);
    if (status) params.set("status", status);
    if (clientId.trim()) params.set("client_id", clientId.trim());
    return params.toString();
  }, [target, status, clientId]);

  const loadEscalations = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    try {
      const data = await request<EscalationResponse>(`/api/v1/admin/ops/escalations?${query}`, {}, accessToken);
      setItems(data.items);
    } catch (err) {
      showToast("error", err instanceof Error ? err.message : "Не удалось загрузить escalations");
    } finally {
      setLoading(false);
    }
  }, [accessToken, query, showToast]);

  useEffect(() => {
    loadEscalations();
  }, [loadEscalations]);

  const handleAction = async (id: string, action: "ack" | "close") => {
    if (!accessToken) return;
    try {
      await request(`/api/v1/admin/ops/escalations/${id}/${action}`, { method: "POST" }, accessToken);
      showToast("success", action === "ack" ? "Escalation acked" : "Escalation closed");
      loadEscalations();
    } catch (err) {
      showToast("error", err instanceof Error ? err.message : "Ошибка обновления");
    }
  };

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <Toast toast={toast} />
      <div>
        <h1 style={{ fontSize: 24, fontWeight: 700 }}>Ops Escalations</h1>
        <p style={{ color: "#475569" }}>Inbox для SLA escalation задач</p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
        <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span>Target</span>
          <select value={target} onChange={(event) => setTarget(event.target.value)}>
            <option value="">All</option>
            {TARGET_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span>Status</span>
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">All</option>
            {STATUS_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span>Client ID</span>
          <input value={clientId} onChange={(event) => setClientId(event.target.value)} placeholder="client_id" />
        </label>
        <div style={{ display: "flex", alignItems: "flex-end" }}>
          <button
            type="button"
            onClick={loadEscalations}
            style={{ padding: "10px 16px", borderRadius: 8, border: "1px solid #cbd5e1" }}
          >
            Refresh
          </button>
        </div>
      </div>

      {loading ? (
        <div>Loading...</div>
      ) : (
        <div style={{ background: "#fff", borderRadius: 12, padding: 16 }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ textAlign: "left", borderBottom: "1px solid #e2e8f0" }}>
                <th style={{ padding: "8px 6px" }}>created_at</th>
                <th style={{ padding: "8px 6px" }}>target</th>
                <th style={{ padding: "8px 6px" }}>priority</th>
                <th style={{ padding: "8px 6px" }}>primary_reason</th>
                <th style={{ padding: "8px 6px" }}>subject</th>
                <th style={{ padding: "8px 6px" }}>status</th>
                <th style={{ padding: "8px 6px" }}>client_id</th>
                <th style={{ padding: "8px 6px" }}>SLA remaining</th>
                <th style={{ padding: "8px 6px" }}>actions</th>
              </tr>
            </thead>
            <tbody>
              {items.length ? (
                items.map((item) => (
                  <tr key={item.id} style={{ borderBottom: "1px solid #f1f5f9" }}>
                    <td style={{ padding: "8px 6px", fontSize: 12 }}>{new Date(item.created_at).toLocaleString()}</td>
                    <td style={{ padding: "8px 6px" }}>{item.target}</td>
                    <td style={{ padding: "8px 6px" }}>{item.priority}</td>
                    <td style={{ padding: "8px 6px" }}>{item.primary_reason}</td>
                    <td style={{ padding: "8px 6px" }}>
                      <div>{item.subject_type}</div>
                      <div style={{ fontSize: 12, color: "#64748b" }}>{item.subject_id}</div>
                    </td>
                    <td style={{ padding: "8px 6px" }}>{item.status}</td>
                    <td style={{ padding: "8px 6px" }}>{item.client_id ?? "—"}</td>
                    <td style={{ padding: "8px 6px" }}>{formatRemainingMinutes(item.sla_expires_at)}</td>
                    <td style={{ padding: "8px 6px" }}>
                      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                        <button
                          type="button"
                          onClick={() => handleAction(item.id, "ack")}
                          disabled={item.status === "CLOSED"}
                          style={{ padding: "6px 10px", borderRadius: 8, border: "1px solid #cbd5e1" }}
                        >
                          ACK
                        </button>
                        <button
                          type="button"
                          onClick={() => handleAction(item.id, "close")}
                          disabled={item.status === "CLOSED"}
                          style={{ padding: "6px 10px", borderRadius: 8, border: "1px solid #cbd5e1" }}
                        >
                          CLOSE
                        </button>
                        <a
                          href={buildExplainLink(item.subject_type, item.subject_id)}
                          style={{ color: "#2563eb", fontSize: 12, alignSelf: "center" }}
                        >
                          Open explain
                        </a>
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={9} style={{ padding: 12, textAlign: "center", color: "#94a3b8" }}>
                    No escalations found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default EscalationsPage;
