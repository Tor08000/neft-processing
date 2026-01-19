import { useEffect, useMemo, useState } from "react";
import { fetchPartnerBalance, fetchPartnerLedger } from "../api/partnerFinance";
import { useAuth } from "../auth/AuthContext";
import { StatusBadge } from "../components/StatusBadge";
import { ErrorState, LoadingState } from "../components/states";
import { formatCurrency, formatDateTime } from "../utils/format";
import type { PartnerBalance, PartnerLedgerEntry } from "../types/partnerFinance";

export function PartnerFinancePage() {
  const { user } = useAuth();
  const [balance, setBalance] = useState<PartnerBalance | null>(null);
  const [ledger, setLedger] = useState<PartnerLedgerEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const currency = useMemo(() => balance?.currency ?? "RUB", [balance]);

  useEffect(() => {
    let active = true;
    if (!user) return;
    setIsLoading(true);
    Promise.all([fetchPartnerBalance(user.token), fetchPartnerLedger(user.token)])
      .then(([balanceResp, ledgerResp]) => {
        if (!active) return;
        setBalance(balanceResp);
        setLedger(ledgerResp.items ?? []);
      })
      .catch((err) => {
        console.error(err);
        if (active) setError("Не удалось загрузить финансы партнёра");
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [user]);

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <h2>Баланс</h2>
        </div>
        {isLoading ? (
          <LoadingState />
        ) : error ? (
          <ErrorState description={error} />
        ) : (
          <div className="grid three">
            <div className="metric-card">
              <div className="muted">Доступно</div>
              <strong>{formatCurrency(balance?.balance_available ?? null, currency)}</strong>
            </div>
            <div className="metric-card">
              <div className="muted">Ожидает</div>
              <strong>{formatCurrency(balance?.balance_pending ?? null, currency)}</strong>
            </div>
            <div className="metric-card">
              <div className="muted">Заблокировано</div>
              <strong>{formatCurrency(balance?.balance_blocked ?? null, currency)}</strong>
            </div>
          </div>
        )}
      </section>
      <section className="card">
        <div className="section-title">
          <h2>Ledger</h2>
        </div>
        {isLoading ? (
          <LoadingState />
        ) : error ? (
          <ErrorState description={error} />
        ) : ledger.length === 0 ? (
          <div className="empty-state">
            <strong>Нет движений</strong>
            <span className="muted">Начисления и списания появятся после завершения заказов.</span>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Дата</th>
                <th>Тип</th>
                <th>Сумма</th>
                <th>Направление</th>
                <th>Заказ</th>
              </tr>
            </thead>
            <tbody>
              {ledger.map((entry) => (
                <tr key={entry.id}>
                  <td>{formatDateTime(entry.created_at)}</td>
                  <td>
                    <StatusBadge status={entry.entry_type} />
                  </td>
                  <td>{formatCurrency(entry.amount ?? null, entry.currency)}</td>
                  <td>{entry.direction}</td>
                  <td className="mono">{entry.order_id ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
