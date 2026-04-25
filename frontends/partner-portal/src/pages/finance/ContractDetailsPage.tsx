import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchPartnerContract } from "../../api/partnerFinance";
import { useAuth } from "../../auth/AuthContext";
import { EmptyState } from "../../components/EmptyState";
import { PartnerErrorState } from "../../components/PartnerErrorState";
import { StatusBadge } from "../../components/StatusBadge";
import { LoadingState } from "../../components/states";
import type { PartnerContract } from "../../types/partnerFinance";
import { formatDate, formatDateTime } from "../../utils/format";

export function ContractDetailsPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [contract, setContract] = useState<PartnerContract | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const reload = () => setReloadKey((value) => value + 1);

  useEffect(() => {
    let active = true;
    if (!user || !id) return;
    setLoading(true);
    setError(null);
    fetchPartnerContract(user.token, id)
      .then((response) => {
        if (!active) return;
        setContract(response);
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
  }, [user, id, reloadKey]);

  if (!id) {
    return (
      <EmptyState
        title="Contract is not selected"
        description="Open the contract from the partner contract register."
        action={
          <Link className="primary" to="/contracts">
            Back to contracts
          </Link>
        }
      />
    );
  }

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <div>
            <h2>Contract details</h2>
            <p className="muted">Read-only contract card. Changes remain admin-owned.</p>
          </div>
          <div className="toolbar-actions">
            <Link className="ghost" to="/contracts">
              Contracts
            </Link>
          </div>
        </div>
        {loading ? (
          <LoadingState label="Loading contract..." />
        ) : error ? (
          <PartnerErrorState error={error} onRetry={reload} />
        ) : !contract ? (
          <EmptyState title="Contract was not found" description="The partner contract owner returned no record." />
        ) : (
          <div className="stack">
            <div className="meta-grid">
              <div>
                <div className="label">Number</div>
                <div className="mono">{contract.contract_number}</div>
              </div>
              <div>
                <div className="label">Status</div>
                <StatusBadge status={contract.status} />
              </div>
              <div>
                <div className="label">Type</div>
                <div>{contract.contract_type}</div>
              </div>
              <div>
                <div className="label">Currency</div>
                <div>{contract.currency}</div>
              </div>
              <div>
                <div className="label">Partner role</div>
                <div>{contract.party_role}</div>
              </div>
              <div>
                <div className="label">Counterparty</div>
                <div className="mono">{contract.counterparty_id}</div>
              </div>
              <div>
                <div className="label">Effective from</div>
                <div>{formatDate(contract.effective_from)}</div>
              </div>
              <div>
                <div className="label">Effective to</div>
                <div>{formatDate(contract.effective_to)}</div>
              </div>
              <div>
                <div className="label">Created</div>
                <div>{formatDateTime(contract.created_at)}</div>
              </div>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
