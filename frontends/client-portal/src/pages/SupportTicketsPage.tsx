import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchSupportTickets } from "../api/supportTickets";
import { useAuth } from "../auth/AuthContext";
import { AppEmptyState, AppErrorState, AppLoadingState } from "../components/states";
import type { SupportTicketItem } from "../types/supportTickets";
import { formatDateTime } from "../utils/format";
import { supportTicketPriorityLabel, supportTicketStatusLabel, supportTicketStatusTone } from "../utils/supportTickets";

const STATUS_OPTIONS: SupportTicketItem["status"][] = ["OPEN", "IN_PROGRESS", "CLOSED"];

export function SupportTicketsPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<SupportTicketItem[]>([]);
  const [status, setStatus] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const filters = useMemo(
    () => ({
      status: status || undefined,
    }),
    [status],
  );

  useEffect(() => {
    if (!user) return;
    setIsLoading(true);
    fetchSupportTickets(user, filters)
      .then((response) => setItems(response.items))
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [user, filters]);

  if (!user) {
    return null;
  }

  if (isLoading) {
    return <AppLoadingState label="Загружаем обращения..." />;
  }

  if (error) {
    return <AppErrorState message={error} />;
  }

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <div>
            <h2>Поддержка</h2>
            <p className="muted">Создавайте обращения и отслеживайте статус.</p>
          </div>
          <Link className="primary" to="/client/support/new">
            Создать обращение
          </Link>
        </div>
        <div className="filters">
          <label className="filter">
            Статус
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="">Все</option>
              {STATUS_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {supportTicketStatusLabel(option)}
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>

      {items.length === 0 ? (
        <AppEmptyState title="Обращений пока нет" description="Создайте первое обращение, если нужна помощь." />
      ) : (
        <section className="card">
          <table className="data-table">
            <thead>
              <tr>
                <th>Тема</th>
                <th>Статус</th>
                <th>Приоритет</th>
                <th>Создано</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td>
                    <Link to={`/client/support/${item.id}`}>{item.subject}</Link>
                  </td>
                  <td>
                    <span className={supportTicketStatusTone(item.status)}>{supportTicketStatusLabel(item.status)}</span>
                  </td>
                  <td>{supportTicketPriorityLabel(item.priority)}</td>
                  <td>{formatDateTime(item.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
