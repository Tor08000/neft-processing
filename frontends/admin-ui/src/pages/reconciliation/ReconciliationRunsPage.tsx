import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  createExternalRun,
  createInternalRun,
  listRuns,
  listStatements,
  type ExternalStatement,
  type ReconciliationRun,
} from "../../api/reconciliation";
import { UnauthorizedError } from "../../api/client";
import { DateRangeFilter } from "../../components/Filters/DateRangeFilter";
import { SelectFilter } from "../../components/Filters/SelectFilter";
import { CopyButton } from "../../components/CopyButton/CopyButton";
import { Table, type Column } from "../../components/Table/Table";
import { Toast } from "../../components/common/Toast";
import { useToast } from "../../components/Toast/useToast";
import { formatDate, formatDateTime } from "../../utils/format";

const STATUS_OPTIONS = ["completed", "failed", "started"];

const formatPeriod = (start?: string | null, end?: string | null) =>
  `${formatDate(start)} — ${formatDate(end)}`;

const parseNumber = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

const getSummaryNumber = (summary: Record<string, unknown> | null | undefined, keys: string[]): number | null => {
  if (!summary) return null;
  for (const key of keys) {
    const value = parseNumber(summary[key]);
    if (value !== null) return value;
  }
  return null;
};

const scopeBadge = (scope?: string | null) => {
  if (scope === "internal") return "success";
  if (scope === "external") return "warning";
  return "neutral";
};

const statusBadge = (status?: string | null) => {
  if (!status) return "neutral";
  if (status === "completed") return "success";
  if (status === "failed") return "error";
  if (status === "started") return "warning";
  return "neutral";
};

const matchesDateRange = (value: string, from?: string, to?: string) => {
  const ts = new Date(value).getTime();
  if (Number.isNaN(ts)) return false;
  if (from) {
    const fromTs = new Date(from).getTime();
    if (ts < fromTs) return false;
  }
  if (to) {
    const toTs = new Date(to).getTime();
    if (ts > toTs + 24 * 60 * 60 * 1000 - 1) return false;
  }
  return true;
};

export function ReconciliationRunsPage() {
  const navigate = useNavigate();
  const { toast, showToast } = useToast();
  const [runs, setRuns] = useState<ReconciliationRun[]>([]);
  const [scope, setScope] = useState("");
  const [provider, setProvider] = useState("");
  const [status, setStatus] = useState("");
  const [dateField, setDateField] = useState<"created_at" | "period_end">("created_at");
  const [dateRange, setDateRange] = useState<{ from?: string; to?: string }>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notAvailable, setNotAvailable] = useState(false);
  const [unauthorized, setUnauthorized] = useState(false);
  const [internalModalOpen, setInternalModalOpen] = useState(false);
  const [externalModalOpen, setExternalModalOpen] = useState(false);
  const [internalStart, setInternalStart] = useState("");
  const [internalEnd, setInternalEnd] = useState("");
  const [internalError, setInternalError] = useState<string | null>(null);
  const [externalStatementId, setExternalStatementId] = useState("");
  const [externalError, setExternalError] = useState<string | null>(null);
  const [statements, setStatements] = useState<ExternalStatement[]>([]);
  const [statementsLoading, setStatementsLoading] = useState(false);
  const [statementsError, setStatementsError] = useState<string | null>(null);

  const loadRuns = useCallback(() => {
    setIsLoading(true);
    setError(null);
    setUnauthorized(false);
    listRuns({ scope: scope || undefined, provider: provider || undefined, status: status || undefined })
      .then((data) => {
        if (data.unavailable) {
          setNotAvailable(true);
          setRuns([]);
          return;
        }
        setNotAvailable(false);
        setRuns(data.runs ?? []);
      })
      .catch((err: unknown) => {
        if (err instanceof UnauthorizedError) {
          setUnauthorized(true);
          return;
        }
        setError((err as Error).message);
      })
      .finally(() => setIsLoading(false));
  }, [provider, scope, status]);

  useEffect(() => {
    loadRuns();
  }, [loadRuns]);

  const providerOptions = useMemo(() => {
    const unique = new Set(runs.map((item) => item.provider).filter(Boolean) as string[]);
    return Array.from(unique).map((value) => ({ label: value, value }));
  }, [runs]);

  const filteredRuns = useMemo(() => {
    return runs.filter((run) => {
      const dateValue = dateField === "created_at" ? run.created_at : run.period_end;
      if (!matchesDateRange(dateValue, dateRange.from, dateRange.to)) return false;
      return true;
    });
  }, [dateField, dateRange.from, dateRange.to, runs]);

  const columns = useMemo<Column<ReconciliationRun>[]>(
    () => [
      {
        key: "id",
        title: "Run ID",
        render: (item) => (
          <div className="stack-inline" style={{ gap: 8 }}>
            <span>{item.id}</span>
            <CopyButton value={item.id} />
          </div>
        ),
      },
      {
        key: "scope",
        title: "Scope",
        render: (item) => (
          <span className={`neft-badge ${scopeBadge(item.scope)}`}>{item.scope ?? "unknown"}</span>
        ),
      },
      {
        key: "provider",
        title: "Provider",
        render: (item) => item.provider ?? "—",
      },
      {
        key: "period",
        title: "Period",
        render: (item) => formatPeriod(item.period_start, item.period_end),
      },
      {
        key: "status",
        title: "Status",
        render: (item) => (
          <span className={`neft-badge ${statusBadge(item.status)}`}>{item.status ?? "unknown"}</span>
        ),
      },
      {
        key: "discrepancies",
        title: "Discrepancies",
        render: (item) =>
          getSummaryNumber(item.summary, ["mismatches_found", "discrepancies_count", "discrepancies"]) ?? "—",
      },
      {
        key: "delta",
        title: "Total delta abs",
        render: (item) => {
          const value = getSummaryNumber(item.summary, ["total_delta_abs", "delta_abs"]);
          return value !== null ? value.toLocaleString("ru-RU") : "—";
        },
      },
      {
        key: "created",
        title: "Created at",
        render: (item) => formatDateTime(item.created_at),
      },
      {
        key: "actions",
        title: "Actions",
        render: (item) => (
          <div className="stack-inline">
            <button type="button" className="ghost" onClick={() => navigate(`/reconciliation/runs/${item.id}`)}>
              Open
            </button>
          </div>
        ),
      },
    ],
    [navigate],
  );

  const handleInternalRun = async () => {
    setInternalError(null);
    if (!internalStart || !internalEnd) {
      setInternalError("Please provide start and end");
      return;
    }
    const startDate = new Date(internalStart);
    const endDate = new Date(internalEnd);
    if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) {
      setInternalError("Invalid dates");
      return;
    }
    if (endDate <= startDate) {
      setInternalError("End must be after start");
      return;
    }
    const response = await createInternalRun({
      period_start: startDate.toISOString(),
      period_end: endDate.toISOString(),
    });
    if (response.unavailable) {
      setNotAvailable(true);
      showToast("error", "Reconciliation API not available in this environment");
      return;
    }
    if (response.run) {
      showToast("success", "Internal run created");
      setInternalModalOpen(false);
      loadRuns();
      navigate(`/reconciliation/runs/${response.run.id}`);
    }
  };

  const loadStatements = useCallback(async () => {
    setStatementsLoading(true);
    setStatementsError(null);
    try {
      const response = await listStatements();
      if (response.unavailable) {
        setNotAvailable(true);
        return;
      }
      setStatements(response.statements ?? []);
    } catch (err) {
      setStatementsError((err as Error).message);
    } finally {
      setStatementsLoading(false);
    }
  }, []);

  const handleExternalRun = async () => {
    setExternalError(null);
    if (!externalStatementId) {
      setExternalError("Select a statement");
      return;
    }
    const response = await createExternalRun({ statement_id: externalStatementId });
    if (response.unavailable) {
      setNotAvailable(true);
      showToast("error", "Reconciliation API not available in this environment");
      return;
    }
    if (response.run) {
      showToast("success", "External run created");
      setExternalModalOpen(false);
      loadRuns();
      navigate(`/reconciliation/runs/${response.run.id}`);
    }
  };

  if (unauthorized) {
    return <div className="card error-state">Not authorized</div>;
  }

  return (
    <div className="stack">
      <Toast toast={toast} />
      <section className="card">
        <div className="card__header" style={{ justifyContent: "space-between", gap: 16 }}>
          <div>
            <h1 style={{ fontSize: 24, fontWeight: 700 }}>Reconciliation</h1>
            <p className="muted">Runs overview for internal and external reconciliation.</p>
          </div>
          <div className="stack-inline">
            <button type="button" className="neft-btn-secondary" onClick={() => setInternalModalOpen(true)}>
              New internal run
            </button>
            <button
              type="button"
              className="neft-btn-secondary"
              onClick={() => {
                setExternalModalOpen(true);
                if (!statements.length) {
                  loadStatements();
                }
              }}
            >
              New external run
            </button>
          </div>
        </div>
        <div className="filters">
          <SelectFilter
            label="Scope"
            value={scope}
            onChange={setScope}
            options={[
              { label: "internal", value: "internal" },
              { label: "external", value: "external" },
            ]}
          />
          <SelectFilter label="Provider" value={provider} onChange={setProvider} options={providerOptions} />
          <SelectFilter
            label="Status"
            value={status}
            onChange={setStatus}
            options={STATUS_OPTIONS.map((item) => ({ label: item, value: item }))}
          />
          <SelectFilter
            label="Date field"
            value={dateField}
            onChange={(value) => setDateField(value as "created_at" | "period_end")}
            options={[
              { label: "created_at", value: "created_at" },
              { label: "period_end", value: "period_end" },
            ]}
            allowEmpty={false}
          />
          <DateRangeFilter label="Date range" from={dateRange.from} to={dateRange.to} onChange={setDateRange} />
        </div>
      </section>

      {notAvailable ? <div className="card">Reconciliation API not available in this environment</div> : null}
      {error ? <div className="card error-state">{error}</div> : null}

      <Table
        columns={columns}
        data={filteredRuns}
        loading={isLoading}
        emptyState={{ title: "No runs yet", description: "Create a run to start reconciliation." }}
      />

      {internalModalOpen ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal">
            <h3 style={{ marginTop: 0 }}>New internal run</h3>
            <label className="filter" style={{ marginBottom: 12 }}>
              Period start
              <input
                type="datetime-local"
                value={internalStart}
                onChange={(event) => setInternalStart(event.target.value)}
              />
            </label>
            <label className="filter" style={{ marginBottom: 12 }}>
              Period end
              <input
                type="datetime-local"
                value={internalEnd}
                onChange={(event) => setInternalEnd(event.target.value)}
              />
            </label>
            {internalError ? <div className="card error-state">{internalError}</div> : null}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 16 }}>
              <button type="button" className="ghost" onClick={() => setInternalModalOpen(false)}>
                Cancel
              </button>
              <button type="button" onClick={handleInternalRun} className="neft-btn-secondary">
                Create run
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {externalModalOpen ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal">
            <h3 style={{ marginTop: 0 }}>New external run</h3>
            <label className="filter" style={{ marginBottom: 12 }}>
              Statement
              <select
                value={externalStatementId}
                onChange={(event) => setExternalStatementId(event.target.value)}
                disabled={statementsLoading}
              >
                <option value="">Select statement</option>
                {statements.map((statement) => (
                  <option key={statement.id} value={statement.id}>
                    {statement.provider} · {formatPeriod(statement.period_start, statement.period_end)}
                  </option>
                ))}
              </select>
              {statementsLoading ? <span className="muted small">Loading statements...</span> : null}
              {statementsError ? <span className="muted small">{statementsError}</span> : null}
            </label>
            {externalError ? <div className="card error-state">{externalError}</div> : null}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 16 }}>
              <button type="button" className="ghost" onClick={() => setExternalModalOpen(false)}>
                Cancel
              </button>
              <button type="button" onClick={handleExternalRun} className="neft-btn-secondary">
                Create run
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default ReconciliationRunsPage;
