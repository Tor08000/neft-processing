import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { AppForbiddenState } from "../components/states";
import { buildExportJobDownloadUrl, listExportJobs, type ExportJob, type ExportJobStatus } from "../api/exports";
import { ApiError, ValidationError } from "../api/http";
import { hasAnyRole } from "../utils/roles";
import { formatDateTime, formatTime } from "../utils/format";

const statusLabelMap: Record<ExportJobStatus, string> = {
  QUEUED: "В очереди",
  RUNNING: "В работе",
  DONE: "Готово",
  FAILED: "Ошибка",
  CANCELED: "Отменено",
  EXPIRED: "Срок хранения истёк",
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

const resolveJobErrorMessage = (job: ExportJob): string => {
  if (job.error_message === "too_many_rows_limit_exceeded") {
    return "Слишком большой объём данных — сузьте фильтры";
  }
  if (job.error_message === "timeout") {
    return "Превышено время формирования отчёта";
  }
  return job.error_message || "Ошибка";
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
  const numberFormatter = useMemo(() => new Intl.NumberFormat("ru-RU"), []);

  const formatEtaSeconds = useCallback((etaSeconds: number): string => {
    if (etaSeconds < 60) {
      return "меньше минуты";
    }
    if (etaSeconds < 3600) {
      return `${Math.ceil(etaSeconds / 60)} мин`;
    }
    if (etaSeconds < 86400) {
      return `${Math.ceil(etaSeconds / 3600)} ч`;
    }
    return `${Math.ceil(etaSeconds / 86400)} дн`;
  }, []);

  const resolveEtaLabel = useCallback(
    (job: ExportJob): string => {
      if (job.eta_at) {
        return `Готово к: ${formatTime(job.eta_at, user?.timezone)}`;
      }
      if (job.eta_seconds == null) {
        return "Оценка времени недоступна";
      }
      return `≈ ${formatEtaSeconds(job.eta_seconds)}`;
    },
    [formatEtaSeconds, user?.timezone],
  );

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
    async (nextCursor: string | null, reset = false, limit = 20, showLoading = true) => {
      if (!user) return;
      if (showLoading) {
        setLoading(true);
      }
      setError("");
      try {
        const response = await listExportJobs(
          {
            status: status ? (status as ExportJobStatus) : undefined,
            report_type: reportType ? (reportType as ExportJob["report_type"]) : undefined,
            cursor: nextCursor,
            limit,
            only_my: onlyMy,
          },
          user,
        );
        setItems((prev) => (reset ? response.items : [...prev, ...response.items]));
        setCursor(response.next_cursor ?? null);
      } catch (err) {
        setError(resolveErrorMessage(err));
      } finally {
        if (showLoading) {
          setLoading(false);
        }
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

  useEffect(() => {
    if (!user) return;
    if (!items.some((item) => item.status === "RUNNING")) return;
    const interval = window.setInterval(() => {
      loadJobs(null, true, Math.max(items.length, 20), false);
    }, 2000);
    return () => window.clearInterval(interval);
  }, [items, loadJobs, user]);

  const renderRowsCell = (job: ExportJob) => {
    if (job.status === "RUNNING") {
      const processed = job.processed_rows ?? 0;
      const hasPercent = typeof job.progress_percent === "number" && job.estimated_total_rows != null;
      const etaLabel = resolveEtaLabel(job);
      if (hasPercent) {
        const percent = Math.min(job.progress_percent ?? 0, 99);
        const total = job.estimated_total_rows ?? 0;
        return (
          <div className="export-progress">
            <div className="export-progress__bar">
              <span className="export-progress__fill" style={{ width: `${percent}%` }} />
            </div>
            <div className="muted export-progress__text">
              {percent}% — {numberFormatter.format(processed)} / {numberFormatter.format(total)} строк
            </div>
            <div className="muted export-progress__text">{etaLabel}</div>
          </div>
        );
      }

      return (
        <div className="export-progress">
          <div className="export-progress__bar is-indeterminate">
            <span className="export-progress__fill" />
          </div>
          <div className="muted export-progress__text">Обработано: {numberFormatter.format(processed)} строк</div>
          <div className="muted export-progress__text">{etaLabel}</div>
        </div>
      );
    }

    if (job.status === "DONE") {
      const total = job.row_count ?? 0;
      return (
        <div className="export-progress">
          <div className="export-progress__bar">
            <span className="export-progress__fill" style={{ width: "100%" }} />
          </div>
          <div className="muted export-progress__text">100% — {numberFormatter.format(total)} строк</div>
        </div>
      );
    }

    return job.row_count ?? "—";
  };

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
                    <td>{formatDateTime(job.created_at, user.timezone)}</td>
                    <td>
                      <span className={statusBadgeMap[job.status]}>{statusLabelMap[job.status]}</span>
                    </td>
                    <td>{renderRowsCell(job)}</td>
                    <td>
                      {job.status === "DONE" ? (
                        <a className="neft-btn neft-btn-primary" href={buildExportJobDownloadUrl(job.id)}>
                          Скачать
                        </a>
                      ) : job.status === "FAILED" ? (
                        <span className="muted">{resolveJobErrorMessage(job)}</span>
                      ) : job.status === "EXPIRED" ? (
                        <span className="muted">Срок хранения истёк</span>
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
