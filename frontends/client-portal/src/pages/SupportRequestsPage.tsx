import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchSupportRequests } from "../api/support";
import { useAuth } from "../auth/AuthContext";
import { AppEmptyState, AppErrorState, AppLoadingState } from "../components/states";
import type { SupportRequestItem } from "../types/support";
import { formatDateTime } from "../utils/format";
import { supportStatusLabel, supportStatusTone, supportSubjectLabel } from "../utils/support";

const STATUS_OPTIONS = ["OPEN", "IN_PROGRESS", "WAITING", "RESOLVED", "CLOSED"];
const SUBJECT_OPTIONS = ["ORDER", "DOCUMENT", "PAYOUT", "SETTLEMENT", "INTEGRATION", "OTHER"];

export function SupportRequestsPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<SupportRequestItem[]>([]);
  const [status, setStatus] = useState("");
  const [subjectType, setSubjectType] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const filters = useMemo(
    () => ({
      status: status || undefined,
      subject_type: subjectType || undefined,
      from: from || undefined,
      to: to || undefined,
    }),
    [status, subjectType, from, to],
  );

  useEffect(() => {
    if (!user) return;
    setIsLoading(true);
    fetchSupportRequests(user, filters)
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
            <h2>Запросы / Обращения</h2>
            <p className="muted">История обращений по заказам, документам и выплатам.</p>
          </div>
        </div>
        <div className="filters">
          <label className="filter">
            Статус
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="">Все</option>
              {STATUS_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {supportStatusLabel(option as SupportRequestItem["status"])}
                </option>
              ))}
            </select>
          </label>
          <label className="filter">
            Тип объекта
            <select value={subjectType} onChange={(event) => setSubjectType(event.target.value)}>
              <option value="">Все</option>
              {SUBJECT_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {supportSubjectLabel(option as SupportRequestItem["subject_type"])}
                </option>
              ))}
            </select>
          </label>
          <label className="filter">
            Период с
            <input type="date" value={from} onChange={(event) => setFrom(event.target.value)} />
          </label>
          <label className="filter">
            по
            <input type="date" value={to} onChange={(event) => setTo(event.target.value)} />
          </label>
        </div>
      </section>

      {items.length === 0 ? (
        <AppEmptyState
          title="У вас пока нет обращений."
          description="Создайте запрос, если возникла проблема с заказом или документом."
        />
      ) : (
        <section className="card">
          <table className="data-table">
            <thead>
              <tr>
                <th>Дата</th>
                <th>Тема</th>
                <th>Объект</th>
                <th>Статус</th>
                <th>Обновлено</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td>{formatDateTime(item.created_at)}</td>
                  <td>
                    <Link to={`/support/requests/${item.id}`}>{item.title}</Link>
                  </td>
                  <td>{supportSubjectLabel(item.subject_type, item.subject_id)}</td>
                  <td>
                    <span className={supportStatusTone(item.status)}>{supportStatusLabel(item.status)}</span>
                  </td>
                  <td>{formatDateTime(item.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
