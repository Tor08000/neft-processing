import { useQuery } from "@tanstack/react-query";
import { fetchLimits, handleUnauthorized } from "../api";
import type { Limit } from "../types";

interface LimitsPageProps {
  token: string;
}

export function LimitsPage({ token }: LimitsPageProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["limits", token],
    queryFn: () => fetchLimits(token),
  });
  const limits: Limit[] = data ?? [];

  if (isLoading) {
    return <div className="card">Загрузка лимитов...</div>;
  }

  if (error && handleUnauthorized(error)) {
    return null;
  }

  if (error) {
    return <div className="card error">Не удалось загрузить лимиты</div>;
  }
  return (
    <div className="card">
      <div className="section-title">
        <h2>Лимиты</h2>
      </div>
      <table className="data-table">
        <thead>
          <tr>
            <th>Тип</th>
            <th>Период</th>
            <th>Величина</th>
            <th>Использовано</th>
          </tr>
        </thead>
        <tbody>
          {limits.map((limit) => {
            const usedPercent = Math.round((limit.used / limit.amount) * 100);
            return (
              <tr key={limit.id}>
                <td>{limit.type}</td>
                <td>{limit.period}</td>
                <td>{limit.amount.toLocaleString("ru-RU")}</td>
                <td>
                  {limit.used.toLocaleString("ru-RU")} ({usedPercent}%)
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
