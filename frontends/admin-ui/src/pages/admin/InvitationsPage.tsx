import { useState } from "react";
import { listClientInvitations, resendInvitation, revokeInvitation, type AdminInvitationSummary } from "../../api/invitations";

const statusBadge = (status: string) => {
  if (status === "PENDING") return <span className="badge pending">Ожидает</span>;
  if (status === "ACCEPTED") return <span className="badge success">Принято</span>;
  if (status === "REVOKED") return <span className="badge error">Отозвано</span>;
  if (status === "EXPIRED") return <span className="badge warning">Истекло</span>;
  return <span className="badge neutral">{status}</span>;
};

export default function InvitationsPage() {
  const [clientId, setClientId] = useState("");
  const [status, setStatus] = useState("ALL");
  const [q, setQ] = useState("");
  const [sort, setSort] = useState("created_at_desc");
  const [items, setItems] = useState<AdminInvitationSummary[]>([]);

  const load = async () => {
    if (!clientId.trim()) return;
    const response = await listClientInvitations(clientId.trim(), { status, q: q || undefined, sort });
    setItems(response.items ?? []);
  };

  return (
    <section className="card">
      <h2>Invitations</h2>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <input placeholder="client_id" value={clientId} onChange={(event) => setClientId(event.target.value)} />
        <input placeholder="email" value={q} onChange={(event) => setQ(event.target.value)} />
        <select value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="ALL">All</option>
          <option value="PENDING">Pending</option>
          <option value="ACCEPTED">Accepted</option>
          <option value="REVOKED">Revoked</option>
          <option value="EXPIRED">Expired</option>
        </select>
        <select value={sort} onChange={(event) => setSort(event.target.value)}>
          <option value="created_at_desc">Created desc</option>
          <option value="created_at_asc">Created asc</option>
          <option value="expires_at_asc">Expires asc</option>
        </select>
        <button onClick={() => void load()}>Search</button>
      </div>
      <table className="table">
        <thead>
          <tr><th>Email</th><th>Role</th><th>Status</th><th>Created</th><th>Expires</th><th>Sent count</th><th>Actions</th></tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.invitation_id}>
              <td>{item.email}</td>
              <td>{item.role ?? "—"}</td>
              <td>{statusBadge(item.status)}</td>
              <td>{new Date(item.created_at).toLocaleString()}</td>
              <td>{new Date(item.expires_at).toLocaleString()}</td>
              <td>{item.resent_count}</td>
              <td>
                <button disabled={item.status !== "PENDING"} onClick={() => void resendInvitation(item.invitation_id).then(load)}>Resend</button>
                <button disabled={item.status !== "PENDING"} onClick={() => void revokeInvitation(item.invitation_id).then(load)}>Revoke</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
