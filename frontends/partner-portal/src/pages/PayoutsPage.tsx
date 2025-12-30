import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchSettlements, type SettlementListItem } from "../api/partner";
import { useAuth } from "../auth/AuthContext";
import { StatusBadge } from "../components/StatusBadge";
import { formatCurrency, formatDate, formatNumber } from "../utils/format";

export function PayoutsPage() {
  const { user } = useAuth();
  const [settlements, setSettlements] = useState<SettlementListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    if (!user) return;
    setIsLoading(true);
    fetchSettlements(user.token)
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
          <div className="skeleton-stack" aria-busy="true">
            <div className="skeleton-line" />
            <div className="skeleton-line" />
          </div>
        ) : error ? (
          <div className="error" role="alert">
            {error}
          </div>
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
                <th>Net</th>
                <th>Статус</th>
                <th>Операции</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {settlements.map((settlement) => (
                <tr key={settlement.id}>
                  <td>
                    {formatDate(settlement.periodStart)} — {formatDate(settlement.periodEnd)}
                  </td>
                  <td>{formatCurrency(settlement.grossAmount)}</td>
                  <td>{formatCurrency(settlement.netAmount)}</td>
                  <td>
                    <StatusBadge status={settlement.status} />
                  </td>
                  <td>{formatNumber(settlement.transactionsCount ?? null)}</td>
                  <td>
                    <Link className="ghost" to={`/payouts/${settlement.id}`}>
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
