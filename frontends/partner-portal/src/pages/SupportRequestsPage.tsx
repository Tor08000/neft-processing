import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { fetchSupportRequests } from "../api/support";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { EmptyState } from "../components/EmptyState";
import { ErrorState, ForbiddenState, LoadingState } from "../components/states";
import type { SupportRequestItem } from "../types/support";
import { formatDateTime } from "../utils/format";
import { supportStatusLabel, supportStatusTone, supportSubjectLabel } from "../utils/support";

const STATUS_OPTIONS = ["OPEN", "IN_PROGRESS", "WAITING", "RESOLVED", "CLOSED"];
const SUBJECT_OPTIONS = ["ORDER", "DOCUMENT", "PAYOUT", "SETTLEMENT", "INTEGRATION", "OTHER"];

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

export function SupportRequestsPage() {
  const { user } = useAuth();
  const { t } = useTranslation();
  const [items, setItems] = useState<SupportRequestItem[]>([]);
  const [status, setStatus] = useState("");
  const [subjectType, setSubjectType] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiErrorState | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const filters = useMemo(
    () => ({
      status: status || undefined,
      subject_type: subjectType || undefined,
      from: from || undefined,
      to: to || undefined,
    }),
    [status, subjectType, from, to],
  );
  const hasActiveFilters = Boolean(status || subjectType || from || to);

  const resetFilters = () => {
    setStatus("");
    setSubjectType("");
    setFrom("");
    setTo("");
  };

  useEffect(() => {
    if (!user) return;
    setLoading(true);
    setError(null);
    fetchSupportRequests(user.token, filters)
      .then((response) => setItems(response.items))
      .catch((err: unknown) => setError(normalizeError(err, t("supportRequests.errors.loadFailed"))))
      .finally(() => setLoading(false));
  }, [filters, reloadKey, t, user]);

  if (!user) {
    return null;
  }

  if (!loading && error?.status === 403) {
    return (
      <ForbiddenState
        title={t("states.forbiddenTitle")}
        description={t("states.forbiddenDescription")}
        action={
          <Link to="/dashboard" className="ghost">
            {t("supportRequests.list.backToDashboard")}
          </Link>
        }
      />
    );
  }

  return (
    <div className="stack">
      <div className="page-header">
        <div>
          <h1>{t("supportRequests.title")}</h1>
          <p className="muted">{t("supportRequests.subtitle")}</p>
        </div>
      </div>

      <section className="card">
        <div className="section-title">
          <div>
            <h2>{t("supportRequests.list.filtersTitle")}</h2>
            <p className="muted">{t("supportRequests.list.filtersDescription")}</p>
          </div>
        </div>
        <div className="filters">
          <label className="filter">
            {t("common.status")}
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="">{t("common.all")}</option>
              {STATUS_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {supportStatusLabel(option as SupportRequestItem["status"])}
                </option>
              ))}
            </select>
          </label>
          <label className="filter">
            {t("supportRequests.fields.subjectType")}
            <select value={subjectType} onChange={(event) => setSubjectType(event.target.value)}>
              <option value="">{t("common.all")}</option>
              {SUBJECT_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {supportSubjectLabel(option as SupportRequestItem["subject_type"])}
                </option>
              ))}
            </select>
          </label>
          <label className="filter">
            {t("common.from")}
            <input type="date" value={from} onChange={(event) => setFrom(event.target.value)} />
          </label>
          <label className="filter">
            {t("common.to")}
            <input type="date" value={to} onChange={(event) => setTo(event.target.value)} />
          </label>
        </div>
      </section>

      {loading ? (
        <LoadingState label={t("common.loading")} />
      ) : error ? (
        <ErrorState
          title={t("supportRequests.errors.loadFailed")}
          description={formatErrorDescription(error, t)}
          correlationId={error.correlationId}
          onRetry={() => setReloadKey((value) => value + 1)}
          retryLabel={t("actions.retry")}
        />
      ) : items.length === 0 ? (
        <EmptyState
          title={hasActiveFilters ? t("supportRequests.list.filteredTitle") : t("supportRequests.emptyTitle")}
          description={
            hasActiveFilters
              ? t("supportRequests.list.filteredDescription")
              : t("supportRequests.emptyDescription")
          }
          action={
            hasActiveFilters ? (
              <button type="button" className="secondary" onClick={resetFilters}>
                {t("supportRequests.list.resetFilters")}
              </button>
            ) : (
              <Link to="/dashboard" className="ghost">
                {t("supportRequests.list.backToDashboard")}
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
                    <th>{t("supportRequests.fields.createdAt")}</th>
                    <th>{t("supportRequests.fields.title")}</th>
                    <th>{t("supportRequests.fields.subject")}</th>
                    <th>{t("common.status")}</th>
                    <th>{t("common.actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item.id}>
                      <td>{formatDateTime(item.created_at)}</td>
                      <td>
                        <Link to={`/cases/${item.id}`}>{item.title}</Link>
                      </td>
                      <td>{supportSubjectLabel(item.subject_type, item.subject_id)}</td>
                      <td>
                        <span className={`badge ${supportStatusTone(item.status)}`}>{supportStatusLabel(item.status)}</span>
                      </td>
                      <td>
                        <Link to={`/cases/${item.id}`}>{t("common.open")}</Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="table-footer">
              <div className="table-footer__content">
                <span>Requests: {items.length}</span>
              </div>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
