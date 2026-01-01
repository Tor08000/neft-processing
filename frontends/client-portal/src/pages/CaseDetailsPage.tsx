import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchCaseDetails } from "../api/cases";
import { useAuth } from "../auth/AuthContext";
import { AppEmptyState, AppErrorState, AppLoadingState } from "../components/states";
import type { CaseDetailsResponse } from "../types/cases";
import { formatDateTime } from "../utils/format";
import { casePriorityLabel, caseStatusLabel, caseStatusTone } from "../utils/cases";

const formatRemaining = (dueAt?: string | null) => {
  if (!dueAt) return "—";
  const due = new Date(dueAt).getTime();
  const now = Date.now();
  const diffMs = due - now;
  if (diffMs <= 0) {
    return "BREACHED";
  }
  const minutes = Math.round(diffMs / 60000);
  if (minutes < 60) return `${minutes}m left`;
  const hours = Math.floor(minutes / 60);
  const rem = minutes % 60;
  return `${hours}h ${rem}m left`;
};

export function CaseDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const [payload, setPayload] = useState<CaseDetailsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!id || !user) return;
    setIsLoading(true);
    fetchCaseDetails(id, user)
      .then(setPayload)
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [id, user]);

  const timeline = useMemo(() => {
    if (!payload) return [];
    const events: Array<{ id: string; label: string; body?: string | null; created_at: string }> = [];
    payload.snapshots?.forEach((snapshot) => {
      events.push({
        id: `snapshot-${snapshot.id}`,
        label: "Snapshot created",
        body: snapshot.note ?? null,
        created_at: snapshot.created_at,
      });
    });
    payload.comments.forEach((comment) => {
      events.push({
        id: `comment-${comment.id}`,
        label: comment.type === "system" ? "Система" : comment.author ? `Комментарий · ${comment.author}` : "Комментарий",
        body: comment.body,
        created_at: comment.created_at,
      });
    });
    return events.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
  }, [payload]);

  const copyLink = useCallback(() => {
    void navigator.clipboard.writeText(window.location.href);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }, []);

  if (!id) {
    return <AppEmptyState title="Кейс не найден" description="Проверьте идентификатор в ссылке." />;
  }
  if (isLoading) {
    return <AppLoadingState label="Загружаем кейс..." />;
  }
  if (error) {
    return <AppErrorState message={error} />;
  }
  if (!payload) {
    return <AppEmptyState title="Кейс не найден" description="Попробуйте обновить страницу." />;
  }

  const latest = payload.latest_snapshot;

  return (
    <div className="stack">
      <section className="card">
        <div className="card__header">
          <div>
            <h2>{payload.case.title}</h2>
            <p className="muted">Case ID: {payload.case.id}</p>
          </div>
          <div className="stack-inline">
            <button type="button" className="ghost" onClick={copyLink}>
              {copied ? "Ссылка скопирована" : "Скопировать ссылку"}
            </button>
            <Link className="ghost" to="/cases">
              К списку кейсов
            </Link>
          </div>
        </div>
        <div className="meta-grid">
          <div>
            <div className="label">Статус</div>
            <span className={caseStatusTone(payload.case.status)}>{caseStatusLabel(payload.case.status)}</span>
          </div>
          <div>
            <div className="label">Приоритет</div>
            <div>{casePriorityLabel(payload.case.priority)}</div>
          </div>
          <div>
            <div className="label">Тип</div>
            <div>{payload.case.kind}</div>
          </div>
          <div>
            <div className="label">Queue</div>
            <div>{payload.case.queue}</div>
          </div>
          <div>
            <div className="label">Entity</div>
            <div>{payload.case.entity_id ?? payload.case.kpi_key ?? "—"}</div>
          </div>
          <div>
            <div className="label">Создано</div>
            <div>{formatDateTime(payload.case.created_at)}</div>
          </div>
          <div>
            <div className="label">First response</div>
            <div>{formatRemaining(payload.case.first_response_due_at ?? null)}</div>
          </div>
          <div>
            <div className="label">Обновлено</div>
            <div>{formatDateTime(payload.case.last_activity_at)}</div>
          </div>
          <div>
            <div className="label">Resolve</div>
            <div>{formatRemaining(payload.case.resolve_due_at ?? null)}</div>
          </div>
        </div>
      </section>

      <section className="card">
        <h3>Timeline</h3>
        {timeline.length === 0 ? (
          <AppEmptyState title="История пока недоступна" description="События появятся после обновлений." />
        ) : (
          <div className="timeline-list">
            {timeline.map((item) => (
              <div className="timeline-item" key={item.id}>
                <div className="timeline-item__meta">
                  <span className="timeline-item__title">{item.label}</span>
                  <span className="muted small">{formatDateTime(item.created_at)}</span>
                </div>
                {item.body ? <div className="timeline-item__body">{item.body}</div> : null}
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="card">
        <h3>Snapshot</h3>
        {latest ? (
          <div className="stack">
            <div className="muted">Создано: {formatDateTime(latest.created_at)}</div>
            {latest.note ? <div className="muted">{latest.note}</div> : null}
            <details>
              <summary>Explain snapshot</summary>
              <pre>{JSON.stringify(latest.explain_snapshot, null, 2)}</pre>
            </details>
            {latest.diff_snapshot ? (
              <details>
                <summary>Diff snapshot</summary>
                <pre>{JSON.stringify(latest.diff_snapshot, null, 2)}</pre>
              </details>
            ) : null}
            {latest.selected_actions ? (
              <details>
                <summary>Selected actions</summary>
                <pre>{JSON.stringify(latest.selected_actions, null, 2)}</pre>
              </details>
            ) : null}
          </div>
        ) : (
          <div className="muted">Снимок недоступен</div>
        )}
      </section>
    </div>
  );
}

export default CaseDetailsPage;
