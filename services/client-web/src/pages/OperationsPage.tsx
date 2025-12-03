import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchOperations, handleUnauthorized } from "../api";
import type { Operation } from "../types";

interface OperationsPageProps {
  token: string;
}

export function OperationsPage({ token }: OperationsPageProps) {
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [page, setPage] = useState(0);

  const { data, isLoading, error } = useQuery({
    queryKey: ["operations", token, statusFilter, page],
    queryFn: () => fetchOperations(token, { status: statusFilter, limit: 20, offset: page * 20 }),
  });

  const operations: Operation[] = data?.items ?? [];

  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / 20));

  if (error && handleUnauthorized(error)) {
    return null;
  }

  return (
    <div className="card">
      <div className="section-title">
        <h2>Операции</h2>
        <div className="filters">
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">Все статусы</option>
            <option value="success">Успешные</option>
            <option value="pending">В обработке</option>
            <option value="failed">Отклонено</option>
          </select>
        </div>
      </div>

      {isLoading && <div>Загрузка...</div>}
      {error && <div className="error">Не удалось загрузить операции</div>}

      {!isLoading && !error && (
        <>
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
              {operations.map((operation) => (
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

          <div className="pagination">
            <button disabled={page === 0} onClick={() => setPage((p) => Math.max(0, p - 1))}>
              Назад
            </button>
            <span>
              Страница {page + 1} из {totalPages}
            </span>
            <button disabled={page + 1 >= totalPages} onClick={() => setPage((p) => p + 1)}>
              Вперёд
            </button>
          </div>
        </>
      )}
    </div>
  );
}
