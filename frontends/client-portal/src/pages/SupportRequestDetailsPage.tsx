import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchSupportRequest } from "../api/support";
import { useAuth } from "../auth/AuthContext";
import { AppEmptyState, AppErrorState, AppLoadingState } from "../components/states";
import type { SupportRequestDetail } from "../types/support";
import { formatDateTime } from "../utils/format";
import { supportStatusLabel, supportStatusTone, supportSubjectLabel } from "../utils/support";

const buildSubjectLink = (subjectType: string, subjectId?: string | null) => {
  if (!subjectId) return null;
  switch (subjectType) {
    case "ORDER":
      return `/operations/${subjectId}`;
    case "DOCUMENT":
      return `/documents/${subjectId}`;
    case "PAYOUT":
      return null;
    case "SETTLEMENT":
      return null;
    case "INTEGRATION":
      return null;
    default:
      return null;
  }
};

export function SupportRequestDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const [supportRequest, setSupportRequest] = useState<SupportRequestDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id || !user) return;
    setIsLoading(true);
    fetchSupportRequest(id, user)
      .then(setSupportRequest)
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [id, user]);

  const subjectLink = useMemo(() => {
    if (!supportRequest) return null;
    return buildSubjectLink(supportRequest.subject_type, supportRequest.subject_id);
  }, [supportRequest]);

  if (!id) {
    return <AppEmptyState title="Обращение не найдено" description="Проверьте идентификатор в ссылке." />;
  }

  if (isLoading) {
    return <AppLoadingState label="Загружаем обращение..." />;
  }

  if (error) {
    return <AppErrorState message={error} />;
  }

  if (!supportRequest) {
    return <AppEmptyState title="Обращение не найдено" description="Попробуйте обновить страницу." />;
  }

  return (
    <div className="stack">
      <section className="card">
        <div className="card__header">
          <div>
            <h2>{supportRequest.title}</h2>
            <p className="muted">Номер обращения: {supportRequest.id}</p>
          </div>
          <Link className="ghost" to="/support/requests">
            К списку обращений
          </Link>
        </div>
        <div className="meta-grid">
          <div>
            <div className="label">Статус</div>
            <span className={supportStatusTone(supportRequest.status)}>
              {supportStatusLabel(supportRequest.status)}
            </span>
          </div>
          <div>
            <div className="label">Объект</div>
            {subjectLink ? (
              <Link to={subjectLink}>{supportSubjectLabel(supportRequest.subject_type, supportRequest.subject_id)}</Link>
            ) : (
              <div>{supportSubjectLabel(supportRequest.subject_type, supportRequest.subject_id)}</div>
            )}
          </div>
          <div>
            <div className="label">Создано</div>
            <div>{formatDateTime(supportRequest.created_at)}</div>
          </div>
          <div>
            <div className="label">Обновлено</div>
            <div>{formatDateTime(supportRequest.updated_at)}</div>
          </div>
          <div>
            <div className="label">Correlation ID</div>
            <div>{supportRequest.correlation_id ?? "—"}</div>
          </div>
          <div>
            <div className="label">Event ID</div>
            <div>{supportRequest.event_id ?? "—"}</div>
          </div>
        </div>
        <div className="card__section">
          <h3>Описание</h3>
          <p>{supportRequest.description}</p>
        </div>
      </section>

      <section className="card">
        <h3>Timeline</h3>
        {supportRequest.timeline.length === 0 ? (
          <AppEmptyState title="История пока недоступна" description="Статусы появятся после обработки." />
        ) : (
          <div className="timeline-list">
            {supportRequest.timeline.map((event, index) => (
              <div className="timeline-item" key={`${event.status}-${index}`}>
                <div className="timeline-item__meta">
                  <span className="timeline-item__title">{supportStatusLabel(event.status)}</span>
                  <span className="muted small">{formatDateTime(event.occurred_at)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
