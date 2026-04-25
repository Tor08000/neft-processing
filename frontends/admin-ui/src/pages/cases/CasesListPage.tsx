import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  fetchCases,
  type CaseKind,
  type CaseItem,
  type CasePriority,
  type CaseQueue,
  type CaseStatus,
} from "../../api/cases";
import { closeAdminCase, isNotAvailableError } from "../../api/adminCases";
import { UnauthorizedError } from "../../api/client";
import { describeRuntimeError, type RuntimeErrorMeta } from "../../api/runtimeError";
import { CloseCaseModal } from "../../components/cases/CloseCaseModal";
import { Table } from "../../components/Table/Table";
import { Toast } from "../../components/common/Toast";
import { useToast } from "../../components/Toast/useToast";
import { useAdmin } from "../../admin/AdminContext";
import { AdminUnauthorizedPage } from "../admin/AdminStatusPages";
import { casesListCopy } from "../operatorKeyPageCopy";

const STATUS_OPTIONS: CaseStatus[] = ["TRIAGE", "IN_PROGRESS", "WAITING", "RESOLVED", "CLOSED"];
const PRIORITY_OPTIONS: CasePriority[] = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];
const QUEUE_OPTIONS: CaseQueue[] = ["SUPPORT", "FINANCE_OPS", "GENERAL", "FRAUD_OPS"];

const KIND_LABELS: Record<CaseKind, string> = {
  operation: "Operation",
  invoice: "Invoice",
  order: "Order",
  support: "Support",
  dispute: "Dispute",
  incident: "Incident",
  kpi: "KPI",
  fleet: "Fleet",
  booking: "Booking",
};

const formatTimestamp = (value?: string | null) => {
  if (!value) return "—";
  return new Date(value).toLocaleString("ru-RU");
};

const statusTone = (status: CaseStatus) => {
  if (status === "RESOLVED") return "neft-chip neft-chip-ok";
  if (status === "CLOSED") return "neft-chip neft-chip-err";
  return "neft-chip neft-chip-muted";
};

const priorityTone = (priority?: CasePriority) => {
  if (priority === "HIGH" || priority === "CRITICAL") return "neft-chip neft-chip-err";
  if (priority === "MEDIUM") return "neft-chip neft-chip-warn";
  return "neft-chip neft-chip-muted";
};

const kindLabel = (kind: CaseKind) => KIND_LABELS[kind] ?? kind;

const queueLabel = (queue: CaseQueue) => {
  switch (queue) {
    case "SUPPORT":
      return "Support";
    case "FINANCE_OPS":
      return "Finance ops";
    case "GENERAL":
      return "General";
    case "FRAUD_OPS":
      return "Fraud ops";
    default:
      return queue;
  }
};

const resolveTitle = (item: CaseItem) => item.title ?? (item.kind ? `${item.kind} · ${item.id}` : `Case ${item.id}`);

const isForbidden = (error: unknown) => error instanceof Error && /HTTP 403\\b/.test(error.message);


export function CasesListPage() {
  const navigate = useNavigate();
  const { profile } = useAdmin();
  const [searchParams] = useSearchParams();
  const { toast, showToast } = useToast();
  const [items, setItems] = useState<CaseItem[]>([]);
  const [status, setStatus] = useState<CaseStatus | "">(() => (searchParams.get("status") as CaseStatus | "") || "");
  const [priority, setPriority] = useState<CasePriority | "">("");
  const [queue, setQueue] = useState<CaseQueue | "">(() => (searchParams.get("queue") as CaseQueue | "") || "");
  const [query, setQuery] = useState(() => searchParams.get("q") ?? "");
  const [limit] = useState(20);
  const [cursor, setCursor] = useState<string | null>(null);
  const [cursorHistory, setCursorHistory] = useState<string[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<RuntimeErrorMeta | null>(null);
  const [unauthorized, setUnauthorized] = useState(false);
  const [notAvailable, setNotAvailable] = useState(false);
  const [closeTarget, setCloseTarget] = useState<CaseItem | null>(null);
  const hasActiveFilters = Boolean(status || priority || queue || query);
  const canOperateCases = Boolean(profile?.permissions?.cases?.operate) && !profile?.read_only;

  const params = useMemo(
    () => ({
      status: status || undefined,
      priority: priority || undefined,
      queue: queue || undefined,
      q: query || undefined,
      limit,
      cursor: cursor ?? undefined,
    }),
    [status, priority, queue, query, limit, cursor],
  );

  useEffect(() => {
    setCursor(null);
    setCursorHistory([]);
  }, [status, priority, queue, query]);

  useEffect(() => {
    setStatus((searchParams.get("status") as CaseStatus | "") || "");
    setQueue((searchParams.get("queue") as CaseQueue | "") || "");
    setQuery(searchParams.get("q") ?? "");
  }, [searchParams]);

  const loadCases = useCallback(() => {
    setIsLoading(true);
    setError(null);
    setUnauthorized(false);
    fetchCases(params)
      .then((data) => {
        setItems(data.items ?? []);
        setTotal(data.total ?? data.items?.length ?? 0);
        setNextCursor(data.next_cursor ?? null);
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
        setError(
          describeRuntimeError(
            err,
            "Cases owner route returned an internal error. Retry or inspect request metadata below.",
          ),
        );
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
        render: (item: CaseItem) => (
          <div>
            <div>{resolveTitle(item)}</div>
            <div className="muted small">
              {kindLabel(item.kind)}
              {item.entity_type ? ` · ${item.entity_type}` : ""}
              {item.entity_id ? ` · ${item.entity_id}` : ""}
            </div>
          </div>
        ),
      },
      {
        key: "scope",
        title: "Scope",
        render: (item: CaseItem) => (
          <div className="muted small">
            {item.client_id ? `Client ${item.client_id}` : item.partner_id ? `Partner ${item.partner_id}` : "Unscoped"}
          </div>
        ),
      },
      {
        key: "queue",
        title: "Queue",
        render: (item: CaseItem) => <span className="neft-chip neft-chip-muted">{queueLabel(item.queue)}</span>,
      },
      {
        key: "created",
        title: "Created at",
        render: (item: CaseItem) => formatTimestamp(item.created_at),
      },
      {
        key: "updated",
        title: "Updated / Closed",
        render: (item: CaseItem) => formatTimestamp(item.last_activity_at ?? item.updated_at),
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
              disabled={item.status !== "TRIAGE" || notAvailable || !canOperateCases}
              title={
                !canOperateCases
                  ? "Requires cases operate capability"
                  : notAvailable
                    ? "Not available in this environment"
                    : undefined
              }
            >
              Close
            </button>
          </div>
        ),
      },
    ],
    [canOperateCases, navigate, notAvailable],
  );

  const handleClose = async (payload: { resolutionNote: string; actionsApplied: boolean }) => {
    if (!closeTarget || !canOperateCases) return;
    try {
      await closeAdminCase(closeTarget.id, {
        resolution_note: payload.resolutionNote,
        resolution_code: null,
      });
      setCloseTarget(null);
      showToast("success", "Case closed");
      loadCases();
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

  const resetFilters = () => {
    setStatus("");
    setPriority("");
    setQueue("");
    setQuery("");
    setCursor(null);
    setCursorHistory([]);
  };

  const queueTitle = queue === "SUPPORT" ? "Support & Incident Inbox" : "Cases";
  const queueDescription =
    queue === "SUPPORT"
      ? "Canonical support, dispute, incident and order cases on the shared lifecycle."
      : "Canonical operational cases across support, disputes and adjacent owner flows.";
  const isSupportQueueInbox = queue === "SUPPORT" && !status && !priority && !query;
  const isFilteredEmpty = hasActiveFilters && !isSupportQueueInbox;

  return (
    <div className="stack">
      <Toast toast={toast} />
      <div className="page-header">
        <div>
          <h1>{queueTitle}</h1>
          <p className="muted">{queueDescription}</p>
        </div>
      </div>

      <Table
        columns={columns}
        data={sortedItems}
        loading={isLoading}
        toolbar={
          <div className="filters">
            <label className="filter">
              Status
              <select value={status} onChange={(event) => setStatus(event.target.value as CaseStatus | "")}>
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
              <select value={priority} onChange={(event) => setPriority(event.target.value as CasePriority | "")}>
                <option value="">All</option>
                {PRIORITY_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>
            <label className="filter">
              Queue
              <select value={queue} onChange={(event) => setQueue(event.target.value as CaseQueue | "")}>
                <option value="">All</option>
                {QUEUE_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {queueLabel(option)}
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
                placeholder="ID / title / description / entity"
              />
            </label>
          </div>
        }
        errorState={
          notAvailable
            ? {
                title: "Cases workflow unavailable",
                description: casesListCopy.unavailableDescription,
              }
              : error
                ? {
                    title: "Failed to load cases",
                    description: error.description,
                    actionLabel: "Retry",
                    actionOnClick: loadCases,
                    details: error.details,
                    requestId: error.requestId,
                    correlationId: error.correlationId,
                  }
                : undefined
        }
        emptyState={{
          title: isFilteredEmpty ? "No cases found" : queue === "SUPPORT" ? "Support queue is empty" : "No cases found",
          description: isFilteredEmpty
            ? "Try resetting filters to restore the full operator queue."
            : queue === "SUPPORT"
              ? "New support, dispute and incident cases will appear here when they enter the shared lifecycle."
              : "This canonical cases surface will populate when new operational cases are created.",
          actionLabel: isFilteredEmpty ? "Reset filters" : undefined,
          actionOnClick: isFilteredEmpty ? resetFilters : undefined,
        }}
        footer={
          <div className="table-footer__content">
            <span>{total ? `${items.length} shown of ${total}` : `${items.length} shown`}</span>
            <div className="toolbar-actions">
              <button type="button" className="ghost" onClick={handlePrev} disabled={cursorHistory.length === 0}>
                Previous
              </button>
              <button type="button" className="ghost" onClick={handleNext} disabled={!nextCursor}>
                Next
              </button>
            </div>
          </div>
        }
      />

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
