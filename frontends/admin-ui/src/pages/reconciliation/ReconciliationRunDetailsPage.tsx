import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  getRun,
  ignoreDiscrepancy,
  listDiscrepancies,
  resolveDiscrepancy,
  type ReconciliationDiscrepancy,
  type ReconciliationRun,
} from "../../api/reconciliation";
import { UnauthorizedError } from "../../api/client";
import { CopyButton } from "../../components/CopyButton/CopyButton";
import { Table, type Column } from "../../components/Table/Table";
import { JsonViewer } from "../../components/common/JsonViewer";
import { Tabs } from "../../components/common/Tabs";
import { Toast } from "../../components/common/Toast";
import { useToast } from "../../components/Toast/useToast";
import { formatDate, formatDateTime } from "../../utils/format";

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

const formatValue = (value?: number | string | null) => {
  if (value === null || value === undefined || value === "") return "—";
  const numeric = parseNumber(value);
  return numeric !== null ? numeric.toLocaleString("ru-RU") : String(value);
};

const statusBadge = (status?: string | null) => {
  if (!status) return "neutral";
  if (status === "completed" || status === "resolved") return "success";
  if (status === "failed") return "error";
  if (status === "started" || status === "open") return "warning";
  if (status === "ignored") return "neutral";
  return "neutral";
};

const deltaTone = (value?: number | string | null) => {
  const numeric = parseNumber(value);
  if (numeric === null) return "#475569";
  if (numeric > 0) return "#dc2626";
  if (numeric < 0) return "#16a34a";
  return "#475569";
};


export function ReconciliationRunDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { toast, showToast } = useToast();
  const [run, setRun] = useState<ReconciliationRun | null>(null);
  const [discrepancies, setDiscrepancies] = useState<ReconciliationDiscrepancy[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notAvailable, setNotAvailable] = useState(false);
  const [unauthorized, setUnauthorized] = useState(false);
  const [activeTab, setActiveTab] = useState("discrepancies");
  const [showAudit, setShowAudit] = useState(false);
  const [resolveTarget, setResolveTarget] = useState<ReconciliationDiscrepancy | null>(null);
  const [resolveNote, setResolveNote] = useState("");
  const [resolveError, setResolveError] = useState<string | null>(null);
  const [ignoreTarget, setIgnoreTarget] = useState<ReconciliationDiscrepancy | null>(null);
  const [ignoreReason, setIgnoreReason] = useState("");
  const [ignoreError, setIgnoreError] = useState<string | null>(null);

  const loadRun = useCallback(() => {
    if (!id) return;
    setLoading(true);
    setError(null);
    setUnauthorized(false);
    Promise.all([getRun(id), listDiscrepancies(id)])
      .then(([runResponse, discrepancyResponse]) => {
        if (runResponse.unavailable || discrepancyResponse.unavailable) {
          setNotAvailable(true);
          setRun(null);
          setDiscrepancies([]);
          return;
        }
        setNotAvailable(false);
        setRun(runResponse.run);
        setDiscrepancies(discrepancyResponse.discrepancies ?? []);
      })
      .catch((err: unknown) => {
        if (err instanceof UnauthorizedError) {
          setUnauthorized(true);
          return;
        }
        setError((err as Error).message);
      })
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    loadRun();
  }, [loadRun]);

  const summaryCards = useMemo(() => {
    if (!run) return [];
    return [
      {
        label: "Accounts checked",
        value: getSummaryNumber(run.summary, ["accounts_checked", "accounts"]) ?? "—",
      },
      {
        label: "Mismatches",
        value:
          getSummaryNumber(run.summary, ["mismatches_found", "discrepancies_count", "discrepancies"]) ??
          discrepancies.length,
      },
      {
        label: "Total delta abs",
        value: getSummaryNumber(run.summary, ["total_delta_abs", "delta_abs"]) ?? "—",
      },
    ];
  }, [discrepancies.length, run]);

  const auditIntegrity = useMemo(() => {
    if (!run?.summary) return "unknown";
    const chain = run.summary["audit_chain_verified"];
    const signature = run.summary["audit_signature_verified"];
    if (chain === true && signature === true) return "verified";
    if (chain === false || signature === false) return "broken";
    return "unknown";
  }, [run?.summary]);

  const handleExport = () => {
    if (!run) return;
    const payload = {
      run,
      discrepancies,
      exported_at: new Date().toISOString(),
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `reconciliation_run_${run.id}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const handleResolve = async () => {
    if (!resolveTarget) return;
    if (resolveNote.trim().length < 10) {
      setResolveError("Note must be at least 10 characters");
      return;
    }
    setResolveError(null);
    const response = await resolveDiscrepancy(resolveTarget.id, { note: resolveNote.trim() });
    if (response.unavailable) {
      setNotAvailable(true);
      showToast("error", "Reconciliation API not available in this environment");
      return;
    }
    const adjustmentId = response.adjustment_tx_id;
    setDiscrepancies((prev) =>
      prev.map((item) =>
        item.id === resolveTarget.id
          ? {
              ...item,
              status: "resolved",
              resolution: { ...item.resolution, note: resolveNote.trim(), adjustment_tx_id: adjustmentId },
            }
          : item,
      ),
    );
    setResolveTarget(null);
    setResolveNote("");
    showToast("success", "Adjustment posted");
  };

  const handleIgnore = async () => {
    if (!ignoreTarget) return;
    if (!ignoreReason.trim()) {
      setIgnoreError("Reason is required");
      return;
    }
    setIgnoreError(null);
    const response = await ignoreDiscrepancy(ignoreTarget.id, { reason: ignoreReason.trim() });
    if (response.unavailable) {
      setNotAvailable(true);
      showToast("error", "Reconciliation API not available in this environment");
      return;
    }
    setDiscrepancies((prev) =>
      prev.map((item) =>
        item.id === ignoreTarget.id
          ? {
              ...item,
              status: "ignored",
              resolution: { ...item.resolution, reason: ignoreReason.trim() },
            }
          : item,
      ),
    );
    setIgnoreTarget(null);
    setIgnoreReason("");
    showToast("success", "Discrepancy ignored");
  };

  const columns = useMemo<Column<ReconciliationDiscrepancy>[]>(
    () => [
      {
        key: "id",
        title: "Discrepancy ID",
        render: (item) => (
          <div className="stack-inline" style={{ gap: 8 }}>
            <span>{item.id}</span>
            <CopyButton value={item.id} />
          </div>
        ),
      },
      {
        key: "type",
        title: "Type",
        render: (item) => <span className="neft-badge info">{item.discrepancy_type}</span>,
      },
      {
        key: "account",
        title: "Account",
        render: (item) => (
          <div>
            <div>{item.ledger_account_id ?? "—"}</div>
            <div className="muted small">{item.currency}</div>
          </div>
        ),
      },
      {
        key: "internal",
        title: "Internal amount",
        render: (item) => formatValue(item.internal_amount),
      },
      {
        key: "external",
        title: "External amount",
        render: (item) => formatValue(item.external_amount),
      },
      {
        key: "delta",
        title: "Delta",
        render: (item) => (
          <span style={{ color: deltaTone(item.delta), fontWeight: 600 }}>{formatValue(item.delta)}</span>
        ),
      },
      {
        key: "status",
        title: "Status",
        render: (item) => (
          <span className={`neft-badge ${statusBadge(item.status)}`}>{item.status ?? "unknown"}</span>
        ),
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
            <button
              type="button"
              className="ghost"
              onClick={() => setResolveTarget(item)}
              disabled={item.status !== "open" || notAvailable}
            >
              Resolve
            </button>
            <button
              type="button"
              className="ghost"
              onClick={() => setIgnoreTarget(item)}
              disabled={item.status !== "open" || notAvailable}
            >
              Ignore
            </button>
          </div>
        ),
      },
      {
        key: "details",
        title: "Details",
        render: (item) => (
          <details>
            <summary>View</summary>
            <div style={{ marginTop: 8 }}>
              <JsonViewer value={item.details ?? {}} redactionMode="audit" />
              {item.resolution ? (
                <div style={{ marginTop: 12 }}>
                  <JsonViewer value={item.resolution} redactionMode="audit" title="Resolution" />
                </div>
              ) : null}
              {item.resolution && typeof item.resolution.adjustment_tx_id === "string" ? (
                <div style={{ marginTop: 8 }}>
                  <div className="muted small">Adjustment transaction</div>
                  <div className="stack-inline" style={{ gap: 8 }}>
                    <span>{String(item.resolution.adjustment_tx_id)}</span>
                    <CopyButton value={String(item.resolution.adjustment_tx_id)} />
                  </div>
                </div>
              ) : null}
            </div>
          </details>
        ),
      },
    ],
    [notAvailable],
  );

  if (unauthorized) {
    return <div className="card error-state">Not authorized</div>;
  }

  return (
    <div className="stack">
      <Toast toast={toast} />
      <section className="card">
        <div className="card__header" style={{ justifyContent: "space-between", gap: 16 }}>
          <div>
            <h1 style={{ fontSize: 24, fontWeight: 700 }}>Run {run?.id ?? ""}</h1>
            <div className="stack-inline" style={{ flexWrap: "wrap" }}>
              <span className={`neft-badge ${statusBadge(run?.status)}`}>{run?.status ?? "unknown"}</span>
              <span className={`neft-badge ${run?.scope === "external" ? "warning" : "success"}`}>
                {run?.scope ?? "unknown"}
              </span>
              {run?.provider ? <span className="muted">{run.provider}</span> : null}
              <span className="muted">{formatDate(run?.period_start)} — {formatDate(run?.period_end)}</span>
            </div>
          </div>
          <div className="stack-inline">
            <button type="button" className="ghost" onClick={() => navigate("/reconciliation")}>Back</button>
            <button type="button" className="neft-btn-secondary" onClick={handleExport} disabled={!run}>
              Export report JSON
            </button>
            {run?.audit_event_id ? (
              <button type="button" className="neft-btn-secondary" onClick={() => setShowAudit((prev) => !prev)}>
                Show audit details
              </button>
            ) : null}
          </div>
        </div>
        <div className="stack-inline" style={{ gap: 16, alignItems: "center" }}>
          <div className="stack-inline" style={{ gap: 8 }}>
            <span className="muted">Run ID:</span>
            <span>{run?.id ?? ""}</span>
            <CopyButton value={run?.id ?? ""} />
          </div>
          {run?.audit_event_id ? (
            <div className="stack-inline" style={{ gap: 8 }}>
              <span className="muted">Audit event:</span>
              <span>{run.audit_event_id}</span>
              <CopyButton value={run.audit_event_id} />
            </div>
          ) : null}
        </div>
      </section>

      {showAudit && run?.audit_event_id ? (
        <section className="card">
          <h3>Audit integrity</h3>
          <div className="stack">
            <div className={`neft-badge ${auditIntegrity === "verified" ? "success" : auditIntegrity === "broken" ? "danger" : "neutral"}`}>
              {auditIntegrity}
            </div>
            <p className="muted">
              Audit integrity is derived from hash chain and signatures when available. If verification endpoints are
              not configured, status remains unknown.
            </p>
          </div>
        </section>
      ) : null}

      {notAvailable ? <div className="card">Reconciliation API not available in this environment</div> : null}
      {error ? <div className="card error-state">{error}</div> : null}

      <div className="card-grid" style={{ marginBottom: 16 }}>
        {summaryCards.map((card) => (
          <div key={card.label} className="card">
            <div className="muted" style={{ marginBottom: 8 }}>
              {card.label}
            </div>
            <div style={{ fontSize: 20, fontWeight: 700 }}>{card.value}</div>
          </div>
        ))}
      </div>

      <Tabs
        tabs={[
          { id: "discrepancies", label: "Discrepancies" },
          { id: "links", label: "Links" },
        ]}
        active={activeTab}
        onChange={setActiveTab}
      />

      {activeTab === "discrepancies" ? (
        <Table
          columns={columns}
          data={discrepancies}
          loading={loading}
          emptyState={{ title: "No discrepancies", description: "This run is balanced." }}
        />
      ) : (
        <section className="card">
          <h3>Reconciliation links</h3>
          {run?.summary && run.summary["links"] ? (
            <JsonViewer value={run.summary["links"]} redactionMode="audit" />
          ) : (
            <p className="muted">Links endpoint unavailable or no links in this run.</p>
          )}
        </section>
      )}

      {resolveTarget ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal">
            <h3 style={{ marginTop: 0 }}>Resolve discrepancy</h3>
            <p className="muted">
              Delta: {formatValue(resolveTarget.delta)} · Proposed adjustment direction:{" "}
              {(() => {
                const delta = parseNumber(resolveTarget.delta);
                if (delta === null) return "unknown";
                return delta > 0 ? "decrease ledger" : "increase ledger";
              })()}
            </p>
            <label className="filter">
              Note
              <textarea
                value={resolveNote}
                onChange={(event) => setResolveNote(event.target.value)}
                rows={4}
                placeholder="Provide a detailed note (min 10 characters)"
              />
            </label>
            {resolveError ? <div className="card error-state">{resolveError}</div> : null}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 16 }}>
              <button type="button" className="ghost" onClick={() => setResolveTarget(null)}>
                Cancel
              </button>
              <button type="button" className="neft-btn-secondary" onClick={handleResolve}>
                Confirm
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {ignoreTarget ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal">
            <h3 style={{ marginTop: 0 }}>Ignore discrepancy</h3>
            <label className="filter">
              Reason
              <textarea
                value={ignoreReason}
                onChange={(event) => setIgnoreReason(event.target.value)}
                rows={3}
                placeholder="Provide a reason"
              />
            </label>
            {ignoreError ? <div className="card error-state">{ignoreError}</div> : null}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 16 }}>
              <button type="button" className="ghost" onClick={() => setIgnoreTarget(null)}>
                Cancel
              </button>
              <button type="button" className="neft-btn-secondary" onClick={handleIgnore}>
                Confirm
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {run ? (
        <div className="stack-inline" style={{ justifyContent: "flex-end" }}>
          <Link to="/reconciliation/statements" className="ghost">
            External statements
          </Link>
        </div>
      ) : null}
    </div>
  );
}

export default ReconciliationRunDetailsPage;
