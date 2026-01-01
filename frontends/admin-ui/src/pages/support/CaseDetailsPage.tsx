import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  addCaseComment,
  fetchCaseDetails,
  updateCase,
  type CaseComment,
  type CaseDetailsResponse,
  type CasePriority,
  type CaseStatus,
} from "../../api/cases";
import { JsonViewer } from "../../components/common/JsonViewer";
import { Toast } from "../../components/common/Toast";
import { useToast } from "../../components/Toast/useToast";

const STATUS_OPTIONS: CaseStatus[] = ["TRIAGE", "IN_PROGRESS", "RESOLVED", "CLOSED"];
const PRIORITY_OPTIONS: CasePriority[] = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];

const formatTimestamp = (value?: string | null) => {
  if (!value) return "—";
  return new Date(value).toLocaleString("ru-RU");
};

const statusTone = (status: CaseStatus) => {
  if (status === "RESOLVED") return "badge badge-success";
  if (status === "CLOSED") return "badge badge-danger";
  return "badge";
};

const priorityTone = (priority: CasePriority) => {
  if (priority === "HIGH" || priority === "CRITICAL") return "badge badge-danger";
  return "badge";
};

export function CaseDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const [payload, setPayload] = useState<CaseDetailsResponse | null>(null);
  const [assignedTo, setAssignedTo] = useState("");
  const [status, setStatus] = useState<CaseStatus>("TRIAGE");
  const [priority, setPriority] = useState<CasePriority>("MEDIUM");
  const [comment, setComment] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { toast, showToast } = useToast();

  const loadDetails = useCallback(() => {
    if (!id) return;
    setIsLoading(true);
    fetchCaseDetails(id, true)
      .then((data) => {
        setPayload(data);
        setAssignedTo(data.case.assigned_to ?? "");
        setStatus(data.case.status);
        setPriority(data.case.priority);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [id]);

  useEffect(() => {
    loadDetails();
  }, [loadDetails]);

  const handleUpdate = async () => {
    if (!id) return;
    try {
      const updated = await updateCase(id, {
        status,
        priority,
        assigned_to: assignedTo || null,
      });
      setPayload((prev) => (prev ? { ...prev, case: updated } : prev));
      showToast("success", "Кейс обновлён");
      loadDetails();
    } catch (err) {
      showToast("error", (err as Error).message);
    }
  };

  const handleComment = async () => {
    if (!id || !comment.trim()) return;
    try {
      const newComment = await addCaseComment(id, { body: comment.trim() });
      setPayload((prev) =>
        prev ? { ...prev, comments: [...prev.comments, newComment] } : prev,
      );
      setComment("");
      showToast("success", "Комментарий добавлен");
      loadDetails();
    } catch (err) {
      showToast("error", (err as Error).message);
    }
  };

  const timelineItems = useMemo(() => {
    if (!payload) return [];
    const entries: Array<{ id: string; label: string; body?: string | null; created_at: string }> = [];
    payload.snapshots?.forEach((snapshot) => {
      entries.push({
        id: `snapshot-${snapshot.id}`,
        label: "Snapshot created",
        body: snapshot.note ?? null,
        created_at: snapshot.created_at,
      });
    });
    payload.comments.forEach((item) => {
      entries.push({
        id: `comment-${item.id}`,
        label: item.author ? `Комментарий · ${item.author}` : "Комментарий",
        body: item.body,
        created_at: item.created_at,
      });
    });
    return entries.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
  }, [payload]);

  if (!id) {
    return <div className="card">Кейс не найден</div>;
  }

  if (isLoading) {
    return <div className="card">Загружаем кейс...</div>;
  }

  if (error) {
    return <div className="card error-state">{error}</div>;
  }

  if (!payload) {
    return <div className="card">Кейс не найден</div>;
  }

  const latestSnapshot = payload.latest_snapshot;

  return (
    <div className="stack">
      <Toast toast={toast} />
      <section className="card">
        <div className="card__header">
          <div>
            <h2>{payload.case.title}</h2>
            <p className="muted">Case ID: {payload.case.id}</p>
          </div>
          <Link className="ghost" to="/support/cases">
            К списку кейсов
          </Link>
        </div>
        <div className="meta-grid">
          <div>
            <div className="label">Status</div>
            <span className={statusTone(payload.case.status)}>{payload.case.status}</span>
          </div>
          <div>
            <div className="label">Priority</div>
            <span className={priorityTone(payload.case.priority)}>{payload.case.priority}</span>
          </div>
          <div>
            <div className="label">Assigned</div>
            <div>{payload.case.assigned_to ?? "—"}</div>
          </div>
          <div>
            <div className="label">Kind</div>
            <div>{payload.case.kind}</div>
          </div>
          <div>
            <div className="label">Entity</div>
            <div>{payload.case.entity_id ?? payload.case.kpi_key ?? "—"}</div>
          </div>
          <div>
            <div className="label">Last activity</div>
            <div>{formatTimestamp(payload.case.last_activity_at)}</div>
          </div>
        </div>
      </section>

      <section className="card">
        <h3>Управление</h3>
        <div className="form-grid">
          <label className="filter">
            Статус
            <select value={status} onChange={(event) => setStatus(event.target.value as CaseStatus)}>
              {STATUS_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
          <label className="filter">
            Приоритет
            <select value={priority} onChange={(event) => setPriority(event.target.value as CasePriority)}>
              {PRIORITY_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
          <label className="filter">
            Назначить
            <input value={assignedTo} onChange={(event) => setAssignedTo(event.target.value)} placeholder="ops@neft.io" />
          </label>
        </div>
        <div style={{ marginTop: 12 }}>
          <button type="button" className="neft-btn-primary" onClick={handleUpdate}>
            Сохранить
          </button>
        </div>
      </section>

      <section className="card">
        <h3>Комментарии</h3>
        <div className="form-grid">
          <textarea
            rows={3}
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            placeholder="Комментарий для команды ops"
          />
          <button type="button" className="neft-btn-secondary" onClick={handleComment}>
            Добавить комментарий
          </button>
        </div>
        <div className="timeline-list" style={{ marginTop: 12 }}>
          {payload.comments.length === 0 ? (
            <div className="muted">Комментариев пока нет</div>
          ) : (
            payload.comments.map((item: CaseComment) => (
              <div className="timeline-item" key={item.id}>
                <div className="timeline-item__meta">
                  <span className="timeline-item__title">{item.author ?? "Комментарий"}</span>
                  <span className="muted small">{formatTimestamp(item.created_at)}</span>
                </div>
                <div className="timeline-item__body">{item.body}</div>
              </div>
            ))
          )}
        </div>
      </section>

      <section className="card">
        <h3>Timeline</h3>
        {timelineItems.length === 0 ? (
          <div className="muted">История пока недоступна</div>
        ) : (
          <div className="timeline-list">
            {timelineItems.map((item) => (
              <div className="timeline-item" key={item.id}>
                <div className="timeline-item__meta">
                  <span className="timeline-item__title">{item.label}</span>
                  <span className="muted small">{formatTimestamp(item.created_at)}</span>
                </div>
                {item.body ? <div className="timeline-item__body">{item.body}</div> : null}
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="card">
        <h3>Snapshot</h3>
        {latestSnapshot ? (
          <div className="stack">
            <div className="muted">Создано: {formatTimestamp(latestSnapshot.created_at)}</div>
            {latestSnapshot.note ? <div className="muted">{latestSnapshot.note}</div> : null}
            <JsonViewer title="Explain snapshot" value={latestSnapshot.explain_snapshot} />
            {latestSnapshot.diff_snapshot ? <JsonViewer title="Diff snapshot" value={latestSnapshot.diff_snapshot} /> : null}
            {latestSnapshot.selected_actions ? (
              <JsonViewer title="Selected actions" value={latestSnapshot.selected_actions} />
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
