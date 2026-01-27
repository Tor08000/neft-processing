import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchPartnerDashboard } from "../api/portal";
import { fetchPartnerBalance, fetchPartnerPayoutPreview, fetchPartnerPayouts } from "../api/partnerFinance";
import { useAuth } from "../auth/AuthContext";
import { usePortal } from "../auth/PortalContext";
import type { PartnerDashboardSummary } from "../types/portal";
import { formatCurrency } from "../utils/format";
import { ErrorState, LoadingState } from "../components/states";

export function DashboardPage() {
  const { user } = useAuth();
  const { portal } = usePortal();
  const [summary, setSummary] = useState<PartnerDashboardSummary | null>(null);
  const [balance, setBalance] = useState<{ balance_available?: number; balance_pending?: number; balance_blocked?: number } | null>(null);
  const [blockedCount, setBlockedCount] = useState<number | null>(null);
  const [legalStatus, setLegalStatus] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    setIsLoading(true);
    setError(null);
    const meta = portal?.partner?.profile?.meta_json ?? {};
    const portalLegalStatus =
      typeof (meta as Record<string, unknown>).legal_status === "string"
        ? ((meta as Record<string, unknown>).legal_status as string)
        : null;
    Promise.all([
      fetchPartnerDashboard(user),
      fetchPartnerBalance(user.token),
      fetchPartnerPayoutPreview(user.token),
      fetchPartnerPayouts(user.token),
    ])
      .then(([dashboard, balanceResp, previewResp, payoutsResp]) => {
        setSummary(dashboard);
        setBalance(balanceResp);
        const previewLegal = previewResp.legal_status ?? portalLegalStatus;
        setLegalStatus(previewLegal);
        const items = payoutsResp.items ?? [];
        const blocked = items.filter((item) => item.status === "BLOCKED" || item.status === "REJECTED").length;
        setBlockedCount(blocked);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [portal, user]);

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
            Запросить выплату
          </Link>
        </div>
        {isLoading ? <LoadingState /> : null}
        {error ? <ErrorState description={error} /> : null}
        {!isLoading && !error && summary ? (
          <div className="stats-grid">
            <div className="stat">
              <span className="muted">Баланс</span>
              <strong>{formatCurrency(balance?.balance_available ?? null)}</strong>
              <div className="muted small">Ожидает: {formatCurrency(balance?.balance_pending ?? null)}</div>
            </div>
            <div className="stat">
              <span className="muted">Заблокировано</span>
              <strong>{formatCurrency(balance?.balance_blocked ?? null)}</strong>
              <div className="muted small">Блокированных выплат: {blockedCount ?? 0}</div>
            </div>
            <div className="stat">
              <span className="muted">Legal статус</span>
              <strong>{legalStatus ?? "—"}</strong>
            </div>
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
