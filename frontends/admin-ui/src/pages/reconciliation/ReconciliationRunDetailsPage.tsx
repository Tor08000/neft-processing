import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  downloadRunExport,
  getDiscrepancy,
  getRun,
  ignoreDiscrepancy,
  listDiscrepancies,
  listRunLinks,
  resolveDiscrepancy,
  type ReconciliationDiscrepancy,
  type ReconciliationLink,
  type ReconciliationRunExportOptions,
  type ReconciliationRun,
} from "../../api/reconciliation";
import { UnauthorizedError } from "../../api/client";
import { CopyButton } from "../../components/CopyButton/CopyButton";
import { SelectFilter } from "../../components/Filters/SelectFilter";
import { Table, type Column } from "../../components/Table/Table";
import { JsonViewer } from "../../components/common/JsonViewer";
import { Tabs } from "../../components/common/Tabs";
import { Toast } from "../../components/common/Toast";
import { useToast } from "../../components/Toast/useToast";
import { formatDate, formatDateTime } from "../../utils/format";
import { AdminUnauthorizedPage } from "../admin/AdminStatusPages";

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
  if (!status) return "muted";
  if (status === "completed" || status === "resolved") return "ok";
  if (status === "failed") return "err";
  if (status === "started" || status === "open") return "warn";
  if (status === "ignored") return "muted";
  return "muted";
};

const deltaTone = (value?: number | string | null) => {
  const numeric = parseNumber(value);
  if (numeric === null) return "var(--neft-text-muted)";
  if (numeric > 0) return "var(--neft-error)";
  if (numeric < 0) return "var(--neft-success)";
  return "var(--neft-text-muted)";
};


export function ReconciliationRunDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { toast, showToast } = useToast();
  const [run, setRun] = useState<ReconciliationRun | null>(null);
  const [discrepancies, setDiscrepancies] = useState<ReconciliationDiscrepancy[]>([]);
  const [links, setLinks] = useState<ReconciliationLink[]>([]);
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
  const [detailTarget, setDetailTarget] = useState<ReconciliationDiscrepancy | null>(null);
  const [detailLoadingId, setDetailLoadingId] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [exportingFormat, setExportingFormat] = useState<"json" | "csv" | null>(null);
  const [exportScope, setExportScope] = useState<"full" | "discrepancies">("full");
  const [exportDiscrepancyStatus, setExportDiscrepancyStatus] = useState<"" | "open" | "resolved" | "ignored">("");
  const [exportDiscrepancyType, setExportDiscrepancyType] = useState("");

  const loadRun = useCallback(() => {
    if (!id) return;
    setLoading(true);
    setError(null);
    setUnauthorized(false);
    Promise.all([getRun(id), listDiscrepancies(id), listRunLinks(id)])
      .then(([runResponse, discrepancyResponse, linkResponse]) => {
        if (runResponse.unavailable || discrepancyResponse.unavailable || linkResponse.unavailable) {
          setNotAvailable(true);
          setRun(null);
          setDiscrepancies([]);
          setLinks([]);
          setDetailTarget(null);
          return;
        }
        setNotAvailable(false);
        setRun(runResponse.run);
        setDiscrepancies(discrepancyResponse.discrepancies ?? []);
        setLinks(linkResponse.links ?? []);
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
      {
        label: "Links matched",
        value: run.link_counts?.matched ?? getSummaryNumber(run.summary, ["links_matched"]) ?? "—",
      },
      {
        label: "Links mismatched",
        value: run.link_counts?.mismatched ?? getSummaryNumber(run.summary, ["links_mismatched"]) ?? "—",
      },
      {
        label: "Links pending",
        value: run.link_counts?.pending ?? getSummaryNumber(run.summary, ["links_pending"]) ?? "—",
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

  const handleDownloadExport = useCallback(
    async (format: "json" | "csv") => {
      if (!run) return;
      setExportingFormat(format);
      try {
        const options: ReconciliationRunExportOptions = {
          export_scope: exportScope,
          discrepancy_status: exportDiscrepancyStatus,
          discrepancy_type: exportDiscrepancyType,
        };
        const payload = await downloadRunExport(run.id, format, options);
        if (payload.unavailable) {
          setNotAvailable(true);
          showToast("error", "Reconciliation export is not available in this environment");
          return;
        }
        const url = URL.createObjectURL(payload.blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = payload.fileName ?? `reconciliation_run_${run.id}.${format}`;
        anchor.click();
        URL.revokeObjectURL(url);
      } catch (err) {
        if (err instanceof UnauthorizedError) {
          setUnauthorized(true);
          return;
        }
        showToast("error", (err as Error).message);
      } finally {
        setExportingFormat(null);
      }
    },
    [exportDiscrepancyStatus, exportDiscrepancyType, exportScope, run, showToast],
  );

  const handleOpenDiscrepancy = useCallback(
    async (item: ReconciliationDiscrepancy) => {
      setDetailError(null);
      setDetailLoadingId(item.id);
      try {
        const response = await getDiscrepancy(item.id);
        if (response.unavailable || !response.discrepancy) {
          setNotAvailable(true);
          showToast("error", "Discrepancy detail is not available in this environment");
          return;
        }
        setDetailTarget(response.discrepancy);
      } catch (err) {
        if (err instanceof UnauthorizedError) {
          setUnauthorized(true);
          return;
        }
        const message = (err as Error).message;
        setDetailError(message);
        showToast("error", message);
      } finally {
        setDetailLoadingId(null);
      }
    },
    [showToast],
  );

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
    if (detailTarget?.id === resolveTarget.id) {
      setDetailTarget(null);
    }
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
    if (detailTarget?.id === ignoreTarget.id) {
      setDetailTarget(null);
    }
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
        render: (item) => <span className="neft-chip neft-chip-info">{item.discrepancy_type}</span>,
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
          <span className={`neft-chip neft-chip-${statusBadge(item.status)}`}>{item.status ?? "unknown"}</span>
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
          <button
            type="button"
            className="ghost"
            onClick={() => void handleOpenDiscrepancy(item)}
            disabled={detailLoadingId === item.id}
          >
            {detailLoadingId === item.id ? "Loading..." : "View"}
          </button>
        ),
      },
    ],
    [detailLoadingId, handleOpenDiscrepancy, notAvailable],
  );

  const linkColumns = useMemo<Column<ReconciliationLink>[]>(
    () => [
      {
        key: "id",
        title: "Link ID",
        render: (item) => (
          <div className="stack-inline" style={{ gap: 8 }}>
            <span>{item.id}</span>
            <CopyButton value={item.id} />
          </div>
        ),
      },
      {
        key: "entity",
        title: "Entity",
        render: (item) => (
          <div>
            <div>{item.entity_type}</div>
            <div className="muted small">{item.entity_id}</div>
          </div>
        ),
      },
      {
        key: "expected",
        title: "Expected",
        render: (item) => (
          <div>
            <div>{formatValue(item.expected_amount)}</div>
            <div className="muted small">{item.currency}</div>
          </div>
        ),
      },
      {
        key: "direction",
        title: "Direction",
        render: (item) => item.direction,
      },
      {
        key: "status",
        title: "Link status",
        render: (item) => <span className={`neft-chip neft-chip-${statusBadge(item.status)}`}>{item.status}</span>,
      },
      {
        key: "review",
        title: "Review",
        render: (item) =>
          item.review_status ? (
            <div>
              <div className={`neft-chip neft-chip-${statusBadge(item.review_status)}`}>{item.review_status}</div>
              {item.discrepancy_ids.length ? <div className="muted small">{item.discrepancy_ids.join(", ")}</div> : null}
            </div>
          ) : (
            <span className="muted">—</span>
          ),
      },
      {
        key: "match_key",
        title: "Match key",
        render: (item) => item.match_key ?? "—",
      },
      {
        key: "expected_at",
        title: "Expected at",
        render: (item) => formatDateTime(item.expected_at),
      },
    ],
    [],
  );

  const exportDiscrepancyTypeOptions = useMemo(
    () =>
      Array.from(new Set(discrepancies.map((item) => item.discrepancy_type).filter(Boolean))).map((value) => ({
        label: value,
        value,
      })),
    [discrepancies],
  );

  if (unauthorized) {
    return <AdminUnauthorizedPage />;
  }

  return (
    <div className="stack">
      <Toast toast={toast} />
      <section className="neft-card">
        <div className="card__header" style={{ justifyContent: "space-between", gap: 16 }}>
          <div>
            <h1 style={{ fontSize: 24, fontWeight: 700 }}>Run {run?.id ?? ""}</h1>
            <div className="stack-inline" style={{ flexWrap: "wrap" }}>
              <span className={`neft-chip neft-chip-${statusBadge(run?.status)}`}>{run?.status ?? "unknown"}</span>
              <span className={`neft-chip ${run?.scope === "external" ? "neft-chip-info" : "neft-chip-ok"}`}>
                {run?.scope ?? "unknown"}
              </span>
              {run?.provider ? <span className="muted">{run.provider}</span> : null}
              <span className="muted">{formatDate(run?.period_start)} — {formatDate(run?.period_end)}</span>
            </div>
          </div>
          <div className="stack-inline">
            <button type="button" className="ghost" onClick={() => navigate("/reconciliation")}>Back</button>
            <button
              type="button"
              className="neft-btn-secondary"
              onClick={() => void handleDownloadExport("json")}
              disabled={!run || exportingFormat !== null}
            >
              {exportingFormat === "json" ? "Exporting JSON..." : "Export JSON"}
            </button>
            <button
              type="button"
              className="neft-btn-secondary"
              onClick={() => void handleDownloadExport("csv")}
              disabled={!run || exportingFormat !== null}
            >
              {exportingFormat === "csv" ? "Exporting CSV..." : "Export CSV"}
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
        {run?.statement ? (
          <div className="card-grid" style={{ marginTop: 16 }}>
            <div className="neft-card">
              <div className="muted" style={{ marginBottom: 8 }}>
                Statement
              </div>
              <div className="stack">
                <div className="stack-inline" style={{ gap: 8 }}>
                  <span>{run.statement.id}</span>
                  <CopyButton value={run.statement.id} />
                </div>
                <div className="muted small">
                  {run.statement.provider} · {run.statement.currency} · {formatDate(run.statement.period_start)} —{" "}
                  {formatDate(run.statement.period_end)}
                </div>
              </div>
            </div>
          </div>
        ) : null}
        <div className="filters" style={{ marginTop: 16 }}>
          <SelectFilter
            label="Export scope"
            value={exportScope}
            onChange={(value) => setExportScope(value === "discrepancies" ? "discrepancies" : "full")}
            options={[
              { label: "Full run", value: "full" },
              { label: "Discrepancies only", value: "discrepancies" },
            ]}
            allowEmpty={false}
          />
          <SelectFilter
            label="Discrepancy status"
            value={exportDiscrepancyStatus}
            onChange={(value) =>
              setExportDiscrepancyStatus(
                value === "open" || value === "resolved" || value === "ignored" ? value : "",
              )
            }
            options={[
              { label: "Open", value: "open" },
              { label: "Resolved", value: "resolved" },
              { label: "Ignored", value: "ignored" },
            ]}
          />
          <SelectFilter
            label="Discrepancy type"
            value={exportDiscrepancyType}
            onChange={setExportDiscrepancyType}
            options={exportDiscrepancyTypeOptions}
          />
        </div>
      </section>

      {showAudit && run?.audit_event_id ? (
        <section className="neft-card">
          <h3>Audit integrity</h3>
          <div className="stack">
            <div
              className={`neft-chip ${
                auditIntegrity === "verified"
                  ? "neft-chip-ok"
                  : auditIntegrity === "broken"
                    ? "neft-chip-err"
                    : "neft-chip-muted"
              }`}
            >
              {auditIntegrity}
            </div>
            <p className="muted">
              Audit integrity is derived from hash chain and signatures when available. If verification endpoints are
              not configured, status remains unknown.
            </p>
          </div>
        </section>
      ) : null}

      {detailTarget ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal" style={{ maxWidth: 960 }}>
            <div className="stack-inline" style={{ justifyContent: "space-between", gap: 12, alignItems: "center" }}>
              <div>
                <h3 style={{ marginTop: 0, marginBottom: 8 }}>Discrepancy {detailTarget.id}</h3>
                <div className="stack-inline" style={{ gap: 8, flexWrap: "wrap" }}>
                  <span className={`neft-chip neft-chip-${statusBadge(detailTarget.status)}`}>{detailTarget.status}</span>
                  <span className="neft-chip neft-chip-info">{detailTarget.discrepancy_type}</span>
                  <span className="muted">{formatDateTime(detailTarget.created_at)}</span>
                </div>
              </div>
              <button type="button" className="ghost" onClick={() => setDetailTarget(null)}>
                Close
              </button>
            </div>
            {detailError ? <div className="card error-state">{detailError}</div> : null}
            <div className="stack" style={{ gap: 16 }}>
              <JsonViewer value={detailTarget.details ?? {}} redactionMode="audit" title="Details" />
              {detailTarget.resolution ? (
                <JsonViewer value={detailTarget.resolution} redactionMode="audit" title="Resolution" />
              ) : null}
              {detailTarget.adjustment_explain ? (
                <div className="card">
                  <div className="muted" style={{ marginBottom: 8 }}>Adjustment explain</div>
                  <div className="stack" style={{ gap: 8 }}>
                    <div className="stack-inline" style={{ gap: 8 }}>
                      <span>{detailTarget.adjustment_explain.adjustment_tx_id}</span>
                      <CopyButton value={detailTarget.adjustment_explain.adjustment_tx_id} />
                    </div>
                    <div className="muted small">
                      {detailTarget.adjustment_explain.transaction_type ?? "unknown"} · ref{" "}
                      {detailTarget.adjustment_explain.external_ref_type ?? "—"} /{" "}
                      {detailTarget.adjustment_explain.external_ref_id ?? "—"}
                    </div>
                    <div className="muted small">
                      tenant: {detailTarget.adjustment_explain.tenant_id ?? "—"} · total:{" "}
                      {formatValue(detailTarget.adjustment_explain.total_amount)} · currency:{" "}
                      {detailTarget.adjustment_explain.currency ?? "—"} · posted:{" "}
                      {detailTarget.adjustment_explain.posted_at
                        ? formatDateTime(detailTarget.adjustment_explain.posted_at)
                        : "—"}
                    </div>
                    {detailTarget.adjustment_explain.meta ? (
                      <JsonViewer value={detailTarget.adjustment_explain.meta} redactionMode="audit" title="Ledger meta" />
                    ) : null}
                    <div className="stack" style={{ gap: 6 }}>
                      {detailTarget.adjustment_explain.entries.map((entry) => (
                        <div key={entry.entry_hash} className="card">
                          <div className="stack-inline" style={{ justifyContent: "space-between", gap: 12 }}>
                            <strong>{entry.account_type}</strong>
                            <span>{entry.direction}</span>
                          </div>
                          <div className="muted small">
                            {formatValue(entry.amount)} {entry.currency} · client {entry.client_id ?? "—"}
                          </div>
                        </div>
                      ))}
                    </div>
                    {detailTarget.adjustment_explain.audit_events.length ? (
                      <div className="card">
                        <div className="muted" style={{ marginBottom: 8 }}>Adjustment audit</div>
                        <div className="stack">
                          {detailTarget.adjustment_explain.audit_events.map((event) => (
                            <div key={`${event.entity_type}-${event.entity_id}-${event.ts}-${event.event_type}`} className="card">
                              <div className="stack-inline" style={{ justifyContent: "space-between", gap: 12 }}>
                                <strong>{event.event_type}</strong>
                                <span className="muted">{formatDateTime(event.ts)}</span>
                              </div>
                              <div className="muted small">
                                {event.action}
                                {event.actor_id ? ` · ${event.actor_id}` : ""}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </div>
                </div>
              ) : null}
              {detailTarget.timeline?.length ? (
                <div className="card">
                  <div className="muted" style={{ marginBottom: 8 }}>Discrepancy timeline</div>
                  <div className="stack">
                    {detailTarget.timeline.map((event) => (
                      <div key={`${event.entity_type}-${event.entity_id}-${event.ts}-${event.event_type}`} className="card">
                        <div className="stack-inline" style={{ justifyContent: "space-between", gap: 12 }}>
                          <strong>{event.event_type}</strong>
                          <span className="muted">{formatDateTime(event.ts)}</span>
                        </div>
                        <div className="muted small">
                          {event.action}
                          {event.reason ? ` · ${event.reason}` : ""}
                          {event.actor_id ? ` · ${event.actor_id}` : ""}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}

      {notAvailable ? <div className="neft-card">Reconciliation API not available in this environment</div> : null}
      {error ? <div className="neft-card error-state">{error}</div> : null}

      <div className="card-grid" style={{ marginBottom: 16 }}>
        {summaryCards.map((card) => (
          <div key={card.label} className="neft-card">
            <div className="muted" style={{ marginBottom: 8 }}>
              {card.label}
            </div>
            <div style={{ fontSize: 20, fontWeight: 700 }}>{card.value}</div>
          </div>
        ))}
      </div>

      {run?.timeline?.length ? (
        <section className="neft-card">
          <h3>Run timeline</h3>
          <div className="stack">
            {run.timeline.map((item) => (
              <div key={`${item.ts}-${item.event_type}`} className="card">
                <div className="stack-inline" style={{ justifyContent: "space-between", gap: 12 }}>
                  <strong>{item.event_type}</strong>
                  <span className="muted">{formatDateTime(item.ts)}</span>
                </div>
                <div className="muted small">
                  {item.action}
                  {item.reason ? ` · ${item.reason}` : ""}
                  {item.actor_id ? ` · ${item.actor_id}` : ""}
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : null}

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
        <Table
          columns={linkColumns}
          data={links}
          loading={loading}
          emptyState={{ title: "No run links", description: "This run has no persisted reconciliation links." }}
        />
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
