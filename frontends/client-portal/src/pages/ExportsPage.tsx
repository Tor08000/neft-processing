import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { AppForbiddenState } from "../components/states";
import { buildExportJobDownloadUrl, listExportJobs, type ExportJob, type ExportJobStatus } from "../api/exports";
import { ApiError, ValidationError } from "../api/http";
import { hasAnyRole } from "../utils/roles";

const statusLabelMap: Record<ExportJobStatus, string> = {
  QUEUED: "В очереди",
  RUNNING: "В работе",
  DONE: "Готово",
  FAILED: "Ошибка",
  CANCELED: "Отменено",
  EXPIRED: "Истекло",
};

const statusBadgeMap: Record<ExportJobStatus, string> = {
  QUEUED: "badge badge-muted",
  RUNNING: "badge badge-info",
  DONE: "badge badge-success",
  FAILED: "badge badge-error",
  CANCELED: "badge badge-warning",
  EXPIRED: "badge badge-warning",
};

const resolveErrorMessage = (error: unknown): string => {
  if (error instanceof ValidationError) {
    return "Ошибка валидации";
  }
  if (error instanceof ApiError) {
    if (error.status === 403) {
      return "Доступ запрещён";
    }
    return error.message || "Ошибка загрузки";
  }
  if (error instanceof Error) {
    return error.message || "Ошибка загрузки";
  }
  return "Ошибка загрузки";
};

export function ExportsPage() {
  const { user } = useAuth();
  const [status, setStatus] = useState("");
  const [reportType, setReportType] = useState("");
  const [onlyMy, setOnlyMy] = useState(true);
  const [items, setItems] = useState<ExportJob[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const canAccess = useMemo(
    () =>
      hasAnyRole(user, [
        "CLIENT_OWNER",
        "CLIENT_ADMIN",
        "CLIENT_ACCOUNTANT",
        "CLIENT_FLEET_MANAGER",
      ]),
    [user],
  );

  const loadJobs = useCallback(
    async (nextCursor: string | null, reset = false) => {
      if (!user) return;
      setLoading(true);
      setError("");
      try {
        const response = await listExportJobs(
          {
            status: status ? (status as ExportJobStatus) : undefined,
            report_type: reportType ? (reportType as ExportJob["report_type"]) : undefined,
            cursor: nextCursor,
            limit: 20,
            only_my: onlyMy,
          },
          user,
        );
        setItems((prev) => (reset ? response.items : [...prev, ...response.items]));
        setCursor(response.next_cursor ?? null);
      } catch (err) {
        setError(resolveErrorMessage(err));
      } finally {
        setLoading(false);
      }
    },
    [onlyMy, reportType, status, user],
  );

  useEffect(() => {
    setItems([]);
    setCursor(null);
    if (user) {
      loadJobs(null, true);
    }
  }, [loadJobs, user]);

  if (!user) {
    return <AppForbiddenState message="Требуется авторизация" />;
  }

  if (!canAccess) {
    return <AppForbiddenState message="Недостаточно прав для доступа к экспортам" />;
  }

  return (
    <div className="stack">
      <section className="card">
        <div className="card__header">
          <div>
            <h2>Exports</h2>
            <p className="muted">История задач экспорта с фильтрами, статусом и ссылкой на скачивание.</p>
          </div>
        </div>
        <div className="filters">
          <div className="filter">
            <label htmlFor="export-status">Статус</label>
            <select id="export-status" value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="">Все</option>
              {Object.entries(statusLabelMap).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div className="filter">
            <label htmlFor="export-type">Тип отчёта</label>
            <select id="export-type" value={reportType} onChange={(event) => setReportType(event.target.value)}>
              <option value="">Все</option>
              <option value="cards">Cards</option>
              <option value="users">Users</option>
              <option value="transactions">Transactions</option>
              <option value="documents">Documents</option>
              <option value="audit">Audit</option>
              <option value="support">Support</option>
            </select>
          </div>
          <div className="filter">
            <label htmlFor="export-only-my">Только мои</label>
            <select id="export-only-my" value={onlyMy ? "yes" : "no"} onChange={(event) => setOnlyMy(event.target.value === "yes")}>
              <option value="yes">Да</option>
              <option value="no">Нет</option>
            </select>
          </div>
          <div className="filter">
            <label>&nbsp;</label>
            <button type="button" className="neft-btn" disabled={loading} onClick={() => loadJobs(null, true)}>
              {loading ? "Обновляем…" : "Обновить"}
            </button>
          </div>
        </div>
        {error ? <div className="muted">{error}</div> : null}
      </section>

      <section className="card">
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Отчёт</th>
                <th>Формат</th>
                <th>Создан</th>
                <th>Статус</th>
                <th>Строки</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="muted">
                    {loading ? "Загрузка…" : "Нет экспортов"}
                  </td>
                </tr>
              ) : (
                items.map((job) => (
                  <tr key={job.id}>
                    <td>
                      <div>{job.report_type}</div>
                      <div className="muted">{job.file_name || "—"}</div>
                    </td>
                    <td>{job.format}</td>
                    <td>{new Date(job.created_at).toLocaleString()}</td>
                    <td>
                      <span className={statusBadgeMap[job.status]}>{statusLabelMap[job.status]}</span>
                    </td>
                    <td>{job.row_count ?? "—"}</td>
                    <td>
                      {job.status === "DONE" ? (
                        <a className="neft-btn neft-btn-primary" href={buildExportJobDownloadUrl(job.id)}>
                          Скачать
                        </a>
                      ) : job.status === "FAILED" ? (
                        <span className="muted">{job.error_message || "Ошибка"}</span>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        {cursor ? (
          <div className="card__footer">
            <button type="button" className="neft-btn" disabled={loading} onClick={() => loadJobs(cursor, false)}>
              {loading ? "Загрузка…" : "Показать ещё"}
            </button>
          </div>
        ) : null}
      </section>
    </div>
  );
}
