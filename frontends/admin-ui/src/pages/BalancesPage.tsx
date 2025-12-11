import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AccountBalance, fetchAccounts } from "../api/accounts";

export default function BalancesPage() {
  const [accounts, setAccounts] = useState<AccountBalance[]>([]);
  const [loading, setLoading] = useState(false);
  const [clientFilter, setClientFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAccounts({ client_id: clientFilter || undefined, status: statusFilter || undefined, limit: 100 });
      setAccounts(data.items);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 16 }}>Balances</h1>
      <div style={{ display: "flex", gap: 12, marginBottom: 16 }}>
        <input
          placeholder="Client ID"
          value={clientFilter}
          onChange={(e) => setClientFilter(e.target.value)}
          style={{ padding: 8, borderRadius: 8, border: "1px solid #cbd5e1" }}
        />
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={{ padding: 8, borderRadius: 8 }}>
          <option value="">Any status</option>
          <option value="ACTIVE">ACTIVE</option>
          <option value="FROZEN">FROZEN</option>
          <option value="CLOSED">CLOSED</option>
        </select>
        <button onClick={load} disabled={loading} style={{ padding: "8px 12px", borderRadius: 8 }}>
          {loading ? "Loading..." : "Apply"}
        </button>
      </div>
      {error && <div style={{ color: "red", marginBottom: 8 }}>{error}</div>}
      <table style={{ width: "100%", background: "#fff", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th style={{ textAlign: "left", padding: 8 }}>Account</th>
            <th style={{ textAlign: "left", padding: 8 }}>Client</th>
            <th style={{ textAlign: "left", padding: 8 }}>Card</th>
            <th style={{ textAlign: "left", padding: 8 }}>Balance</th>
            <th style={{ textAlign: "left", padding: 8 }}>Status</th>
          </tr>
        </thead>
        <tbody>
          {accounts.map((acc) => (
            <tr key={acc.id} style={{ borderTop: "1px solid #e2e8f0" }}>
              <td style={{ padding: 8 }}>
                <Link to={`/accounts/${acc.id}`}>#{acc.id}</Link>
              </td>
              <td style={{ padding: 8 }}>{acc.client_id}</td>
              <td style={{ padding: 8 }}>{acc.card_id ?? "—"}</td>
              <td style={{ padding: 8 }}>
                {acc.balance} {acc.currency}
              </td>
              <td style={{ padding: 8 }}>{acc.status}</td>
            </tr>
          ))}
          {!loading && accounts.length === 0 && (
            <tr>
              <td colSpan={5} style={{ padding: 12, textAlign: "center" }}>
                No accounts found
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
