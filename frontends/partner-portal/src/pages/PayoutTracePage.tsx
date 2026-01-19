import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchPartnerPayoutTrace } from "../api/partnerFinance";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, LoadingState } from "../components/states";
import { StatusBadge } from "../components/StatusBadge";
import type { PartnerPayoutTrace } from "../types/partnerFinance";
import { formatCurrency, formatDate, formatDateTime } from "../utils/format";

export function PayoutTracePage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [trace, setTrace] = useState<PartnerPayoutTrace | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user || !id) return;
    setIsLoading(true);
    setError(null);
    fetchPartnerPayoutTrace(user.token, id)
      .then((data) => setTrace(data))
      .catch((err) => {
        console.error(err);
        setError("Не удалось загрузить payout trace");
      })
      .finally(() => setIsLoading(false));
  }, [user, id]);

  if (!id) return null;
  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState description={error} />;
  if (!trace) return <ErrorState description="Payout не найден" />;

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <div>
            <h2>Payout {trace.payout_id}</h2>
            <p className="muted">
              {formatDate(trace.date_from)} — {formatDate(trace.date_to)}
            </p>
          </div>
          <Link className="ghost" to="/payouts/batches">
            Назад к payout batches
          </Link>
        </div>
        <div className="meta-grid">
          <div>
            <div className="label">Статус</div>
            <StatusBadge status={trace.payout_state} />
          </div>
          <div>
            <div className="label">Создано</div>
            <div>{formatDateTime(trace.created_at)}</div>
          </div>
          <div>
            <div className="label">Итого</div>
            <div>{formatCurrency(trace.total_amount, trace.orders[0]?.currency ?? "RUB")}</div>
          </div>
          <div>
            <div className="label">Gross</div>
            <div>{formatCurrency(trace.summary.gross_total, trace.orders[0]?.currency ?? "RUB")}</div>
          </div>
          <div>
            <div className="label">Fee</div>
            <div>{formatCurrency(trace.summary.fee_total, trace.orders[0]?.currency ?? "RUB")}</div>
          </div>
          <div>
            <div className="label">Penalties</div>
            <div>{formatCurrency(trace.summary.penalties_total, trace.orders[0]?.currency ?? "RUB")}</div>
          </div>
          <div>
            <div className="label">Net</div>
            <div>{formatCurrency(trace.summary.net_total, trace.orders[0]?.currency ?? "RUB")}</div>
          </div>
        </div>
      </section>

      <section className="card">
        <div className="section-title">
          <h3>Orders in payout batch</h3>
        </div>
        {trace.orders.length ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Order</th>
                <th>Gross</th>
                <th>Fee</th>
                <th>Penalties</th>
                <th>Net</th>
                <th>Finalized</th>
                <th>Link</th>
              </tr>
            </thead>
            <tbody>
              {trace.orders.map((order) => (
                <tr key={order.settlement_snapshot_id ?? order.order_id}>
                  <td className="mono">{order.order_id}</td>
                  <td>{formatCurrency(order.gross_amount, order.currency)}</td>
                  <td>{formatCurrency(order.platform_fee, order.currency)}</td>
                  <td>{formatCurrency(order.penalties, order.currency)}</td>
                  <td>{formatCurrency(order.partner_net, order.currency)}</td>
                  <td>{order.finalized_at ? formatDateTime(order.finalized_at) : "—"}</td>
                  <td>
                    <Link className="link-button" to={`/orders/${order.order_id}`}>
                      Order
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="muted">Пока нет заказов в этом payout batch.</div>
        )}
      </section>
    </div>
  );
}
