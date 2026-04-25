import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchPartnerContracts } from "../../api/partnerFinance";
import { useAuth } from "../../auth/AuthContext";
import { EmptyState } from "../../components/EmptyState";
import { PartnerErrorState } from "../../components/PartnerErrorState";
import { StatusBadge } from "../../components/StatusBadge";
import { LoadingState } from "../../components/states";
import type { PartnerContract } from "../../types/partnerFinance";
import { formatDate } from "../../utils/format";

export function ContractsPage() {
  const { user } = useAuth();
  const [contracts, setContracts] = useState<PartnerContract[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const reload = () => setReloadKey((value) => value + 1);

  useEffect(() => {
    let active = true;
    if (!user) return;
    setLoading(true);
    setError(null);
    fetchPartnerContracts(user.token, { limit: 50, offset: 0 })
      .then((response) => {
        if (!active) return;
        setContracts(response.items ?? []);
        setTotal(response.total ?? 0);
      })
      .catch((err) => {
        if (!active) return;
        setError(err);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [user, reloadKey]);

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <div>
            <h2>Contracts</h2>
            <p className="muted">Read-only partner contract register from the marketplace contract owner.</p>
          </div>
          <div className="toolbar-actions">
            <Link className="ghost" to="/finance">
              Finance
            </Link>
          </div>
        </div>
        {loading ? (
          <LoadingState label="Loading contracts..." />
        ) : error ? (
          <PartnerErrorState error={error} onRetry={reload} />
        ) : contracts.length === 0 ? (
          <EmptyState
            title="No contracts yet"
            description="Contracts appear here only after the backend owner has real partner-linked records."
            action={
              <Link className="primary" to="/finance">
                Open finance
              </Link>
            }
          />
        ) : (
          <div className="table-shell">
            <div className="table-scroll">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Number</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Role</th>
                    <th>Counterparty</th>
                    <th>Effective from</th>
                    <th>Open</th>
                  </tr>
                </thead>
                <tbody>
                  {contracts.map((contract) => (
                    <tr key={contract.id}>
                      <td className="mono">{contract.contract_number}</td>
                      <td>{contract.contract_type}</td>
                      <td>
                        <StatusBadge status={contract.status} />
                      </td>
                      <td>{contract.party_role}</td>
                      <td className="mono">{contract.counterparty_id}</td>
                      <td>{formatDate(contract.effective_from)}</td>
                      <td>
                        <Link className="link-button" to={`/contracts/${contract.id}`}>
                          Details
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="table-footer">
              <div className="table-footer__content">
                <span className="muted">Contracts: {total}</span>
              </div>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
