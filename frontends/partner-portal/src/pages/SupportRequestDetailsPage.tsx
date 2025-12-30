import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchSupportRequest } from "../api/support";
import { useAuth } from "../auth/AuthContext";
import { EmptyState } from "../components/EmptyState";
import { ErrorState, LoadingState } from "../components/states";
import type { SupportRequestDetail } from "../types/support";
import { formatDateTime } from "../utils/format";
import { supportStatusLabel, supportStatusTone, supportSubjectLabel } from "../utils/support";
import { useI18n } from "../i18n";

const buildSubjectLink = (subjectType: string, subjectId?: string | null) => {
  if (!subjectId) return null;
  switch (subjectType) {
    case "ORDER":
      return `/orders/${subjectId}`;
    case "DOCUMENT":
      return `/documents/${subjectId}`;
    case "PAYOUT":
      return `/payouts/${subjectId}`;
    case "INTEGRATION":
      return "/integrations";
    default:
      return null;
  }
};

export function SupportRequestDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const { t } = useI18n();
  const [supportRequest, setSupportRequest] = useState<SupportRequestDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id || !user) return;
    setLoading(true);
    fetchSupportRequest(id, user.token)
      .then(setSupportRequest)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id, user]);

  const subjectLink = useMemo(() => {
    if (!supportRequest) return null;
    return buildSubjectLink(supportRequest.subject_type, supportRequest.subject_id);
  }, [supportRequest]);

  if (!id) {
    return <EmptyState title={t("supportRequests.emptyTitle")} description={t("supportRequests.emptyDescription")} />;
  }

  if (loading) {
    return <LoadingState label={t("common.loading")} />;
  }

  if (error) {
    return <ErrorState description={error} />;
  }

  if (!supportRequest) {
    return <EmptyState title={t("supportRequests.emptyTitle")} description={t("supportRequests.emptyDescription")} />;
  }

  return (
    <div className="stack">
      <section className="card">
        <div className="card__header">
          <div>
            <h2>{supportRequest.title}</h2>
            <p className="muted">{t("supportRequests.modal.requestId", { id: supportRequest.id })}</p>
          </div>
          <Link className="ghost" to="/support/requests">
            {t("common.back")}
          </Link>
        </div>
        <div className="meta-grid">
          <div>
            <div className="label">{t("common.status")}</div>
            <span className={`badge ${supportStatusTone(supportRequest.status)}`}>
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
        </div>
        <div className="card__section">
          <h3>{t("supportRequests.fields.description")}</h3>
          <p>{supportRequest.description}</p>
        </div>
      </section>

      <section className="card">
        <h3>Timeline</h3>
        {supportRequest.timeline.length === 0 ? (
          <EmptyState title={t("supportRequests.emptyTitle")} description={t("supportRequests.emptyDescription")} />
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
