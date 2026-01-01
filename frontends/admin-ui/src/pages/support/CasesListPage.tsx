import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  fetchCases,
  type CaseItem,
  type CaseKind,
  type CasePriority,
  type CaseQueue,
  type CaseSlaState,
  type CaseStatus,
} from "../../api/cases";
import { useAuth } from "../../auth/AuthContext";
import { Table } from "../../components/Table/Table";

const STATUS_OPTIONS: CaseStatus[] = ["TRIAGE", "IN_PROGRESS", "RESOLVED", "CLOSED"];
const PRIORITY_OPTIONS: CasePriority[] = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];
const KIND_OPTIONS: CaseKind[] = ["operation", "invoice", "order", "kpi"];
const QUEUE_OPTIONS: CaseQueue[] = ["FRAUD_OPS", "FINANCE_OPS", "SUPPORT", "GENERAL"];
const SLA_OPTIONS: CaseSlaState[] = ["ON_TRACK", "WARNING", "BREACHED"];
const ESCALATION_OPTIONS = ["0", "1", "2"];

const formatTimestamp = (value?: string | null) => {
  if (!value) return "—";
  return new Date(value).toLocaleString("ru-RU");
};

const shortId = (value: string) => value.slice(0, 8);

const statusTone = (status: CaseStatus) => {
  if (status === "RESOLVED") return "badge badge-success";
  if (status === "CLOSED") return "badge badge-danger";
  return "badge";
};

const priorityTone = (priority: CasePriority) => {
  if (priority === "HIGH" || priority === "CRITICAL") return "badge badge-danger";
  return "badge";
};

const slaTone = (slaState?: CaseSlaState | null) => {
  if (slaState === "BREACHED") return "badge badge-danger";
  if (slaState === "WARNING") return "badge badge-success";
  return "badge";
};

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

export function CasesListPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [items, setItems] = useState<CaseItem[]>([]);
  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");
  const [kind, setKind] = useState("");
  const [queue, setQueue] = useState("");
  const [slaState, setSlaState] = useState("");
  const [escalationLevel, setEscalationLevel] = useState("");
  const [query, setQuery] = useState("");
  const [quickFilter, setQuickFilter] = useState<"mine" | "attention" | "closed" | "">("");
  const [limit] = useState(20);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const params = useMemo(
    () => {
      const base = {
        status: (status || undefined) as CaseStatus | undefined,
        priority: (priority || undefined) as CasePriority | undefined,
        kind: (kind || undefined) as CaseKind | undefined,
        queue: (queue || undefined) as CaseQueue | undefined,
        sla_state: (slaState || undefined) as CaseSlaState | undefined,
        escalation_level_min: escalationLevel ? Number(escalationLevel) : undefined,
        q: query || undefined,
        limit,
      };
      if (quickFilter === "mine") {
        return { ...base, assigned_to: user?.email };
      }
      if (quickFilter === "attention") {
        return { ...base, sla_state: "BREACHED" as CaseSlaState };
      }
      if (quickFilter === "closed") {
        return { ...base, status: "CLOSED" as CaseStatus };
      }
      return base;
    },
    [status, priority, kind, queue, slaState, escalationLevel, query, limit, quickFilter, user?.email],
  );

  useEffect(() => {
    setIsLoading(true);
    fetchCases(params)
      .then((data) => setItems(data.items))
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [params]);

  const columns = useMemo(
    () => [
      {
        key: "id",
        title: "ID",
        render: (item: CaseItem) => shortId(item.id),
      },
      {
        key: "queue",
        title: "Queue",
        render: (item: CaseItem) => <span className="badge">{item.queue}</span>,
      },
      {
        key: "title",
        title: "Title",
        dataIndex: "title" as const,
      },
      {
        key: "kind",
        title: "Kind / Entity",
        render: (item: CaseItem) => `${item.kind}${item.entity_id ? ` · ${item.entity_id}` : ""}`,
      },
      {
        key: "status",
        title: "Status",
        render: (item: CaseItem) => <span className={statusTone(item.status)}>{item.status}</span>,
      },
      {
        key: "priority",
        title: "Priority",
        render: (item: CaseItem) => <span className={priorityTone(item.priority)}>{item.priority}</span>,
      },
      {
        key: "sla",
        title: "SLA",
        render: (item: CaseItem) => (
          <span className={slaTone(item.sla_state)}>{formatRemaining(nextDueAt(item))}</span>
        ),
      },
      {
        key: "escalation",
        title: "Escalation",
        render: (item: CaseItem) => <span className="badge">{`E${item.escalation_level}`}</span>,
      },
      {
        key: "updated",
        title: "Last activity",
        render: (item: CaseItem) => formatTimestamp(item.last_activity_at),
      },
      {
        key: "assigned",
        title: "Assigned",
        render: (item: CaseItem) => item.assigned_to ?? "—",
      },
    ],
    [],
  );

  const sortedItems = useMemo(() => {
    const weight = (slaState?: CaseSlaState | null) => {
      if (slaState === "BREACHED") return 0;
      if (slaState === "WARNING") return 1;
      return 2;
    };
    return [...items].sort((a, b) => {
      const weightDiff = weight(a.sla_state) - weight(b.sla_state);
      if (weightDiff !== 0) return weightDiff;
      return new Date(b.last_activity_at).getTime() - new Date(a.last_activity_at).getTime();
    });
  }, [items]);

  return (
    <div className="stack">
      <section className="card">
        <div className="card__header">
          <div>
            <h1 style={{ fontSize: 24, fontWeight: 700 }}>Support Cases</h1>
            <p className="muted">Ops escalations captured from Explain v2.</p>
          </div>
          <button type="button" className="ghost" onClick={() => navigate("/explain")}>
            Создать кейс из Explain
          </button>
        </div>
        <div className="filters">
          <div className="stack-inline">
            <button
              type="button"
              className={`pill ${quickFilter === "mine" ? "pill--accent" : "pill--outline"}`}
              onClick={() => setQuickFilter(quickFilter === "mine" ? "" : "mine")}
            >
              Мои
            </button>
            <button
              type="button"
              className={`pill ${quickFilter === "attention" ? "pill--accent" : "pill--outline"}`}
              onClick={() => setQuickFilter(quickFilter === "attention" ? "" : "attention")}
            >
              Требует внимания
            </button>
            <button
              type="button"
              className={`pill ${quickFilter === "closed" ? "pill--accent" : "pill--outline"}`}
              onClick={() => setQuickFilter(quickFilter === "closed" ? "" : "closed")}
            >
              Закрытые
            </button>
          </div>
          <label className="filter">
            Status
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="">Все</option>
              {STATUS_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
          <label className="filter">
            Priority
            <select value={priority} onChange={(event) => setPriority(event.target.value)}>
              <option value="">Все</option>
              {PRIORITY_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
          <label className="filter">
            Kind
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
            Queue
            <select value={queue} onChange={(event) => setQueue(event.target.value)}>
              <option value="">Все</option>
              {QUEUE_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
          <label className="filter">
            SLA
            <select value={slaState} onChange={(event) => setSlaState(event.target.value)}>
              <option value="">Все</option>
              {SLA_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
          <label className="filter">
            Escalation
            <select value={escalationLevel} onChange={(event) => setEscalationLevel(event.target.value)}>
              <option value="">Все</option>
              {ESCALATION_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  E{option}
                </option>
              ))}
            </select>
          </label>
          <label className="filter">
            Search
            <input
              type="text"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="ID / title"
            />
          </label>
        </div>
      </section>

      {error ? <div className="card error-state">{error}</div> : null}

      <Table
        columns={columns}
        data={sortedItems}
        loading={isLoading}
        emptyState={{
          title: "Кейсов нет",
          description: "Создайте кейс из Explain, чтобы зафиксировать снимок и действия.",
          actionLabel: "Создать кейс из Explain",
          actionOnClick: () => navigate("/explain"),
        }}
        onRowClick={(record) => navigate(`/support/cases/${record.id}`)}
      />

    </div>
  );
}

export default CasesListPage;
