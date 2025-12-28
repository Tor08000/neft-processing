import React, { useCallback, useEffect, useMemo, useState } from "react";
import { request } from "../../api/http";
import { useAuth } from "../../auth/AuthContext";
import { Toast } from "../../components/common/Toast";
import { EscalationRow, OpsEscalationRow } from "../../components/ops/EscalationRow";
import { ReasonModal } from "../../components/ops/ReasonModal";
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
  sla_started_at: string | null;
  sla_due_at: string | null;
  sla_overdue: boolean;
  sla_elapsed_seconds: number | null;
  created_at: string;
  acked_at: string | null;
  acked_by: string | null;
  ack_reason: string | null;
  closed_at: string | null;
  closed_by: string | null;
  close_reason: string | null;
  unified_explain_snapshot_hash: string | null;
  unified_explain_snapshot: Record<string, unknown> | null;
};

type EscalationResponse = {
  items: OpsEscalation[];
  total: number;
  limit: number;
  offset: number;
};

const TARGET_OPTIONS = ["CRM", "COMPLIANCE", "LOGISTICS", "FINANCE"] as const;
const STATUS_OPTIONS = ["OPEN", "ACK", "CLOSED"] as const;
const PRIMARY_REASON_OPTIONS = ["LIMIT", "RISK", "LOGISTICS", "MONEY", "POLICY", "UNKNOWN"] as const;

const formatTimestamp = (value?: string | null) => {
  if (!value) return "—";
  return new Date(value).toLocaleString();
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
  const [primaryReason, setPrimaryReason] = useState<string>("");
  const [clientId, setClientId] = useState("");
  const [overdueOnly, setOverdueOnly] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [actionModal, setActionModal] = useState<{ id: string; action: "ack" | "close" } | null>(null);

  const query = useMemo(() => {
    const params = new URLSearchParams();
    if (target) params.set("target", target);
    if (status) params.set("status", status);
    if (primaryReason) params.set("primary_reason", primaryReason);
    if (overdueOnly) params.set("overdue", "true");
    if (clientId.trim()) params.set("client_id", clientId.trim());
    return params.toString();
  }, [target, status, primaryReason, overdueOnly, clientId]);

  const selectedEscalation = useMemo(
    () => items.find((item) => item.id === selectedId) ?? null,
    [items, selectedId],
  );

  const loadEscalations = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    try {
      const data = await request<EscalationResponse>(`/api/v1/admin/ops/escalations?${query}`, {}, accessToken);
      setItems(data.items);
      setSelectedId((prev) => {
        if (prev && data.items.some((item) => item.id === prev)) {
          return prev;
        }
        return data.items[0]?.id ?? null;
      });
    } catch (err) {
      showToast("error", err instanceof Error ? err.message : "Не удалось загрузить escalations");
    } finally {
      setLoading(false);
    }
  }, [accessToken, query, showToast]);

  useEffect(() => {
    loadEscalations();
  }, [loadEscalations]);

  const handleAction = async (id: string, action: "ack" | "close", reason: string) => {
    if (!accessToken) return;
    try {
      await request(
        `/api/v1/admin/ops/escalations/${id}/${action}`,
        { method: "POST", body: JSON.stringify({ reason }) },
        accessToken,
      );
      showToast("success", action === "ack" ? "Escalation acked" : "Escalation closed");
      loadEscalations();
    } catch (err) {
      showToast("error", err instanceof Error ? err.message : "Ошибка обновления");
    }
  };

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <Toast toast={toast} />
      <ReasonModal
        open={Boolean(actionModal)}
        title={actionModal?.action === "ack" ? "ACK escalation" : "Close escalation"}
        confirmLabel={actionModal?.action === "ack" ? "ACK" : "Close"}
        onCancel={() => setActionModal(null)}
        onConfirm={(reason) => {
          if (!actionModal) return;
          handleAction(actionModal.id, actionModal.action, reason);
          setActionModal(null);
        }}
      />
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
          <span>Primary reason</span>
          <select value={primaryReason} onChange={(event) => setPrimaryReason(event.target.value)}>
            <option value="">All</option>
            {PRIMARY_REASON_OPTIONS.map((option) => (
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
        <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <input type="checkbox" checked={overdueOnly} onChange={(event) => setOverdueOnly(event.target.checked)} />
          <span>Overdue only</span>
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
        <div style={{ display: "grid", gap: 16 }}>
          <div style={{ background: "#fff", borderRadius: 12, padding: 16 }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ textAlign: "left", borderBottom: "1px solid #e2e8f0" }}>
                  <th style={{ padding: "8px 6px" }}>created_at</th>
                  <th style={{ padding: "8px 6px" }}>target</th>
                  <th style={{ padding: "8px 6px" }}>primary_reason</th>
                  <th style={{ padding: "8px 6px" }}>SLA</th>
                  <th style={{ padding: "8px 6px" }}>status</th>
                  <th style={{ padding: "8px 6px" }}>subject</th>
                </tr>
              </thead>
              <tbody>
                {items.length ? (
                  items.map((item) => {
                    const rowItem: OpsEscalationRow = {
                      id: item.id,
                      target: item.target,
                      status: item.status,
                      priority: item.priority,
                      primary_reason: item.primary_reason,
                      subject_type: item.subject_type,
                      subject_id: item.subject_id,
                      sla_due_at: item.sla_due_at,
                      sla_overdue: item.sla_overdue,
                      created_at: item.created_at,
                    };
                    return (
                      <EscalationRow
                        key={item.id}
                        item={rowItem}
                        isSelected={item.id === selectedId}
                        onSelect={setSelectedId}
                      />
                    );
                  })
                ) : (
                  <tr>
                    <td colSpan={6} style={{ padding: 12, textAlign: "center", color: "#94a3b8" }}>
                      No escalations found
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          {selectedEscalation ? (
            <div style={{ background: "#fff", borderRadius: 12, padding: 16, display: "grid", gap: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
                <div>
                  <h3 style={{ margin: 0 }}>Escalation {selectedEscalation.id}</h3>
                  <div style={{ color: "#475569", fontSize: 12 }}>
                    Target: {selectedEscalation.target} · Status: {selectedEscalation.status}
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  <button
                    type="button"
                    onClick={() => setActionModal({ id: selectedEscalation.id, action: "ack" })}
                    disabled={selectedEscalation.status !== "OPEN"}
                    style={{ padding: "6px 10px", borderRadius: 8, border: "1px solid #cbd5e1" }}
                  >
                    ACK
                  </button>
                  <button
                    type="button"
                    onClick={() => setActionModal({ id: selectedEscalation.id, action: "close" })}
                    disabled={selectedEscalation.status === "CLOSED"}
                    style={{ padding: "6px 10px", borderRadius: 8, border: "1px solid #cbd5e1" }}
                  >
                    CLOSE
                  </button>
                  <a
                    href={buildExplainLink(selectedEscalation.subject_type, selectedEscalation.subject_id)}
                    style={{ color: "#2563eb", fontSize: 12, alignSelf: "center" }}
                  >
                    Open explain
                  </a>
                </div>
              </div>
              <div style={{ display: "grid", gap: 8 }}>
                <div>
                  <strong>Primary reason</strong>
                  <span
                    style={{
                      marginLeft: 8,
                      padding: "4px 8px",
                      borderRadius: 999,
                      background: "#fee2e2",
                      fontSize: 12,
                      fontWeight: 600,
                    }}
                  >
                    {selectedEscalation.primary_reason}
                  </span>
                </div>
                <div>
                  <strong>SLA due at</strong>: {formatTimestamp(selectedEscalation.sla_due_at)}
                </div>
                <div>
                  <strong>Client</strong>: {selectedEscalation.client_id ?? "—"}
                </div>
                <div>
                  <strong>Snapshot hash</strong>: {selectedEscalation.unified_explain_snapshot_hash ?? "—"}
                </div>
              </div>
              <div>
                <h4 style={{ marginBottom: 8 }}>Unified Explain snapshot</h4>
                <pre
                  style={{
                    background: "#f8fafc",
                    padding: 12,
                    borderRadius: 8,
                    maxHeight: 260,
                    overflow: "auto",
                  }}
                >
                  {selectedEscalation.unified_explain_snapshot
                    ? JSON.stringify(selectedEscalation.unified_explain_snapshot, null, 2)
                    : "—"}
                </pre>
              </div>
              <div>
                <h4 style={{ marginBottom: 8 }}>History</h4>
                <ul style={{ margin: 0, paddingLeft: 18 }}>
                  <li>Created: {formatTimestamp(selectedEscalation.created_at)}</li>
                  {selectedEscalation.acked_at && (
                    <li>
                      ACK: {formatTimestamp(selectedEscalation.acked_at)} · {selectedEscalation.acked_by ?? "—"} ·{" "}
                      {selectedEscalation.ack_reason ?? "—"}
                    </li>
                  )}
                  {selectedEscalation.closed_at && (
                    <li>
                      Closed: {formatTimestamp(selectedEscalation.closed_at)} · {selectedEscalation.closed_by ?? "—"} ·{" "}
                      {selectedEscalation.close_reason ?? "—"}
                    </li>
                  )}
                </ul>
              </div>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
};

export default EscalationsPage;
