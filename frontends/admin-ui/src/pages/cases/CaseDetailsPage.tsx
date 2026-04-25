import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import {
  fetchCaseDetails,
  type CaseDetailsResponse,
  type CaseItem,
  type CaseSnapshot,
  type CaseStatus,
} from "../../api/cases";
import {
  closeAdminCase,
  isNotAvailableError,
  listCaseEvents,
  updateAdminCaseStatus,
  type CaseEvent,
  type CaseEventType,
  type CaseFieldChange,
} from "../../api/adminCases";
import {
  downloadCaseExport,
  listCaseExports,
  verifyCaseExport,
  type CaseExportItem,
  type CaseExportVerifyResult,
} from "../../api/adminExports";
import { listDecisionMemory, type DecisionMemoryEntry } from "../../api/decisionMemory";
import { UnauthorizedError } from "../../api/client";
import { computeExplainScore } from "../../gamification/score";
import { loadStreakState } from "../../gamification/streak";
import type { ExplainV2Response } from "../../types/explainV2";
import { recordActionApplied, recordCaseClosed } from "../../mastery/events";
import { buildMasterySnapshot } from "../../mastery/levels";
import { loadMasteryEvents, loadMasteryState } from "../../mastery/storage";
import type { MasteryEvent } from "../../mastery/types";
import { Tabs } from "../../components/common/Tabs";
import { JsonViewer } from "../../components/common/JsonViewer";
import { CloseCaseModal, getSelectedActionsCount } from "../../components/cases/CloseCaseModal";
import { Toast } from "../../components/common/Toast";
import { useToast } from "../../components/Toast/useToast";
import { useAdmin } from "../../admin/AdminContext";
import { AdminUnauthorizedPage } from "../admin/AdminStatusPages";
import { loadCaseExports } from "../../utils/caseExportRegistry";
import { CopyChip } from "../../components/common/CopyChip";
import { isRedactedValue, redactForAudit } from "../../redaction/apply";
import type { RedactedValue } from "../../redaction/types";
import { computeChain, verifyChain } from "../../audit_chain/chain";
import type { ChainLink, ChainVerificationResult } from "../../audit_chain/types";

const statusTone = (status: CaseStatus) => {
  if (status === "RESOLVED") return "neft-chip neft-chip-ok";
  if (status === "CLOSED") return "neft-chip neft-chip-err";
  return "neft-chip neft-chip-muted";
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

const TIMELINE_TABS = [
  { id: "audit", label: "Audit timeline" },
  { id: "decisions", label: "Decision History" },
];

const DECISION_TYPE_LABELS: Record<DecisionMemoryEntry["decision_type"], string> = {
  explain: "Explain",
  diff: "Diff",
  action: "Action",
  close: "Close",
};

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

const formatScoreSummary = (snapshot?: Record<string, unknown> | null) => {
  if (!snapshot) return "—";
  const parts: string[] = [];
  if ("score" in snapshot) parts.push(`score: ${String(snapshot.score)}`);
  if ("penalty" in snapshot) parts.push(`penalty: ${String(snapshot.penalty)}`);
  if ("confidence" in snapshot) parts.push(`confidence: ${String(snapshot.confidence)}`);
  return parts.length ? parts.join(" · ") : JSON.stringify(snapshot);
};

const formatMasterySummary = (snapshot?: Record<string, unknown> | null) => {
  if (!snapshot) return "—";
  const level = snapshot.level ? String(snapshot.level) : "—";
  const progress = snapshot.progress_to_next;
  if (typeof progress === "number") {
    return `${level} · ${Math.round(progress * 100)}%`;
  }
  return level;
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

const buildSyntheticEvents = (
  caseItem: CaseItem,
  timeline: Array<{ status: CaseStatus; occurred_at: string }>,
): CaseEvent[] => {
  const events: CaseEvent[] = [];
  const statusTimeline = timeline.length
    ? timeline
    : [{ status: caseItem.status, occurred_at: caseItem.created_at }];

  statusTimeline.forEach((entry, index) => {
    if (index === 0) {
      events.push({
        id: `synthetic_created_${caseItem.id}`,
        at: entry.occurred_at,
        type: "CASE_CREATED",
        actor: caseItem.created_by ? { email: caseItem.created_by } : null,
        source: "synthetic",
        meta: {
          changes: [
            createChange("status", null, entry.status),
            ...(caseItem.priority ? [createChange("priority", null, caseItem.priority)] : []),
          ],
          reason: "Derived from case lifecycle",
        },
      });
      return;
    }

    const previous = statusTimeline[index - 1];
    events.push({
      id: `synthetic_status_${caseItem.id}_${index}`,
      at: entry.occurred_at,
      type: entry.status === "CLOSED" ? "CASE_CLOSED" : "STATUS_CHANGED",
      actor: null,
      source: "synthetic",
      meta: {
        changes: [createChange("status", previous.status, entry.status)],
        reason: "Derived from case lifecycle",
      },
    });
  });

  if (events.length === 0) {
    events.push({
      id: `synthetic_created_${caseItem.id}`,
      at: caseItem.created_at,
      type: "CASE_CREATED",
      actor: caseItem.created_by ? { email: caseItem.created_by } : null,
      source: "synthetic",
      meta: {
        changes: [
          createChange("status", null, caseItem.status),
          ...(caseItem.priority ? [createChange("priority", null, caseItem.priority)] : []),
        ],
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
      if (event.type === "case_closed" && caseItem.status !== "CLOSED") {
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
  const { profile } = useAdmin();
  const { toast, showToast } = useToast();
  const [payload, setPayload] = useState<CaseDetailsResponse | null>(null);
  const [events, setEvents] = useState<CaseEvent[]>([]);
  const [optimisticEvents, setOptimisticEvents] = useState<CaseEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isEventsLoading, setIsEventsLoading] = useState(false);
  const [exports, setExports] = useState<CaseExportItem[]>([]);
  const [isExportsLoading, setIsExportsLoading] = useState(false);
  const [exportVerifications, setExportVerifications] = useState<Record<string, CaseExportVerifyResult>>({});
  const [exportVerifyLoading, setExportVerifyLoading] = useState<Record<string, boolean>>({});
  const [decisionHistory, setDecisionHistory] = useState<DecisionMemoryEntry[]>([]);
  const [isDecisionHistoryLoading, setIsDecisionHistoryLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [unauthorized, setUnauthorized] = useState(false);
  const [actionsAvailable, setActionsAvailable] = useState(true);
  const [eventsAvailable, setEventsAvailable] = useState(true);
  const [closeOpen, setCloseOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("explain");
  const [isStatusUpdating, setIsStatusUpdating] = useState(false);
  const [selectedTypes, setSelectedTypes] = useState<CaseEventType[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [showSynthetic, setShowSynthetic] = useState(false);
  const [timelineTab, setTimelineTab] = useState<"audit" | "decisions">("audit");
  const [chainLinks, setChainLinks] = useState<ChainLink[]>([]);
  const [chainStatus, setChainStatus] = useState<ChainVerificationResult>({ status: "unknown" });
  const canOperateCases = Boolean(profile?.permissions?.cases?.operate) && !profile?.read_only;
  const actionDisabledTitle = !canOperateCases
    ? "Requires cases operate capability"
    : !actionsAvailable
      ? "Not available in this environment"
      : undefined;

  const loadDetails = useCallback(async () => {
    if (!id) return;
    setIsLoading(true);
    setError(null);
    setUnauthorized(false);
    try {
      const data = await fetchCaseDetails(id, true);
      setPayload(data);
      setActionsAvailable(true);
    } catch (err: unknown) {
      if (err instanceof UnauthorizedError || isForbidden(err)) {
        setUnauthorized(true);
        throw err;
      }
      setError((err as Error).message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  const loadEvents = useCallback(async () => {
    if (!id) return;
    setIsEventsLoading(true);
    try {
      const data = await listCaseEvents(id);
      setEvents(data.items ?? []);
      setEventsAvailable(!data.unavailable);
      setOptimisticEvents([]);
    } catch (err) {
      setEventsAvailable(true);
      throw err;
    } finally {
      setIsEventsLoading(false);
    }
  }, [id]);

  const loadExports = useCallback(() => {
    if (!id) return;
    setIsExportsLoading(true);
    listCaseExports(id)
      .then((data) => {
        setExports(data.items ?? []);
        setExportVerifications({});
      })
      .catch((err: unknown) => {
        console.error("Failed to load exports", err);
        setExports([]);
      })
      .finally(() => setIsExportsLoading(false));
  }, [id]);

  const loadDecisionHistory = useCallback(() => {
    if (!id) return;
    setIsDecisionHistoryLoading(true);
    listDecisionMemory(id)
      .then((data) => {
        setDecisionHistory(data.items ?? []);
      })
      .catch((err: unknown) => {
        console.error("Failed to load decision history", err);
        setDecisionHistory([]);
      })
      .finally(() => setIsDecisionHistoryLoading(false));
  }, [id]);

  const handleVerifyExport = useCallback(
    async (exportId: string) => {
      setExportVerifyLoading((prev) => ({ ...prev, [exportId]: true }));
      try {
        const result = await verifyCaseExport(exportId);
        setExportVerifications((prev) => ({ ...prev, [exportId]: result }));
      } catch (err) {
        showToast("error", (err as Error).message);
      } finally {
        setExportVerifyLoading((prev) => ({ ...prev, [exportId]: false }));
      }
    },
    [showToast],
  );

  useEffect(() => {
    void loadDetails().catch(() => undefined);
    void loadEvents().catch(() => undefined);
    void loadExports();
    void loadDecisionHistory();
  }, [loadDetails, loadEvents, loadExports, loadDecisionHistory]);

  const snapshotsSorted = useMemo(() => sortSnapshots(payload?.snapshots), [payload?.snapshots]);
  const firstSnapshot = snapshotsSorted[0];
  const lastSnapshot = snapshotsSorted[snapshotsSorted.length - 1] ?? payload?.latest_snapshot;
  const selectedActionsCount = getSelectedActionsCount(lastSnapshot);
  const exportsById = useMemo(() => new Map(exports.map((item) => [item.id, item])), [exports]);
  const masteryEvents = useMemo(() => loadMasteryEvents(), []);
  const masterySnapshot = useMemo(
    () =>
      buildMasterySnapshot({
        events: masteryEvents,
        state: loadMasteryState(),
        streakCount: loadStreakState().count,
      }),
    [masteryEvents],
  );
  const masterySnapshotPayload = useMemo(
    () => ({
      level: masterySnapshot.level,
      progress_to_next: Number(masterySnapshot.progressToNext.toFixed(2)),
    }),
    [masterySnapshot.level, masterySnapshot.progressToNext],
  );
  const syntheticEvents = useMemo(() => {
    if (!payload) return [];
    const caseEvents = buildSyntheticEvents(payload.case, payload.timeline ?? []);
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

  const handleDownloadExport = useCallback(
    async (exportItem: CaseExportItem) => {
      try {
        const response = await downloadCaseExport(exportItem.id);
        window.open(response.url, "_blank", "noopener,noreferrer");
      } catch (err) {
        showToast("error", (err as Error).message);
      }
    },
    [showToast],
  );

  const handleOpenExportRef = useCallback(
    async (exportId: string) => {
      try {
        const response = await downloadCaseExport(exportId);
        window.open(response.url, "_blank", "noopener,noreferrer");
      } catch (err) {
        showToast("error", (err as Error).message);
      }
    },
    [showToast],
  );

  const handleMarkInProgress = async () => {
    if (!id || !payload || !canOperateCases) return;
    setIsStatusUpdating(true);
    try {
      await updateAdminCaseStatus(id, "IN_PROGRESS");
      await Promise.all([loadDetails(), loadEvents()]);
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
    if (!id || !payload || !canOperateCases) return;
    try {
      const scoreSnapshot = toScoreSnapshot(lastSnapshot);
      await closeAdminCase(id, {
        resolution_note: payloadInput.resolutionNote,
        resolution_code: null,
        score_snapshot: scoreSnapshot ?? null,
        mastery_snapshot: masterySnapshotPayload,
      });
      await Promise.all([loadDetails(), loadEvents()]);
      setCloseOpen(false);
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
    return <div className="neft-card">Case not found</div>;
  }

  if (unauthorized) {
    return <AdminUnauthorizedPage />;
  }

    if (isLoading) {
    return <div className="neft-card">Loading case...</div>;
  }

  if (error) {
    return <div className="neft-card error-state">{error}</div>;
  }

  if (!payload) {
    return <div className="neft-card">Case not found</div>;
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
      <section className="neft-card">
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
            <span className="neft-chip neft-chip-muted">{payload.case.priority ?? "—"}</span>
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
            <div>{payload.case.status === "CLOSED" ? formatTimestamp(payload.case.updated_at) : "—"}</div>
          </div>
          <div>
            <div className="label">Closed by</div>
            <div>—</div>
          </div>
        </div>
        <div className="stack-inline" style={{ marginTop: 16 }}>
          <button
            type="button"
            className="neft-btn-secondary"
            onClick={handleMarkInProgress}
            disabled={payload.case.status !== "TRIAGE" || isStatusUpdating || !actionsAvailable || !canOperateCases}
            title={actionDisabledTitle}
          >
            Mark In Progress
          </button>
          <button
            type="button"
            className="neft-btn-primary"
            onClick={() => setCloseOpen(true)}
            disabled={payload.case.status === "CLOSED" || !actionsAvailable || !canOperateCases}
            title={actionDisabledTitle}
          >
            Close Case
          </button>
        </div>
      </section>

      <section className="neft-card">
        <h3>Summary</h3>
        <div className="stack" style={{ gap: 12 }}>
          <div>
            <div className="label">Note</div>
            <div>{lastSnapshot?.note ?? (payload.comments.length ? payload.comments[payload.comments.length - 1]?.body : null) ?? "—"}</div>
          </div>
          <div>
            <div className="label">Description</div>
            <div>{payload.case.description ?? "—"}</div>
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
            <div>
              <div className="label">Queue</div>
              <div>{payload.case.queue ?? "—"}</div>
            </div>
            <div>
              <div className="label">Entity</div>
              <div>
                {payload.case.entity_type ?? "—"}
                {payload.case.entity_id ? ` · ${payload.case.entity_id}` : ""}
              </div>
            </div>
            <div>
              <div className="label">Client</div>
              <div>{payload.case.client_id ?? "—"}</div>
            </div>
            <div>
              <div className="label">Partner</div>
              <div>{payload.case.partner_id ?? "—"}</div>
            </div>
            <div>
              <div className="label">Source ref</div>
              <div>
                {payload.case.case_source_ref_type ?? "—"}
                {payload.case.case_source_ref_id ? ` · ${payload.case.case_source_ref_id}` : ""}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="neft-card">
        <h3>Lifecycle</h3>
        {payload.timeline.length === 0 ? (
          <div className="muted">No lifecycle events recorded</div>
        ) : (
          <div className="timeline-list">
            {payload.timeline.map((event, index) => (
              <div className="timeline-item" key={`${event.status}-${event.occurred_at}-${index}`}>
                <div className="timeline-item__meta">
                  <span className="timeline-item__title">{event.status}</span>
                  <span className="muted small">{formatTimestamp(event.occurred_at)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="neft-card">
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

      <section className="neft-card">
        <div className="card__header">
          <h3>Exports</h3>
        </div>
        {isExportsLoading ? (
          <div className="muted">Loading exports...</div>
        ) : exports.length === 0 ? (
          <div className="muted">No exports recorded</div>
        ) : (
          <table className="neft-table">
            <thead>
              <tr>
                <th>Kind</th>
                <th>Created</th>
                <th>SHA256</th>
                <th>Signature</th>
                <th>Key ID</th>
                <th>Verification</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {exports.map((exportItem) => {
                const isDeleted = Boolean(exportItem.deleted_at);
                const verification = exportVerifications[exportItem.id];
                const signature = exportItem.artifact_signature ?? null;
                const keyId = exportItem.artifact_signing_key_id ?? null;
                const verificationStatus = verification
                  ? verification.content_hash_verified &&
                    verification.artifact_signature_verified &&
                    verification.audit_chain_verified
                    ? "✅ Verified"
                    : "❌ Broken"
                  : "—";
                return (
                  <tr key={exportItem.id}>
                    <td>
                      <span className="neft-chip neft-chip-muted">{exportItem.kind}</span>
                      {isDeleted ? <span className="pill pill--outline">Deleted</span> : null}
                    </td>
                    <td>{formatTimestamp(exportItem.created_at)}</td>
                    <td title={exportItem.content_sha256}>{shortenHash(exportItem.content_sha256)}</td>
                    <td title={signature ?? undefined}>{signature ? shortenHash(signature) : "—"}</td>
                    <td title={keyId ?? undefined}>{keyId ? shortenHash(keyId) : "—"}</td>
                    <td>
                      <div className="stack-inline">
                        <span>{verificationStatus}</span>
                        <button
                          type="button"
                          className="neft-btn-secondary"
                          onClick={() => void handleVerifyExport(exportItem.id)}
                          disabled={isDeleted || exportVerifyLoading[exportItem.id]}
                        >
                          {exportVerifyLoading[exportItem.id] ? "Verifying..." : "Verify"}
                        </button>
                      </div>
                    </td>
                    <td>
                      <div className="stack-inline">
                        <button
                          type="button"
                          className="neft-btn-secondary"
                          onClick={() => void handleDownloadExport(exportItem)}
                          disabled={isDeleted}
                        >
                          Download
                        </button>
                        <CopyChip label="Export ID" value={exportItem.id} />
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>

      <section className="neft-card">
        <div className="card__header">
          <h3>Timeline</h3>
        </div>
        <Tabs tabs={TIMELINE_TABS} active={timelineTab} onChange={(id) => setTimelineTab(id as "audit" | "decisions")} />
        {timelineTab === "audit" ? (
          <>
            <div className="audit-header">
              <div>
                <h4>Audit timeline</h4>
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
                                <>
                                  <button
                                    type="button"
                                    className="neft-btn-secondary"
                                    onClick={() => void handleOpenExportRef(exportRef.id)}
                                  >
                                    Open export
                                  </button>
                                  <CopyChip label="Export ID" value={exportRef.id} />
                                </>
                              )}
                              {event.meta?.content_sha256 ? (
                                <CopyChip label="SHA256" value={event.meta.content_sha256} />
                              ) : null}
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
          </>
        ) : (
          <>
            <div className="audit-header">
              <div>
                <h4>Decision history</h4>
                <p className="muted small">Read-only decision memory linked to audit events</p>
              </div>
            </div>
            {isDecisionHistoryLoading ? (
              <div className="muted">Loading decision history...</div>
            ) : decisionHistory.length === 0 ? (
              <div className="muted">No decisions recorded</div>
            ) : (
              <table className="neft-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Type</th>
                    <th>Rationale</th>
                    <th>Score</th>
                    <th>Mastery</th>
                    <th>Links</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {decisionHistory.map((entry) => {
                    const auditStatus =
                      entry.audit_chain_verified && entry.audit_signature_verified ? "✅ Verified" : "❌ Broken";
                    const signatureStatus =
                      entry.artifact_signature_verified === null || entry.artifact_signature_verified === undefined
                        ? "—"
                        : entry.artifact_signature_verified
                          ? "✅ Verified"
                          : "❌ Broken";
                    const exportItem = exportsById.get(entry.decision_ref_id);
                    return (
                      <tr key={entry.id}>
                        <td>{formatTimestamp(entry.decision_at)}</td>
                        <td>{DECISION_TYPE_LABELS[entry.decision_type] ?? entry.decision_type}</td>
                        <td>{entry.rationale ?? "—"}</td>
                        <td>{formatScoreSummary(entry.score_snapshot ?? null)}</td>
                        <td>{formatMasterySummary(entry.mastery_snapshot ?? null)}</td>
                        <td>
                          <div className="stack-inline">
                            <CopyChip label="Audit event" value={entry.audit_event_id} />
                            {exportItem ? (
                              <button
                                type="button"
                                className="neft-btn-secondary"
                                onClick={() => void handleOpenExportRef(exportItem.id)}
                              >
                                Export
                              </button>
                            ) : null}
                          </div>
                        </td>
                        <td>
                          <div className="stack-inline">
                            <span>Audit: {auditStatus}</span>
                            <span>Signature: {signatureStatus}</span>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </>
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
