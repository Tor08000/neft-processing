import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../api/http";
import { fetchHelpdeskTicketLink } from "../api/helpdesk";
import { closeSupportTicket, createSupportTicketComment, fetchSupportTicket } from "../api/supportTickets";
import { useAuth } from "../auth/AuthContext";
import { AppEmptyState, AppErrorState, AppLoadingState } from "../components/states";
import { ForbiddenPage } from "./ForbiddenPage";
import type { SupportTicketDetail } from "../types/supportTickets";
import type { HelpdeskTicketLink } from "../types/helpdesk";
import { formatDateTime } from "../utils/format";
import { hasAnyRole } from "../utils/roles";
import {
  supportTicketPriorityLabel,
  supportTicketSlaRemainingLabel,
  supportTicketSlaStatusLabel,
  supportTicketSlaStatusTone,
  supportTicketStatusLabel,
  supportTicketStatusTone,
} from "../utils/supportTickets";

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
  const [helpdeskLink, setHelpdeskLink] = useState<HelpdeskTicketLink | null>(null);
  const [comment, setComment] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [loadError, setLoadError] = useState<{
    message: string;
    status?: number;
    correlationId?: string | null;
  } | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

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

  const slaBreached = useMemo(() => {
    if (!ticket) return false;
    return ticket.sla_first_response_status === "BREACHED" || ticket.sla_resolution_status === "BREACHED";
  }, [ticket]);

  const handleError = useCallback((err: unknown) => {
    if (err instanceof ApiError) {
      setLoadError({
        message: err.status >= 500 ? "Сервис временно недоступен" : err.message,
        status: err.status,
        correlationId: err.correlationId,
      });
      return;
    }
    setLoadError({
      message: err instanceof Error ? err.message : "Не удалось загрузить обращение",
    });
  }, []);

  useEffect(() => {
    if (!id || !user) return;
    setIsLoading(true);
    setTicket(null);
    setLoadError(null);
    setActionError(null);
    fetchSupportTicket(id, user)
      .then(setTicket)
      .catch(handleError)
      .finally(() => setIsLoading(false));
  }, [id, user, handleError, reloadKey]);

  useEffect(() => {
    if (!id || !user) return;
    fetchHelpdeskTicketLink(id, user)
      .then((response) => setHelpdeskLink(response.link ?? null))
      .catch((err) => {
        console.error("Не удалось загрузить helpdesk ссылку", err);
        setHelpdeskLink(null);
      });
  }, [id, user]);

  const handleComment = async () => {
    if (!id || !user || !comment.trim()) return;
    setIsSubmitting(true);
    setActionError(null);
    try {
      const updated = await createSupportTicketComment(id, { message: comment }, user);
      setTicket(updated);
      setComment("");
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Не удалось добавить комментарий");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = async () => {
    if (!id || !user) return;
    setIsSubmitting(true);
    setActionError(null);
    try {
      const updated = await closeSupportTicket(id, user);
      setTicket(updated);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Не удалось закрыть обращение");
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

  if (loadError?.status === 403) {
    return <ForbiddenPage />;
  }

  if (loadError?.status === 404) {
    return <AppEmptyState title="Обращение не найдено" description="Проверьте номер обращения и попробуйте снова." />;
  }

  if (loadError?.status && loadError.status >= 500) {
    return (
      <AppErrorState
        message={loadError.message}
        status={loadError.status}
        correlationId={loadError.correlationId}
        onRetry={() => setReloadKey((value) => value + 1)}
      />
    );
  }

  if (loadError) {
    return (
      <AppErrorState
        message={loadError.message}
        status={loadError.status}
        correlationId={loadError.correlationId}
        onRetry={() => setReloadKey((value) => value + 1)}
      />
    );
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
          {slaBreached ? (
            <div>
              <div className="label">SLA</div>
              <span className="badge error">SLA нарушен</span>
            </div>
          ) : null}
          <div>
            <div className="label">Создано</div>
            <div>{formatDateTime(ticket.created_at)}</div>
          </div>
          <div>
            <div className="label">Обновлено</div>
            <div>{formatDateTime(ticket.updated_at)}</div>
          </div>
          <div>
            <div className="label">Canonical case</div>
            {ticket.case_id ? (
              <div className="stack" style={{ gap: 4 }}>
                <Link to={`/cases/${ticket.case_id}`}>{ticket.case_id}</Link>
                <div className="muted small">
                  {ticket.case_status ?? "—"}
                  {ticket.case_queue ? ` · ${ticket.case_queue}` : ""}
                </div>
              </div>
            ) : (
              <div>—</div>
            )}
          </div>
          <div>
            <div className="label">Зеркало в Helpdesk</div>
            {helpdeskLink ? (
              helpdeskLink.status === "LINKED" ? (
                helpdeskLink.external_url ? (
                  <a href={helpdeskLink.external_url} target="_blank" rel="noreferrer">
                    Открыть тикет
                  </a>
                ) : (
                  <div>{helpdeskLink.external_ticket_id ?? "Связано"}</div>
                )
              ) : (
                <span className="badge error">Ошибка синхронизации</span>
              )
            ) : (
              <div>—</div>
            )}
          </div>
        </div>
        <div className="card__section">
          <h3>Описание</h3>
          <p>{ticket.message}</p>
        </div>
      </section>

      <section className="card">
        <div className="card__header">
          <h3>SLA таймеры</h3>
        </div>
        <div className="meta-grid">
          <div>
            <div className="label">First Response SLA</div>
            <span className={supportTicketSlaStatusTone(ticket.sla_first_response_status)}>
              {supportTicketSlaStatusLabel(ticket.sla_first_response_status)}
            </span>
            <div className="muted small">
              {supportTicketSlaRemainingLabel(
                ticket.sla_first_response_remaining_minutes,
                ticket.sla_first_response_status,
              )}
            </div>
          </div>
          <div>
            <div className="label">Resolution SLA</div>
            <span className={supportTicketSlaStatusTone(ticket.sla_resolution_status)}>
              {supportTicketSlaStatusLabel(ticket.sla_resolution_status)}
            </span>
            <div className="muted small">
              {supportTicketSlaRemainingLabel(
                ticket.sla_resolution_remaining_minutes,
                ticket.sla_resolution_status,
              )}
            </div>
          </div>
          <div>
            <div className="label">First Response due_at</div>
            <div>{ticket.first_response_due_at ? formatDateTime(ticket.first_response_due_at) : "—"}</div>
          </div>
          <div>
            <div className="label">Resolution due_at</div>
            <div>{ticket.resolution_due_at ? formatDateTime(ticket.resolution_due_at) : "—"}</div>
          </div>
          <div>
            <div className="label">First Response факт</div>
            <div>{ticket.first_response_at ? formatDateTime(ticket.first_response_at) : "—"}</div>
          </div>
          <div>
            <div className="label">Resolution факт</div>
            <div>{ticket.resolved_at ? formatDateTime(ticket.resolved_at) : "—"}</div>
          </div>
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
          {actionError ? <div className="notice error">{actionError}</div> : null}
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
