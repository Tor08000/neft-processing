import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchCases } from "../api/cases";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { AppEmptyState, AppErrorState, AppLoadingState } from "../components/states";
import type { CaseItem, CaseKind, CasePriority, CaseStatus } from "../types/cases";
import { casePriorityLabel, caseStatusLabel, caseStatusTone } from "../utils/cases";
import { formatDateTime } from "../utils/format";

const STATUS_OPTIONS: CaseStatus[] = ["TRIAGE", "IN_PROGRESS", "WAITING", "RESOLVED", "CLOSED"];
const PRIORITY_OPTIONS: CasePriority[] = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];
const KIND_OPTIONS: CaseKind[] = ["support", "incident", "dispute", "order", "invoice", "operation", "kpi"];

const CASE_KIND_LABELS: Record<CaseKind, string> = {
  support: "Support",
  incident: "Incident",
  dispute: "Dispute",
  order: "Order",
  invoice: "Invoice",
  operation: "Operation",
  kpi: "KPI",
  fleet: "Fleet",
  booking: "Booking",
};

interface CasesErrorState {
  message: string;
  status?: number;
  correlationId?: string | null;
}

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
  const [error, setError] = useState<CasesErrorState | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const filters = useMemo(
    () => ({
      status: status || undefined,
      priority: priority || undefined,
      kind: kind || undefined,
      q: query || undefined,
    }),
    [status, priority, kind, query],
  );
  const hasActiveFilters = Boolean(status || priority || kind || query);

  const resetFilters = () => {
    setStatus("");
    setPriority("");
    setKind("");
    setQuery("");
  };

  useEffect(() => {
    if (!user) return;
    setIsLoading(true);
    setError(null);
    fetchCases(user, filters)
      .then((response) => setItems(response.items ?? []))
      .catch((err: unknown) => {
        if (err instanceof ApiError) {
          setError({ message: err.message, status: err.status, correlationId: err.correlationId });
          return;
        }
        setError({ message: err instanceof Error ? err.message : "Не удалось загрузить кейсы" });
      })
      .finally(() => setIsLoading(false));
  }, [filters, reloadKey, user]);

  if (!user) return null;

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <div>
            <h2>Инциденты и обращения</h2>
            <p className="muted">Один canonical case lifecycle для поддержки, заказов, документов и dispute-контекста.</p>
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
                  {CASE_KIND_LABELS[option] ?? option}
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

      {isLoading ? <AppLoadingState label="Загружаем кейсы..." /> : null}

      {!isLoading && error ? (
        <AppErrorState
          message={error.status === 404 || error.status === 503 ? "Контур кейсов временно недоступен" : error.message}
          status={error.status}
          correlationId={error.correlationId}
          onRetry={() => setReloadKey((value) => value + 1)}
        />
      ) : null}

      {!isLoading && !error && items.length === 0 ? (
        <AppEmptyState
          title={hasActiveFilters ? "Кейсы не найдены" : "Кейсов пока нет"}
          description={
            hasActiveFilters
              ? "Текущие фильтры скрыли все кейсы. Сбросьте их, чтобы вернуться к полному lifecycle."
              : "Здесь появятся ваши обращения, инциденты по заказам, dispute-кейсы и связанные операционные разборы."
          }
          action={
            hasActiveFilters ? (
              <button type="button" className="secondary" onClick={resetFilters}>
                Сбросить фильтры
              </button>
            ) : (
              <Link className="primary" to="/client/support/new">
                Создать обращение
              </Link>
            )
          }
        />
      ) : null}

      {!isLoading && !error && items.length > 0 ? (
        <section className="card">
          <div className="table-shell">
            <div className="table-scroll">
              <table className="table neft-table">
                <thead>
                  <tr>
                    <th>Дата</th>
                    <th>Название</th>
                    <th>Тип</th>
                    <th>Контекст</th>
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
                      <td>{CASE_KIND_LABELS[item.kind] ?? item.kind}</td>
                      <td>
                        {item.entity_type
                          ? `${item.entity_type}${item.entity_id ? ` / ${item.entity_id}` : ""}`
                          : item.entity_id ?? "—"}
                      </td>
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
            </div>
            <div className="table-footer">
              <div className="table-footer__content">
                <span>Кейсов: {items.length}</span>
              </div>
            </div>
          </div>
        </section>
      ) : null}
    </div>
  );
}

export default CasesPage;
