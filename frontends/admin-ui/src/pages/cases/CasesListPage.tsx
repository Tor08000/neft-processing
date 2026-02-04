import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  closeAdminCase,
  fetchAdminCases,
  type CaseItem,
  type CasePriority,
  type CaseStatus,
  isNotAvailableError,
} from "../../api/adminCases";
import { UnauthorizedError } from "../../api/client";
import { CloseCaseModal } from "../../components/cases/CloseCaseModal";
import { Table } from "../../components/Table/Table";
import { Toast } from "../../components/common/Toast";
import { useToast } from "../../components/Toast/useToast";
import { AdminUnauthorizedPage } from "../admin/AdminStatusPages";

const STATUS_OPTIONS: CaseStatus[] = ["OPEN", "IN_PROGRESS", "CLOSED"];
const PRIORITY_OPTIONS: CasePriority[] = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];

const formatTimestamp = (value?: string | null) => {
  if (!value) return "—";
  return new Date(value).toLocaleString("ru-RU");
};

const statusTone = (status: CaseStatus) => {
  if (status === "CLOSED") return "neft-chip neft-chip-err";
  if (status === "IN_PROGRESS") return "neft-chip neft-chip-ok";
  return "neft-chip neft-chip-muted";
};

const priorityTone = (priority?: CasePriority) => {
  if (priority === "HIGH" || priority === "CRITICAL") return "neft-chip neft-chip-err";
  if (priority === "MEDIUM") return "neft-chip neft-chip-warn";
  return "neft-chip neft-chip-muted";
};

const resolveTitle = (item: CaseItem) => item.title ?? (item.kind ? `${item.kind} · ${item.id}` : `Case ${item.id}`);

const isForbidden = (error: unknown) => error instanceof Error && /HTTP 403\b/.test(error.message);

export function CasesListPage() {
  const navigate = useNavigate();
  const { toast, showToast } = useToast();
  const [items, setItems] = useState<CaseItem[]>([]);
  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");
  const [query, setQuery] = useState("");
  const [limit] = useState(20);
  const [cursor, setCursor] = useState<string | null>(null);
  const [cursorHistory, setCursorHistory] = useState<string[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [unauthorized, setUnauthorized] = useState(false);
  const [notAvailable, setNotAvailable] = useState(false);
  const [closeTarget, setCloseTarget] = useState<CaseItem | null>(null);

  const params = useMemo(
    () => ({
      status: status || undefined,
      priority: priority || undefined,
      q: query || undefined,
      limit,
      cursor,
    }),
    [status, priority, query, limit, cursor],
  );

  useEffect(() => {
    setCursor(null);
    setCursorHistory([]);
  }, [status, priority, query]);

  const loadCases = useCallback(() => {
    setIsLoading(true);
    setError(null);
    setUnauthorized(false);
    fetchAdminCases(params)
      .then((data) => {
        setItems(data.items ?? []);
        setNextCursor(data.next_cursor ?? null);
        setNotAvailable(false);
      })
      .catch((err: unknown) => {
        if (err instanceof UnauthorizedError || isForbidden(err)) {
          setUnauthorized(true);
          setItems([]);
          return;
        }
        if (isNotAvailableError(err)) {
          setNotAvailable(true);
          setItems([]);
          setNextCursor(null);
          return;
        }
        setError((err as Error).message);
      })
      .finally(() => setIsLoading(false));
  }, [params]);

  useEffect(() => {
    loadCases();
  }, [loadCases]);

  const sortedItems = useMemo(
    () =>
      [...items].sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
      ),
    [items],
  );

  const columns = useMemo(
    () => [
      {
        key: "id",
        title: "ID",
        render: (item: CaseItem) => (
          <button
            type="button"
            className="ghost"
            onClick={() => navigator.clipboard.writeText(item.id)}
          >
            {item.id}
          </button>
        ),
      },
      {
        key: "status",
        title: "Status",
        render: (item: CaseItem) => <span className={statusTone(item.status)}>{item.status}</span>,
      },
      {
        key: "priority",
        title: "Priority",
        render: (item: CaseItem) =>
          item.priority ? <span className={priorityTone(item.priority)}>{item.priority}</span> : "—",
      },
      {
        key: "title",
        title: "Title",
        render: (item: CaseItem) => resolveTitle(item),
      },
      {
        key: "created",
        title: "Created at",
        render: (item: CaseItem) => formatTimestamp(item.created_at),
      },
      {
        key: "updated",
        title: "Updated / Closed",
        render: (item: CaseItem) => formatTimestamp(item.closed_at ?? item.updated_at),
      },
      {
        key: "actions",
        title: "Quick actions",
        render: (item: CaseItem) => (
          <div className="stack-inline">
            <button type="button" className="ghost" onClick={() => navigate(`/cases/${item.id}`)}>
              Open
            </button>
            <button
              type="button"
              className="ghost"
              onClick={() => setCloseTarget(item)}
              disabled={item.status !== "OPEN" || notAvailable}
              title={notAvailable ? "Not available in this environment" : undefined}
            >
              Close
            </button>
          </div>
        ),
      },
    ],
    [navigate, notAvailable],
  );

  const handleClose = async (payload: { resolutionNote: string; actionsApplied: boolean }) => {
    if (!closeTarget) return;
    try {
      const response = await closeAdminCase(closeTarget.id, {
        resolution_note: payload.resolutionNote,
        resolution_code: null,
      });
      const updated = response ?? { ...closeTarget, status: "CLOSED" as CaseStatus };
      setItems((prev) => prev.map((item) => (item.id === closeTarget.id ? { ...item, ...updated } : item)));
      setCloseTarget(null);
      showToast("success", "Case closed");
    } catch (err) {
      if (isNotAvailableError(err)) {
        setNotAvailable(true);
        const message = "Not available in this environment";
        showToast("error", message);
        throw new Error(message);
      } else {
        const message = (err as Error).message;
        showToast("error", message);
        throw new Error(message);
      }
    }
  };

  const handleNext = () => {
    if (!nextCursor) return;
    setCursorHistory((prev) => [...prev, cursor ?? ""]);
    setCursor(nextCursor);
  };

  const handlePrev = () => {
    setCursorHistory((prev) => {
      const next = [...prev];
      const last = next.pop();
      setCursor(last ? last : null);
      return next;
    });
  };

  if (unauthorized) {
    return <AdminUnauthorizedPage />;
  }

  return (
    <div className="stack">
      <Toast toast={toast} />
      <section className="neft-card">
        <div className="card__header">
          <div>
            <h1 style={{ fontSize: 24, fontWeight: 700 }}>Cases</h1>
            <p className="muted">Case lifecycle tracking from Explain v2.</p>
          </div>
        </div>
        <div className="filters">
          <label className="filter">
            Status
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="">All</option>
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
              <option value="">All</option>
              {PRIORITY_OPTIONS.map((option) => (
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
              placeholder="ID / note"
            />
          </label>
        </div>
      </section>

      {notAvailable ? <div className="neft-card">Not available in this environment</div> : null}
      {error ? <div className="neft-card error-state">{error}</div> : null}

      <Table
        columns={columns}
        data={sortedItems}
        loading={isLoading}
        emptyState={{
          title: "No cases found",
          description: "Try adjusting filters to see cases.",
        }}
      />

      <div className="stack-inline" style={{ justifyContent: "flex-end" }}>
        <button type="button" className="ghost" onClick={handlePrev} disabled={cursorHistory.length === 0}>
          Previous
        </button>
        <button type="button" className="ghost" onClick={handleNext} disabled={!nextCursor}>
          Next
        </button>
      </div>

      <CloseCaseModal
        open={Boolean(closeTarget)}
        caseItem={closeTarget}
        selectedActionsCount={0}
        onCancel={() => setCloseTarget(null)}
        onSubmit={handleClose}
      />
    </div>
  );
}

export default CasesListPage;
