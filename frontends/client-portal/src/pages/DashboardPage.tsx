import { useQuery } from "@tanstack/react-query";
import { fetchDashboard, handleUnauthorized } from "../api";
import type { DashboardSummary, Operation } from "../types";

interface DashboardPageProps {
  token: string;
}

export function DashboardPage({ token }: DashboardPageProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard", token],
    queryFn: () => fetchDashboard(token),
  });

  if (isLoading) {
    return <div className="card">Загрузка дашборда...</div>;
  }

  if (error && handleUnauthorized(error)) {
    return null;
  }

  if (error || !data) {
    return <div className="card error">Не удалось загрузить дашборд</div>;
  }

  const summary: DashboardSummary = data.summary;
  const lastOperations: Operation[] = data.recentOperations;
  return (
    <div className="grid">
      <div className="grid two">
        <div className="card">
          <div className="section-title">
            <span>Операции за период</span>
            <span className="badge pending">{summary.period}</span>
          </div>
          <h2>{summary.totalOperations}</h2>
          <p>транзакций</p>
        </div>

        <div className="card">
          <div className="section-title">
            <span>Суммарный расход</span>
            <span className="badge success">RUB</span>
          </div>
          <h2>{summary.totalAmount.toLocaleString("ru-RU")}</h2>
          <p>по всем операциям</p>
        </div>

        <div className="card">
          <div className="section-title">
            <span>Активные лимиты</span>
          </div>
          <h2>{summary.activeLimits}</h2>
          <p>лимитов активно</p>
        </div>
      </div>

      <div className="card">
        <div className="section-title">
          <h3>Последние операции</h3>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Дата</th>
              <th>Тип</th>
              <th>Статус</th>
              <th>Сумма</th>
              <th>Карта</th>
            </tr>
          </thead>
          <tbody>
            {lastOperations.map((operation) => (
              <tr key={operation.id}>
                <td>{new Date(operation.date).toLocaleString("ru-RU")}</td>
                <td>{operation.type}</td>
                <td>
                  <span
                    className={`badge ${operation.status === "success" ? "success" : operation.status === "pending" ? "pending" : "error"}`}
                  >
                    {operation.status}
                  </span>
                </td>
                <td>{operation.amount.toLocaleString("ru-RU")}</td>
                <td>{operation.cardRef ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
