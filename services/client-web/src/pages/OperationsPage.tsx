import { useMemo, useState } from "react";
import type { Operation } from "../types";

interface OperationsPageProps {
  operations: Operation[];
}

export function OperationsPage({ operations }: OperationsPageProps) {
  const [typeFilter, setTypeFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("");

  const filtered = useMemo(() => {
    return operations.filter((op) => {
      const matchesType = typeFilter ? op.type === typeFilter : true;
      const matchesStatus = statusFilter ? op.status === statusFilter : true;
      return matchesType && matchesStatus;
    });
  }, [operations, statusFilter, typeFilter]);

  return (
    <div className="card">
      <div className="section-title">
        <h2>Операции</h2>
        <div className="filters">
          <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
            <option value="">Все типы</option>
            <option value="auth">Авторизация</option>
            <option value="capture">Списание</option>
            <option value="refund">Возврат</option>
          </select>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">Все статусы</option>
            <option value="success">Успешные</option>
            <option value="pending">В обработке</option>
            <option value="failed">Отклонено</option>
          </select>
        </div>
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
          {filtered.map((operation) => (
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
  );
}
