import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Toast } from "../components/common/Toast";
import { useToast } from "../components/Toast/useToast";
import { createCase, type CaseKind, type CasePriority } from "../api/cases";
import { fetchExplainActions, fetchExplainDiff, fetchExplainV2, evaluateWhatIf } from "../api/explainV2";
import { reduceExplainDiffReasons, type ExplainDiffTab } from "../features/explain/diffReducer";
import type {
  ExplainActionCatalogItem,
  ExplainDiffResponse,
  ExplainEvidence,
  ExplainReasonNode,
  ExplainV2Response,
  WhatIfResponse,
} from "../types/explainV2";

type EvidenceFilter = "all" | "linked";
type ExplainActionOption = ExplainActionCatalogItem & { recommended?: boolean };

const percent = (value?: number | null) => {
  if (value === null || value === undefined) return "—";
  return `${Math.round(value * 100)}%`;
};

const formatTimestamp = (value?: string | null) => {
  if (!value) return "—";
  const date = new Date(value);
  return date.toLocaleString("ru-RU");
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
    const threshold = (item.value as Record<string, unknown>).threshold ?? (item.value as Record<string, unknown>).limit;
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
        <button
          type="button"
          className="explain-tree__toggle"
          onClick={() => onToggle(node.id)}
          disabled={!hasChildren}
        >
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
                <select value={casePriority} onChange={(event) => setCasePriority(event.target.value as CasePriority)}>
                  <option value="LOW">LOW</option>
                  <option value="MEDIUM">MEDIUM</option>
                  <option value="HIGH">HIGH</option>
                  <option value="CRITICAL">CRITICAL</option>
                </select>
              </label>
              <label className="filter">
                Note
                <textarea
                  rows={3}
                  value={caseNote}
                  onChange={(event) => setCaseNote(event.target.value)}
                  placeholder="Комментарий для кейса"
                />
              </label>
              <div className="checkbox">
                <input
                  id="include-explain"
                  type="checkbox"
                  checked={includeExplain}
                  onChange={(event) => setIncludeExplain(event.target.checked)}
                />
                <label htmlFor="include-explain">Include explain snapshot</label>
              </div>
              <div className="checkbox">
                <input
                  id="include-diff"
                  type="checkbox"
                  checked={includeDiff}
                  onChange={(event) => setIncludeDiff(event.target.checked)}
                  disabled={!diffData}
                />
                <label htmlFor="include-diff">Include diff snapshot</label>
              </div>
              <div className="checkbox">
                <input
                  id="include-actions"
                  type="checkbox"
                  checked={includeActions}
                  onChange={(event) => setIncludeActions(event.target.checked)}
                  disabled={!selectedActions.length}
                />
                <label htmlFor="include-actions">Include selected actions</label>
              </div>
              {createdCaseId ? (
                <div className="card" style={{ marginTop: 12 }}>
                  <strong>Кейс создан</strong>
                  <div className="muted">ID: {createdCaseId}</div>
                  <button
                    type="button"
                    className="neft-btn-secondary"
                    style={{ marginTop: 8 }}
                    onClick={() => (window.location.href = `/support/cases/${createdCaseId}`)}
                  >
                    Открыть кейс
                  </button>
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
                disabled={isCaseSubmitting}
              >
                {isCaseSubmitting ? "Создаём..." : "Создать"}
              </button>
            </div>
          </div>
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

export const ExplainPage = () => {
  const [searchParams] = useSearchParams();
  const { toast, showToast } = useToast();
  const [payload, setPayload] = useState<ExplainV2Response | null>(null);
  const [actionsCatalog, setActionsCatalog] = useState<ExplainActionCatalogItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<EvidenceFilter>("all");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedActions, setSelectedActions] = useState<ExplainActionCatalogItem[]>([]);
  const [whatIf, setWhatIf] = useState<WhatIfResponse | null>(null);
  const [whatIfError, setWhatIfError] = useState<string | null>(null);
  const [isWhatIfLoading, setIsWhatIfLoading] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [selectedReasonId, setSelectedReasonId] = useState<string | null>(null);
  const [selectedEvidenceIds, setSelectedEvidenceIds] = useState<Set<string>>(new Set());
  const [diffData, setDiffData] = useState<ExplainDiffResponse | null>(null);
  const [diffError, setDiffError] = useState<string | null>(null);
  const [isDiffLoading, setIsDiffLoading] = useState(false);
  const [showDiff, setShowDiff] = useState(false);
  const [leftSnapshot, setLeftSnapshot] = useState("");
  const [rightSnapshot, setRightSnapshot] = useState("");
  const [actionId, setActionId] = useState("");
  const [reasonTab, setReasonTab] = useState<ExplainDiffTab>("strong");
  const [caseModalOpen, setCaseModalOpen] = useState(false);
  const [casePriority, setCasePriority] = useState<CasePriority>("MEDIUM");
  const [caseNote, setCaseNote] = useState("");
  const [includeExplain, setIncludeExplain] = useState(true);
  const [includeDiff, setIncludeDiff] = useState(true);
  const [includeActions, setIncludeActions] = useState(true);
  const [isCaseSubmitting, setIsCaseSubmitting] = useState(false);
  const [createdCaseId, setCreatedCaseId] = useState<string | null>(null);

  const kind = searchParams.get("kind") ?? (searchParams.get("kpi_key") ? "kpi" : null);
  const entityId = searchParams.get("id");
  const kpiKey = searchParams.get("kpi_key");
  const windowDays = searchParams.get("window_days") ?? "7";
  const diffRequested = searchParams.get("diff") === "1";

  useEffect(() => {
    if (payload?.reason_tree) {
      setExpanded(new Set([payload.reason_tree.id]));
      setSelectedReasonId(null);
      setSelectedEvidenceIds(new Set());
      setFilter("all");
    }
  }, [payload?.reason_tree]);

  useEffect(() => {
    setSelectedActions([]);
  }, [payload?.id]);

  useEffect(() => {
    setDiffData(null);
    setDiffError(null);
    setShowDiff(false);
  }, [payload?.id, kind]);

  useEffect(() => {
    setLeftSnapshot(searchParams.get("left_snapshot") ?? "");
    setRightSnapshot(searchParams.get("right_snapshot") ?? "");
    setActionId(searchParams.get("action_id") ?? "");
    if (diffRequested) {
      setShowDiff(true);
    }
  }, [diffRequested, searchParams]);

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

  const linkedEvidenceIds = useMemo(() => selectedEvidenceIds, [selectedEvidenceIds]);

  const evidence = useMemo(() => {
    const items = payload?.evidence ?? [];
    if (filter === "linked" && linkedEvidenceIds.size > 0) {
      return items.filter((item) => linkedEvidenceIds.has(item.id));
    }
    return items;
  }, [filter, linkedEvidenceIds, payload?.evidence]);

  const loadExplain = useCallback(async () => {
    if (!kind) {
      setError("Не указан тип explain.");
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = {};
      if (kind === "kpi") {
        if (!kpiKey) {
          setError("Не указан KPI.");
          setIsLoading(false);
          return;
        }
        params.kpi_key = kpiKey;
        params.window_days = windowDays;
      } else if (entityId) {
        params.kind = kind;
        params.id = entityId;
      } else {
        setError("Не указан идентификатор.");
        setIsLoading(false);
        return;
      }
      const data = await fetchExplainV2(params);
      setPayload(data);
    } catch (err) {
      setError((err as Error).message);
      setPayload(null);
    } finally {
      setIsLoading(false);
    }
  }, [entityId, kind, kpiKey, windowDays]);

  const loadActions = useCallback(async () => {
    if (!kind) return;
    try {
      const params: Record<string, string> = {};
      if (kind === "kpi") {
        if (!kpiKey) return;
        params.kpi_key = kpiKey;
      } else if (entityId) {
        params.kind = kind;
        params.id = entityId;
      } else {
        return;
      }
      const data = await fetchExplainActions(params);
      setActionsCatalog(data);
    } catch {
      setActionsCatalog([]);
    }
  }, [entityId, kind, kpiKey]);

  useEffect(() => {
    void loadExplain();
    void loadActions();
  }, [loadExplain, loadActions]);

  const copyLink = useCallback(() => {
    const url = window.location.href;
    void navigator.clipboard.writeText(url);
    showToast("success", "Ссылка скопирована");
  }, [showToast]);

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

  const loadDiff = useCallback(async () => {
    if (!kind) return;
    if (!leftSnapshot || !rightSnapshot) {
      setDiffError("Укажите snapshot для сравнения.");
      setShowDiff(true);
      return;
    }
    setIsDiffLoading(true);
    setDiffError(null);
    try {
      const diffKind = (kind === "marketplace_order" ? "order" : kind) as "operation" | "invoice" | "order" | "kpi";
      const response = await fetchExplainDiff({
        kind: diffKind,
        id: diffKind === "kpi" ? undefined : entityId ?? undefined,
        left_snapshot: leftSnapshot,
        right_snapshot: rightSnapshot,
        action_id: actionId || undefined,
      });
      setDiffData(response);
      setShowDiff(true);
    } catch (err) {
      setDiffError((err as Error).message);
      setDiffData(null);
      setShowDiff(true);
    } finally {
      setIsDiffLoading(false);
    }
  }, [actionId, entityId, kind, leftSnapshot, rightSnapshot]);

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
    ensureOption(leftSnapshot);
    ensureOption(rightSnapshot);
    return options;
  }, [leftSnapshot, payload?.generated_at, payload?.policy_snapshot, rightSnapshot]);

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

  const selectedActionCodes = useMemo(() => new Set(selectedActions.map((item) => item.action_code)), [selectedActions]);

  const toggleAction = useCallback(
    (item: ExplainActionCatalogItem) => {
      setSelectedActions((prev) => {
        const exists = prev.find((action) => action.action_code === item.action_code);
        if (exists) {
          return prev.filter((action) => action.action_code !== item.action_code);
        }
        if (prev.length >= 3) return prev;
        return [...prev, item];
      });
    },
    [],
  );

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
        max_candidates: Math.min(3, Math.max(1, selectedActions.length)),
      });
      setWhatIf(response);
    } catch (err) {
      setWhatIfError((err as Error).message);
      setWhatIf(null);
    } finally {
      setIsWhatIfLoading(false);
    }
  }, [entityId, kind, selectedActions.length]);

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
    if (kind === "marketplace_order") return "order";
    return kind;
  }, [kind]);

  const handleCreateCase = useCallback(async () => {
    if (!payload || !caseKind) return;
    setIsCaseSubmitting(true);
    try {
      const candidatesByCode = new Map(
        (whatIf?.candidates ?? []).map((candidate) => [candidate.action.code, candidate]),
      );
      const selected = includeActions
        ? selectedActions.map((item) => ({
            code: item.action_code,
            what_if: candidatesByCode.get(item.action_code) ?? null,
          }))
        : null;
      const response = await createCase({
        kind: caseKind,
        entity_id: caseKind === "kpi" ? undefined : payload.id,
        kpi_key: caseKind === "kpi" ? payload.id : undefined,
        window_days: caseKind === "kpi" ? Number(windowDays) : undefined,
        priority: casePriority,
        note: caseNote || null,
        explain: includeExplain ? payload : null,
        diff: includeDiff ? diffData ?? null : null,
        selected_actions: selected,
      });
      setCreatedCaseId(response.id);
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
    includeActions,
    selectedActions,
    includeExplain,
    includeDiff,
    diffData,
    windowDays,
    casePriority,
    caseNote,
    showToast,
  ]);

  useEffect(() => {
    if (drawerOpen && canCompare && selectedActions.length >= 2 && !isWhatIfLoading) {
      void evaluate();
    }
  }, [drawerOpen, canCompare, selectedActions.length, evaluate, isWhatIfLoading]);

  if (showDiff) {
    return (
      <div className="card">
        <div className="card__header">
          <Toast toast={toast} />
          <div>
            <h2>Explain Diff</h2>
            <p className="muted">До → После · режим сравнения</p>
          </div>
          <button type="button" className="ghost" onClick={() => setShowDiff(false)}>
            Назад к explain
          </button>
        </div>

        <div className="explain-diff__controls">
          <label>
            Снимок: До
            <select value={leftSnapshot} onChange={(event) => setLeftSnapshot(event.target.value)}>
              <option value="">Выберите...</option>
              {snapshotOptions.map((option) => (
                <option key={`left-${option.value}`} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <input
              type="text"
              value={leftSnapshot}
              onChange={(event) => setLeftSnapshot(event.target.value)}
              placeholder="snapshot_id / policy_version"
            />
          </label>
          <label>
            Снимок: После
            <select value={rightSnapshot} onChange={(event) => setRightSnapshot(event.target.value)}>
              <option value="">Выберите...</option>
              {snapshotOptions.map((option) => (
                <option key={`right-${option.value}`} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <input
              type="text"
              value={rightSnapshot}
              onChange={(event) => setRightSnapshot(event.target.value)}
              placeholder="snapshot_id / policy_version"
            />
          </label>
          <label>
            Action (optional)
            <input
              type="text"
              value={actionId}
              onChange={(event) => setActionId(event.target.value)}
              placeholder="action_id"
            />
          </label>
          <div className="explain-diff__controls-actions">
            <button type="button" className="neft-btn-primary" onClick={() => void loadDiff()}>
              Сравнить
            </button>
            <button type="button" className="ghost" disabled title="Экспорт скоро">
              Экспорт
            </button>
          </div>
        </div>

        {isDiffLoading ? <div className="card">Готовим diff...</div> : null}
        {diffError ? <div className="card card--error">Ошибка: {diffError}</div> : null}

        {diffData ? (
          <div className="explain-diff__panel">
            <div className="explain-diff__meta">
              <div className="explain-diff__meta-item">
                <span className="muted small">{diffData.meta.left.label}</span>
                <strong>{diffData.decision_diff.before ?? "—"}</strong>
              </div>
              <div className="explain-diff__meta-item">
                <span className="muted small">→</span>
              </div>
              <div className="explain-diff__meta-item">
                <span className="muted small">{diffData.meta.right.label}</span>
                <strong>{diffData.decision_diff.after ?? "—"}</strong>
              </div>
              <div className="explain-diff__meta-item">
                <span className="muted small">Δ риска</span>
                <strong
                  className={`explain-diff__delta ${diffData.score_diff.delta && diffData.score_diff.delta < 0 ? "is-improved" : diffData.score_diff.delta && diffData.score_diff.delta > 0 ? "is-worsened" : ""}`}
                >
                  {diffData.score_diff.delta === null || diffData.score_diff.delta === undefined
                    ? "—"
                    : `${diffData.score_diff.delta < 0 ? "↓" : diffData.score_diff.delta > 0 ? "↑" : "→"} ${formatDelta(
                        diffData.score_diff.delta,
                      )}`}
                </strong>
              </div>
            </div>

            <div className="card explain-card explain-diff__summary">
              <div>
                <div className="muted small">Risk</div>
                <div className="explain-diff__risk">
                  <strong>{diffData.score_diff.risk_before?.toFixed(2) ?? "—"}</strong>
                  <span>→</span>
                  <strong>{diffData.score_diff.risk_after?.toFixed(2) ?? "—"}</strong>
                </div>
              </div>
              <div
                className={`explain-diff__delta ${diffData.score_diff.delta && diffData.score_diff.delta < 0 ? "is-improved" : diffData.score_diff.delta && diffData.score_diff.delta > 0 ? "is-worsened" : ""}`}
              >
                {formatDelta(diffData.score_diff.delta)}
              </div>
            </div>

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

            <div className="card explain-card">
              <h3>Evidence</h3>
              {diffData.evidence_diff.length ? (
                <div className="explain-diff__evidence-columns">
                  {(["removed", "added"] as const).map((status) => (
                    <div key={status} className="explain-diff__evidence-column">
                      <div className="muted small">{status === "removed" ? "Removed" : "Added"}</div>
                      <div className="explain-diff__list">
                        {diffData.evidence_diff
                          .filter((item) => item.status === status)
                          .map((item) => (
                            <button
                              key={item.evidence_id}
                              type="button"
                              className={`explain-diff__item is-${item.status}`}
                              onClick={() => {
                                const anchor = document.querySelector(`[data-evidence-id="${item.evidence_id}"]`);
                                if (anchor) {
                                  anchor.scrollIntoView({ behavior: "smooth", block: "center" });
                                }
                              }}
                            >
                              <span>{item.evidence_id}</span>
                              <span className="pill pill--outline">{item.status}</span>
                            </button>
                          ))}
                        {!diffData.evidence_diff.some((item) => item.status === status) ? (
                          <div className="muted small">Нет изменений.</div>
                        ) : null}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="muted small">Изменений нет.</div>
              )}
            </div>

            {diffData.action_impact ? (
              <div className="card explain-card">
                <h3>Action impact</h3>
                <div className="explain-diff__action">
                  <div>
                    <div className="muted small">Action</div>
                    <strong>{diffData.action_impact.action_id}</strong>
                  </div>
                  <div>
                    <div className="muted small">Ожидаемый эффект</div>
                    <strong>{formatDelta(diffData.action_impact.expected_delta)}</strong>
                  </div>
                  <div>
                    <div className="muted small">Confidence</div>
                    <strong>{diffData.action_impact.confidence.toFixed(2)}</strong>
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div className="explain-v2">
      <Toast toast={toast} />
      <div className="page-header">
        <div>
          <h1>Explain v2</h1>
          <p className="muted">Решение, причины, статус, действия.</p>
        </div>
        <div className="stack-inline">
          <button
            type="button"
            className="neft-btn-secondary"
            onClick={() => setShowDiff(true)}
          >
            Сравнить
          </button>
          <button
            type="button"
            className="neft-btn-primary"
            onClick={() => setCaseModalOpen(true)}
            disabled={!payload || !caseKind}
          >
            Создать кейс
          </button>
          <button type="button" className="neft-btn-secondary" onClick={copyLink}>
            Скопировать ссылку
          </button>
          <button type="button" className="neft-btn-secondary" title="В разработке" disabled>
            Экспорт
          </button>
        </div>
      </div>

      {isLoading ? <div className="card">Загружаем explain...</div> : null}
      {error ? (
        <div className="card card--error">
          <div className="stack">
            <div>
              <strong>Проблема:</strong> Данные Explain временно недоступны.
            </div>
            <div>
              <strong>Причина:</strong> {error}
            </div>
            <div>
              <strong>Статус:</strong> ожидание повторной попытки.
            </div>
            <div>
              <strong>Система:</strong> повторит запрос через 60 секунд.
            </div>
            <div>
              <strong>Действие:</strong> можно запустить запрос вручную.
            </div>
          </div>
          <button type="button" className="ghost" onClick={() => void loadExplain()}>
            Повторить
          </button>
        </div>
      ) : null}

      {!isLoading && !error && !payload?.reason_tree ? (
        <div className="card card--empty">
          <div className="stack">
            <div>
              <strong>Проблема:</strong> Нет данных Explain.
            </div>
            <div>
              <strong>Причина:</strong> Explain не сформирован по выбранным параметрам.
            </div>
            <div>
              <strong>Статус:</strong> данных нет.
            </div>
            <div>
              <strong>Система:</strong> работает штатно.
            </div>
            <div>
              <strong>Действие:</strong> уточните параметры или выберите другой период.
            </div>
          </div>
        </div>
      ) : null}

      {payload ? (
        <div className="explain-grid">
          <section className="card explain-card">
            <div className="explain-header">
              <div>
                <div className={`pill pill--${payload.decision === "DECLINE" ? "danger" : payload.decision === "APPROVE" ? "success" : "neutral"}`}>
                  {payload.decision}
                </div>
                <div className="explain-header__meta">
                  <span>Score: {payload.score ?? "—"}</span>
                  <span>Band: {scoreBandLabel(payload.score_band)}</span>
                </div>
              </div>
              <div className="explain-header__meta">
                <span>Policy: {payload.policy_snapshot ?? "—"}</span>
                <span>{formatTimestamp(payload.generated_at)}</span>
              </div>
            </div>
          </section>

          <section className="card explain-card">
            <div className="card__header">
              <h3>Reason Tree</h3>
            </div>
            {payload.reason_tree ? (
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
              <div className="muted">Дерево причин недоступно.</div>
            )}
          </section>

          <section className="card explain-card">
            <div className="card__header">
              <h3>Evidence</h3>
              <div className="explain-filter">
                <label>
                  <input
                    type="radio"
                    checked={filter === "all"}
                    onChange={() => setFilter("all")}
                  />
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
            {payload.documents.length ? (
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

          <section className="card explain-card">
            <div className="card__header">
              <h3>Recommended actions</h3>
            </div>
            <div className="explain-actions">
              {actionOptions.length ? (
                actionOptions.map((action) => {
                  const disabled = !selectedActionCodes.has(action.action_code) && selectedActions.length >= 3;
                  return (
                    <label
                      key={action.action_code}
                      className={`explain-action${disabled ? " is-disabled" : ""}`}
                      title={disabled ? "Максимум 3" : undefined}
                    >
                      <input
                        type="checkbox"
                        checked={selectedActionCodes.has(action.action_code)}
                        onChange={() => toggleAction(action)}
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
            <div className="explain-actions__footer">
              <button
                type="button"
                className="primary"
                onClick={() => setShowDiff(true)}
                disabled={!canDiff}
              >
                Сравнить
              </button>
              {!canCompare ? <span className="muted small">What-if доступен только для операций/инвойсов/заказов.</span> : null}
              <button type="button" className="ghost" onClick={openWhatIf} disabled={!canCompare}>
                Открыть What-if
              </button>
            </div>
          </section>
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
                  disabled={!canCompare || selectedActions.length < 2 || isWhatIfLoading}
                >
                  Запустить симуляцию
                </button>
                <button type="button" className="ghost" onClick={() => setShowDiff(true)} disabled={!canDiff}>
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
