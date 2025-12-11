import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchAccountStatement, StatementResponse } from "../api/accounts";

export default function AccountDetailsPage() {
  const { accountId } = useParams<{ accountId: string }>();
  const [data, setData] = useState<StatementResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const load = async () => {
      if (!accountId) return;
      setLoading(true);
      setError(null);
      try {
        const resp = await fetchAccountStatement(Number(accountId));
        setData(resp);
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [accountId]);

  if (!accountId) {
    return <div>Account not found</div>;
  }

  return (
    <div>
      <Link to="/accounts" style={{ display: "inline-block", marginBottom: 12 }}>
        ← Back
      </Link>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 12 }}>Account #{accountId}</h1>
      {loading && <div>Loading...</div>}
      {error && <div style={{ color: "red" }}>{error}</div>}
      <table style={{ width: "100%", background: "#fff", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th style={{ textAlign: "left", padding: 8 }}>Date</th>
            <th style={{ textAlign: "left", padding: 8 }}>Operation</th>
            <th style={{ textAlign: "left", padding: 8 }}>Direction</th>
            <th style={{ textAlign: "left", padding: 8 }}>Amount</th>
            <th style={{ textAlign: "left", padding: 8 }}>Balance</th>
          </tr>
        </thead>
        <tbody>
          {data?.entries.map((entry) => (
            <tr key={entry.id} style={{ borderTop: "1px solid #e2e8f0" }}>
              <td style={{ padding: 8 }}>{new Date(entry.posted_at).toLocaleString()}</td>
              <td style={{ padding: 8 }}>{entry.operation_id ?? ""}</td>
              <td style={{ padding: 8 }}>{entry.direction}</td>
              <td style={{ padding: 8 }}>
                {entry.amount} {entry.currency}
              </td>
              <td style={{ padding: 8 }}>{entry.balance_after ?? ""}</td>
            </tr>
          ))}
          {!loading && (data?.entries.length ?? 0) === 0 && (
            <tr>
              <td colSpan={5} style={{ padding: 12, textAlign: "center" }}>
                No ledger entries yet
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
