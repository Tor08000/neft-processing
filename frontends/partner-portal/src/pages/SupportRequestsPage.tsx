import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchSupportRequests } from "../api/support";
import { useAuth } from "../auth/AuthContext";
import { EmptyState } from "../components/EmptyState";
import { ErrorState, LoadingState } from "../components/states";
import type { SupportRequestItem } from "../types/support";
import { formatDateTime } from "../utils/format";
import { supportStatusLabel, supportStatusTone, supportSubjectLabel } from "../utils/support";
import { useI18n } from "../i18n";

const STATUS_OPTIONS = ["OPEN", "IN_PROGRESS", "WAITING", "RESOLVED", "CLOSED"];
const SUBJECT_OPTIONS = ["ORDER", "DOCUMENT", "PAYOUT", "SETTLEMENT", "INTEGRATION", "OTHER"];

export function SupportRequestsPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [items, setItems] = useState<SupportRequestItem[]>([]);
  const [status, setStatus] = useState("");
  const [subjectType, setSubjectType] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [loading, setLoading] = useState(true);
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
    setLoading(true);
    fetchSupportRequests(user.token, filters)
      .then((response) => setItems(response.items))
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [user, filters]);

  if (!user) {
    return null;
  }

  if (loading) {
    return <LoadingState label={t("common.loading")} />;
  }

  if (error) {
    return <ErrorState description={error} />;
  }

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <div>
            <h2>{t("supportRequests.title")}</h2>
            <p className="muted">{t("supportRequests.subtitle")}</p>
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
            Тип объекта
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

      {items.length === 0 ? (
        <EmptyState title={t("supportRequests.emptyTitle")} description={t("supportRequests.emptyDescription")} />
      ) : (
        <section className="card">
          <table className="data-table">
            <thead>
              <tr>
                <th>Дата</th>
                <th>{t("supportRequests.fields.title")}</th>
                <th>Объект</th>
                <th>{t("common.status")}</th>
                <th>{t("common.actions")}</th>
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
                    <span className={`badge ${supportStatusTone(item.status)}`}>{supportStatusLabel(item.status)}</span>
                  </td>
                  <td>
                    <Link to={`/support/requests/${item.id}`}>{t("common.open")}</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
