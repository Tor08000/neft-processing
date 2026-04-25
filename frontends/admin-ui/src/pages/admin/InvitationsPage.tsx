import { useEffect, useState } from "react";
import {
  listAdminInvitations,
  resendInvitation,
  revokeInvitation,
  type AdminInvitationSummary,
} from "../../api/invitations";
import { EmptyState } from "../../components/common/EmptyState";
import { ErrorState } from "../../components/common/ErrorState";
import { invitationsCopy } from "./adminKeyPageCopy";

const EMPTY_VALUE = "-";

const statusBadge = (status: string) => {
  if (status === "PENDING") return <span className="badge pending">{invitationsCopy.status.pending}</span>;
  if (status === "ACCEPTED") return <span className="badge success">{invitationsCopy.status.accepted}</span>;
  if (status === "REVOKED") return <span className="badge error">{invitationsCopy.status.revoked}</span>;
  if (status === "EXPIRED") return <span className="badge warning">{invitationsCopy.status.expired}</span>;
  return <span className="badge neutral">{status}</span>;
};

export default function InvitationsPage() {
  const [clientId, setClientId] = useState("");
  const [status, setStatus] = useState("ALL");
  const [q, setQ] = useState("");
  const [sort, setSort] = useState("created_at_desc");
  const [items, setItems] = useState<AdminInvitationSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const hasFilters = Boolean(clientId.trim() || q.trim() || status !== "ALL");

  const load = async (overrides?: { clientId?: string; status?: string; q?: string; sort?: string }) => {
    const nextClientId = overrides?.clientId ?? clientId;
    const nextStatus = overrides?.status ?? status;
    const nextQuery = overrides?.q ?? q;
    const nextSort = overrides?.sort ?? sort;
    setLoading(true);
    setLoadError(null);
    setItems([]);
    setTotal(0);
    try {
      const response = await listAdminInvitations({
        client_id: nextClientId.trim() || undefined,
        status: nextStatus,
        q: nextQuery || undefined,
        sort: nextSort,
      });
      setItems(response.items ?? []);
      setTotal(response.total ?? 0);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "Failed to load invitations");
    } finally {
      setLoading(false);
    }
  };

  const resetFilters = () => {
    const next = { clientId: "", status: "ALL", q: "", sort };
    setClientId(next.clientId);
    setStatus(next.status);
    setQ(next.q);
    void load(next);
  };

  useEffect(() => {
    void load();
  }, []);

  return (
    <section className="card">
      <h2>Invitations</h2>
      <p className="muted">
        Canonical onboarding/admin invitation inbox. `client_id` is now an optional filter, not a required lookup key.
      </p>
      <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
        <input
          placeholder="client_id (optional)"
          value={clientId}
          onChange={(event) => setClientId(event.target.value)}
        />
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
        <button type="button" onClick={() => void load()}>
          {loading ? "Loading inbox..." : "Search"}
        </button>
        {hasFilters ? (
          <button type="button" onClick={resetFilters}>
            Reset filters
          </button>
        ) : null}
      </div>

      {loadError ? (
        <ErrorState
          title="Failed to load invitations"
          description={loadError}
          actionLabel="Retry"
          onAction={() => void load()}
        />
      ) : null}

      {!loadError && !loading && items.length === 0 ? (
        <EmptyState
          title={hasFilters ? "Invitations not found" : "No invitations yet"}
          description={
            hasFilters
              ? "Adjust or reset the filters to inspect a different invitation slice."
              : "The canonical admin onboarding inbox is currently empty."
          }
          primaryAction={{
            label: hasFilters ? "Reset filters" : "Refresh",
            onClick: () => {
              if (hasFilters) {
                resetFilters();
                return;
              }
              void load();
            },
          }}
        />
      ) : null}

      {!loadError && items.length > 0 ? (
        <>
          <div className="muted" style={{ marginBottom: 12 }}>
            Total: {total}
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Email</th>
                <th>Role</th>
                <th>Status</th>
                <th>Created</th>
                <th>Expires</th>
                <th>Sent count</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.invitation_id}>
                  <td>{item.email}</td>
                  <td>{item.role ?? EMPTY_VALUE}</td>
                  <td>{statusBadge(item.status)}</td>
                  <td>{new Date(item.created_at).toLocaleString()}</td>
                  <td>{new Date(item.expires_at).toLocaleString()}</td>
                  <td>{item.resent_count}</td>
                  <td>
                    <button
                      type="button"
                      disabled={item.status !== "PENDING"}
                      onClick={() =>
                        void resendInvitation(item.invitation_id).then(() => load())
                      }
                    >
                      Resend
                    </button>
                    <button
                      type="button"
                      disabled={item.status !== "PENDING"}
                      onClick={() =>
                        void revokeInvitation(item.invitation_id).then(() => load())
                      }
                    >
                      Revoke
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : null}
    </section>
  );
}
