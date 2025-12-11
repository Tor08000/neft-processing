import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchOperations } from "../api/operations";
import { useAuth } from "../auth/AuthContext";
import type { OperationSummary } from "../types/operations";

export function OperationsPage() {
  const { user } = useAuth();
  const [operations, setOperations] = useState<OperationSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchOperations(user)
      .then((resp) => setOperations(resp.items))
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [user]);

  if (isLoading) {
    return <div className="card">Загружаем операции...</div>;
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
      <h2>Операции</h2>
      {operations.length === 0 ? (
        <p className="muted">Операций пока нет.</p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Дата</th>
              <th>Сумма</th>
              <th>Статус</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {operations.map((op) => (
              <tr key={op.id}>
                <td>{op.id}</td>
                <td>{new Date(op.created_at).toLocaleString()}</td>
                <td>
                  {op.amount} {op.currency}
                </td>
                <td>{op.status}</td>
                <td>
                  <Link to={`/operations/${op.id}`} className="ghost">
                    Подробнее
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
