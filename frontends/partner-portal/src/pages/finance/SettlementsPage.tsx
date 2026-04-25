import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchPartnerSettlements } from "../../api/partnerFinance";
import { useAuth } from "../../auth/AuthContext";
import { EmptyState } from "../../components/EmptyState";
import { PartnerErrorState } from "../../components/PartnerErrorState";
import { StatusBadge } from "../../components/StatusBadge";
import { LoadingState } from "../../components/states";
import type { PartnerSettlement } from "../../types/partnerFinance";
import { formatCurrency, formatDate } from "../../utils/format";

export function SettlementsPage() {
  const { user } = useAuth();
  const [settlements, setSettlements] = useState<PartnerSettlement[]>([]);
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
    fetchPartnerSettlements(user.token, { limit: 50, offset: 0 })
      .then((response) => {
        if (!active) return;
        setSettlements(response.items ?? []);
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
            <h2>Settlements</h2>
            <p className="muted">Read-only settlement periods from the finance owner.</p>
          </div>
          <div className="toolbar-actions">
            <Link className="ghost" to="/finance">
              Finance
            </Link>
          </div>
        </div>
        {loading ? (
          <LoadingState label="Loading settlements..." />
        ) : error ? (
          <PartnerErrorState error={error} onRetry={reload} />
        ) : settlements.length === 0 ? (
          <EmptyState
            title="No settlements yet"
            description="Settlement periods appear after finalized owner snapshots. No demo rows are invented here."
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
                    <th>Period</th>
                    <th>Status</th>
                    <th>Gross</th>
                    <th>Fees</th>
                    <th>Refunds</th>
                    <th>Net</th>
                    <th>Open</th>
                  </tr>
                </thead>
                <tbody>
                  {settlements.map((settlement) => (
                    <tr key={settlement.id}>
                      <td>
                        {formatDate(settlement.period_start)} - {formatDate(settlement.period_end)}
                      </td>
                      <td>
                        <StatusBadge status={settlement.status} />
                      </td>
                      <td>{formatCurrency(settlement.total_gross, settlement.currency)}</td>
                      <td>{formatCurrency(settlement.total_fees, settlement.currency)}</td>
                      <td>{formatCurrency(settlement.total_refunds, settlement.currency)}</td>
                      <td>{formatCurrency(settlement.net_amount, settlement.currency)}</td>
                      <td>
                        <Link className="link-button" to={`/settlements/${settlement.id}`}>
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
                <span className="muted">Settlements: {total}</span>
              </div>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
