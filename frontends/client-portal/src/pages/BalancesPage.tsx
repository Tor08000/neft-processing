import { type ChangeEvent, useEffect, useMemo, useState } from "react";
import { fetchBalances } from "../api/balances";
import { fetchStatements } from "../api/statements";
import { useAuth } from "../auth/AuthContext";
import type { BalanceItem } from "../types/balances";
import type { Statement } from "../types/statements";
import { formatMoney } from "../utils/format";

const todayIso = () => new Date().toISOString().slice(0, 10);

export function BalancesPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<BalanceItem[]>([]);
  const [statements, setStatements] = useState<Statement[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState(() => {
    const to = todayIso();
    const fromDate = new Date();
    fromDate.setDate(fromDate.getDate() - 30);
    const from = fromDate.toISOString().slice(0, 10);
    return { from, to };
  });

  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetchBalances(user),
      fetchStatements(user, { from: filters.from, to: filters.to }),
    ])
      .then(([balancesResp, statementsResp]) => {
        setItems(balancesResp.items);
        setStatements(statementsResp);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [user, filters]);

  const totals = useMemo(() => {
    const totalCurrent = items.reduce((acc, item) => acc + Number(item.current ?? 0), 0);
    const totalTopup = statements.reduce((acc, s) => acc + Number(s.credits ?? 0), 0);
    const totalSpent = statements.reduce((acc, s) => acc + Number(s.debits ?? 0), 0);
    return { totalCurrent, totalTopup, totalSpent };
  }, [items, statements]);

  const handleFilterChange = (event: ChangeEvent<HTMLInputElement>) => {
    const { name, value } = event.target;
    setFilters((prev) => ({ ...prev, [name]: value }));
  };

  if (loading) {
    return <div className="card">Загружаем балансы...</div>;
  }

  if (error) {
    return (
      <div className="card error" role="alert">
        {error}
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card__header">
        <div>
          <h2>Балансы и доступные средства</h2>
          <p className="muted">Актуальные остатки и движение средств за период</p>
        </div>
        <div className="filters">
          <div className="filter">
            <label htmlFor="from">Период с</label>
            <input id="from" name="from" type="date" value={filters.from} onChange={handleFilterChange} />
          </div>
          <div className="filter">
            <label htmlFor="to">Период по</label>
            <input id="to" name="to" type="date" value={filters.to} onChange={handleFilterChange} />
          </div>
        </div>
      </div>

      <div className="kpis">
        <div className="kpi">
          <p className="label">Текущий баланс</p>
          <p className="value">{formatMoney(totals.totalCurrent, items[0]?.currency ?? "RUB")}</p>
        </div>
        <div className="kpi">
          <p className="label">Пополнено за период</p>
          <p className="value success">{formatMoney(totals.totalTopup, items[0]?.currency ?? "RUB")}</p>
        </div>
        <div className="kpi">
          <p className="label">Израсходовано за период</p>
          <p className="value warning">{formatMoney(totals.totalSpent, items[0]?.currency ?? "RUB")}</p>
        </div>
      </div>

      {items.length === 0 ? (
        <p className="muted">Нет счетов, доступных для отображения.</p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Валюта</th>
              <th>Текущий баланс</th>
              <th>Доступно</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.currency}>
                <td>{item.currency}</td>
                <td>{formatMoney(item.current, item.currency)}</td>
                <td>{formatMoney(item.available, item.currency)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
