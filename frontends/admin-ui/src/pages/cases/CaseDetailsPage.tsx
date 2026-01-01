import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import {
  closeAdminCase,
  fetchAdminCaseDetails,
  isNotAvailableError,
  listCaseEvents,
  updateAdminCaseStatus,
  type CaseDetailsResponse,
  type CaseEvent,
  type CaseItem,
  type CaseSnapshot,
  type CaseStatus,
  type CaseEventType,
  type CaseFieldChange,
} from "../../api/adminCases";
import { UnauthorizedError } from "../../api/client";
import { computeExplainScore } from "../../gamification/score";
import type { ExplainV2Response } from "../../types/explainV2";
import { recordActionApplied, recordCaseClosed } from "../../mastery/events";
import { loadMasteryEvents } from "../../mastery/storage";
import type { MasteryEvent } from "../../mastery/types";
import { Tabs } from "../../components/common/Tabs";
import { JsonViewer } from "../../components/common/JsonViewer";
import { CloseCaseModal, getSelectedActionsCount } from "../../components/cases/CloseCaseModal";
import { Toast } from "../../components/common/Toast";
import { useToast } from "../../components/Toast/useToast";
import { loadCaseExports } from "../../utils/caseExportRegistry";
import { CopyChip } from "../../components/common/CopyChip";
import { isRedactedValue, redactForAudit } from "../../redaction/apply";
import type { RedactedValue } from "../../redaction/types";
import { computeChain, verifyChain } from "../../audit_chain/chain";
import type { ChainLink, ChainVerificationResult } from "../../audit_chain/types";

const statusTone = (status: CaseStatus) => {
  if (status === "CLOSED") return "badge badge-danger";
  if (status === "IN_PROGRESS") return "badge badge-success";
  return "badge";
};

const formatTimestamp = (value?: string | null) => {
  if (!value) return "—";
  return new Date(value).toLocaleString("ru-RU");
};

const resolveTitle = (id: string, kind?: string | null, title?: string | null) =>
  title ?? (kind ? `${kind} · ${id}` : `Case ${id}`);

const isForbidden = (error: unknown) => error instanceof Error && /HTTP 403\b/.test(error.message);

const toScoreSnapshot = (snapshot?: CaseSnapshot | null) => {
  const explain = snapshot?.explain_snapshot as ExplainV2Response | null | undefined;
  if (!explain) return undefined;
  return computeExplainScore(explain);
};

const sortSnapshots = (snapshots?: CaseSnapshot[] | null) =>
  (snapshots ?? []).slice().sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());

const EVENT_TYPE_LABELS: Record<CaseEventType, string> = {
  CASE_CREATED: "Case created",
  STATUS_CHANGED: "Status changed",
  CASE_CLOSED: "Case closed",
  NOTE_UPDATED: "Note updated",
  ACTIONS_APPLIED: "Actions applied",
  EXPORT_CREATED: "Export created",
};

const EVENT_TYPE_ICONS: Record<CaseEventType, string> = {
  CASE_CREATED: "🟢",
  STATUS_CHANGED: "🔄",
  CASE_CLOSED: "✅",
  NOTE_UPDATED: "📝",
  ACTIONS_APPLIED: "⚙️",
  EXPORT_CREATED: "📦",
};

const EVENT_FILTERS: CaseEventType[] = [
  "CASE_CREATED",
  "STATUS_CHANGED",
  "CASE_CLOSED",
  "NOTE_UPDATED",
  "ACTIONS_APPLIED",
  "EXPORT_CREATED",
];

const EXPORT_KIND_LABELS: Record<NonNullable<NonNullable<CaseEvent["meta"]>["export_ref"]>["kind"], string> = {
  explain_export: "Explain export",
  diff_export: "Diff export",
  case_export: "Case export",
};

const toEventLabel = (event: CaseEvent) => EVENT_TYPE_LABELS[event.type] ?? event.type;

const formatActor = (actor?: CaseEvent["actor"] | null) => actor?.name ?? actor?.email ?? actor?.id ?? "System";

const renderRedactedValue = (value: RedactedValue): ReactNode => {
  const tooltip = `${value.reason.message} (${value.reason.kind}:${value.reason.rule})`;
  return (
    <span className="audit-redacted" title={tooltip}>
      <span aria-hidden="true">🔒</span> {value.display}
      {value.hash ? <span className="muted small"> ({value.hash})</span> : null}
    </span>
  );
};

const renderAuditValue = (fieldPath: string, value: unknown): ReactNode => {
  const redacted = redactForAudit(fieldPath, value);
  if (isRedactedValue(redacted)) {
    return renderRedactedValue(redacted);
  }
  if (value === null || value === undefined) {
    return <span className="muted">—</span>;
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return <span>{String(value)}</span>;
  }
  const preview = Array.isArray(value) ? "[…]" : "{…}";
  return (
    <details className="audit-json">
      <summary>
        <span className="code-inline">{preview}</span>
        <span className="audit-json__label">View JSON</span>
      </summary>
      <div className="audit-json__content">
        <JsonViewer value={value} redactionMode="audit" />
      </div>
    </details>
  );
};

const HASH_PREVIEW_LENGTH = 12;

const shortenHash = (value: string) =>
  value.length > HASH_PREVIEW_LENGTH ? `${value.slice(0, HASH_PREVIEW_LENGTH)}…` : value;

const HashCopy = ({ label, value }: { label: string; value: string }) => {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(false), 2000);
    return () => window.clearTimeout(timer);
  }, [copied]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
    } catch (err) {
      console.error("Copy failed", err);
    }
  };

  return (
    <div className="audit-hash">
      <span className="audit-hash__label">{label}</span>
      <span className="audit-hash__value" title={value}>
        {shortenHash(value)}
      </span>
      <button type="button" className="neft-btn-secondary audit-hash__button" onClick={handleCopy}>
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
};

const createChange = (field: string, from: unknown, to: unknown): CaseFieldChange => ({ field, from, to });

const buildSyntheticEvents = (caseItem: CaseItem): CaseEvent[] => {
  const events: CaseEvent[] = [];
  events.push({
    id: `synthetic_created_${caseItem.id}`,
    at: caseItem.created_at,
    type: "CASE_CREATED",
    actor: caseItem.created_by ? { email: caseItem.created_by } : null,
    source: "synthetic",
    meta: {
      changes: [
        createChange("status", null, "OPEN"),
        ...(caseItem.priority ? [createChange("priority", null, caseItem.priority)] : []),
      ],
      reason: "Derived from case fields",
    },
  });
  if (caseItem.status === "IN_PROGRESS" && caseItem.updated_at) {
    events.push({
      id: `synthetic_status_${caseItem.id}`,
      at: caseItem.updated_at,
      type: "STATUS_CHANGED",
      actor: null,
      source: "synthetic",
      meta: {
        changes: [createChange("status", "OPEN", "IN_PROGRESS")],
        reason: "Derived from case fields",
      },
    });
  }
  if (caseItem.closed_at) {
    events.push({
      id: `synthetic_closed_${caseItem.id}`,
      at: caseItem.closed_at,
      type: "CASE_CLOSED",
      actor: caseItem.closed_by ? { email: caseItem.closed_by } : null,
      source: "synthetic",
      meta: {
        changes: [createChange("status", "IN_PROGRESS", "CLOSED")],
        reason: "Derived from case fields",
      },
    });
  }
  return events;
};

const buildExportEvents = (caseId: string): CaseEvent[] =>
  loadCaseExports()
    .filter((entry) => entry.case_id === caseId)
    .map((entry) => ({
      id: `synthetic_export_${entry.id}`,
      at: entry.created_at,
      type: "EXPORT_CREATED" as const,
      actor: null,
      source: "local",
      meta: {
        export_ref: {
          kind:
            entry.type === "diff"
              ? "diff_export"
              : entry.type === "case"
                ? "case_export"
                : "explain_export",
          id: entry.id,
        },
        reason: "Local export registry",
      },
    }));

const buildMasteryEvents = (caseItem: CaseItem, masteryEvents: MasteryEvent[]): CaseEvent[] =>
  masteryEvents
    .filter((event) => event.case_id === caseItem.id)
    .map<CaseEvent | null>((event, index) => {
      if (event.type === "action_applied") {
        return {
          id: `synthetic_action_${caseItem.id}_${index}`,
          at: event.at,
          type: "ACTIONS_APPLIED",
          actor: null,
          source: "synthetic",
          meta: {
            selected_actions_count: event.selected_actions_count ?? null,
            reason: "Derived from mastery events",
          },
        };
      }
      if (event.type === "case_closed" && !caseItem.closed_at) {
        return {
          id: `synthetic_closed_mastery_${caseItem.id}_${index}`,
          at: event.at,
          type: "CASE_CLOSED",
          actor: null,
          source: "synthetic",
          meta: {
            changes: [createChange("status", "IN_PROGRESS", "CLOSED")],
            reason: "Derived from mastery events",
          },
        };
      }
      return null;
    })
    .filter((event): event is CaseEvent => event !== null);

export function CaseDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const { toast, showToast } = useToast();
  const [payload, setPayload] = useState<CaseDetailsResponse | null>(null);
  const [events, setEvents] = useState<CaseEvent[]>([]);
  const [optimisticEvents, setOptimisticEvents] = useState<CaseEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isEventsLoading, setIsEventsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [unauthorized, setUnauthorized] = useState(false);
  const [notAvailable, setNotAvailable] = useState(false);
  const [actionsAvailable, setActionsAvailable] = useState(true);
  const [eventsAvailable, setEventsAvailable] = useState(true);
  const [closeOpen, setCloseOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("explain");
  const [isStatusUpdating, setIsStatusUpdating] = useState(false);
  const [selectedTypes, setSelectedTypes] = useState<CaseEventType[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [showSynthetic, setShowSynthetic] = useState(false);
  const [chainLinks, setChainLinks] = useState<ChainLink[]>([]);
  const [chainStatus, setChainStatus] = useState<ChainVerificationResult>({ status: "unknown" });

  const loadDetails = useCallback(() => {
    if (!id) return;
    setIsLoading(true);
    setError(null);
    setUnauthorized(false);
    fetchAdminCaseDetails(id)
      .then((data) => {
        setPayload(data);
        setNotAvailable(false);
        setActionsAvailable(true);
      })
      .catch((err: unknown) => {
        if (err instanceof UnauthorizedError || isForbidden(err)) {
          setUnauthorized(true);
          return;
        }
        if (isNotAvailableError(err)) {
          setNotAvailable(true);
          return;
        }
        setError((err as Error).message);
      })
      .finally(() => setIsLoading(false));
  }, [id]);

  const loadEvents = useCallback(() => {
    if (!id) return;
    setIsEventsLoading(true);
    listCaseEvents(id)
      .then((data) => {
        setEvents(data.items ?? []);
        setEventsAvailable(!data.unavailable);
        setOptimisticEvents([]);
      })
      .catch(() => {
        setEventsAvailable(true);
      })
      .finally(() => setIsEventsLoading(false));
  }, [id]);

  useEffect(() => {
    loadDetails();
    loadEvents();
  }, [loadDetails, loadEvents]);

  const snapshotsSorted = useMemo(() => sortSnapshots(payload?.snapshots), [payload?.snapshots]);
  const firstSnapshot = snapshotsSorted[0];
  const lastSnapshot = snapshotsSorted[snapshotsSorted.length - 1] ?? payload?.latest_snapshot;
  const selectedActionsCount = getSelectedActionsCount(lastSnapshot);
  const masteryEvents = useMemo(() => loadMasteryEvents(), []);
  const syntheticEvents = useMemo(() => {
    if (!payload) return [];
    const caseEvents = buildSyntheticEvents(payload.case);
    const exportEvents = buildExportEvents(payload.case.id);
    const masteryDerived = buildMasteryEvents(payload.case, masteryEvents);
    return [...caseEvents, ...exportEvents, ...masteryDerived].sort(
      (a, b) => new Date(a.at).getTime() - new Date(b.at).getTime(),
    );
  }, [payload, masteryEvents]);

  const hasRemoteEvents = eventsAvailable && events.length > 0;
  const showSyntheticToggle = hasRemoteEvents && syntheticEvents.length > 0;

  const baseEvents = useMemo(() => {
    if (hasRemoteEvents) return events;
    if (!eventsAvailable || events.length === 0) return syntheticEvents;
    return events;
  }, [events, eventsAvailable, hasRemoteEvents, syntheticEvents]);

  const combinedEvents = useMemo(() => {
    const includeSynthetic = showSyntheticToggle && showSynthetic;
    const merged = includeSynthetic ? [...baseEvents, ...syntheticEvents] : baseEvents;
    const withOptimistic = [...merged, ...optimisticEvents];
    return withOptimistic.sort((a, b) => new Date(a.at).getTime() - new Date(b.at).getTime());
  }, [baseEvents, optimisticEvents, showSyntheticToggle, showSynthetic, syntheticEvents]);

  const filteredEvents = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return combinedEvents.filter((event) => {
      if (selectedTypes.length > 0 && !selectedTypes.includes(event.type)) {
        return false;
      }
      if (!query) return true;
      const actor = event.actor;
      const changeFields = event.meta?.changes?.map((change) => change.field) ?? [];
      const haystack = [
        event.type,
        actor?.email,
        actor?.name,
        actor?.id,
        event.request_id,
        event.trace_id,
        ...changeFields,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(query);
    });
  }, [combinedEvents, searchQuery, selectedTypes]);

  const chainLinksById = useMemo(
    () => new Map(chainLinks.map((link) => [link.event_id, link])),
    [chainLinks],
  );

  useEffect(() => {
    let isActive = true;
    const run = async () => {
      if (!payload?.case.id || filteredEvents.length === 0) {
        if (isActive) {
          setChainLinks([]);
          setChainStatus({ status: "unknown" });
        }
        return;
      }
      try {
        const links = await computeChain(payload.case.id, filteredEvents);
        const verification = await verifyChain(payload.case.id, filteredEvents, links);
        if (!isActive) return;
        setChainLinks(links);
        setChainStatus(verification);
      } catch (err) {
        console.error("Audit chain verification failed", err);
        if (!isActive) return;
        setChainLinks([]);
        setChainStatus({ status: "unknown" });
      }
    };
    void run();
    return () => {
      isActive = false;
    };
  }, [filteredEvents, payload?.case.id]);

  const tabOptions = useMemo(
    () => [
      { id: "explain", label: "Explain JSON" },
      { id: "diff", label: "Diff JSON" },
      { id: "actions", label: "Selected actions" },
    ],
    [],
  );

  const handleCopyLink = useCallback(() => {
    void navigator.clipboard.writeText(window.location.href);
    showToast("success", "Link copied");
  }, [showToast]);

  const handleMarkInProgress = async () => {
    if (!id || !payload) return;
    setIsStatusUpdating(true);
    try {
      const previousStatus = payload.case.status;
      const response = await updateAdminCaseStatus(id, "IN_PROGRESS");
      if (response) {
        setPayload((prev) => (prev ? { ...prev, case: response } : prev));
      } else {
        setPayload((prev) => (prev ? { ...prev, case: { ...prev.case, status: "IN_PROGRESS" } } : prev));
      }
      setOptimisticEvents((prev) => [
        ...prev,
        {
          id: `synthetic_status_${Date.now()}`,
          at: new Date().toISOString(),
          type: "STATUS_CHANGED",
          actor: null,
          source: "local",
          meta: {
            changes: [createChange("status", previousStatus, "IN_PROGRESS")],
            reason: "Updated from UI",
          },
        },
      ]);
      if (eventsAvailable) {
        loadEvents();
      }
      showToast("success", "Status updated");
    } catch (err) {
      if (isNotAvailableError(err)) {
        setActionsAvailable(false);
        showToast("error", "Not available in this environment");
      } else {
        showToast("error", (err as Error).message);
      }
    } finally {
      setIsStatusUpdating(false);
    }
  };

  const handleClose = async (payloadInput: { resolutionNote: string; actionsApplied: boolean }) => {
    if (!id || !payload) return;
    try {
      const response = await closeAdminCase(id, {
        resolution_note: payloadInput.resolutionNote,
        resolution_code: null,
      });
      const updatedCase =
        response ?? {
          ...payload.case,
          status: "CLOSED" as CaseStatus,
          closed_at: new Date().toISOString(),
        };
      setPayload((prev) => (prev ? { ...prev, case: { ...prev.case, ...updatedCase } } : prev));
      setCloseOpen(false);
      setOptimisticEvents((prev) => [
        ...prev,
        {
          id: `synthetic_close_${Date.now()}`,
          at: new Date().toISOString(),
          type: "CASE_CLOSED",
          actor: null,
          source: "local",
          meta: {
            changes: [createChange("status", payload.case.status, "CLOSED")],
            reason: "Updated from UI",
          },
        },
      ]);
      if (eventsAvailable) {
        loadEvents();
      }
      const scoreSnapshot = toScoreSnapshot(lastSnapshot);
      recordCaseClosed(id, { scoreSnapshot });
      if (payloadInput.actionsApplied) {
        const scoreBefore = toScoreSnapshot(firstSnapshot);
        const scoreAfter = snapshotsSorted.length > 1 ? toScoreSnapshot(lastSnapshot) : undefined;
        recordActionApplied({
          caseId: id,
          selectedActionsCount,
          scoreBefore,
          scoreAfter,
        });
      }
      showToast("success", "Case closed");
    } catch (err) {
      if (isNotAvailableError(err)) {
        setActionsAvailable(false);
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

  if (!id) {
    return <div className="card">Case not found</div>;
  }

  if (unauthorized) {
    return <div className="card error-state">Not authorized</div>;
  }

  if (notAvailable) {
    return <div className="card">Not available in this environment</div>;
  }

  if (isLoading) {
    return <div className="card">Loading case...</div>;
  }

  if (error) {
    return <div className="card error-state">{error}</div>;
  }

  if (!payload) {
    return <div className="card">Case not found</div>;
  }

  const activeSnapshot = lastSnapshot ?? payload.latest_snapshot;
  const traceUrlTemplate = import.meta.env.VITE_OBSERVABILITY_TRACE_URL_TEMPLATE as string | undefined;
  const integrityLabel =
    chainStatus.status === "verified"
      ? "Integrity: Verified"
      : chainStatus.status === "broken"
        ? "Integrity: Broken"
        : "Integrity: Unknown";
  const integrityIcon =
    chainStatus.status === "verified" ? "✅" : chainStatus.status === "broken" ? "⚠️" : "ⓘ";
  const integrityTooltip =
    chainStatus.status === "verified"
      ? "Hash chain matches all events"
      : chainStatus.status === "broken"
        ? `Event sequence mismatch detected at #${(chainStatus.broken_at_index ?? 0) + 1}`
        : "Not enough data to verify chain";

  return (
    <div className="stack">
      <Toast toast={toast} />
      <section className="card">
        <div className="card__header">
          <div>
            <h2>{resolveTitle(payload.case.id, payload.case.kind, payload.case.title)}</h2>
            <p className="muted">Case ID: {payload.case.id}</p>
          </div>
          <div className="stack-inline">
            <button type="button" className="ghost" onClick={handleCopyLink}>
              Copy link
            </button>
            <Link className="ghost" to="/cases">
              Back to cases
            </Link>
          </div>
        </div>
        <div className="meta-grid">
          <div>
            <div className="label">Status</div>
            <span className={statusTone(payload.case.status)}>{payload.case.status}</span>
          </div>
          <div>
            <div className="label">Priority</div>
            <span className="badge">{payload.case.priority ?? "—"}</span>
          </div>
          <div>
            <div className="label">Created</div>
            <div>{formatTimestamp(payload.case.created_at)}</div>
          </div>
          <div>
            <div className="label">Created by</div>
            <div>{payload.case.created_by ?? "—"}</div>
          </div>
          <div>
            <div className="label">Closed</div>
            <div>{formatTimestamp(payload.case.closed_at)}</div>
          </div>
          <div>
            <div className="label">Closed by</div>
            <div>{payload.case.closed_by ?? "—"}</div>
          </div>
        </div>
        <div className="stack-inline" style={{ marginTop: 16 }}>
          <button
            type="button"
            className="neft-btn-secondary"
            onClick={handleMarkInProgress}
            disabled={payload.case.status !== "OPEN" || isStatusUpdating || !actionsAvailable}
            title={!actionsAvailable ? "Not available in this environment" : undefined}
          >
            Mark In Progress
          </button>
          <button
            type="button"
            className="neft-btn-primary"
            onClick={() => setCloseOpen(true)}
            disabled={payload.case.status === "CLOSED" || !actionsAvailable}
            title={!actionsAvailable ? "Not available in this environment" : undefined}
          >
            Close Case
          </button>
        </div>
      </section>

      <section className="card">
        <h3>Summary</h3>
        <div className="stack" style={{ gap: 12 }}>
          <div>
            <div className="label">Note</div>
            <div>{payload.case.note ?? "—"}</div>
          </div>
          <div className="meta-grid">
            <div>
              <div className="label">Updated</div>
              <div>{formatTimestamp(payload.case.updated_at)}</div>
            </div>
            <div>
              <div className="label">Kind</div>
              <div>{payload.case.kind ?? "—"}</div>
            </div>
          </div>
        </div>
      </section>

      <section className="card">
        <h3>Snapshots / Evidence</h3>
        {activeSnapshot ? (
          <div>
            <Tabs tabs={tabOptions} active={activeTab} onChange={setActiveTab} />
            {activeTab === "explain" ? (
              <JsonViewer title="Explain JSON" value={activeSnapshot.explain_snapshot} />
            ) : null}
            {activeTab === "diff" ? (
              activeSnapshot.diff_snapshot ? (
                <JsonViewer title="Diff JSON" value={activeSnapshot.diff_snapshot} />
              ) : (
                <div className="muted">Diff snapshot not available</div>
              )
            ) : null}
            {activeTab === "actions" ? (
              activeSnapshot.selected_actions ? (
                <JsonViewer title="Selected actions" value={activeSnapshot.selected_actions} />
              ) : (
                <div className="muted">No selected actions</div>
              )
            ) : null}
          </div>
        ) : (
          <div className="muted">Snapshots not available</div>
        )}
      </section>

      <section className="card">
        <div className="audit-header">
          <div>
            <h3>Audit timeline</h3>
            {!eventsAvailable ? (
              <p className="muted small">Events endpoint unavailable · Showing synthetic timeline</p>
            ) : null}
          </div>
          <div className={`audit-integrity audit-integrity--${chainStatus.status}`} title={integrityTooltip}>
            <span className="audit-integrity__icon" aria-hidden="true">
              {integrityIcon}
            </span>
            <span>{integrityLabel}</span>
          </div>
        </div>
        {chainStatus.status === "broken" ? (
          <div className="audit-integrity-details">
            <div className="audit-integrity-details__title">
              Mismatch detected at event #{(chainStatus.broken_at_index ?? 0) + 1}
            </div>
            <div className="audit-integrity-details__hashes">
              {chainStatus.expected_hash ? <HashCopy label="Expected" value={chainStatus.expected_hash} /> : null}
              {chainStatus.actual_hash ? <HashCopy label="Actual" value={chainStatus.actual_hash} /> : null}
            </div>
          </div>
        ) : null}
        <div className="audit-controls">
          <div className="audit-controls__filters">
            {EVENT_FILTERS.map((type) => (
              <label className="checkbox audit-filter" key={type}>
                <input
                  type="checkbox"
                  checked={selectedTypes.includes(type)}
                  onChange={(event) => {
                    setSelectedTypes((prev) => {
                      if (event.target.checked) {
                        return [...prev, type];
                      }
                      return prev.filter((entry) => entry !== type);
                    });
                  }}
                />
                <span>{EVENT_TYPE_LABELS[type]}</span>
              </label>
            ))}
          </div>
          <div className="audit-controls__search">
            <input
              type="search"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search by actor, field, request id"
            />
          </div>
          {showSyntheticToggle ? (
            <label className="checkbox audit-toggle">
              <input
                type="checkbox"
                checked={showSynthetic}
                onChange={(event) => setShowSynthetic(event.target.checked)}
              />
              <span>Show synthetic events</span>
            </label>
          ) : null}
        </div>
        {isEventsLoading ? (
          <div className="muted">Loading timeline...</div>
        ) : filteredEvents.length === 0 ? (
          <div className="muted">No events yet</div>
        ) : (
          <div className="audit-timeline" data-testid="audit-timeline">
            {filteredEvents.map((event, index) => {
              const isSynthetic = event.source === "synthetic" || event.id.startsWith("synthetic_");
              const isBroken = chainStatus.status === "broken" && chainStatus.broken_at_index === index;
              const exportRef = event.meta?.export_ref ?? null;
              const traceUrl =
                event.trace_id && traceUrlTemplate
                  ? traceUrlTemplate.replace("{trace_id}", event.trace_id)
                  : null;
              const chainLink = chainLinksById.get(event.id);
              return (
                <div className={`audit-item${isBroken ? " audit-item--broken" : ""}`} key={event.id}>
                  <div className="audit-item__marker">
                    <span className="audit-item__icon">{EVENT_TYPE_ICONS[event.type]}</span>
                  </div>
                  <div className="audit-item__content">
                    <div className="audit-item__header">
                      <div className="audit-item__title">
                        <span>{toEventLabel(event)}</span>
                        {isSynthetic ? <span className="pill pill--outline">Synthetic</span> : null}
                      </div>
                      <div className="audit-item__meta">
                        <span>{formatActor(event.actor)}</span>
                        <span className="muted small">{formatTimestamp(event.at)}</span>
                      </div>
                    </div>
                    {event.meta?.reason ? <div className="audit-item__reason">Reason: {event.meta.reason}</div> : null}
                    {event.meta?.selected_actions_count !== null && event.meta?.selected_actions_count !== undefined ? (
                      <div className="audit-item__reason">
                        Selected actions: {event.meta.selected_actions_count}
                      </div>
                    ) : null}
                    {event.meta?.changes && event.meta.changes.length > 0 ? (
                      <div className="audit-block">
                        <div className="label">Changes</div>
                        <table className="audit-table">
                          <thead>
                            <tr>
                              <th>Field</th>
                              <th>From</th>
                              <th>To</th>
                            </tr>
                          </thead>
                          <tbody>
                            {event.meta.changes.map((change) => (
                              <tr key={`${event.id}-${change.field}`}>
                                <td>{change.field}</td>
                                <td>{renderAuditValue(change.field, change.from)}</td>
                                <td>{renderAuditValue(change.field, change.to)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : null}
                    {event.request_id || event.trace_id ? (
                      <div className="audit-block">
                        <div className="label">Trace</div>
                        <div className="audit-trace">
                          {event.request_id ? <CopyChip label="Request ID" value={event.request_id} /> : null}
                          {event.trace_id ? <CopyChip label="Trace ID" value={event.trace_id} /> : null}
                          {traceUrl ? (
                            <a className="ghost" href={traceUrl} target="_blank" rel="noreferrer">
                              Open trace
                            </a>
                          ) : null}
                        </div>
                      </div>
                    ) : null}
                    {exportRef ? (
                      <div className="audit-block">
                        <div className="label">Artifacts</div>
                        <div className="audit-artifacts">
                          <span className="muted">{EXPORT_KIND_LABELS[exportRef.kind]}</span>
                          {exportRef.url ? (
                            <a className="neft-btn-secondary" href={exportRef.url}>
                              Open export
                            </a>
                          ) : (
                            <CopyChip label="Export ID" value={exportRef.id} />
                          )}
                        </div>
                      </div>
                    ) : null}
                    {chainLink ? (
                      <details className="audit-advanced">
                        <summary>Advanced</summary>
                        <div className="audit-advanced__content">
                          <HashCopy label="hash" value={chainLink.hash} />
                          <HashCopy label="prev" value={chainLink.prev_hash} />
                        </div>
                      </details>
                    ) : null}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      <CloseCaseModal
        open={closeOpen}
        caseItem={payload.case}
        selectedActionsCount={selectedActionsCount}
        onCancel={() => setCloseOpen(false)}
        onSubmit={handleClose}
      />
    </div>
  );
}

export default CaseDetailsPage;
