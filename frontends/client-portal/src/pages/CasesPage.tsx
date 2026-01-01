import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchCases } from "../api/cases";
import { useAuth } from "../auth/AuthContext";
import { AppEmptyState, AppErrorState, AppLoadingState } from "../components/states";
import type { CaseItem, CaseKind, CasePriority, CaseStatus } from "../types/cases";
import { formatDateTime } from "../utils/format";
import { casePriorityLabel, caseStatusLabel, caseStatusTone } from "../utils/cases";

const STATUS_OPTIONS: CaseStatus[] = ["TRIAGE", "IN_PROGRESS", "RESOLVED", "CLOSED"];
const PRIORITY_OPTIONS: CasePriority[] = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];
const KIND_OPTIONS: CaseKind[] = ["operation", "invoice", "order", "kpi"];

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

const nextDueAt = (item: CaseItem) => {
  const first = item.first_response_due_at ? new Date(item.first_response_due_at).getTime() : null;
  const resolve = item.resolve_due_at ? new Date(item.resolve_due_at).getTime() : null;
  if (first && resolve) return new Date(Math.min(first, resolve)).toISOString();
  if (first) return new Date(first).toISOString();
  if (resolve) return new Date(resolve).toISOString();
  return null;
};

export function CasesPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<CaseItem[]>([]);
  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");
  const [kind, setKind] = useState("");
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const filters = useMemo(
    () => ({
      status: status || undefined,
      priority: priority || undefined,
      kind: kind || undefined,
      q: query || undefined,
    }),
    [status, priority, kind, query],
  );

  useEffect(() => {
    if (!user) return;
    setIsLoading(true);
    fetchCases(user, filters)
      .then((response) => setItems(response.items))
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [user, filters]);

  if (!user) return null;
  if (isLoading) {
    return <AppLoadingState label="Загружаем кейсы..." />;
  }
  if (error) {
    return <AppErrorState message={error} />;
  }

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <div>
            <h2>Support Cases</h2>
            <p className="muted">Кейсы по explain/diff и выбранным действиям.</p>
          </div>
        </div>
        <div className="filters">
          <label className="filter">
            Статус
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="">Все</option>
              {STATUS_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {caseStatusLabel(option)}
                </option>
              ))}
            </select>
          </label>
          <label className="filter">
            Приоритет
            <select value={priority} onChange={(event) => setPriority(event.target.value)}>
              <option value="">Все</option>
              {PRIORITY_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {casePriorityLabel(option)}
                </option>
              ))}
            </select>
          </label>
          <label className="filter">
            Тип
            <select value={kind} onChange={(event) => setKind(event.target.value)}>
              <option value="">Все</option>
              {KIND_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
          <label className="filter">
            Поиск
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="ID или название" />
          </label>
        </div>
      </section>

      {items.length === 0 ? (
        <AppEmptyState title="Кейсов пока нет" description="Кейсы появятся после создания из explain." />
      ) : (
        <section className="card">
          <table className="data-table">
            <thead>
              <tr>
                <th>Дата</th>
                <th>Название</th>
                <th>Тип</th>
                <th>Статус</th>
                <th>Приоритет</th>
                <th>Queue</th>
                <th>SLA</th>
                <th>Обновлено</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td>{formatDateTime(item.created_at)}</td>
                  <td>
                    <Link to={`/cases/${item.id}`}>{item.title}</Link>
                  </td>
                  <td>{item.kind}</td>
                  <td>
                    <span className={caseStatusTone(item.status)}>{caseStatusLabel(item.status)}</span>
                  </td>
                  <td>{casePriorityLabel(item.priority)}</td>
                  <td>{item.queue}</td>
                  <td>{formatRemaining(nextDueAt(item))}</td>
                  <td>{formatDateTime(item.last_activity_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}

export default CasesPage;
