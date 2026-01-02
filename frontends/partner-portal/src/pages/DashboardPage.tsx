import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchPartnerDashboard } from "../api/portal";
import { useAuth } from "../auth/AuthContext";
import type { PartnerDashboardSummary } from "../types/portal";
import { formatCurrency } from "../utils/format";
import { ErrorState, LoadingState } from "../components/states";

export function DashboardPage() {
  const { user } = useAuth();
  const [summary, setSummary] = useState<PartnerDashboardSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    setIsLoading(true);
    setError(null);
    fetchPartnerDashboard(user)
      .then((data) => setSummary(data))
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [user]);

  if (!user) {
    return null;
  }

  return (
    <div className="stack" aria-live="polite">
      <section className="card">
        <div className="card__header">
          <div>
            <h2>Партнёрский обзор</h2>
            <p className="muted">Статусы контрактов, settlement и SLA.</p>
          </div>
          <Link className="ghost" to="/payouts">
            Перейти к settlements
          </Link>
        </div>
        {isLoading ? <LoadingState /> : null}
        {error ? <ErrorState description={error} /> : null}
        {!isLoading && !error && summary ? (
          <div className="stats-grid">
            <div className="stat">
              <span className="muted">Активные контракты</span>
              <strong>{summary.active_contracts}</strong>
            </div>
            <div className="stat">
              <span className="muted">Текущий период</span>
              <strong>{summary.current_settlement_period ?? "—"}</strong>
            </div>
            <div className="stat">
              <span className="muted">Ближайшая выплата</span>
              <strong>{summary.upcoming_payout ? formatCurrency(summary.upcoming_payout) : "—"}</strong>
            </div>
            <div className="stat">
              <span className="muted">SLA статус</span>
              <strong>{summary.sla.status}</strong>
              <div className="muted small">Нарушений: {summary.sla.violations}</div>
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}
