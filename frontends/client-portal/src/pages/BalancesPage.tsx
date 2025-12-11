import { useEffect, useState } from "react";
import { fetchBalances } from "../api/balances";
import { useAuth } from "../auth/AuthContext";
import type { BalanceItem } from "../types/balances";

export function BalancesPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<BalanceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchBalances(user)
      .then((resp) => setItems(resp.items))
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [user]);

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
      <h2>Балансы и доступные средства</h2>
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
                <td>{item.current}</td>
                <td>{item.available}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
