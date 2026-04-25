import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchPartnerSettlement } from "../../api/partnerFinance";
import { useAuth } from "../../auth/AuthContext";
import { EmptyState } from "../../components/EmptyState";
import { PartnerErrorState } from "../../components/PartnerErrorState";
import { StatusBadge } from "../../components/StatusBadge";
import { LoadingState } from "../../components/states";
import type { PartnerSettlement } from "../../types/partnerFinance";
import { formatCurrency, formatDate, formatDateTime } from "../../utils/format";

export function SettlementDetailsPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [settlement, setSettlement] = useState<PartnerSettlement | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const reload = () => setReloadKey((value) => value + 1);

  useEffect(() => {
    let active = true;
    if (!user || !id) return;
    setLoading(true);
    setError(null);
    fetchPartnerSettlement(user.token, id)
      .then((response) => {
        if (!active) return;
        setSettlement(response);
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

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <div>
            <h2>Settlement details</h2>
            <p className="muted">Read-only period card with linked marketplace snapshots when present.</p>
          </div>
          <div className="toolbar-actions">
            <Link className="ghost" to="/settlements">
              Settlements
            </Link>
          </div>
        </div>
        {!id ? (
          <EmptyState title="Settlement is not selected" description="Open a settlement from the register." />
        ) : loading ? (
          <LoadingState label="Loading settlement..." />
        ) : error ? (
          <PartnerErrorState error={error} onRetry={reload} />
        ) : !settlement ? (
          <EmptyState title="Settlement was not found" description="The finance owner returned no record." />
        ) : (
          <div className="stack">
            <div className="meta-grid">
              <div>
                <div className="label">Period</div>
                <div>
                  {formatDate(settlement.period_start)} - {formatDate(settlement.period_end)}
                </div>
              </div>
              <div>
                <div className="label">Status</div>
                <StatusBadge status={settlement.status} />
              </div>
              <div>
                <div className="label">Gross</div>
                <div>{formatCurrency(settlement.total_gross, settlement.currency)}</div>
              </div>
              <div>
                <div className="label">Fees</div>
                <div>{formatCurrency(settlement.total_fees, settlement.currency)}</div>
              </div>
              <div>
                <div className="label">Refunds</div>
                <div>{formatCurrency(settlement.total_refunds, settlement.currency)}</div>
              </div>
              <div>
                <div className="label">Net</div>
                <div>{formatCurrency(settlement.net_amount, settlement.currency)}</div>
              </div>
              <div>
                <div className="label">Created</div>
                <div>{formatDateTime(settlement.created_at)}</div>
              </div>
              <div>
                <div className="label">Period hash</div>
                <div className="mono">{settlement.period_hash ?? "-"}</div>
              </div>
            </div>

            <section className="card">
              <div className="section-title">
                <h3>Settlement items</h3>
              </div>
              {settlement.items?.length ? (
                <div className="table-shell">
                  <div className="table-scroll">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Source</th>
                          <th>Direction</th>
                          <th>Amount</th>
                          <th>Created</th>
                        </tr>
                      </thead>
                      <tbody>
                        {settlement.items.map((item) => (
                          <tr key={item.id}>
                            <td className="mono">
                              {item.source_type} / {item.source_id}
                            </td>
                            <td>{item.direction}</td>
                            <td>{formatCurrency(item.amount, settlement.currency)}</td>
                            <td>{formatDateTime(item.created_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : (
                <EmptyState title="No settlement items" description="Line items are not available for this period yet." />
              )}
            </section>

            <section className="card">
              <div className="section-title">
                <h3>Marketplace snapshots</h3>
              </div>
              {settlement.marketplace_snapshots?.length ? (
                <div className="table-shell">
                  <div className="table-scroll">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Order</th>
                          <th>Gross</th>
                          <th>Fee</th>
                          <th>Penalties</th>
                          <th>Net</th>
                          <th>Hash</th>
                        </tr>
                      </thead>
                      <tbody>
                        {settlement.marketplace_snapshots.map((snapshot) => (
                          <tr key={snapshot.id}>
                            <td className="mono">{snapshot.order_id}</td>
                            <td>{formatCurrency(snapshot.gross_amount, snapshot.currency)}</td>
                            <td>{formatCurrency(snapshot.platform_fee, snapshot.currency)}</td>
                            <td>{formatCurrency(snapshot.penalties, snapshot.currency)}</td>
                            <td>{formatCurrency(snapshot.partner_net, snapshot.currency)}</td>
                            <td className="mono">{snapshot.hash ?? "-"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : (
                <EmptyState
                  title="No marketplace snapshots"
                  description="Finalized marketplace order snapshots will appear here when linked to the settlement period."
                />
              )}
            </section>
          </div>
        )}
      </section>
    </div>
  );
}
