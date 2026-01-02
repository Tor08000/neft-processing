import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchClientDashboard } from "../api/portal";
import { useAuth } from "../auth/AuthContext";
import { AppEmptyState, AppErrorState, AppLoadingState } from "../components/states";
import { MoneyValue } from "../components/common/MoneyValue";
import type { ClientDashboardSummary } from "../types/portal";

export function DashboardPage() {
  const { user } = useAuth();
  const [summary, setSummary] = useState<ClientDashboardSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    setIsLoading(true);
    setError(null);
    fetchClientDashboard(user)
      .then((dashboard) => setSummary(dashboard))
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
            <h2>Обзор клиента</h2>
            <p className="muted">Краткий статус контрактов, платежей и SLA.</p>
          </div>
          <Link className="ghost" to="/invoices">
            Перейти к инвойсам
          </Link>
        </div>
        {isLoading ? <AppLoadingState /> : null}
        {error ? <AppErrorState message={error} /> : null}
        {!isLoading && !error && summary ? (
          <div className="kpi-grid">
            <div className="kpi-card">
              <div className="kpi-card__title">Активные контракты</div>
              <div className="kpi-card__value">{summary.active_contracts}</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-card__title">Инвойсы к оплате</div>
              <div className="kpi-card__value">{summary.invoices_due}</div>
              <div className="muted small">
                <MoneyValue amount={summary.invoices_due_amount} />
              </div>
            </div>
            <div className="kpi-card">
              <div className="kpi-card__title">Платежи за 30 дней</div>
              <div className="kpi-card__value">{summary.payments_last_30d_count}</div>
              <div className="muted small">
                <MoneyValue amount={summary.payments_last_30d} />
              </div>
            </div>
            <div className="kpi-card">
              <div className="kpi-card__title">SLA статус</div>
              <div className="kpi-card__value">{summary.sla.status}</div>
              <div className="muted small">Нарушений: {summary.sla.violations}</div>
            </div>
          </div>
        ) : null}
        {!isLoading && !error && !summary ? <AppEmptyState description="Нет данных для обзора." /> : null}
      </section>
    </div>
  );
}
