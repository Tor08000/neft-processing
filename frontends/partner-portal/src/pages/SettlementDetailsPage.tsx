import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { confirmPartnerSettlement, fetchPartnerSettlementDetails } from "../api/portal";
import { useAuth } from "../auth/AuthContext";
import type { PartnerSettlementDetails } from "../types/portal";
import { formatCurrency, formatDate } from "../utils/format";
import { ErrorState, LoadingState } from "../components/states";
import { StatusBadge } from "../components/StatusBadge";

export function SettlementDetailsPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [settlement, setSettlement] = useState<PartnerSettlementDetails | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    if (!id) return;
    setIsLoading(true);
    setError(null);
    fetchPartnerSettlementDetails(user, id)
      .then((data) => setSettlement(data))
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [id, user]);

  const handleConfirm = async () => {
    if (!id) return;
    setConfirming(true);
    try {
      await confirmPartnerSettlement(user, id);
      setSettlement((prev) => (prev ? { ...prev, payout_status: "CONFIRMED" } : prev));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setConfirming(false);
    }
  };

  if (!id) return null;
  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState description={error} />;
  if (!settlement) return <ErrorState description="Settlement не найден" />;

  return (
    <div className="stack">
      <div className="card">
        <div className="card__header">
          <div>
            <h2>Settlement {settlement.settlement_ref}</h2>
            <p className="muted">
              {formatDate(settlement.period_start)} — {formatDate(settlement.period_end)}
            </p>
          </div>
          <div className="actions">
            <Link className="ghost" to="/payouts">
              Назад
            </Link>
            <button type="button" className="ghost" onClick={handleConfirm} disabled={confirming}>
              Подтвердить payout
            </button>
          </div>
        </div>
        <div className="stats-grid">
          <div className="stat">
            <span className="muted">Gross</span>
            <strong>{formatCurrency(settlement.gross, settlement.currency)}</strong>
          </div>
          <div className="stat">
            <span className="muted">Fees</span>
            <strong>{formatCurrency(settlement.fees, settlement.currency)}</strong>
          </div>
          <div className="stat">
            <span className="muted">Refunds</span>
            <strong>{formatCurrency(settlement.refunds, settlement.currency)}</strong>
          </div>
          <div className="stat">
            <span className="muted">Net</span>
            <strong>{formatCurrency(settlement.net_amount, settlement.currency)}</strong>
          </div>
          <div className="stat">
            <span className="muted">Статус</span>
            <StatusBadge status={settlement.status} />
          </div>
          <div className="stat">
            <span className="muted">Payout status</span>
            <strong>{settlement.payout_status ?? "—"}</strong>
          </div>
        </div>
      </div>

      <section className="card">
        <div className="card__header">
          <h3>Settlement breakdown</h3>
        </div>
        {settlement.items_summary.length ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Источник</th>
                <th>Направление</th>
                <th>Количество</th>
                <th>Сумма</th>
              </tr>
            </thead>
            <tbody>
              {settlement.items_summary.map((item, index) => (
                <tr key={`${item.source_type}-${item.direction}-${index}`}>
                  <td>{item.source_type}</td>
                  <td>{item.direction}</td>
                  <td>{item.count}</td>
                  <td>{formatCurrency(item.amount, settlement.currency)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted">Детализация пока недоступна.</p>
        )}
      </section>
    </div>
  );
}
