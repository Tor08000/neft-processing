import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  createExternalRun,
  getDiscrepancy,
  getStatement,
  listStatementDiscrepancies,
  listStatements,
  uploadStatement,
  type ExternalStatement,
  type ReconciliationDiscrepancy,
} from "../../api/reconciliation";
import { UnauthorizedError } from "../../api/client";
import { DateRangeFilter } from "../../components/Filters/DateRangeFilter";
import { SelectFilter } from "../../components/Filters/SelectFilter";
import { CopyButton } from "../../components/CopyButton/CopyButton";
import { Table, type Column } from "../../components/Table/Table";
import { JsonViewer } from "../../components/common/JsonViewer";
import { Toast } from "../../components/common/Toast";
import { useToast } from "../../components/Toast/useToast";
import { formatDate, formatDateTime } from "../../utils/format";
import { AdminUnauthorizedPage } from "../admin/AdminStatusPages";

const formatPeriod = (start?: string | null, end?: string | null) =>
  `${formatDate(start)} — ${formatDate(end)}`;

const parseNumber = (value: string): number | null => {
  if (!value) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
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

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value && typeof value === "object" && !Array.isArray(value));

export function ReconciliationStatementsPage() {
  const navigate = useNavigate();
  const { toast, showToast } = useToast();
  const [statements, setStatements] = useState<ExternalStatement[]>([]);
  const [provider, setProvider] = useState("");
  const [dateRange, setDateRange] = useState<{ from?: string; to?: string }>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notAvailable, setNotAvailable] = useState(false);
  const [unauthorized, setUnauthorized] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadProvider, setUploadProvider] = useState("");
  const [uploadCurrency, setUploadCurrency] = useState("");
  const [uploadStart, setUploadStart] = useState("");
  const [uploadEnd, setUploadEnd] = useState("");
  const [uploadTotalIn, setUploadTotalIn] = useState("");
  const [uploadTotalOut, setUploadTotalOut] = useState("");
  const [uploadClosing, setUploadClosing] = useState("");
  const [uploadLines, setUploadLines] = useState("");
  const [viewStatement, setViewStatement] = useState<ExternalStatement | null>(null);
  const [viewLoading, setViewLoading] = useState(false);
  const [viewDiscrepancies, setViewDiscrepancies] = useState<ReconciliationDiscrepancy[]>([]);
  const [viewDiscrepancyError, setViewDiscrepancyError] = useState<string | null>(null);
  const [discrepancyDetail, setDiscrepancyDetail] = useState<ReconciliationDiscrepancy | null>(null);
  const [discrepancyDetailLoadingId, setDiscrepancyDetailLoadingId] = useState<string | null>(null);

  const loadStatements = useCallback(() => {
    setIsLoading(true);
    setError(null);
    setUnauthorized(false);
    listStatements({ provider: provider || undefined })
      .then((data) => {
        if (data.unavailable) {
          setNotAvailable(true);
          setStatements([]);
          return;
        }
        setNotAvailable(false);
        setStatements(data.statements ?? []);
      })
      .catch((err: unknown) => {
        if (err instanceof UnauthorizedError) {
          setUnauthorized(true);
          return;
        }
        setError((err as Error).message);
      })
      .finally(() => setIsLoading(false));
  }, [provider]);

  useEffect(() => {
    loadStatements();
  }, [loadStatements]);

  const providerOptions = useMemo(() => {
    const unique = new Set(statements.map((item) => item.provider).filter(Boolean));
    return Array.from(unique).map((value) => ({ label: value, value }));
  }, [statements]);

  const filteredStatements = useMemo(() => {
    return statements.filter((statement) => matchesDateRange(statement.period_end, dateRange.from, dateRange.to));
  }, [dateRange.from, dateRange.to, statements]);

  const columns = useMemo<Column<ExternalStatement>[]>(
    () => [
      {
        key: "id",
        title: "Statement ID",
        render: (item) => (
          <div className="stack-inline" style={{ gap: 8 }}>
            <span>{item.id}</span>
            <CopyButton value={item.id} />
          </div>
        ),
      },
      { key: "provider", title: "Provider", render: (item) => item.provider },
      { key: "period", title: "Period", render: (item) => formatPeriod(item.period_start, item.period_end) },
      { key: "currency", title: "Currency", render: (item) => item.currency },
      {
        key: "totals",
        title: "Totals",
        render: (item) => (
          <div>
            <div>In: {item.total_in ?? "—"}</div>
            <div>Out: {item.total_out ?? "—"}</div>
            <div>Closing: {item.closing_balance ?? "—"}</div>
          </div>
        ),
      },
      { key: "created", title: "Created at", render: (item) => formatDateTime(item.created_at) },
      {
        key: "actions",
        title: "Actions",
        render: (item) => (
          <div className="stack-inline">
            <button
              type="button"
              className="ghost"
              onClick={async () => {
                const response = await createExternalRun({ statement_id: item.id });
                if (response.unavailable) {
                  setNotAvailable(true);
                  showToast("error", "Reconciliation API not available in this environment");
                  return;
                }
                if (response.run) {
                  showToast("success", "External run created");
                  navigate(`/reconciliation/runs/${response.run.id}`);
                }
              }}
              disabled={notAvailable}
            >
              Run reconciliation
            </button>
            <button
              type="button"
              className="ghost"
              onClick={async () => {
                setViewLoading(true);
                const [statementResponse, discrepancyResponse] = await Promise.all([
                  getStatement(item.id),
                  listStatementDiscrepancies(item.id),
                ]);
                setViewLoading(false);
                if (statementResponse.unavailable || discrepancyResponse.unavailable) {
                  setNotAvailable(true);
                  showToast("error", "Reconciliation API not available in this environment");
                  return;
                }
                setViewStatement(statementResponse.statement ?? item);
                setViewDiscrepancies(discrepancyResponse.discrepancies ?? []);
                setViewDiscrepancyError(null);
              }}
            >
              View
            </button>
          </div>
        ),
      },
    ],
    [navigate, notAvailable, showToast],
  );

  const handleUpload = async () => {
    setUploadError(null);
    if (!uploadProvider || !uploadCurrency || !uploadStart || !uploadEnd) {
      setUploadError("Provider, currency, and period are required");
      return;
    }
    const startDate = new Date(uploadStart);
    const endDate = new Date(uploadEnd);
    if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) {
      setUploadError("Invalid period dates");
      return;
    }
    if (endDate <= startDate) {
      setUploadError("End must be after start");
      return;
    }
    let parsedLines: Record<string, unknown>[] | null = null;
    if (uploadLines.trim()) {
      try {
        const parsed = JSON.parse(uploadLines);
        if (!Array.isArray(parsed)) {
          setUploadError("Lines must be a JSON array");
          return;
        }
        const requiredKeys = ["id", "at", "amount", "direction", "ref"];
        for (const item of parsed) {
          if (!isRecord(item) || !requiredKeys.every((key) => key in item)) {
            setUploadError("Each line must include id, at, amount, direction, ref");
            return;
          }
        }
        parsedLines = parsed as Record<string, unknown>[];
      } catch {
        setUploadError("Lines must be valid JSON");
        return;
      }
    }

    const response = await uploadStatement({
      provider: uploadProvider,
      period_start: startDate.toISOString(),
      period_end: endDate.toISOString(),
      currency: uploadCurrency,
      totals: {
        total_in: parseNumber(uploadTotalIn),
        total_out: parseNumber(uploadTotalOut),
        closing_balance: parseNumber(uploadClosing),
      },
      lines: parsedLines,
    });

    if (response.unavailable) {
      setNotAvailable(true);
      showToast("error", "Reconciliation API not available in this environment");
      return;
    }

    if (response.statement) {
      showToast("success", "Statement uploaded");
      setUploadOpen(false);
      setUploadProvider("");
      setUploadCurrency("");
      setUploadStart("");
      setUploadEnd("");
      setUploadTotalIn("");
      setUploadTotalOut("");
      setUploadClosing("");
      setUploadLines("");
      loadStatements();
    }
  };

  const openDiscrepancyDetail = useCallback(
    async (discrepancyId: string) => {
      setViewDiscrepancyError(null);
      setDiscrepancyDetailLoadingId(discrepancyId);
      try {
        const response = await getDiscrepancy(discrepancyId);
        if (response.unavailable || !response.discrepancy) {
          setNotAvailable(true);
          showToast("error", "Reconciliation API not available in this environment");
          return;
        }
        setDiscrepancyDetail(response.discrepancy);
      } catch (err) {
        if (err instanceof UnauthorizedError) {
          setUnauthorized(true);
          return;
        }
        const message = (err as Error).message;
        setViewDiscrepancyError(message);
        showToast("error", message);
      } finally {
        setDiscrepancyDetailLoadingId(null);
      }
    },
    [showToast],
  );

  if (unauthorized) {
    return <AdminUnauthorizedPage />;
  }

  return (
    <div className="stack">
      <Toast toast={toast} />
      <section className="card">
        <div className="card__header" style={{ justifyContent: "space-between", gap: 16 }}>
          <div>
            <h1 style={{ fontSize: 24, fontWeight: 700 }}>External statements</h1>
            <p className="muted">Upload external statements and trigger reconciliation runs.</p>
          </div>
          <div className="stack-inline">
            <button type="button" className="neft-btn-secondary" onClick={() => setUploadOpen(true)}>
              Upload statement
            </button>
          </div>
        </div>
        <div className="filters">
          <SelectFilter label="Provider" value={provider} onChange={setProvider} options={providerOptions} />
          <DateRangeFilter label="Period end" from={dateRange.from} to={dateRange.to} onChange={setDateRange} />
        </div>
      </section>

      {notAvailable ? <div className="card">Reconciliation API not available in this environment</div> : null}
      {error ? <div className="card error-state">{error}</div> : null}

      <Table
        columns={columns}
        data={filteredStatements}
        loading={isLoading}
        emptyState={{ title: "No statements yet", description: "Upload a statement to begin reconciliation." }}
      />

      {uploadOpen ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal">
            <h3 style={{ marginTop: 0 }}>Upload statement</h3>
            <label className="filter">
              Provider
              <input value={uploadProvider} onChange={(event) => setUploadProvider(event.target.value)} />
            </label>
            <label className="filter">
              Currency
              <input value={uploadCurrency} onChange={(event) => setUploadCurrency(event.target.value)} />
            </label>
            <label className="filter">
              Period start
              <input type="datetime-local" value={uploadStart} onChange={(event) => setUploadStart(event.target.value)} />
            </label>
            <label className="filter">
              Period end
              <input type="datetime-local" value={uploadEnd} onChange={(event) => setUploadEnd(event.target.value)} />
            </label>
            <div className="card" style={{ marginBottom: 12 }}>
              <div className="muted">Totals</div>
              <label className="filter">
                Total in
                <input value={uploadTotalIn} onChange={(event) => setUploadTotalIn(event.target.value)} />
              </label>
              <label className="filter">
                Total out
                <input value={uploadTotalOut} onChange={(event) => setUploadTotalOut(event.target.value)} />
              </label>
              <label className="filter">
                Closing balance
                <input value={uploadClosing} onChange={(event) => setUploadClosing(event.target.value)} />
              </label>
            </div>
            <label className="filter">
              Lines JSON
              <textarea
                value={uploadLines}
                onChange={(event) => setUploadLines(event.target.value)}
                rows={6}
                placeholder='[{"id":"line-1","at":"2024-01-01T00:00:00Z","amount":100,"direction":"in","ref":"ref"}]'
              />
            </label>
            {uploadError ? <div className="card error-state">{uploadError}</div> : null}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 16 }}>
              <button type="button" className="ghost" onClick={() => setUploadOpen(false)}>
                Cancel
              </button>
              <button type="button" className="neft-btn-secondary" onClick={handleUpload}>
                Upload
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {viewStatement ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal" style={{ maxWidth: 720 }}>
            <h3 style={{ marginTop: 0 }}>Statement {viewStatement.id}</h3>
            <div className="stack">
              <div>
                <div className="muted">Provider</div>
                <div>{viewStatement.provider}</div>
              </div>
              <div>
                <div className="muted">Period</div>
                <div>{formatPeriod(viewStatement.period_start, viewStatement.period_end)}</div>
              </div>
              <div>
                <div className="muted">Totals</div>
                <div>
                  In: {viewStatement.total_in ?? "—"} · Out: {viewStatement.total_out ?? "—"} · Closing:{" "}
                  {viewStatement.closing_balance ?? "—"}
                </div>
              </div>
              {viewLoading ? <div className="muted">Loading explain…</div> : null}
              {viewStatement.explain ? (
                <div className="card">
                  <div className="muted" style={{ marginBottom: 8 }}>
                    Statement explain
                  </div>
                  <div className="stack">
                    <div>
                      Related run:{" "}
                      {viewStatement.explain.related_run_id ? (
                        <button
                          type="button"
                          className="ghost"
                          onClick={() => navigate(`/reconciliation/runs/${viewStatement.explain?.related_run_id}`)}
                        >
                          {viewStatement.explain.related_run_id}
                        </button>
                      ) : (
                        "—"
                      )}
                    </div>
                    <div className="muted small">
                      Relation source: {viewStatement.explain.relation_source ?? "—"} · run status:{" "}
                      {viewStatement.explain.related_run_status ?? "—"}
                    </div>
                    <div>
                      Lines: {viewStatement.explain.line_count} · matched: {viewStatement.explain.matched_links} ·
                      mismatched: {viewStatement.explain.mismatched_links} · pending: {viewStatement.explain.pending_links}
                    </div>
                    <div>
                      Unmatched external: {viewStatement.explain.unmatched_external} · unmatched internal:{" "}
                      {viewStatement.explain.unmatched_internal} · amount mismatches:{" "}
                      {viewStatement.explain.mismatched_amount}
                    </div>
                    <div>
                      Open: {viewStatement.explain.open_discrepancies} · resolved:{" "}
                      {viewStatement.explain.resolved_discrepancies} · ignored:{" "}
                      {viewStatement.explain.ignored_discrepancies} · adjusted:{" "}
                      {viewStatement.explain.adjusted_discrepancies}
                    </div>
                    <div className="stack" style={{ gap: 8 }}>
                      {viewStatement.explain.total_checks.map((item) => (
                        <div key={item.kind} className="card">
                          <div className="stack-inline" style={{ justifyContent: "space-between", gap: 12 }}>
                            <strong>{item.kind}</strong>
                            <span className={`neft-chip neft-chip-${item.status === "matched" ? "ok" : item.status === "mismatch" ? "warn" : "muted"}`}>
                              {item.status}
                            </span>
                          </div>
                          <div className="muted small">
                            external: {item.external_amount ?? "—"} · internal: {item.internal_amount ?? "—"} · delta:{" "}
                            {item.delta ?? "—"}
                          </div>
                          {item.discrepancy_id ? (
                            <div style={{ marginTop: 8 }}>
                              <button
                                type="button"
                                className="ghost"
                                onClick={() => void openDiscrepancyDetail(item.discrepancy_id!)}
                                disabled={discrepancyDetailLoadingId === item.discrepancy_id}
                              >
                                {discrepancyDetailLoadingId === item.discrepancy_id
                                  ? "Loading discrepancy..."
                                  : `Open discrepancy ${item.discrepancy_id}`}
                              </button>
                            </div>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : null}
              <div className="card">
                <div className="muted" style={{ marginBottom: 8 }}>
                  Statement discrepancies
                </div>
                {viewDiscrepancyError ? <div className="card error-state">{viewDiscrepancyError}</div> : null}
                {viewLoading ? (
                  <div className="muted">Loading discrepancies…</div>
                ) : viewDiscrepancies.length ? (
                  <div className="stack">
                    {viewDiscrepancies.map((item) => (
                      <div key={item.id} className="card">
                        <div className="stack-inline" style={{ justifyContent: "space-between", gap: 12 }}>
                          <div>
                            <strong>{item.discrepancy_type}</strong>
                            <div className="muted small">
                              {item.status} · delta {item.delta ?? "—"} · {formatDateTime(item.created_at)}
                            </div>
                          </div>
                          <div className="stack-inline" style={{ gap: 8 }}>
                            {viewStatement.explain?.related_run_id ? (
                              <button
                                type="button"
                                className="ghost"
                                onClick={() => navigate(`/reconciliation/runs/${viewStatement.explain?.related_run_id}`)}
                              >
                                Open run
                              </button>
                            ) : null}
                            <button
                              type="button"
                              className="ghost"
                              onClick={() => void openDiscrepancyDetail(item.id)}
                              disabled={discrepancyDetailLoadingId === item.id}
                            >
                              {discrepancyDetailLoadingId === item.id ? "Loading..." : "Open discrepancy"}
                            </button>
                          </div>
                        </div>
                        {item.adjustment_explain ? (
                          <div className="muted small" style={{ marginTop: 8 }}>
                            Adjustment: {item.adjustment_explain.adjustment_tx_id} ·{" "}
                            {item.adjustment_explain.transaction_type ?? "unknown"} ·{" "}
                            {item.adjustment_explain.total_amount ?? "—"} {item.adjustment_explain.currency ?? ""}
                          </div>
                        ) : null}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="muted">No discrepancies linked to this statement.</div>
                )}
              </div>
              {viewStatement.audit_event_id ? (
                <div>
                  <div className="muted">Audit event</div>
                  <div className="stack-inline" style={{ gap: 8 }}>
                    <span>{viewStatement.audit_event_id}</span>
                    <CopyButton value={viewStatement.audit_event_id} />
                  </div>
                </div>
              ) : null}
              {viewStatement.timeline?.length ? (
                <div className="card">
                  <div className="muted" style={{ marginBottom: 8 }}>
                    Timeline
                  </div>
                  <div className="stack">
                    {viewStatement.timeline.map((item) => (
                      <div key={`${item.ts}-${item.event_type}`} className="card">
                        <div className="stack-inline" style={{ justifyContent: "space-between", gap: 12 }}>
                          <strong>{item.event_type}</strong>
                          <span className="muted">{formatDateTime(item.ts)}</span>
                        </div>
                        <div className="muted small">
                          {item.action}
                          {item.reason ? ` · ${item.reason}` : ""}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
              <JsonViewer value={viewStatement.lines ?? []} redactionMode="audit" title="Lines" />
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 16 }}>
              <button
                type="button"
                className="ghost"
                onClick={() => {
                  setViewStatement(null);
                  setViewDiscrepancies([]);
                  setDiscrepancyDetail(null);
                  setViewDiscrepancyError(null);
                }}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      ) : null}
      {discrepancyDetail ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal" style={{ maxWidth: 900 }}>
            <div className="stack-inline" style={{ justifyContent: "space-between", gap: 12, alignItems: "center" }}>
              <div>
                <h3 style={{ marginTop: 0, marginBottom: 8 }}>Discrepancy {discrepancyDetail.id}</h3>
                <div className="muted small">
                  {discrepancyDetail.discrepancy_type} · {discrepancyDetail.status} · {formatDateTime(discrepancyDetail.created_at)}
                </div>
              </div>
              <button type="button" className="ghost" onClick={() => setDiscrepancyDetail(null)}>
                Close
              </button>
            </div>
            <div className="stack" style={{ gap: 16 }}>
              <JsonViewer value={discrepancyDetail.details ?? {}} redactionMode="audit" title="Details" />
              {discrepancyDetail.resolution ? (
                <JsonViewer value={discrepancyDetail.resolution} redactionMode="audit" title="Resolution" />
              ) : null}
              {discrepancyDetail.adjustment_explain ? (
                <div className="card">
                  <div className="muted" style={{ marginBottom: 8 }}>Adjustment explain</div>
                  <div className="stack" style={{ gap: 8 }}>
                    <div className="stack-inline" style={{ gap: 8 }}>
                      <span>{discrepancyDetail.adjustment_explain.adjustment_tx_id}</span>
                      <CopyButton value={discrepancyDetail.adjustment_explain.adjustment_tx_id} />
                    </div>
                    <div className="muted small">
                      {discrepancyDetail.adjustment_explain.transaction_type ?? "unknown"} · ref{" "}
                      {discrepancyDetail.adjustment_explain.external_ref_type ?? "—"} /{" "}
                      {discrepancyDetail.adjustment_explain.external_ref_id ?? "—"}
                    </div>
                    <div className="muted small">
                      tenant: {discrepancyDetail.adjustment_explain.tenant_id ?? "—"} · total:{" "}
                      {discrepancyDetail.adjustment_explain.total_amount ?? "—"} · currency:{" "}
                      {discrepancyDetail.adjustment_explain.currency ?? "—"}
                    </div>
                  </div>
                </div>
              ) : null}
              {discrepancyDetail.timeline?.length ? (
                <div className="card">
                  <div className="muted" style={{ marginBottom: 8 }}>Discrepancy timeline</div>
                  <div className="stack">
                    {discrepancyDetail.timeline.map((item) => (
                      <div key={`${item.entity_type}-${item.entity_id}-${item.ts}-${item.event_type}`} className="card">
                        <div className="stack-inline" style={{ justifyContent: "space-between", gap: 12 }}>
                          <strong>{item.event_type}</strong>
                          <span className="muted">{formatDateTime(item.ts)}</span>
                        </div>
                        <div className="muted small">
                          {item.action}
                          {item.reason ? ` · ${item.reason}` : ""}
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
    </div>
  );
}

export default ReconciliationStatementsPage;
