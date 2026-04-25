import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { fetchSupportRequest } from "../api/support";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { usePortal } from "../auth/PortalContext";
import { resolvePartnerPortalSurface } from "../access/partnerWorkspace";
import { EmptyState } from "../components/EmptyState";
import { ErrorState, ForbiddenState, LoadingState } from "../components/states";
import type { SupportRequestDetail } from "../types/support";
import { formatDateTime } from "../utils/format";
import { supportStatusLabel, supportStatusTone, supportSubjectLabel } from "../utils/support";

const buildSubjectLink = (
  subjectType: string,
  subjectId: string | null | undefined,
  options: { hasFinance: boolean; hasMarketplace: boolean },
) => {
  switch (subjectType) {
    case "ORDER":
      return options.hasMarketplace && subjectId ? `/orders/${subjectId}` : null;
    case "DOCUMENT":
      return options.hasFinance ? "/documents" : null;
    case "PAYOUT":
      return options.hasFinance ? "/payouts" : null;
    case "SETTLEMENT":
      return options.hasFinance ? "/finance" : null;
    default:
      return null;
  }
};

type ApiErrorState = {
  message: string;
  status?: number;
  correlationId?: string | null;
};

const normalizeError = (error: unknown, fallback: string): ApiErrorState => {
  if (error instanceof ApiError) {
    return { message: error.message, status: error.status, correlationId: error.correlationId };
  }
  if (error instanceof Error) {
    return { message: error.message };
  }
  return { message: fallback };
};

const formatErrorDescription = (
  error: ApiErrorState,
  translate: (key: string, params?: Record<string, unknown>) => string,
) => {
  const parts = [error.message];
  if (error.status) {
    parts.push(translate("errors.errorCode", { code: error.status }));
  }
  return parts.join(" · ");
};

const formatRemaining = (dueAt?: string | null) => {
  if (!dueAt) return "—";
  const due = new Date(dueAt).getTime();
  const now = Date.now();
  const diffMs = due - now;
  if (diffMs <= 0) return "BREACHED";
  const minutes = Math.round(diffMs / 60000);
  if (minutes < 60) return `${minutes}m left`;
  const hours = Math.floor(minutes / 60);
  const rem = minutes % 60;
  return `${hours}h ${rem}m left`;
};

export function SupportRequestDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const { portal } = usePortal();
  const { t } = useTranslation();
  const [supportRequest, setSupportRequest] = useState<SupportRequestDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiErrorState | null>(null);
  const surface = useMemo(() => resolvePartnerPortalSurface(portal), [portal]);

  const loadSupportRequest = useCallback(() => {
    if (!id || !user) return Promise.resolve();
    setLoading(true);
    setError(null);
    return fetchSupportRequest(id, user.token)
      .then((data) => {
        setSupportRequest(data);
      })
      .catch((err: unknown) => {
        setSupportRequest(null);
        setError(normalizeError(err, t("supportRequests.errors.loadFailed")));
      })
      .finally(() => setLoading(false));
  }, [id, t, user]);

  useEffect(() => {
    void loadSupportRequest();
  }, [loadSupportRequest]);

  const subjectLink = useMemo(() => {
    if (!supportRequest) return null;
    return buildSubjectLink(supportRequest.subject_type, supportRequest.subject_id, {
      hasFinance: surface.workspaceCodes.has("finance"),
      hasMarketplace: surface.workspaceCodes.has("marketplace"),
    });
  }, [supportRequest, surface]);
  const canonicalCaseLink = supportRequest ? `/cases/${supportRequest.id}` : null;

  if (!id) {
    return (
      <EmptyState
        title={t("supportRequests.detailNotFoundTitle")}
        description={t("supportRequests.detailNotFoundDescription")}
        action={
          <Link className="ghost" to="/support/requests">
            {t("common.back")}
          </Link>
        }
      />
    );
  }

  if (loading) {
    return <LoadingState label={t("common.loading")} />;
  }

  if (error?.status === 403) {
    return (
      <ForbiddenState
        title={t("states.forbiddenTitle")}
        description={t("states.forbiddenDescription")}
        action={
          <Link className="ghost" to="/support/requests">
            {t("common.back")}
          </Link>
        }
      />
    );
  }

  if (error?.status === 404) {
    return (
      <EmptyState
        title={t("supportRequests.detailNotFoundTitle")}
        description={t("supportRequests.detailNotFoundDescription")}
        action={
          <Link className="ghost" to="/support/requests">
            {t("common.back")}
          </Link>
        }
      />
    );
  }

  if (error) {
    return (
      <ErrorState
        title={t("supportRequests.errors.loadFailed")}
        description={formatErrorDescription(error, t)}
        correlationId={error.correlationId}
        onRetry={() => void loadSupportRequest()}
        retryLabel={t("actions.retry")}
      />
    );
  }

  if (!supportRequest) {
    return (
      <EmptyState
        title={t("supportRequests.detailNotFoundTitle")}
        description={t("supportRequests.detailNotFoundDescription")}
        action={
          <Link className="ghost" to="/support/requests">
            {t("common.back")}
          </Link>
        }
      />
    );
  }

  const sourceLabel = supportRequest.case_source_ref_type
    ? `${supportRequest.case_source_ref_type}${supportRequest.case_source_ref_id ? ` / ${supportRequest.case_source_ref_id}` : ""}`
    : t("common.notAvailable");

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
            <div className="label">{t("supportRequests.fields.subject")}</div>
            {subjectLink ? (
              <Link to={subjectLink}>{supportSubjectLabel(supportRequest.subject_type, supportRequest.subject_id)}</Link>
            ) : (
              <div>{supportSubjectLabel(supportRequest.subject_type, supportRequest.subject_id)}</div>
            )}
          </div>
          <div>
            <div className="label">{t("supportRequests.fields.created")}</div>
            <div>{formatDateTime(supportRequest.created_at)}</div>
          </div>
          <div>
            <div className="label">{t("supportRequests.fields.updated")}</div>
            <div>{formatDateTime(supportRequest.updated_at)}</div>
          </div>
          <div>
            <div className="label">Case ID</div>
            {canonicalCaseLink ? (
              <Link className="mono" to={canonicalCaseLink}>
                {supportRequest.id}
              </Link>
            ) : (
              <div className="mono">{supportRequest.id}</div>
            )}
          </div>
          <div>
            <div className="label">Queue</div>
            <div>{supportRequest.case_queue ?? t("common.notAvailable")}</div>
          </div>
          <div>
            <div className="label">Source</div>
            <div>{sourceLabel}</div>
          </div>
          <div>
            <div className="label">First response</div>
            <div>{formatRemaining(supportRequest.case_first_response_due_at)}</div>
          </div>
          <div>
            <div className="label">Resolve</div>
            <div>{formatRemaining(supportRequest.case_resolve_due_at)}</div>
          </div>
        </div>
        <div className="card__section">
          <h3>{t("supportRequests.fields.description")}</h3>
          <p>{supportRequest.description}</p>
        </div>
      </section>

      <section className="card">
        <h3>{t("supportRequests.sections.timeline")}</h3>
        {supportRequest.timeline.length === 0 ? (
          <EmptyState
            title={t("supportRequests.timelineEmptyTitle")}
            description={t("supportRequests.timelineEmptyDescription")}
          />
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
