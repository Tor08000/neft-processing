import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../api/http";
import { closeSupportTicket, createSupportTicketComment, fetchSupportTicket } from "../api/supportTickets";
import { useAuth } from "../auth/AuthContext";
import { AppEmptyState, AppLoadingState } from "../components/states";
import { StatusPage } from "../components/StatusPage";
import { ForbiddenPage } from "./ForbiddenPage";
import type { SupportTicketDetail } from "../types/supportTickets";
import { formatDateTime } from "../utils/format";
import { hasAnyRole } from "../utils/roles";
import { supportTicketPriorityLabel, supportTicketStatusLabel, supportTicketStatusTone } from "../utils/supportTickets";

const decodeJwtPayload = (token: string | null | undefined): Record<string, unknown> | null => {
  if (!token) return null;
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  const normalized = parts[1].replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
  try {
    const decoded = atob(padded);
    return JSON.parse(decoded) as Record<string, unknown>;
  } catch (err) {
    console.error("Failed to decode token payload", err);
    return null;
  }
};

export function SupportTicketDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const [ticket, setTicket] = useState<SupportTicketDetail | null>(null);
  const [comment, setComment] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorStatus, setErrorStatus] = useState<number | null>(null);

  const userId = useMemo(() => {
    const payload = decodeJwtPayload(user?.token);
    const raw = payload?.user_id ?? payload?.sub;
    return raw ? String(raw) : null;
  }, [user?.token]);

  const canClose = useMemo(() => {
    if (!ticket || !user) return false;
    const isAdmin = hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_ADMIN"]);
    const isCreator = userId && ticket.created_by_user_id === userId;
    return isAdmin || Boolean(isCreator);
  }, [ticket, user, userId]);

  const handleError = useCallback((err: unknown) => {
    if (err instanceof ApiError) {
      setErrorStatus(err.status);
      if (err.status >= 500) {
        setError("Сервис временно недоступен");
      }
      return;
    }
    setError(err instanceof Error ? err.message : "Не удалось загрузить обращение");
  }, []);

  useEffect(() => {
    if (!id || !user) return;
    setIsLoading(true);
    setError(null);
    setErrorStatus(null);
    fetchSupportTicket(id, user)
      .then(setTicket)
      .catch(handleError)
      .finally(() => setIsLoading(false));
  }, [id, user, handleError]);

  const handleComment = async () => {
    if (!id || !user || !comment.trim()) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const updated = await createSupportTicketComment(id, { message: comment }, user);
      setTicket(updated);
      setComment("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось добавить комментарий");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = async () => {
    if (!id || !user) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const updated = await closeSupportTicket(id, user);
      setTicket(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось закрыть обращение");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!id) {
    return <AppEmptyState title="Обращение не найдено" description="Проверьте ссылку." />;
  }

  if (isLoading) {
    return <AppLoadingState label="Загружаем обращение..." />;
  }

  if (errorStatus === 403) {
    return <ForbiddenPage />;
  }

  if (errorStatus === 404) {
    return <StatusPage title="Обращение не найдено" description="Проверьте номер обращения и попробуйте снова." />;
  }

  if (errorStatus && errorStatus >= 500) {
    return <StatusPage title="Сервис недоступен" description="Попробуйте обновить страницу позже." />;
  }

  if (!ticket) {
    return <AppEmptyState title="Обращение не найдено" description="Попробуйте обновить страницу." />;
  }

  return (
    <div className="stack">
      <section className="card">
        <div className="card__header">
          <div>
            <h2>{ticket.subject}</h2>
            <p className="muted">Номер обращения: {ticket.id}</p>
          </div>
          <Link className="ghost" to="/client/support">
            К списку обращений
          </Link>
        </div>
        <div className="meta-grid">
          <div>
            <div className="label">Статус</div>
            <span className={supportTicketStatusTone(ticket.status)}>{supportTicketStatusLabel(ticket.status)}</span>
          </div>
          <div>
            <div className="label">Приоритет</div>
            <div>{supportTicketPriorityLabel(ticket.priority)}</div>
          </div>
          <div>
            <div className="label">Создано</div>
            <div>{formatDateTime(ticket.created_at)}</div>
          </div>
          <div>
            <div className="label">Обновлено</div>
            <div>{formatDateTime(ticket.updated_at)}</div>
          </div>
        </div>
        <div className="card__section">
          <h3>Описание</h3>
          <p>{ticket.message}</p>
        </div>
      </section>

      <section className="card">
        <div className="card__header">
          <h3>Комментарии</h3>
          {canClose && ticket.status !== "CLOSED" ? (
            <button className="ghost" type="button" onClick={() => void handleClose()} disabled={isSubmitting}>
              Закрыть обращение
            </button>
          ) : null}
        </div>
        {ticket.comments.length === 0 ? (
          <AppEmptyState title="Комментариев пока нет" description="Добавьте уточнение, если нужно." />
        ) : (
          <div className="timeline-list">
            {ticket.comments.map((item, index) => (
              <div className="timeline-item" key={`${item.user_id}-${item.created_at}-${index}`}>
                <div className="timeline-item__meta">
                  <span className="timeline-item__title">{item.user_id}</span>
                  <span className="muted small">{formatDateTime(item.created_at)}</span>
                </div>
                <div>{item.message}</div>
              </div>
            ))}
          </div>
        )}
        <div className="card__section">
          <label className="filter">
            Добавить комментарий
            <textarea rows={4} value={comment} onChange={(event) => setComment(event.target.value)} />
          </label>
          {error ? <div className="notice error">{error}</div> : null}
          <div className="actions">
            <button
              className="primary"
              type="button"
              onClick={() => void handleComment()}
              disabled={!comment.trim() || isSubmitting}
            >
              Отправить
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
