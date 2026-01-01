import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { createCase, type CaseKind, type CasePriority } from "../api/cases";
import { fetchExplainActions, fetchExplainDiff, fetchExplainV2, evaluateWhatIf } from "../api/explainV2";
import { CopyButton } from "../components/CopyButton/CopyButton";
import { JsonViewer } from "../components/common/JsonViewer";
import { Toast } from "../components/common/Toast";
import { useToast } from "../components/Toast/useToast";
import { reduceExplainDiffReasons, type ExplainDiffTab } from "../features/explain/diffReducer";
import {
  ACHIEVEMENT_DEFINITIONS,
  loadAchievementsState,
  loadAchievementStats,
  saveAchievementsState,
  saveAchievementStats,
  unlockAchievements,
  updateAchievementStats,
} from "../gamification/achievements";
import { computeExplainScore } from "../gamification/score";
import { loadStreakState, saveStreakState, updateStreak } from "../gamification/streak";
import type {
  AchievementEvent,
  AchievementStats,
  AchievementsState,
  ExplainScore,
  StreakState,
} from "../gamification/types";
import { recordCaseCreated, recordDiffRunSuccess, recordExplainRunSuccess } from "../mastery/events";
import { buildMasterySnapshot } from "../mastery/levels";
import { loadMasteryEvents, loadMasteryState } from "../mastery/storage";
import { recordCaseExport, type CaseExportType } from "../utils/caseExportRegistry";
import type {
  ExplainActionCatalogItem,
  ExplainDiffResponse,
  ExplainEvidence,
  ExplainReasonNode,
  ExplainV2Response,
  WhatIfResponse,
} from "../types/explainV2";
import {
  DEFAULT_EXPLAIN_QUERY_STATE,
  type ExplainMode,
  type ExplainQueryState,
  parseExplainQueryState,
  serializeExplainQueryState,
} from "./explainQueryState";

type EvidenceFilter = "all" | "linked";

type ExplainActionOption = ExplainActionCatalogItem & { recommended?: boolean };

type ErrorDetails = {
  title: string;
  message: string;
  details?: string | null;
};

const isCaseKind = (value: string): value is CaseKind =>
  value === "operation" || value === "invoice" || value === "order" || value === "kpi";

const percent = (value?: number | null) => {
  if (value === null || value === undefined) return "—";
  return `${Math.round(value * 100)}%`;
};

const formatTimestamp = (value?: string | null) => {
  if (!value) return "—";
  const date = new Date(value);
  return date.toLocaleString("ru-RU");
};

const formatTime = (value?: Date | null) => {
  if (!value) return "—";
  return value.toLocaleTimeString("ru-RU");
};

const scoreBandLabel = (band?: string | null) => {
  if (!band) return "—";
  const map: Record<string, string> = {
    low: "низкий",
    medium: "средний",
    high: "высокий",
    block: "блок",
    review: "проверка",
  };
  return map[band] ?? band;
};

const collectEvidenceRefs = (node: ExplainReasonNode): Set<string> => {
  const refs = new Set(node.evidence_refs ?? []);
  (node.children ?? []).forEach((child) => {
    collectEvidenceRefs(child).forEach((ref) => refs.add(ref));
  });
  return refs;
};

const confidenceLabel = (value?: number | null) => {
  if (value === null || value === undefined) return "—";
  if (value >= 0.75) return "High";
  if (value >= 0.4) return "Med";
  return "Low";
};

const renderEvidenceValue = (item: ExplainEvidence) => {
  if (item.value === null || item.value === undefined) return null;
  if (item.type === "metric" && typeof item.value === "object") {
    const actual = (item.value as Record<string, unknown>).actual ?? (item.value as Record<string, unknown>).value;
    const threshold =
      (item.value as Record<string, unknown>).threshold ?? (item.value as Record<string, unknown>).limit;
    if (actual !== undefined || threshold !== undefined) {
      return (
        <div className="explain-evidence__kv">
          <div>
            <span className="muted small">Actual</span>
            <strong>{String(actual ?? "—")}</strong>
          </div>
          <div>
            <span className="muted small">Threshold</span>
            <strong>{String(threshold ?? "—")}</strong>
          </div>
        </div>
      );
    }
  }
  if (item.type === "field" && typeof item.value === "object") {
    const home = (item.value as Record<string, unknown>).home;
    const station = (item.value as Record<string, unknown>).station;
    if (home !== undefined || station !== undefined) {
      return (
        <div className="explain-evidence__kv">
          <div>
            <span className="muted small">Home</span>
            <strong>{String(home ?? "—")}</strong>
          </div>
          <div>
            <span className="muted small">Station</span>
            <strong>{String(station ?? "—")}</strong>
          </div>
        </div>
      );
    }
  }
  if (typeof item.value === "object") {
    return (
      <details className="explain-evidence__details">
        <summary>Details</summary>
        <pre className="explain-evidence__value">{JSON.stringify(item.value, null, 2)}</pre>
      </details>
    );
  }
  return <pre className="explain-evidence__value">{JSON.stringify(item.value, null, 2)}</pre>;
};

const diffBadgeLabel: Record<string, string> = {
  removed: "убрано",
  weakened: "ослаблено",
  strengthened: "усилено",
  added: "добавлено",
  unchanged: "без изменений",
};

const formatDelta = (delta?: number | null) => {
  if (delta === null || delta === undefined) return "—";
  const sign = delta > 0 ? "+" : "";
  return `${sign}${delta.toFixed(2)}`;
};

const MODE_OPTIONS: { id: ExplainMode; label: string }[] = [
  { id: "explain", label: "Explain" },
  { id: "diff", label: "Diff" },
  { id: "actions", label: "Actions" },
  { id: "case", label: "Case" },
];

const CASE_PRIORITY_HINTS: Record<CasePriority, string> = {
  LOW: "1 · Низкий",
  MEDIUM: "2 · Средний",
  HIGH: "3 · Высокий",
  CRITICAL: "4 · Критичный",
};

const ReasonTreeNode = ({
  node,
  level,
  expanded,
  selectedId,
  onToggle,
  onSelect,
}: {
  node: ExplainReasonNode;
  level: number;
  expanded: Set<string>;
  selectedId?: string | null;
  onToggle: (id: string) => void;
  onSelect: (node: ExplainReasonNode) => void;
}) => {
  const hasChildren = Boolean(node.children && node.children.length);
  const isExpanded = expanded.has(node.id);
  const children = node.children ? [...node.children].sort((a, b) => b.weight - a.weight) : [];
  const evidenceCount = collectEvidenceRefs(node).size;

  return (
    <div className="explain-tree__node">
      <div className={`explain-tree__row${selectedId === node.id ? " is-selected" : ""}`}>
        <button type="button" className="explain-tree__toggle" onClick={() => onToggle(node.id)} disabled={!hasChildren}>
          {hasChildren ? (isExpanded ? "−" : "+") : "•"}
        </button>
        <button type="button" className="explain-tree__title" onClick={() => onSelect(node)}>
          <span className="explain-tree__label">
            {node.title}
            {selectedId === node.id ? <span className="explain-tree__selected">selected</span> : null}
          </span>
          <span className="explain-tree__meta">
            {evidenceCount ? <span className="explain-tree__count">{evidenceCount}</span> : null}
            <span className="explain-tree__weight">{percent(node.weight)}</span>
          </span>
        </button>
      </div>
      {hasChildren && isExpanded ? (
        <div className="explain-tree__children" style={{ marginLeft: level * 16 }}>
          {children.map((child) => (
            <ReasonTreeNode
              key={child.id}
              node={child}
              level={level + 1}
              expanded={expanded}
              selectedId={selectedId}
              onToggle={onToggle}
              onSelect={onSelect}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
};

const EvidenceCard = ({ item, highlighted }: { item: ExplainEvidence; highlighted: boolean }) => (
  <div className={`explain-evidence__card${highlighted ? " is-highlighted" : ""}`} data-evidence-id={item.id}>
    <div className="explain-evidence__meta">
      <div className="explain-evidence__chips">
        <span className="pill pill--neutral">{item.type}</span>
        <span className="pill pill--outline">{item.source ?? "unknown"}</span>
        <span className="pill pill--outline">Conf: {confidenceLabel(item.confidence)}</span>
        {highlighted ? <span className="pill pill--accent">связано</span> : null}
      </div>
    </div>
    <div className="explain-evidence__label">{item.label}</div>
    {renderEvidenceValue(item)}
  </div>
);

const ErrorNotice = ({ error }: { error: ErrorDetails }) => {
  const copyValue = `${error.title}\n${error.message}${error.details ? `\n${error.details}` : ""}`;
  return (
    <div className="card card--error explain-error">
      <div className="explain-error__meta">
        <div>
          <strong>{error.title}</strong>
          <div className="muted small">{error.message}</div>
          {error.details ? <div className="muted small">{error.details}</div> : null}
        </div>
        <CopyButton value={copyValue} label="Copy error details" />
      </div>
    </div>
  );
};

const EmptyState = ({ title, subtitle }: { title: string; subtitle?: string }) => (
  <div className="explain-empty">
    <strong>{title}</strong>
    {subtitle ? <span>{subtitle}</span> : null}
  </div>
);

const SummaryCard = ({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) => (
  <div className="explain-summary__card">
    <span className="explain-summary__label">{label}</span>
    <span className="explain-summary__value">{value}</span>
    {hint ? <span className="muted small">{hint}</span> : null}
  </div>
);

const SCORE_LABELS: Record<ExplainScore["level"], string> = {
  clean: "Clean",
  risky: "Risky",
  critical: "Critical",
};

const ScoreBadge = ({ score, compact }: { score: ExplainScore; compact?: boolean }) => (
  <span
    className={`score-badge score-badge--${score.level}${compact ? " score-badge--compact" : ""}`}
    title={`Explain score: ${SCORE_LABELS[score.level]}`}
  >
    {SCORE_LABELS[score.level]}
  </span>
);

const ConfidenceMeter = ({ confidence }: { confidence: number }) => (
  <div
    className="explain-metric explain-metric--confidence"
    title="Model confidence based on data completeness and signal strength"
  >
    <div className="explain-metric__bar">
      <div className="explain-metric__fill" style={{ width: `${Math.round(confidence * 100)}%` }} />
    </div>
    <span className="explain-metric__value">{percent(confidence)}</span>
  </div>
);

const PenaltyMarker = ({ penalty }: { penalty: number }) => {
  const tone = penalty >= 70 ? "critical" : penalty >= 40 ? "risky" : "clean";
  return (
    <span className={`penalty-marker penalty-marker--${tone}`} title="Penalty increased due to elevated risk signals">
      {penalty}
    </span>
  );
};

const ActionSelectionList = ({
  actions,
  selectedCodes,
  onToggle,
  limit,
}: {
  actions: ExplainActionOption[];
  selectedCodes: Set<string>;
  onToggle: (item: ExplainActionOption) => void;
  limit: number;
}) => (
  <div className="explain-actions">
    {actions.length ? (
      actions.map((action) => {
        const disabled = !selectedCodes.has(action.action_code) && selectedCodes.size >= limit;
        return (
          <label
            key={action.action_code}
            className={`explain-action${disabled ? " is-disabled" : ""}`}
            title={disabled ? `Максимум ${limit}` : undefined}
          >
            <input
              type="checkbox"
              checked={selectedCodes.has(action.action_code)}
              onChange={() => onToggle(action)}
              disabled={disabled}
            />
            <div className="explain-action__body">
              <div className="explain-action__title">
                {action.label}
                {action.recommended ? <span className="pill pill--accent">recommended</span> : null}
              </div>
              {action.description ? <div className="muted small">{action.description}</div> : null}
              {action.risk_hint ? <div className="muted small">Hint: {action.risk_hint}</div> : null}
            </div>
          </label>
        );
      })
    ) : (
      <div className="muted">Рекомендации отсутствуют.</div>
    )}
  </div>
);

export const ExplainPage = () => {
  const [searchParams] = useSearchParams();
  const { toast, showToast } = useToast();
  const [queryState, setQueryState] = useState<ExplainQueryState>(() => parseExplainQueryState(searchParams));
  const [payload, setPayload] = useState<ExplainV2Response | null>(null);
  const [actionsCatalog, setActionsCatalog] = useState<ExplainActionCatalogItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ErrorDetails | null>(null);
  const [filter, setFilter] = useState<EvidenceFilter>("all");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [whatIf, setWhatIf] = useState<WhatIfResponse | null>(null);
  const [whatIfError, setWhatIfError] = useState<string | null>(null);
  const [isWhatIfLoading, setIsWhatIfLoading] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [selectedReasonId, setSelectedReasonId] = useState<string | null>(null);
  const [selectedEvidenceIds, setSelectedEvidenceIds] = useState<Set<string>>(new Set());
  const [diffData, setDiffData] = useState<ExplainDiffResponse | null>(null);
  const [diffError, setDiffError] = useState<ErrorDetails | null>(null);
  const [isDiffLoading, setIsDiffLoading] = useState(false);
  const [reasonTab, setReasonTab] = useState<ExplainDiffTab>("strong");
  const [caseModalOpen, setCaseModalOpen] = useState(false);
  const [isCaseSubmitting, setIsCaseSubmitting] = useState(false);
  const [createdCaseId, setCreatedCaseId] = useState<string | null>(null);
  const [lastRunAt, setLastRunAt] = useState<Date | null>(null);
  const [lastRunDuration, setLastRunDuration] = useState<number | null>(null);
  const [streak, setStreak] = useState<StreakState>(() => loadStreakState());
  const [achievementStats, setAchievementStats] = useState<AchievementStats>(() => loadAchievementStats());
  const [achievements, setAchievements] = useState<AchievementsState>(() => loadAchievementsState());
  const [masterySnapshot, setMasterySnapshot] = useState(() =>
    buildMasterySnapshot({
      events: loadMasteryEvents(),
      state: loadMasteryState(),
      streakCount: loadStreakState().count,
    }),
  );

  const lastRunStateRef = useRef<ExplainQueryState | null>(null);
  const explainRequestIdRef = useRef(0);
  const diffRequestIdRef = useRef(0);
  const querySyncRef = useRef<string>("");
  const initialRunRef = useRef(false);

  const kind = searchParams.get("kind") ?? (searchParams.get("kpi_key") ? "kpi" : null);
  const entityId = searchParams.get("id");
  const kpiKey = searchParams.get("kpi_key");
  const windowDays = searchParams.get("window_days") ?? "7";

  useEffect(() => {
    setQueryState(parseExplainQueryState(searchParams));
  }, [searchParams]);

  useEffect(() => {
    const params = serializeExplainQueryState(queryState, new URLSearchParams(window.location.search));
    const nextSearch = params.toString();
    if (querySyncRef.current === nextSearch) return;
    querySyncRef.current = nextSearch;
    const url = new URL(window.location.href);
    url.search = nextSearch;
    window.history.replaceState({}, "", url.toString());
  }, [queryState]);

  useEffect(() => {
    if (payload?.reason_tree) {
      setExpanded(new Set([payload.reason_tree.id]));
      setSelectedReasonId(null);
      setSelectedEvidenceIds(new Set());
      setFilter("all");
    }
  }, [payload?.reason_tree]);

  useEffect(() => {
    setDiffData(null);
    setDiffError(null);
  }, [payload?.id, kind]);

  useEffect(() => {
    setReasonTab("strong");
  }, [diffData]);

  useEffect(() => {
    if (caseModalOpen) {
      setCreatedCaseId(null);
    }
  }, [caseModalOpen]);

  useEffect(() => {
    if (selectedReasonId) {
      setFilter("linked");
    } else {
      setFilter("all");
    }
  }, [selectedReasonId]);

  const registerAchievementEvent = useCallback((event: AchievementEvent) => {
    setAchievementStats((prevStats) => {
      const nextStats = updateAchievementStats(prevStats, event);
      saveAchievementStats(nextStats);
      setAchievements((prevAchievements) => {
        const nextAchievements = unlockAchievements(prevAchievements, nextStats);
        saveAchievementsState(nextAchievements);
        return nextAchievements;
      });
      return nextStats;
    });
  }, []);

  const refreshMasterySnapshot = useCallback(() => {
    setMasterySnapshot(
      buildMasterySnapshot({
        events: loadMasteryEvents(),
        state: loadMasteryState(),
        streakCount: streak.count,
      }),
    );
  }, [streak.count]);

  useEffect(() => {
    refreshMasterySnapshot();
  }, [refreshMasterySnapshot]);

  // TODO: wire recordCaseClosed / recordActionApplied when case workflows are available.

  const linkedEvidenceIds = useMemo(() => selectedEvidenceIds, [selectedEvidenceIds]);

  const evidence = useMemo(() => {
    const items = payload?.evidence ?? [];
    if (filter === "linked" && linkedEvidenceIds.size > 0) {
      return items.filter((item) => linkedEvidenceIds.has(item.id));
    }
    return items;
  }, [filter, linkedEvidenceIds, payload?.evidence]);

  const topReasons = useMemo(() => {
    const children = payload?.reason_tree?.children ?? [];
    return [...children]
      .sort((a, b) => b.weight - a.weight)
      .slice(0, 3)
      .map((node) => node.title);
  }, [payload?.reason_tree?.children]);

  const actionOptions = useMemo<ExplainActionOption[]>(() => {
    const merged = [
      ...(payload?.recommended_actions.map((item) => ({
        action_code: item.action_code,
        label: item.title,
        description: item.description ?? null,
        recommended: true,
      })) ?? []),
      ...actionsCatalog.map((item) => ({ ...item, recommended: false })),
    ];
    const seen = new Map<string, ExplainActionOption>();
    merged.forEach((item) => {
      if (!seen.has(item.action_code)) {
        seen.set(item.action_code, item);
      }
    });
    return Array.from(seen.values());
  }, [actionsCatalog, payload?.recommended_actions]);

  const selectedActionCodes = useMemo(() => new Set(queryState.selectedActions), [queryState.selectedActions]);

  const selectedActions = useMemo(() => {
    if (!queryState.selectedActions.length) return [];
    const mapped = new Map(actionOptions.map((item) => [item.action_code, item]));
    return queryState.selectedActions.map((code) =>
      mapped.get(code) ?? ({ action_code: code, label: code } satisfies ExplainActionCatalogItem),
    );
  }, [actionOptions, queryState.selectedActions]);

  const toggleAction = useCallback(
    (item: ExplainActionCatalogItem) => {
      setQueryState((prev) => {
        const exists = prev.selectedActions.includes(item.action_code);
        if (exists) {
          return { ...prev, selectedActions: prev.selectedActions.filter((code) => code !== item.action_code) };
        }
        if (prev.selectedActions.length >= 3) return prev;
        return { ...prev, selectedActions: [...prev.selectedActions, item.action_code] };
      });
    },
    [],
  );

  const loadExplain = useCallback(async () => {
    if (!kind) {
      setError({ title: "Explain failed", message: "Не указан тип explain." });
      return;
    }
    const requestId = ++explainRequestIdRef.current;
    const startedAt = performance.now();
    setIsLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = {};
      if (kind === "kpi") {
        if (!kpiKey) {
          setError({ title: "Explain failed", message: "Не указан KPI." });
          setIsLoading(false);
          return;
        }
        params.kpi_key = kpiKey;
        params.window_days = windowDays;
      } else if (entityId) {
        params.kind = kind;
        params.id = entityId;
      } else {
        setError({ title: "Explain failed", message: "Не указан идентификатор." });
        setIsLoading(false);
        return;
      }
      const [explainResult, actionsResult] = await Promise.allSettled([
        fetchExplainV2(params),
        fetchExplainActions(params),
      ]);
      if (requestId !== explainRequestIdRef.current) return;
      if (explainResult.status === "fulfilled") {
        const runAt = new Date();
        const scoreSnapshot = computeExplainScore(explainResult.value);
        setPayload(explainResult.value);
        setLastRunAt(runAt);
        setLastRunDuration(Math.round(performance.now() - startedAt));
        lastRunStateRef.current = queryState;
        setStreak((prev) => {
          const next = updateStreak(prev, runAt);
          saveStreakState(next);
          return next;
        });
        registerAchievementEvent("explain_run");
        recordExplainRunSuccess(scoreSnapshot);
        refreshMasterySnapshot();
      } else {
        setPayload(null);
        setError({ title: "Explain failed", message: explainResult.reason.message });
      }
      if (actionsResult.status === "fulfilled") {
        setActionsCatalog(actionsResult.value);
      } else {
        setActionsCatalog([]);
      }
    } catch (err) {
      if (requestId !== explainRequestIdRef.current) return;
      setError({ title: "Explain failed", message: (err as Error).message });
      setPayload(null);
    } finally {
      if (requestId === explainRequestIdRef.current) {
        setIsLoading(false);
      }
    }
  }, [entityId, kind, kpiKey, queryState, refreshMasterySnapshot, registerAchievementEvent, windowDays]);

  const loadDiff = useCallback(async () => {
    if (!kind) return;
    if (!queryState.leftSnapshot || !queryState.rightSnapshot) {
      setDiffError({ title: "Diff failed", message: "Укажите snapshot для сравнения." });
      return;
    }
    const requestId = ++diffRequestIdRef.current;
    setIsDiffLoading(true);
    setDiffError(null);
    try {
      const diffKind = (kind === "marketplace_order" ? "order" : kind) as
        | "operation"
        | "invoice"
        | "order"
        | "kpi";
      const response = await fetchExplainDiff({
        kind: diffKind,
        id: diffKind === "kpi" ? undefined : entityId ?? undefined,
        left_snapshot: queryState.leftSnapshot,
        right_snapshot: queryState.rightSnapshot,
        action_id: queryState.actionId || undefined,
      });
      if (requestId !== diffRequestIdRef.current) return;
      setDiffData(response);
      registerAchievementEvent("diff_run");
      recordDiffRunSuccess();
      refreshMasterySnapshot();
    } catch (err) {
      if (requestId !== diffRequestIdRef.current) return;
      setDiffError({ title: "Diff failed", message: (err as Error).message });
      setDiffData(null);
    } finally {
      if (requestId === diffRequestIdRef.current) {
        setIsDiffLoading(false);
      }
    }
  }, [
    entityId,
    kind,
    queryState.actionId,
    queryState.leftSnapshot,
    queryState.rightSnapshot,
    refreshMasterySnapshot,
    registerAchievementEvent,
  ]);

  const reasonSummary = useMemo(
    () => reduceExplainDiffReasons(diffData?.reasons_diff ?? [], reasonTab),
    [diffData?.reasons_diff, reasonTab],
  );

  const snapshotOptions = useMemo(() => {
    const options: { value: string; label: string }[] = [
      {
        value: "latest",
        label: payload?.generated_at ? `Последний · ${formatTimestamp(payload.generated_at)}` : "Последний",
      },
      { value: "previous", label: "Предыдущий" },
      { value: "baseline", label: "Baseline" },
    ];
    if (payload?.policy_snapshot) {
      options.push({ value: payload.policy_snapshot, label: `Policy · ${payload.policy_snapshot}` });
    }
    if (payload?.generated_at) {
      options.push({
        value: `generated_at:${payload.generated_at}`,
        label: `Generated · ${formatTimestamp(payload.generated_at)}`,
      });
    }
    const ensureOption = (value: string) => {
      if (!value) return;
      if (!options.some((item) => item.value === value)) {
        options.push({ value, label: `Выбран: ${value}` });
      }
    };
    ensureOption(queryState.leftSnapshot);
    ensureOption(queryState.rightSnapshot);
    return options;
  }, [queryState.leftSnapshot, payload?.generated_at, payload?.policy_snapshot, queryState.rightSnapshot]);

  const openWhatIf = useCallback(() => {
    setDrawerOpen(true);
    setWhatIf(null);
    setWhatIfError(null);
  }, []);

  const evaluate = useCallback(async () => {
    if (!kind || !entityId) return;
    const subjectType = kind === "operation" ? "FUEL_TX" : kind === "invoice" ? "INVOICE" : "ORDER";
    setIsWhatIfLoading(true);
    setWhatIfError(null);
    try {
      const response = await evaluateWhatIf({
        subject: { type: subjectType, id: entityId },
        max_candidates: Math.min(3, Math.max(1, queryState.selectedActions.length)),
      });
      setWhatIf(response);
    } catch (err) {
      setWhatIfError((err as Error).message);
      setWhatIf(null);
    } finally {
      setIsWhatIfLoading(false);
    }
  }, [entityId, kind, queryState.selectedActions.length]);

  const candidatesByAction = useMemo(() => {
    if (!whatIf) return new Map<string, WhatIfResponse["candidates"][number]>();
    return new Map(whatIf.candidates.map((candidate) => [candidate.action.code, candidate]));
  }, [whatIf]);

  const filteredCandidates = useMemo(() => {
    if (!selectedActions.length) return [];
    return selectedActions.map((action) => ({
      action,
      candidate: candidatesByAction.get(action.action_code) ?? null,
    }));
  }, [candidatesByAction, selectedActions]);

  const canCompare = kind !== "kpi" && entityId;
  const canDiff = Boolean(kind === "kpi" ? kpiKey : entityId);
  const caseKind = useMemo<CaseKind | null>(() => {
    if (!kind) return null;
    const normalized = kind === "marketplace_order" ? "order" : kind;
    return isCaseKind(normalized) ? normalized : null;
  }, [kind]);

  const explainScore = useMemo(() => computeExplainScore(payload), [payload]);
  const unlockedAchievements = useMemo(
    () => ACHIEVEMENT_DEFINITIONS.filter((achievement) => achievements[achievement.key]),
    [achievements],
  );
  const unlockedAchievementKeys = useMemo(
    () => unlockedAchievements.map((achievement) => achievement.key),
    [unlockedAchievements],
  );

  const handleCreateCase = useCallback(async () => {
    if (!payload || !caseKind) return;
    setIsCaseSubmitting(true);
    try {
      const candidatesByCode = new Map(
        (whatIf?.candidates ?? []).map((candidate) => [candidate.action.code, candidate]),
      );
      const selected = queryState.includeActions
        ? queryState.selectedActions.map((code) => ({
            code,
            what_if: candidatesByCode.get(code) ?? null,
          }))
        : null;
      const response = await createCase({
        kind: caseKind,
        entity_id: caseKind === "kpi" ? undefined : payload.id,
        kpi_key: caseKind === "kpi" ? payload.id : undefined,
        window_days: caseKind === "kpi" ? Number(windowDays) : undefined,
        priority: queryState.casePriority,
        note: queryState.caseNote || null,
        explain: queryState.includeExplain ? payload : null,
        diff: queryState.includeDiff ? diffData ?? null : null,
        selected_actions: selected,
      });
      setCreatedCaseId(response.id);
      setCaseModalOpen(false);
      registerAchievementEvent("case_created");
      recordCaseCreated({
        caseId: response.id,
        selectedActionsCount: queryState.includeActions ? queryState.selectedActions.length : 0,
        score: explainScore,
      });
      refreshMasterySnapshot();
      showToast("success", "Кейс создан");
    } catch (err) {
      showToast("error", (err as Error).message);
    } finally {
      setIsCaseSubmitting(false);
    }
  }, [
    payload,
    caseKind,
    whatIf?.candidates,
    queryState,
    diffData,
    windowDays,
    explainScore,
    refreshMasterySnapshot,
    registerAchievementEvent,
    showToast,
  ]);

  useEffect(() => {
    if (drawerOpen && canCompare && queryState.selectedActions.length >= 2 && !isWhatIfLoading) {
      void evaluate();
    }
  }, [drawerOpen, canCompare, queryState.selectedActions.length, evaluate, isWhatIfLoading]);

  useEffect(() => {
    if (!initialRunRef.current && canDiff) {
      initialRunRef.current = true;
      void loadExplain();
    }
  }, [canDiff, loadExplain]);

  const handleRun = useCallback(async () => {
    await loadExplain();
    if (queryState.mode === "diff") {
      await loadDiff();
    }
  }, [loadDiff, loadExplain, queryState.mode]);

  const handleReset = useCallback(() => {
    setQueryState({
      ...DEFAULT_EXPLAIN_QUERY_STATE,
      mode: "explain",
      leftSnapshot: "",
      rightSnapshot: "",
      actionId: "",
    });
    setDrawerOpen(false);
    setCaseModalOpen(false);
    setCreatedCaseId(null);
    setWhatIf(null);
    setDiffData(null);
    setDiffError(null);
  }, []);

  const shareUrl = useMemo(() => {
    const params = serializeExplainQueryState(queryState, new URLSearchParams(window.location.search));
    const url = new URL(window.location.href);
    url.search = params.toString();
    return url.toString();
  }, [queryState]);

  const copyLink = useCallback(() => {
    void navigator.clipboard.writeText(shareUrl);
    showToast("success", "Ссылка скопирована");
  }, [shareUrl, showToast]);

  const handleExport = useCallback(() => {
    const payloadData = {
      meta: {
        generated_at: new Date().toISOString(),
        mode: queryState.mode,
        params: queryState,
        duration_ms: lastRunDuration ?? null,
        score: payload
          ? {
              level: explainScore.level,
              confidence: explainScore.confidence,
              penalty: explainScore.penalty,
            }
          : null,
        streak: streak.count,
        achievements: unlockedAchievementKeys,
        mastery: {
          level: masterySnapshot.level,
          label: masterySnapshot.label,
          progress_to_next: Number(masterySnapshot.progressToNext.toFixed(2)),
          signals: {
            total_explains: masterySnapshot.counters.totalExplains,
            total_diffs: masterySnapshot.counters.totalDiffs,
            total_cases_created: masterySnapshot.counters.totalCasesCreated,
            improvements: masterySnapshot.signals.improvements,
            clean_after_action_rate: Number(masterySnapshot.signals.cleanAfterActionRate.toFixed(2)),
          },
        },
      },
      explain: payload ?? null,
      diff: diffData ?? null,
      actions: {
        include_actions: queryState.includeActions,
        selected: queryState.selectedActions,
      },
      case: {
        priority: queryState.casePriority,
        note: queryState.caseNote || null,
      },
    };
    const exportType: CaseExportType = queryState.mode === "diff" ? "diff" : "explain";
    if (createdCaseId) {
      recordCaseExport({ caseId: createdCaseId, type: exportType });
    }
    const blob = new Blob([JSON.stringify(payloadData, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `explain_${Date.now()}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }, [
    diffData,
    explainScore,
    lastRunDuration,
    masterySnapshot,
    payload,
    queryState,
    streak.count,
    unlockedAchievementKeys,
  ]);

  const toggleNode = useCallback((nodeId: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  }, []);

  const handleSelectNode = useCallback((node: ExplainReasonNode) => {
    setSelectedReasonId((prev) => {
      if (prev === node.id) {
        setSelectedEvidenceIds(new Set());
        return null;
      }
      setSelectedEvidenceIds(collectEvidenceRefs(node));
      return node.id;
    });
  }, []);

  const hasUnsavedChanges = useMemo(() => {
    if (!lastRunStateRef.current) return false;
    return JSON.stringify(lastRunStateRef.current) !== JSON.stringify(queryState);
  }, [queryState]);

  const canRunExplain = Boolean(kind && (kind === "kpi" ? kpiKey : entityId));
  const canRunDiff = queryState.mode !== "diff" || (queryState.leftSnapshot && queryState.rightSnapshot);
  const canRun = canRunExplain && canRunDiff;

  const panelUpdating = isLoading || (queryState.mode === "diff" && isDiffLoading);

  const sourceLabel = useMemo(() => {
    if (payload?.kind) {
      return `${payload.kind} · ${payload.id}`;
    }
    if (kind === "kpi" && kpiKey) return `kpi · ${kpiKey}`;
    if (kind && entityId) return `${kind} · ${entityId}`;
    return "—";
  }, [entityId, kpiKey, kind, payload?.id, payload?.kind]);

  const explainSummaryCards = useMemo(() => {
    if (!payload) return [];
    const cards: { label: string; value: ReactNode; hint?: string }[] = [
      {
        label: "Outcome",
        value: payload.decision,
      },
      {
        label: "Score",
        value: payload.score?.toFixed(2) ?? "—",
        hint: `Band: ${scoreBandLabel(payload.score_band)}`,
      },
      {
        label: "Status",
        value: <ScoreBadge score={explainScore} />,
        hint: `Confidence: ${percent(explainScore.confidence)} · Penalty: ${explainScore.penalty}`,
      },
      {
        label: "Confidence",
        value: <ConfidenceMeter confidence={explainScore.confidence} />,
      },
      {
        label: "Penalty",
        value: <PenaltyMarker penalty={explainScore.penalty} />,
      },
    ];
    if (topReasons.length) {
      cards.push({
        label: "Top reasons",
        value: topReasons.join(", "),
      });
    }
    if (payload.recommended_actions.length) {
      cards.push({
        label: "Recommended",
        value: String(payload.recommended_actions.length),
        hint: "actions",
      });
    }
    return cards;
  }, [explainScore, payload, topReasons]);

  const diffSummaryCards = useMemo(() => {
    if (!diffData) return [];
    return [
      {
        label: "Decision",
        value: `${diffData.decision_diff.before ?? "—"} → ${diffData.decision_diff.after ?? "—"}`,
      },
      {
        label: "Δ риска",
        value: formatDelta(diffData.score_diff.delta),
        hint: `${diffData.score_diff.risk_before?.toFixed(2) ?? "—"} → ${
          diffData.score_diff.risk_after?.toFixed(2) ?? "—"
        }`,
      },
    ];
  }, [diffData]);

  const caseValidation = useMemo(() => {
    const issues: string[] = [];
    if (queryState.includeExplain && !payload) {
      issues.push("Explain отсутствует — выполните Run.");
    }
    if (queryState.includeDiff && !diffData) {
      issues.push("Diff отсутствует — выполните сравнение.");
    }
    return issues;
  }, [diffData, payload, queryState.includeDiff, queryState.includeExplain]);

  const disableCreateCase = Boolean(caseValidation.length) || !caseKind || isCaseSubmitting;

  const canExport = Boolean(payload || diffData || queryState.selectedActions.length);
  const masteryTitle = masterySnapshot.missingRequirements.length
    ? `What counts:\n${masterySnapshot.missingRequirements.join("\n")}`
    : "All criteria met.";

  return (
    <div className="explain-v2">
      <Toast toast={toast} />
      <div className="page-header">
        <div>
          <h1>Explain v2</h1>
          <p className="muted">Решение, причины, статус, действия.</p>
        </div>
      </div>

      <div className="explain-control-bar">
        <div className="explain-control-bar__row">
          <div className="segmented-control" role="tablist" aria-label="Explain modes">
            {MODE_OPTIONS.map((mode) => (
              <button
                key={mode.id}
                type="button"
                className={queryState.mode === mode.id ? "is-active" : ""}
                onClick={() => setQueryState((prev) => ({ ...prev, mode: mode.id }))}
              >
                {mode.label}
              </button>
            ))}
          </div>

          <div className="explain-control-bar__actions">
            <button
              type="button"
              className="neft-btn-primary"
              onClick={() => void handleRun()}
              disabled={!canRun || isLoading}
            >
              {isLoading ? "Running..." : payload ? "Re-run" : "Run"}
            </button>
            <button type="button" className="ghost" onClick={handleReset}>
              Reset
            </button>
            <button type="button" className="ghost" onClick={copyLink}>
              Share
            </button>
            <button type="button" className="ghost" onClick={handleExport} disabled={!canExport}>
              Export
            </button>
          </div>

          <div className="explain-control-bar__status">
            <div className="explain-control-bar__status-row">
              <span>Last run: {formatTime(lastRunAt)}</span>
              {payload ? <ScoreBadge score={explainScore} compact /> : null}
            </div>
            <span>Duration: {lastRunDuration ? `${lastRunDuration}ms` : "—"}</span>
            <span>Source: {sourceLabel}</span>
            <div className="explain-control-bar__mastery" title={masteryTitle}>
              <div className="explain-control-bar__mastery-row">
                <span className="pill pill--outline">Mastery: {masterySnapshot.label}</span>
                {masterySnapshot.nextLabel ? <span>Next: {masterySnapshot.nextLabel}</span> : <span>Top level</span>}
              </div>
              <div className="explain-control-bar__mastery-progress">
                <div className="explain-control-bar__mastery-bar">
                  <span style={{ width: `${Math.round(masterySnapshot.progressToNext * 100)}%` }} />
                </div>
                <span>{Math.round(masterySnapshot.progressToNext * 100)}%</span>
                <details className="explain-control-bar__mastery-details">
                  <summary>What counts</summary>
                  <div className="explain-control-bar__mastery-body">
                    {masterySnapshot.requirements.length ? (
                      <ul>
                        {masterySnapshot.requirements.map((req) => (
                          <li key={req.id} className={req.met ? "is-met" : undefined}>
                            {req.label} · {req.current}/{req.target}
                            {req.soft ? " (future metric)" : ""}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <div>All criteria met.</div>
                    )}
                    {masterySnapshot.recommendations.length ? (
                      <div className="muted small">
                        Next steps: {masterySnapshot.recommendations.join(" · ")}
                      </div>
                    ) : null}
                  </div>
                </details>
              </div>
            </div>
            <div className="explain-control-bar__meta">
              {hasUnsavedChanges ? <span className="pill pill--accent">Unsaved changes</span> : null}
              <span className="pill pill--outline" title="Consecutive explain runs without interruption">
                🔥 Streak: {streak.count || "—"}
              </span>
              {unlockedAchievements.length ? (
                <div
                  className="explain-control-bar__achievements"
                  title={`Progress: ${achievementStats.explainRuns} explains · ${achievementStats.diffRuns} diffs · ${achievementStats.casesCreated} cases`}
                >
                  {unlockedAchievements.map((achievement) => (
                    <span
                      key={achievement.key}
                      className="explain-achievement"
                      title={`${achievement.label} · ${achievement.description}`}
                    >
                      {achievement.icon}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </div>

      <div className="explain-layout">
        <div className="explain-layout__left">
          <section className="card explain-card">
            <div className="card__header">
              <h3>Reason Tree</h3>
            </div>
            {isLoading && !payload ? <div className="muted">Загружаем explain...</div> : null}
            {payload?.reason_tree ? (
              <div className="explain-tree">
                <ReasonTreeNode
                  node={payload.reason_tree}
                  level={1}
                  expanded={expanded}
                  selectedId={selectedReasonId}
                  onToggle={toggleNode}
                  onSelect={handleSelectNode}
                />
              </div>
            ) : (
              <EmptyState title="Нажмите Run чтобы получить explain" subtitle="Дерево причин появится здесь." />
            )}
          </section>

          <section className="card explain-card">
            <div className="card__header">
              <h3>Evidence</h3>
              <div className="explain-filter">
                <label>
                  <input type="radio" checked={filter === "all"} onChange={() => setFilter("all")} />
                  Все
                </label>
                <label>
                  <input
                    type="radio"
                    checked={filter === "linked"}
                    onChange={() => setFilter("linked")}
                    disabled={linkedEvidenceIds.size === 0}
                  />
                  Связанные
                </label>
              </div>
            </div>
            <div className="explain-evidence">
              {filter === "linked" && selectedReasonId && evidence.length === 0 ? (
                <div className="muted">Нет доказательств для выбранной причины.</div>
              ) : evidence.length ? (
                evidence.map((item) => (
                  <EvidenceCard key={item.id} item={item} highlighted={linkedEvidenceIds.has(item.id)} />
                ))
              ) : (
                <div className="muted">Evidence отсутствуют.</div>
              )}
            </div>
          </section>

          <section className="card explain-card">
            <div className="card__header">
              <h3>Documents</h3>
            </div>
            {payload?.documents.length ? (
              <div className="explain-docs">
                {payload.documents.map((doc) => (
                  <a key={doc.id} href={doc.url} target="_blank" rel="noreferrer" className="ghost">
                    {doc.title}
                  </a>
                ))}
              </div>
            ) : (
              <div className="card card--empty">Документы отсутствуют.</div>
            )}
          </section>
        </div>

        <div className="explain-layout__right">
          <div className="explain-tabs">
            {MODE_OPTIONS.map((mode) => (
              <button
                key={`tab-${mode.id}`}
                type="button"
                className={`explain-tab${queryState.mode === mode.id ? " is-active" : ""}`}
                onClick={() => setQueryState((prev) => ({ ...prev, mode: mode.id }))}
              >
                {mode.label}
              </button>
            ))}
          </div>

          <div className="explain-panel">
            {panelUpdating ? <div className="explain-panel__overlay">Updating…</div> : null}

            {queryState.mode === "explain" ? (
              <>
                {explainSummaryCards.length ? (
                  <div className="explain-summary">
                    {explainSummaryCards.map((card) => (
                      <SummaryCard key={card.label} label={card.label} value={card.value} hint={card.hint} />
                    ))}
                  </div>
                ) : null}
                {error ? (
                  <ErrorNotice error={error} />
                ) : payload ? (
                  <JsonViewer value={payload} title="Explain JSON" enableSearch enableCollapse />
                ) : (
                  <EmptyState title="Нажмите Run чтобы получить explain" subtitle="Здесь появится JSON ответ." />
                )}
              </>
            ) : null}

            {queryState.mode === "diff" ? (
              <>
                <div className="card explain-card">
                  <div className="explain-diff__controls">
                    <label>
                      Снимок: До
                      <select
                        value={queryState.leftSnapshot}
                        onChange={(event) =>
                          setQueryState((prev) => ({ ...prev, leftSnapshot: event.target.value }))
                        }
                      >
                        <option value="">Выберите...</option>
                        {snapshotOptions.map((option) => (
                          <option key={`left-${option.value}`} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                      <input
                        type="text"
                        value={queryState.leftSnapshot}
                        onChange={(event) =>
                          setQueryState((prev) => ({ ...prev, leftSnapshot: event.target.value }))
                        }
                        placeholder="snapshot_id / policy_version"
                      />
                    </label>
                    <label>
                      Снимок: После
                      <select
                        value={queryState.rightSnapshot}
                        onChange={(event) =>
                          setQueryState((prev) => ({ ...prev, rightSnapshot: event.target.value }))
                        }
                      >
                        <option value="">Выберите...</option>
                        {snapshotOptions.map((option) => (
                          <option key={`right-${option.value}`} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                      <input
                        type="text"
                        value={queryState.rightSnapshot}
                        onChange={(event) =>
                          setQueryState((prev) => ({ ...prev, rightSnapshot: event.target.value }))
                        }
                        placeholder="snapshot_id / policy_version"
                      />
                    </label>
                    <label>
                      Action (optional)
                      <input
                        type="text"
                        value={queryState.actionId}
                        onChange={(event) => setQueryState((prev) => ({ ...prev, actionId: event.target.value }))}
                        placeholder="action_id"
                      />
                    </label>
                    <div className="explain-diff__controls-actions">
                      <button type="button" className="neft-btn-primary" onClick={() => void loadDiff()}>
                        Сравнить
                      </button>
                    </div>
                  </div>
                </div>

                {diffSummaryCards.length ? (
                  <div className="explain-summary">
                    {diffSummaryCards.map((card) => (
                      <SummaryCard key={card.label} label={card.label} value={card.value} hint={card.hint} />
                    ))}
                  </div>
                ) : null}

                {diffError ? (
                  <ErrorNotice error={diffError} />
                ) : diffData ? (
                  <>
                    <div className="card explain-card">
                      <div className="explain-diff__section-header">
                        <h3>Причины</h3>
                      </div>
                      <div className="explain-diff__tabs">
                        {(
                          [
                            { id: "strong", label: "Сильно изменилось" },
                            { id: "added", label: "Добавилось" },
                            { id: "removed", label: "Убрано" },
                            { id: "all", label: "Показать всё" },
                          ] as const
                        ).map((tab) => (
                          <button
                            key={tab.id}
                            type="button"
                            className={`explain-diff__tab${reasonTab === tab.id ? " is-active" : ""}`}
                            onClick={() => setReasonTab(tab.id)}
                          >
                            {tab.label}
                          </button>
                        ))}
                      </div>
                      <div className="explain-diff__table">
                        <div className="explain-diff__row explain-diff__row--head">
                          <span>Причина</span>
                          <span>Было</span>
                          <span>Стало</span>
                          <span>Δ</span>
                        </div>
                        {reasonSummary.visible.length ? (
                          reasonSummary.visible.map((reason) => (
                            <div key={reason.reason_code} className={`explain-diff__row is-${reason.status}`}>
                              <span className="explain-diff__reason">
                                {reason.reason_code}
                                <span className="pill pill--outline">{diffBadgeLabel[reason.status]}</span>
                              </span>
                              <span>{reason.weight_before ?? "—"}</span>
                              <span>{reason.weight_after ?? "—"}</span>
                              <span>{formatDelta(reason.delta)}</span>
                            </div>
                          ))
                        ) : (
                          <div className="muted small">Нет значимых изменений.</div>
                        )}
                      </div>
                    </div>
                    <JsonViewer value={diffData} title="Diff JSON" enableSearch enableCollapse />
                  </>
                ) : (
                  <EmptyState title="Diff требует два состояния" subtitle="Выберите snapshots и нажмите Сравнить." />
                )}
              </>
            ) : null}

            {queryState.mode === "actions" ? (
              <>
                <div className="explain-summary">
                  <SummaryCard label="Selected actions" value={String(selectedActionCodes.size)} hint="до 3" />
                  <SummaryCard
                    label="Recommended"
                    value={String(payload?.recommended_actions.length ?? 0)}
                    hint="доступно"
                  />
                </div>
                <ActionSelectionList
                  actions={actionOptions}
                  selectedCodes={selectedActionCodes}
                  onToggle={toggleAction}
                  limit={3}
                />
                <div className="explain-actions__footer">
                  <button
                    type="button"
                    className="primary"
                    onClick={() => setQueryState((prev) => ({ ...prev, mode: "diff" }))}
                    disabled={!canDiff}
                  >
                    Сравнить
                  </button>
                  {!canCompare ? (
                    <span className="muted small">What-if доступен только для операций/инвойсов/заказов.</span>
                  ) : null}
                  <button type="button" className="ghost" onClick={openWhatIf} disabled={!canCompare}>
                    Открыть What-if
                  </button>
                </div>
              </>
            ) : null}

            {queryState.mode === "case" ? (
              <>
                <div className="explain-summary">
                  <SummaryCard label="Priority" value={queryState.casePriority} hint={CASE_PRIORITY_HINTS[queryState.casePriority]} />
                  <SummaryCard
                    label="Include"
                    value={[
                      queryState.includeExplain ? "Explain" : null,
                      queryState.includeDiff ? "Diff" : null,
                      queryState.includeActions ? "Actions" : null,
                    ]
                      .filter(Boolean)
                      .join(", ") || "—"}
                  />
                  <SummaryCard label="Selected actions" value={String(selectedActionCodes.size)} />
                </div>
                <div className="explain-case__meta">
                  <div className="card explain-card">
                    <div className="stack">
                      <strong>Case note</strong>
                      <span className="muted small">
                        {queryState.caseNote ? "Готово к отправке" : "Add context for reviewers"}
                      </span>
                    </div>
                    {queryState.caseNote ? <div>{queryState.caseNote}</div> : null}
                  </div>
                  {createdCaseId ? (
                    <div className="card explain-card">
                      <strong>Кейс создан</strong>
                      <div className="muted">ID: {createdCaseId}</div>
                      <div className="stack-inline">
                        <CopyButton value={createdCaseId} label="Copy ID" />
                        <button
                          type="button"
                          className="neft-btn-secondary"
                          onClick={() => (window.location.href = `/support/cases/${createdCaseId}`)}
                        >
                          Открыть кейс
                        </button>
                      </div>
                    </div>
                  ) : null}
                  <button
                    type="button"
                    className="neft-btn-primary"
                    onClick={() => setCaseModalOpen(true)}
                    disabled={!payload || !caseKind}
                  >
                    Создать кейс
                  </button>
                  {caseValidation.length ? (
                    <div className="explain-empty">
                      {caseValidation.map((issue) => (
                        <div key={issue}>{issue}</div>
                      ))}
                    </div>
                  ) : null}
                </div>
              </>
            ) : null}
          </div>
        </div>
      </div>

      {caseModalOpen ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal">
            <div className="modal__header">
              <h3>Создать кейс</h3>
              <button type="button" className="ghost" onClick={() => setCaseModalOpen(false)}>
                ✕
              </button>
            </div>
            <div className="modal__body">
              <label className="filter">
                Priority
                <select
                  value={queryState.casePriority}
                  onChange={(event) =>
                    setQueryState((prev) => ({ ...prev, casePriority: event.target.value as CasePriority }))
                  }
                >
                  <option value="LOW">LOW</option>
                  <option value="MEDIUM">MEDIUM</option>
                  <option value="HIGH">HIGH</option>
                  <option value="CRITICAL">CRITICAL</option>
                </select>
                <span className="muted small">{CASE_PRIORITY_HINTS[queryState.casePriority]}</span>
              </label>
              <label className="filter">
                Note
                <textarea
                  rows={4}
                  value={queryState.caseNote}
                  maxLength={1000}
                  onChange={(event) => setQueryState((prev) => ({ ...prev, caseNote: event.target.value }))}
                  placeholder="Комментарий для кейса"
                />
                <span className="muted small">
                  {queryState.caseNote ? `${queryState.caseNote.length}/1000` : "Add context for reviewers"}
                </span>
              </label>
              <div className="checkbox">
                <input
                  id="include-explain"
                  type="checkbox"
                  checked={queryState.includeExplain}
                  onChange={(event) =>
                    setQueryState((prev) => ({ ...prev, includeExplain: event.target.checked }))
                  }
                />
                <label htmlFor="include-explain">Include explain snapshot</label>
              </div>
              <div className="checkbox">
                <input
                  id="include-diff"
                  type="checkbox"
                  checked={queryState.includeDiff}
                  onChange={(event) => setQueryState((prev) => ({ ...prev, includeDiff: event.target.checked }))}
                  disabled={!diffData}
                />
                <label htmlFor="include-diff">Include diff snapshot</label>
                {!diffData ? <span className="muted small">Diff недоступен — выполните сравнение.</span> : null}
              </div>
              <div className="checkbox">
                <input
                  id="include-actions"
                  type="checkbox"
                  checked={queryState.includeActions}
                  onChange={(event) =>
                    setQueryState((prev) => ({ ...prev, includeActions: event.target.checked }))
                  }
                />
                <label htmlFor="include-actions">Include selected actions</label>
              </div>
              {queryState.includeActions ? (
                <ActionSelectionList
                  actions={actionOptions}
                  selectedCodes={selectedActionCodes}
                  onToggle={toggleAction}
                  limit={3}
                />
              ) : null}
              {caseValidation.length ? (
                <div className="explain-empty">
                  {caseValidation.map((issue) => (
                    <div key={issue}>{issue}</div>
                  ))}
                </div>
              ) : null}
            </div>
            <div className="modal__footer">
              <button type="button" className="ghost" onClick={() => setCaseModalOpen(false)}>
                Отмена
              </button>
              <button
                type="button"
                className="neft-btn-primary"
                onClick={() => void handleCreateCase()}
                disabled={disableCreateCase}
              >
                {isCaseSubmitting ? "Создаём..." : "Создать"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {drawerOpen ? (
        <div className="explain-drawer">
          <div className="explain-drawer__content">
            <div className="explain-drawer__header">
              <h3>What-if сравнение</h3>
              <button type="button" className="ghost" onClick={() => setDrawerOpen(false)}>
                Закрыть
              </button>
            </div>
            <div className="explain-drawer__body">
              <div className="explain-drawer__actions">
                <h4>Выбранные действия</h4>
                <div className="explain-drawer__list">
                  {selectedActions.length ? (
                    selectedActions.map((item) => (
                      <div key={item.action_code} className="explain-drawer__selected">
                        <strong>{item.label}</strong>
                        {item.description ? <span className="muted small">{item.description}</span> : null}
                      </div>
                    ))
                  ) : (
                    <div className="muted small">Выберите 2–3 действия в списке выше.</div>
                  )}
                </div>
                <button
                  type="button"
                  className="primary"
                  onClick={() => void evaluate()}
                  disabled={!canCompare || queryState.selectedActions.length < 2 || isWhatIfLoading}
                >
                  Запустить симуляцию
                </button>
                <button
                  type="button"
                  className="ghost"
                  onClick={() => setQueryState((prev) => ({ ...prev, mode: "diff" }))}
                  disabled={!canDiff}
                >
                  Сравнить
                </button>
                <div className="muted small">Применение недоступно — только симуляция.</div>
              </div>

              <div className="explain-drawer__results">
                <div className="explain-whatif-banner">Симуляция (не исполняется)</div>
                {isWhatIfLoading ? <div className="muted">Рассчитываем...</div> : null}
                {whatIfError ? <div className="muted">Ошибка: {whatIfError}</div> : null}
                {filteredCandidates.map(({ action, candidate }) => (
                  <div key={action.action_code} className="explain-whatif-card">
                    <div className="explain-whatif-card__title">{action.label}</div>
                    {candidate ? (
                      <>
                        <div className="explain-whatif-card__meta">
                          <span>Эффект: {candidate.projection.expected_effect_label}</span>
                          <span>Вероятность: {candidate.projection.probability_improved_pct}%</span>
                        </div>
                        <div className="explain-whatif-card__meta">
                          <span>Risk: {candidate.risk.outlook}</span>
                          <span>Memory penalty: {candidate.memory.memory_penalty_pct}%</span>
                        </div>
                      </>
                    ) : (
                      <div className="muted">Нет данных симуляции.</div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};

export default ExplainPage;
