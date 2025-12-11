import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { fetchOperationDetails } from "../api/operations";
import { useAuth } from "../auth/AuthContext";
import type { OperationDetails } from "../types/operations";

export function OperationDetailsPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [operation, setOperation] = useState<OperationDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    fetchOperationDetails(id, user)
      .then(setOperation)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id, user]);

  if (loading) {
    return <div className="card">Загружаем операцию...</div>;
  }

  if (error) {
    return (
      <div className="card error" role="alert">
        {error}
      </div>
    );
  }

  if (!operation) {
    return (
      <div className="card error" role="alert">
        Операция не найдена
      </div>
    );
  }

  return (
    <div className="card">
      <h2>Операция {operation.id}</h2>
      <dl className="meta-grid">
        <div>
          <dt className="label">Дата</dt>
          <dd>{new Date(operation.created_at).toLocaleString()}</dd>
        </div>
        <div>
          <dt className="label">Сумма</dt>
          <dd>
            {operation.amount} {operation.currency}
          </dd>
        </div>
        <div>
          <dt className="label">Статус</dt>
          <dd>{operation.status}</dd>
        </div>
        <div>
          <dt className="label">Карта</dt>
          <dd>{operation.card_id}</dd>
        </div>
        {operation.reason && (
          <div>
            <dt className="label">Причина</dt>
            <dd>{operation.reason}</dd>
          </div>
        )}
      </dl>
    </div>
  );
}
