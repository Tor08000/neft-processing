import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchClientContractDetails } from "../api/portal";
import { useAuth } from "../auth/AuthContext";
import type { ClientContractDetails } from "../types/portal";
import { AppErrorState, AppLoadingState } from "../components/states";
import { formatDate, formatDateTime } from "../utils/format";
import { MoneyValue } from "../components/common/MoneyValue";

export function ClientContractDetailsPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [contract, setContract] = useState<ClientContractDetails | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setIsLoading(true);
    setError(null);
    fetchClientContractDetails(user, id)
      .then((data) => setContract(data))
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [id, user]);

  if (!id) return null;
  if (isLoading) return <AppLoadingState />;
  if (error) return <AppErrorState message={error} />;
  if (!contract) return <AppErrorState message="Контракт не найден" />;

  return (
    <div className="stack">
      <div className="card">
        <div className="card__header">
          <div>
            <h2>{contract.contract_number}</h2>
            <p className="muted">Тип: {contract.contract_type}</p>
          </div>
          <Link className="ghost" to="/contracts">
            Назад к списку
          </Link>
        </div>
        <div className="stats-grid">
          <div className="stat">
            <span className="muted">Даты</span>
            <strong>
              {formatDate(contract.effective_from)} — {contract.effective_to ? formatDate(contract.effective_to) : "—"}
            </strong>
          </div>
          <div className="stat">
            <span className="muted">SLA статус</span>
            <strong>{contract.sla_status}</strong>
          </div>
          <div className="stat">
            <span className="muted">Нарушения</span>
            <strong>{contract.sla_violations}</strong>
          </div>
          <div className="stat">
            <span className="muted">Пени</span>
            <strong>
              <MoneyValue amount={contract.penalties_total} />
            </strong>
          </div>
        </div>
      </div>

      <section className="card">
        <div className="card__header">
          <h3>SLA обязательства</h3>
        </div>
        {contract.obligations.length ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Тип</th>
                <th>Метрика</th>
                <th>Порог</th>
                <th>Сравнение</th>
                <th>Окно</th>
                <th>Штраф</th>
              </tr>
            </thead>
            <tbody>
              {contract.obligations.map((obligation, index) => (
                <tr key={`${obligation.metric}-${index}`}>
                  <td>{obligation.obligation_type}</td>
                  <td>{obligation.metric}</td>
                  <td>{obligation.threshold}</td>
                  <td>{obligation.comparison}</td>
                  <td>{obligation.window ?? "—"}</td>
                  <td>
                    {obligation.penalty_type}: {obligation.penalty_value}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted">Обязательства не заданы.</p>
        )}
      </section>

      <section className="card">
        <div className="card__header">
          <h3>История SLA</h3>
        </div>
        {contract.sla_results.length ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Период</th>
                <th>Статус</th>
                <th>Значение</th>
              </tr>
            </thead>
            <tbody>
              {contract.sla_results.map((result, index) => (
                <tr key={`${result.period_start}-${index}`}>
                  <td>
                    {formatDateTime(result.period_start)} — {formatDateTime(result.period_end)}
                  </td>
                  <td>{result.status}</td>
                  <td>{result.measured_value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted">Истории SLA пока нет.</p>
        )}
      </section>
    </div>
  );
}
