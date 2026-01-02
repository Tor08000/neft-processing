import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchPartnerSettlements } from "../api/portal";
import { useAuth } from "../auth/AuthContext";
import { StatusBadge } from "../components/StatusBadge";
import { formatCurrency, formatDate } from "../utils/format";
import type { PartnerSettlementSummary } from "../types/portal";
import { ErrorState, LoadingState } from "../components/states";

export function PayoutsPage() {
  const { user } = useAuth();
  const [settlements, setSettlements] = useState<PartnerSettlementSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    if (!user) return;
    setIsLoading(true);
    fetchPartnerSettlements(user)
      .then((data) => {
        if (active) {
          setSettlements(data.items ?? []);
        }
      })
      .catch((err) => {
        console.error(err);
        if (active) {
          setError("Не удалось загрузить выплаты");
        }
      })
      .finally(() => {
        if (active) {
          setIsLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [user]);

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <h2>Выплаты / Settlements</h2>
          <Link className="ghost" to="/payouts/batches">
            Payout batches
          </Link>
        </div>
        {isLoading ? (
          <LoadingState />
        ) : error ? (
          <ErrorState description={error} />
        ) : settlements.length === 0 ? (
          <div className="empty-state">
            <strong>Выплаты не найдены</strong>
            <span className="muted">Данные появятся после расчёта.</span>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Период</th>
                <th>Gross</th>
                <th>Fees</th>
                <th>Refunds</th>
                <th>Net</th>
                <th>Статус</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {settlements.map((settlement) => (
                <tr key={settlement.settlement_ref}>
                  <td>
                    {formatDate(settlement.period_start)} — {formatDate(settlement.period_end)}
                  </td>
                  <td>{formatCurrency(settlement.gross, settlement.currency)}</td>
                  <td>{formatCurrency(settlement.fees, settlement.currency)}</td>
                  <td>{formatCurrency(settlement.refunds, settlement.currency)}</td>
                  <td>{formatCurrency(settlement.net_amount, settlement.currency)}</td>
                  <td>
                    <StatusBadge status={settlement.status} />
                  </td>
                  <td>
                    <Link className="ghost" to={`/payouts/${settlement.settlement_ref}`}>
                      details
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
