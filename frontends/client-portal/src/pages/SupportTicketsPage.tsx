import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/http";
import { fetchSupportTickets } from "../api/supportTickets";
import { useAuth } from "../auth/AuthContext";
import { AppEmptyState, AppErrorState, AppLoadingState } from "../components/states";
import type { SupportTicketItem } from "../types/supportTickets";
import { formatDateTime } from "../utils/format";
import {
  supportTicketPriorityLabel,
  supportTicketSlaRemainingLabel,
  supportTicketSlaStatusLabel,
  supportTicketSlaStatusTone,
  supportTicketStatusLabel,
  supportTicketStatusTone,
} from "../utils/supportTickets";

const STATUS_OPTIONS: SupportTicketItem["status"][] = ["OPEN", "IN_PROGRESS", "CLOSED"];

type SupportTicketsErrorState = {
  message: string;
  status?: number;
  correlationId?: string | null;
};

const normalizeError = (error: unknown): SupportTicketsErrorState => {
  if (error instanceof ApiError) {
    return {
      message: error.status >= 500 ? "Сервис временно недоступен" : error.message,
      status: error.status,
      correlationId: error.correlationId,
    };
  }
  if (error instanceof Error) {
    return { message: error.message };
  }
  return { message: "Не удалось загрузить обращения" };
};

export function SupportTicketsPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<SupportTicketItem[]>([]);
  const [status, setStatus] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<SupportTicketsErrorState | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const filters = useMemo(
    () => ({
      status: status || undefined,
    }),
    [status],
  );
  const hasActiveFilters = Boolean(status);

  const resetFilters = () => {
    setStatus("");
  };

  useEffect(() => {
    if (!user) return;
    setIsLoading(true);
    setError(null);
    fetchSupportTickets(user, filters)
      .then((response) => setItems(response.items ?? []))
      .catch((err: unknown) => setError(normalizeError(err)))
      .finally(() => setIsLoading(false));
  }, [user, filters, reloadKey]);

  if (!user) {
    return null;
  }

  return (
    <div className="stack">
      <div className="page-header">
        <div>
          <h1>Поддержка</h1>
          <p className="muted">Создавайте обращения и отслеживайте статус, SLA и связь с canonical case lifecycle.</p>
        </div>
        <Link className="primary" to="/client/support/new">
          Создать обращение
        </Link>
      </div>

      <section className="card">
        <div className="section-title">
          <div>
            <h2>Фильтры обращений</h2>
            <p className="muted">Support inbox остаётся client-owned workflow surface: без пустых broad tabs и без скрытых операторских действий.</p>
          </div>
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

      {isLoading ? (
        <AppLoadingState label="Загружаем обращения..." />
      ) : error ? (
        <AppErrorState
          message={error.message}
          status={error.status}
          correlationId={error.correlationId}
          onRetry={() => setReloadKey((value) => value + 1)}
        />
      ) : items.length === 0 ? (
        <AppEmptyState
          title={hasActiveFilters ? "Обращения не найдены" : "Обращений пока нет"}
          description={
            hasActiveFilters
              ? "Текущие фильтры скрыли все обращения. Сбросьте их, чтобы вернуться к полному inbox."
              : "Создайте первое обращение, если нужна помощь с документами, оплатой или сервисом."
          }
          action={
            hasActiveFilters ? (
              <button type="button" className="secondary" onClick={resetFilters}>
                Сбросить фильтры
              </button>
            ) : (
              <Link className="primary" to="/client/support/new">
                Создать обращение
              </Link>
            )
          }
        />
      ) : (
        <section className="card">
          <div className="table-shell">
            <div className="table-scroll">
              <table className="table neft-table">
                <thead>
                  <tr>
                    <th>Тема</th>
                    <th>Статус</th>
                    <th>Приоритет</th>
                    <th>Связанный кейс</th>
                    <th>SLA первого ответа</th>
                    <th>SLA решения</th>
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
                      <td>
                        {item.case_id ? (
                          <div className="stack" style={{ gap: 4 }}>
                            <Link to={`/cases/${item.case_id}`}>{item.case_id}</Link>
                            <span className="muted small">{item.case_status ?? "—"}</span>
                          </div>
                        ) : (
                          <span className="muted">Создаётся</span>
                        )}
                      </td>
                      <td>
                        <span
                          className={supportTicketSlaStatusTone(item.sla_first_response_status)}
                          title={supportTicketSlaRemainingLabel(
                            item.sla_first_response_remaining_minutes,
                            item.sla_first_response_status,
                          )}
                        >
                          {supportTicketSlaStatusLabel(item.sla_first_response_status)}
                        </span>
                      </td>
                      <td>
                        <span
                          className={supportTicketSlaStatusTone(item.sla_resolution_status)}
                          title={supportTicketSlaRemainingLabel(
                            item.sla_resolution_remaining_minutes,
                            item.sla_resolution_status,
                          )}
                        >
                          {supportTicketSlaStatusLabel(item.sla_resolution_status)}
                        </span>
                      </td>
                      <td>{formatDateTime(item.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="table-footer">
              <div className="table-footer__content">
                <span>Обращений: {items.length}</span>
              </div>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
