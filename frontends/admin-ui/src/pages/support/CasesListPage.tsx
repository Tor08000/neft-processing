import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchCases, type CaseItem, type CaseKind, type CasePriority, type CaseStatus } from "../../api/cases";
import { Table } from "../../components/Table/Table";

const STATUS_OPTIONS: CaseStatus[] = ["TRIAGE", "IN_PROGRESS", "RESOLVED", "CLOSED"];
const PRIORITY_OPTIONS: CasePriority[] = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];
const KIND_OPTIONS: CaseKind[] = ["operation", "invoice", "order", "kpi"];

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

export function CasesListPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<CaseItem[]>([]);
  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");
  const [kind, setKind] = useState("");
  const [query, setQuery] = useState("");
  const [limit] = useState(20);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const params = useMemo(
    () => ({
      status: (status || undefined) as CaseStatus | undefined,
      priority: (priority || undefined) as CasePriority | undefined,
      kind: (kind || undefined) as CaseKind | undefined,
      q: query || undefined,
      limit,
    }),
    [status, priority, kind, query, limit],
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
        data={items}
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
