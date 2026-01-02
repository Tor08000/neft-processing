import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchClientContracts } from "../api/portal";
import { useAuth } from "../auth/AuthContext";
import type { ClientContractSummary } from "../types/portal";
import { formatDate } from "../utils/format";
import { AppErrorState, AppLoadingState } from "../components/states";

const slaTone = (status: string) => {
  if (status === "OK") return "success";
  if (status === "VIOLATIONS") return "warning";
  return "neutral";
};

export function ClientContractsPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<ClientContractSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    fetchClientContracts(user)
      .then((data) => setItems(data.items))
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [user]);

  if (isLoading) {
    return <AppLoadingState />;
  }

  if (error) {
    return <AppErrorState message={error} />;
  }

  return (
    <div className="card">
      <div className="card__header">
        <div>
          <h2>Контракты</h2>
          <p className="muted">Сводка по действующим контрактам и SLA.</p>
        </div>
      </div>
      {items.length ? (
        <table className="data-table">
          <thead>
            <tr>
              <th>Контракт</th>
              <th>Тип</th>
              <th>Даты</th>
              <th>SLA</th>
              <th>Нарушения</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {items.map((contract) => (
              <tr key={contract.contract_number}>
                <td>{contract.contract_number}</td>
                <td>{contract.contract_type}</td>
                <td>
                  {formatDate(contract.effective_from)} — {contract.effective_to ? formatDate(contract.effective_to) : "—"}
                </td>
                <td>
                  <span className={`neft-badge ${slaTone(contract.sla_status)}`}>{contract.sla_status}</span>
                </td>
                <td>{contract.sla_violations}</td>
                <td>
                  <Link className="ghost" to={`/contracts/${contract.contract_number}`}>
                    Открыть
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="muted">Контрактов пока нет.</p>
      )}
    </div>
  );
}
