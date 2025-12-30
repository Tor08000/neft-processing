import { useCallback, useEffect, useMemo, useState } from "react";
import { request } from "../api/http";
import { useAuth } from "../auth/AuthContext";

type SupportRequestItem = {
  id: string;
  tenant_id: number;
  client_id: string | null;
  partner_id: string | null;
  scope_type: string;
  subject_type: string;
  subject_id: string | null;
  title: string;
  status: string;
  priority: string;
  created_at: string;
  updated_at: string;
};

type SupportRequestsResponse = {
  items: SupportRequestItem[];
  total: number;
  limit: number;
  offset: number;
};

const STATUS_OPTIONS = ["OPEN", "IN_PROGRESS", "WAITING", "RESOLVED", "CLOSED"];

const formatDate = (value: string) => new Date(value).toLocaleString();

const statusLabel = (status: string) => {
  switch (status) {
    case "OPEN":
      return "Открыто";
    case "IN_PROGRESS":
      return "В работе";
    case "WAITING":
      return "Ожидает данных";
    case "RESOLVED":
      return "Решено";
    case "CLOSED":
      return "Закрыто";
    default:
      return status;
  }
};

export default function SupportRequestsPage() {
  const { accessToken } = useAuth();
  const [items, setItems] = useState<SupportRequestItem[]>([]);
  const [status, setStatus] = useState("OPEN");
  const [clientId, setClientId] = useState("");
  const [partnerId, setPartnerId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const query = useMemo(() => {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (clientId.trim()) params.set("client_id", clientId.trim());
    if (partnerId.trim()) params.set("partner_id", partnerId.trim());
    return params.toString();
  }, [status, clientId, partnerId]);

  const loadRequests = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    try {
      const data = await request<SupportRequestsResponse>(`/api/v1/support/requests?${query}`, {}, accessToken);
      setItems(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить обращения");
    } finally {
      setLoading(false);
    }
  }, [accessToken, query]);

  useEffect(() => {
    loadRequests();
  }, [loadRequests]);

  const handleStatusChange = async (id: string, nextStatus: string) => {
    if (!accessToken) return;
    try {
      await request(`/api/v1/support/requests/${id}/status`, { method: "POST", body: JSON.stringify({ status: nextStatus }) }, accessToken);
      setItems((prev) => prev.map((item) => (item.id === id ? { ...item, status: nextStatus } : item)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось обновить статус");
    }
  };

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div>
        <h1 style={{ fontSize: 24, fontWeight: 700 }}>Support inbox</h1>
        <p style={{ color: "#475569" }}>Открытые и активные обращения клиентов и партнёров</p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12 }}>
        <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span>Статус</span>
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">Все</option>
            {STATUS_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {statusLabel(option)}
              </option>
            ))}
          </select>
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span>Client ID</span>
          <input value={clientId} onChange={(event) => setClientId(event.target.value)} placeholder="client-123" />
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span>Partner ID</span>
          <input value={partnerId} onChange={(event) => setPartnerId(event.target.value)} placeholder="partner-123" />
        </label>
      </div>

      {loading ? <div>Loading...</div> : null}
      {error ? <div style={{ color: "#b91c1c" }}>{error}</div> : null}

      {!loading && items.length === 0 ? <div>Нет обращений по выбранным фильтрам.</div> : null}

      {!loading && items.length > 0 ? (
        <table style={{ width: "100%", background: "#fff", borderRadius: 12, borderCollapse: "collapse" }}>
          <thead>
            <tr>
              <th style={{ textAlign: "left", padding: 12 }}>Дата</th>
              <th style={{ textAlign: "left", padding: 12 }}>Тема</th>
              <th style={{ textAlign: "left", padding: 12 }}>Объект</th>
              <th style={{ textAlign: "left", padding: 12 }}>Статус</th>
              <th style={{ textAlign: "left", padding: 12 }}>Обновлено</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} style={{ borderTop: "1px solid #e2e8f0" }}>
                <td style={{ padding: 12 }}>{formatDate(item.created_at)}</td>
                <td style={{ padding: 12 }}>{item.title}</td>
                <td style={{ padding: 12 }}>
                  {item.subject_type} {item.subject_id ? `#${item.subject_id}` : ""}
                </td>
                <td style={{ padding: 12 }}>
                  <select value={item.status} onChange={(event) => handleStatusChange(item.id, event.target.value)}>
                    {STATUS_OPTIONS.map((option) => (
                      <option key={option} value={option}>
                        {statusLabel(option)}
                      </option>
                    ))}
                  </select>
                </td>
                <td style={{ padding: 12 }}>{formatDate(item.updated_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </div>
  );
}
